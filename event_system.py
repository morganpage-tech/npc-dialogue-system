"""
Event System for Multiplayer NPC Synchronization
Real-time event broadcasting with WebSocket support.
"""

import asyncio
import json
import time
from typing import Optional, Dict, List, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import weakref

from npc_state_manager import StateEvent, EventType


class SubscriptionType(Enum):
    """Types of event subscriptions."""
    ALL = "all"                    # All events
    PLAYER = "player"              # Events for specific player
    NPC = "npc"                    # Events for specific NPC
    ZONE = "zone"                  # Events in specific zone
    EVENT_TYPE = "event_type"      # Specific event types


@dataclass
class Subscriber:
    """Represents a connected subscriber."""
    subscriber_id: str
    websocket: Any  # WebSocket connection
    subscriptions: Set[str] = field(default_factory=set)
    player_id: Optional[str] = None
    current_zone: Optional[str] = None
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    
    async def send(self, data: Dict):
        """Send data to this subscriber."""
        try:
            if hasattr(self.websocket, 'send_json'):
                await self.websocket.send_json(data)
            elif hasattr(self.websocket, 'send'):
                await self.websocket.send(json.dumps(data))
        except Exception as e:
            print(f"Send error to {self.subscriber_id}: {e}")
            raise


class EventBroadcaster:
    """
    Manages real-time event broadcasting to connected clients.
    
    Features:
    - Topic-based subscriptions (player, npc, zone, event_type)
    - Automatic cleanup of disconnected clients
    - Event filtering and routing
    - Broadcast history for reconnection
    """
    
    def __init__(
        self,
        history_size: int = 100,
        ping_interval: int = 30,
        ping_timeout: int = 60,
    ):
        """
        Initialize the event broadcaster.
        
        Args:
            history_size: Number of events to keep for reconnection
            ping_interval: Seconds between ping checks
            ping_timeout: Seconds before considering client dead
        """
        self.history_size = history_size
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        
        # Subscribers
        self.subscribers: Dict[str, Subscriber] = {}
        
        # Subscription indexes for fast lookup
        self._player_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._npc_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._zone_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._type_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._all_subscribers: Set[str] = set()
        
        # Event history
        self._event_history: List[StateEvent] = []
        
        # Background tasks
        self._running = False
        self._ping_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the broadcaster background tasks."""
        self._running = True
        self._ping_task = asyncio.create_task(self._ping_loop())
    
    async def stop(self):
        """Stop the broadcaster."""
        self._running = False
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
    
    # ============================================
    # SUBSCRIBER MANAGEMENT
    # ============================================
    
    async def connect(
        self,
        subscriber_id: str,
        websocket: Any,
        player_id: str = None,
        initial_zone: str = None,
    ) -> Subscriber:
        """
        Register a new subscriber connection.
        
        Args:
            subscriber_id: Unique identifier for this connection
            websocket: WebSocket connection object
            player_id: Optional player ID
            initial_zone: Optional starting zone
            
        Returns:
            Subscriber object
        """
        subscriber = Subscriber(
            subscriber_id=subscriber_id,
            websocket=websocket,
            player_id=player_id,
            current_zone=initial_zone,
        )
        
        self.subscribers[subscriber_id] = subscriber
        
        # Auto-subscribe to player events
        if player_id:
            await self.subscribe(subscriber_id, f"player:{player_id}")
        
        # Auto-subscribe to zone events
        if initial_zone:
            await self.subscribe(subscriber_id, f"zone:{initial_zone}")
        
        # Send connection acknowledgment
        await subscriber.send({
            "type": "connected",
            "subscriber_id": subscriber_id,
            "timestamp": time.time(),
        })
        
        # Send recent event history
        await self._send_history(subscriber)
        
        return subscriber
    
    async def disconnect(self, subscriber_id: str):
        """Handle subscriber disconnection."""
        if subscriber_id not in self.subscribers:
            return
        
        subscriber = self.subscribers[subscriber_id]
        
        # Clean up all subscriptions
        for sub in list(subscriber.subscriptions):
            await self.unsubscribe(subscriber_id, sub)
        
        # Remove from all subscribers
        self._all_subscribers.discard(subscriber_id)
        
        # Remove subscriber
        del self.subscribers[subscriber_id]
    
    async def subscribe(self, subscriber_id: str, topic: str):
        """
        Subscribe a client to a topic.
        
        Topics:
        - "all" - All events
        - "player:{player_id}" - Events for specific player
        - "npc:{npc_id}" - Events for specific NPC
        - "zone:{zone_id}" - Events in specific zone
        - "type:{event_type}" - Specific event types
        """
        if subscriber_id not in self.subscribers:
            return
        
        subscriber = self.subscribers[subscriber_id]
        subscriber.subscriptions.add(topic)
        
        # Index subscription
        if topic == "all":
            self._all_subscribers.add(subscriber_id)
        elif topic.startswith("player:"):
            player_id = topic.split(":", 1)[1]
            self._player_subscriptions[player_id].add(subscriber_id)
        elif topic.startswith("npc:"):
            npc_id = topic.split(":", 1)[1]
            self._npc_subscriptions[npc_id].add(subscriber_id)
        elif topic.startswith("zone:"):
            zone_id = topic.split(":", 1)[1]
            self._zone_subscriptions[zone_id].add(subscriber_id)
        elif topic.startswith("type:"):
            event_type = topic.split(":", 1)[1]
            self._type_subscriptions[event_type].add(subscriber_id)
        
        # Confirm subscription
        await subscriber.send({
            "type": "subscribed",
            "topic": topic,
            "timestamp": time.time(),
        })
    
    async def unsubscribe(self, subscriber_id: str, topic: str):
        """Unsubscribe from a topic."""
        if subscriber_id not in self.subscribers:
            return
        
        subscriber = self.subscribers[subscriber_id]
        subscriber.subscriptions.discard(topic)
        
        # Remove from index
        if topic == "all":
            self._all_subscribers.discard(subscriber_id)
        elif topic.startswith("player:"):
            player_id = topic.split(":", 1)[1]
            self._player_subscriptions[player_id].discard(subscriber_id)
        elif topic.startswith("npc:"):
            npc_id = topic.split(":", 1)[1]
            self._npc_subscriptions[npc_id].discard(subscriber_id)
        elif topic.startswith("zone:"):
            zone_id = topic.split(":", 1)[1]
            self._zone_subscriptions[zone_id].discard(subscriber_id)
        elif topic.startswith("type:"):
            event_type = topic.split(":", 1)[1]
            self._type_subscriptions[event_type].discard(subscriber_id)
    
    async def update_player_zone(self, subscriber_id: str, new_zone: str):
        """Update subscriber's current zone."""
        if subscriber_id not in self.subscribers:
            return
        
        subscriber = self.subscribers[subscriber_id]
        old_zone = subscriber.current_zone
        
        if old_zone:
            await self.unsubscribe(subscriber_id, f"zone:{old_zone}")
        
        subscriber.current_zone = new_zone
        await self.subscribe(subscriber_id, f"zone:{new_zone}")
    
    # ============================================
    # EVENT BROADCASTING
    # ============================================
    
    async def broadcast(self, event: StateEvent):
        """
        Broadcast an event to all relevant subscribers.
        
        Args:
            event: StateEvent to broadcast
        """
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self.history_size:
            self._event_history = self._event_history[-self.history_size:]
        
        # Build message
        message = {
            "type": "event",
            "event": event.to_dict(),
        }
        
        # Get target subscribers
        target_ids = await self._get_target_subscribers(event)
        
        # Send to all targets
        send_tasks = []
        for sid in target_ids:
            if sid in self.subscribers:
                send_tasks.append(self._safe_send(sid, message))
        
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
    
    async def _get_target_subscribers(self, event: StateEvent) -> Set[str]:
        """Determine which subscribers should receive an event."""
        targets: Set[str] = set()
        
        # All subscribers
        targets.update(self._all_subscribers)
        
        # Event type subscribers
        targets.update(self._type_subscriptions.get(event.event_type.value, set()))
        
        # Player-specific
        if event.player_id:
            targets.update(self._player_subscriptions.get(event.player_id, set()))
        
        # NPC-specific
        if event.npc_id:
            targets.update(self._npc_subscriptions.get(event.npc_id, set()))
        
        # Zone-specific
        if event.zone_id:
            targets.update(self._zone_subscriptions.get(event.zone_id, set()))
        
        return targets
    
    async def _safe_send(self, subscriber_id: str, message: Dict):
        """Safely send message, removing subscriber on failure."""
        try:
            subscriber = self.subscribers.get(subscriber_id)
            if subscriber:
                await subscriber.send(message)
        except Exception:
            # Connection failed, clean up
            await self.disconnect(subscriber_id)
    
    async def _send_history(self, subscriber: Subscriber, limit: int = 20):
        """Send recent event history to a subscriber."""
        if not self._event_history:
            return
        
        recent = self._event_history[-limit:]
        
        for event in recent:
            # Check if subscriber should receive this event
            targets = await self._get_target_subscribers(event)
            if subscriber.subscriber_id in targets:
                await subscriber.send({
                    "type": "event_history",
                    "event": event.to_dict(),
                })
    
    # ============================================
    # PING/PONG
    # ============================================
    
    async def _ping_loop(self):
        """Background task to check connection health."""
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)
                
                now = time.time()
                dead_subscribers = []
                
                for sid, subscriber in list(self.subscribers.items()):
                    # Check for timeout
                    if now - subscriber.last_ping > self.ping_timeout:
                        dead_subscribers.append(sid)
                    else:
                        # Send ping
                        try:
                            await subscriber.send({"type": "ping"})
                        except Exception:
                            dead_subscribers.append(sid)
                
                # Clean up dead connections
                for sid in dead_subscribers:
                    await self.disconnect(sid)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ping loop error: {e}")
    
    async def pong(self, subscriber_id: str):
        """Handle pong response from subscriber."""
        if subscriber_id in self.subscribers:
            self.subscribers[subscriber_id].last_ping = time.time()
    
    # ============================================
    # UTILITY
    # ============================================
    
    def get_stats(self) -> Dict:
        """Get broadcaster statistics."""
        return {
            "connected_subscribers": len(self.subscribers),
            "total_subscriptions": sum(
                len(s.subscriptions) for s in self.subscribers.values()
            ),
            "history_size": len(self._event_history),
            "player_subscriptions": {
                k: len(v) for k, v in self._player_subscriptions.items()
            },
            "npc_subscriptions": {
                k: len(v) for k, v in self._npc_subscriptions.items()
            },
            "zone_subscriptions": {
                k: len(v) for k, v in self._zone_subscriptions.items()
            },
        }


class EventSystem:
    """
    Complete event system combining state manager and broadcaster.
    
    Provides:
    - State management (NPCStateManager)
    - Real-time broadcasting (EventBroadcaster)
    - Integration with dialogue/quest systems
    """
    
    def __init__(
        self,
        state_manager: Any = None,
        broadcaster: EventBroadcaster = None,
    ):
        """
        Initialize the event system.
        
        Args:
            state_manager: NPCStateManager instance (optional)
            broadcaster: EventBroadcaster instance (optional)
        """
        from npc_state_manager import NPCStateManager
        
        self.state_manager = state_manager or NPCStateManager()
        self.broadcaster = broadcaster or EventBroadcaster()
        
        # Wire up state manager events to broadcaster
        self.state_manager.on_any_event(self._on_state_event)
    
    async def start(self):
        """Start the event system."""
        await self.broadcaster.start()
    
    async def stop(self):
        """Stop the event system."""
        await self.broadcaster.stop()
    
    async def _on_state_event(self, event: StateEvent):
        """Handle state manager events and broadcast them."""
        await self.broadcaster.broadcast(event)
    
    # Delegate common operations
    
    async def connect_player(
        self,
        subscriber_id: str,
        websocket: Any,
        player_id: str,
        zone: str = None,
    ) -> Subscriber:
        """Connect a player and initialize their state."""
        # Register in state manager
        self.state_manager.player_connect(player_id)
        
        # Connect to broadcaster
        subscriber = await self.broadcaster.connect(
            subscriber_id=subscriber_id,
            websocket=websocket,
            player_id=player_id,
            initial_zone=zone,
        )
        
        # Broadcast join event
        event = StateEvent(
            event_type=EventType.PLAYER_JOINED,
            timestamp=time.time(),
            data={"player_id": player_id, "zone": zone},
            player_id=player_id,
            zone_id=zone,
        )
        await self.broadcaster.broadcast(event)
        
        return subscriber
    
    async def disconnect_player(self, subscriber_id: str, player_id: str):
        """Disconnect a player."""
        # Broadcast leave event
        event = StateEvent(
            event_type=EventType.PLAYER_LEFT,
            timestamp=time.time(),
            data={"player_id": player_id},
            player_id=player_id,
        )
        await self.broadcaster.broadcast(event)
        
        # Update state manager
        self.state_manager.player_disconnect(player_id)
        
        # Disconnect from broadcaster
        await self.broadcaster.disconnect(subscriber_id)
    
    async def dialogue(
        self,
        player_id: str,
        npc_id: str,
        role: str,
        content: str,
        broadcast: bool = True,
    ) -> StateEvent:
        """
        Add dialogue and optionally broadcast.
        
        Args:
            player_id: Player ID
            npc_id: NPC ID
            role: "user" or "assistant"
            content: Message content
            broadcast: Whether to broadcast the event
            
        Returns:
            StateEvent for the dialogue
        """
        event = self.state_manager.add_dialogue(
            player_id=player_id,
            npc_id=npc_id,
            role=role,
            content=content,
        )
        
        if broadcast:
            await self.broadcaster.broadcast(event)
        
        return event
    
    async def zone_change(
        self,
        player_id: str,
        subscriber_id: str,
        new_zone: str,
    ) -> StateEvent:
        """Handle player zone change."""
        # Get old zone
        player = self.state_manager.get_player(player_id)
        old_zone = player.current_zone if player else None
        
        # Update state
        event = self.state_manager.player_enter_zone(player_id, new_zone)
        
        # Update broadcaster subscriptions
        await self.broadcaster.update_player_zone(subscriber_id, new_zone)
        
        # Broadcast
        await self.broadcaster.broadcast(event)
        
        return event
    
    def get_summary(self) -> Dict:
        """Get system summary."""
        return {
            "state": self.state_manager.get_summary(),
            "broadcaster": self.broadcaster.get_stats(),
        }
