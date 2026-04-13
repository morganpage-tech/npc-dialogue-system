"""
NPC State Manager for Multiplayer Synchronization
Server-side state management with player-isolated and shared state.
"""

import os
import json
import time
import asyncio
import threading
from pathlib import Path
from typing import Optional, Dict, List, Set, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from collections import defaultdict


class StateScope(Enum):
    """Scope of state data."""
    PLAYER = "player"      # Isolated per player
    SHARED = "shared"      # Shared across all players
    NPC = "npc"           # Per-NPC world state


class EventType(Enum):
    """Types of state change events."""
    # Dialogue events
    DIALOGUE_START = "dialogue_start"
    DIALOGUE_END = "dialogue_end"
    DIALOGUE_MESSAGE = "dialogue_message"
    
    # Relationship events
    RELATIONSHIP_CHANGE = "relationship_change"
    FACTION_CHANGE = "faction_change"
    
    # Quest events
    QUEST_ACCEPTED = "quest_accepted"
    QUEST_PROGRESS = "quest_progress"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"
    
    # World events
    WORLD_EVENT = "world_event"
    NPC_STATE_CHANGE = "npc_state_change"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    
    # Zone events
    PLAYER_ENTER_ZONE = "player_enter_zone"
    PLAYER_EXIT_ZONE = "player_exit_zone"


@dataclass
class StateEvent:
    """Represents a state change event."""
    event_type: EventType
    timestamp: float
    data: Dict[str, Any]
    player_id: Optional[str] = None
    npc_id: Optional[str] = None
    zone_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "data": self.data,
            "player_id": self.player_id,
            "npc_id": self.npc_id,
            "zone_id": self.zone_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StateEvent':
        return cls(
            event_type=EventType(data["event_type"]),
            timestamp=data["timestamp"],
            data=data["data"],
            player_id=data.get("player_id"),
            npc_id=data.get("npc_id"),
            zone_id=data.get("zone_id"),
        )


@dataclass
class PlayerState:
    """State isolated to a single player."""
    player_id: str
    connected: bool = True
    connected_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    current_zone: Optional[str] = None
    current_npc: Optional[str] = None
    
    # Dialogue history per NPC
    dialogue_history: Dict[str, List[Dict]] = field(default_factory=dict)
    
    # Relationships per NPC
    relationships: Dict[str, int] = field(default_factory=dict)
    
    # Active quests
    active_quests: Set[str] = field(default_factory=set)
    
    # Completed quests (player's record)
    completed_quests: Set[str] = field(default_factory=set)
    
    # Session metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "connected": self.connected,
            "connected_at": self.connected_at,
            "last_active": self.last_active,
            "current_zone": self.current_zone,
            "current_npc": self.current_npc,
            "dialogue_history": self.dialogue_history,
            "relationships": self.relationships,
            "active_quests": list(self.active_quests),
            "completed_quests": list(self.completed_quests),
            "metadata": self.metadata,
        }


@dataclass
class NPCWorldState:
    """World-visible state for an NPC."""
    npc_id: str
    name: str
    
    # Current activity (visible to all)
    current_activity: str = "idle"
    current_zone: str = "default"
    
    # Is NPC in conversation?
    in_conversation: bool = False
    conversing_with: Optional[str] = None
    
    # Dynamic state (shared)
    mood: str = "neutral"
    available_quests: List[str] = field(default_factory=list)
    
    # Custom state
    custom_state: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "current_activity": self.current_activity,
            "current_zone": self.current_zone,
            "in_conversation": self.in_conversation,
            "conversing_with": self.conversing_with,
            "mood": self.mood,
            "available_quests": self.available_quests,
            "custom_state": self.custom_state,
        }


@dataclass
class WorldState:
    """Shared world state across all players."""
    # Globally completed quests
    completed_quests: Set[str] = field(default_factory=set)
    
    # World events log
    world_events: List[Dict] = field(default_factory=list)
    
    # Faction reputation (shared)
    faction_reputation: Dict[str, int] = field(default_factory=dict)
    
    # Global flags
    global_flags: Dict[str, Any] = field(default_factory=dict)
    
    # Active world conditions
    active_conditions: Set[str] = field(default_factory=set)
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "completed_quests": list(self.completed_quests),
            "world_events": self.world_events[-100:],  # Last 100 events
            "faction_reputation": self.faction_reputation,
            "global_flags": self.global_flags,
            "active_conditions": list(self.active_conditions),
            "created_at": self.created_at,
            "last_modified": self.last_modified,
        }


class EventCallback:
    """Callback registration for events."""
    
    def __init__(self):
        self.callbacks: Dict[EventType, List[Callable]] = defaultdict(list)
        self.all_callbacks: List[Callable] = []
    
    def on(self, event_type: EventType, callback: Callable):
        """Register callback for specific event type."""
        self.callbacks[event_type].append(callback)
    
    def on_any(self, callback: Callable):
        """Register callback for all events."""
        self.all_callbacks.append(callback)
    
    async def emit(self, event: StateEvent):
        """Emit event to all relevant callbacks."""
        # Type-specific callbacks
        for callback in self.callbacks[event.event_type]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"Callback error: {e}")
        
        # All-event callbacks
        for callback in self.all_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"Callback error: {e}")


class NPCStateManager:
    """
    Central state manager for multiplayer NPC synchronization.
    
    Manages:
    - Per-player isolated state (dialogue, relationships, active quests)
    - Shared world state (completed quests, world events)
    - NPC world state (visibility, activity)
    - Event broadcasting for real-time sync
    """
    
    def __init__(
        self,
        persist_dir: str = "state_persistence",
        auto_save: bool = True,
        save_interval: int = 60,
    ):
        """
        Initialize the state manager.
        
        Args:
            persist_dir: Directory for state persistence
            auto_save: Enable automatic periodic saves
            save_interval: Seconds between auto-saves
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # State containers
        self.players: Dict[str, PlayerState] = {}
        self.npcs: Dict[str, NPCWorldState] = {}
        self.world = WorldState()
        
        # Event system
        self.event_callback = EventCallback()
        
        # Thread safety
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        
        # Auto-save
        self.auto_save = auto_save
        self.save_interval = save_interval
        self._save_task: Optional[asyncio.Task] = None
        
        # Event queue for batching
        self._event_queue: List[StateEvent] = []
        self._max_queue_size = 1000
    
    # ============================================
    # PLAYER STATE MANAGEMENT
    # ============================================
    
    def player_connect(self, player_id: str, metadata: Dict = None) -> PlayerState:
        """
        Register a player connection.
        
        Args:
            player_id: Unique player identifier
            metadata: Optional player metadata
            
        Returns:
            PlayerState for the connected player
        """
        with self._lock:
            if player_id in self.players:
                player = self.players[player_id]
                player.connected = True
                player.connected_at = time.time()
                player.last_active = time.time()
            else:
                player = PlayerState(
                    player_id=player_id,
                    metadata=metadata or {},
                )
                self.players[player_id] = player
            
            return player
    
    def player_disconnect(self, player_id: str):
        """Mark player as disconnected."""
        with self._lock:
            if player_id in self.players:
                self.players[player_id].connected = False
                self.players[player_id].current_zone = None
                self.players[player_id].current_npc = None
    
    def get_player(self, player_id: str) -> Optional[PlayerState]:
        """Get player state."""
        return self.players.get(player_id)
    
    def get_connected_players(self) -> List[PlayerState]:
        """Get all connected players."""
        return [p for p in self.players.values() if p.connected]
    
    def get_players_in_zone(self, zone_id: str) -> List[PlayerState]:
        """Get all players in a specific zone."""
        return [
            p for p in self.players.values()
            if p.connected and p.current_zone == zone_id
        ]
    
    def get_players_near_npc(self, npc_id: str) -> List[PlayerState]:
        """Get players currently interacting with or near an NPC."""
        return [
            p for p in self.players.values()
            if p.connected and p.current_npc == npc_id
        ]
    
    # ============================================
    # DIALOGUE STATE
    # ============================================
    
    def add_dialogue(
        self,
        player_id: str,
        npc_id: str,
        role: str,
        content: str,
        metadata: Dict = None,
    ) -> StateEvent:
        """
        Add a dialogue message to player's history.
        
        Args:
            player_id: Player ID
            npc_id: NPC ID
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata
            
        Returns:
            StateEvent for the dialogue
        """
        with self._lock:
            player = self.get_player(player_id)
            if not player:
                raise ValueError(f"Player {player_id} not found")
            
            if npc_id not in player.dialogue_history:
                player.dialogue_history[npc_id] = []
            
            message = {
                "role": role,
                "content": content,
                "timestamp": time.time(),
                "metadata": metadata or {},
            }
            
            player.dialogue_history[npc_id].append(message)
            player.last_active = time.time()
            
            # Update NPC state
            if npc_id in self.npcs:
                self.npcs[npc_id].in_conversation = True
                self.npcs[npc_id].conversing_with = player_id
        
        return StateEvent(
            event_type=EventType.DIALOGUE_MESSAGE,
            timestamp=time.time(),
            data={"message": message},
            player_id=player_id,
            npc_id=npc_id,
        )
    
    def get_dialogue_history(
        self,
        player_id: str,
        npc_id: str,
        limit: int = 50,
    ) -> List[Dict]:
        """Get dialogue history for player-NPC pair."""
        player = self.get_player(player_id)
        if not player or npc_id not in player.dialogue_history:
            return []
        
        history = player.dialogue_history[npc_id]
        return history[-limit:]
    
    def clear_dialogue_history(self, player_id: str, npc_id: str = None):
        """Clear dialogue history for a player."""
        with self._lock:
            player = self.get_player(player_id)
            if not player:
                return
            
            if npc_id:
                player.dialogue_history.pop(npc_id, None)
            else:
                player.dialogue_history.clear()
    
    def end_dialogue(self, player_id: str, npc_id: str) -> StateEvent:
        """End a dialogue session."""
        with self._lock:
            player = self.get_player(player_id)
            if player:
                player.current_npc = None
            
            if npc_id in self.npcs:
                self.npcs[npc_id].in_conversation = False
                self.npcs[npc_id].conversing_with = None
        
        return StateEvent(
            event_type=EventType.DIALOGUE_END,
            timestamp=time.time(),
            data={},
            player_id=player_id,
            npc_id=npc_id,
        )
    
    # ============================================
    # RELATIONSHIP STATE
    # ============================================
    
    def update_relationship(
        self,
        player_id: str,
        npc_id: str,
        change: int,
        reason: str = "",
    ) -> StateEvent:
        """
        Update player-NPC relationship.
        
        Args:
            player_id: Player ID
            npc_id: NPC ID
            change: Relationship change (+/-)
            reason: Reason for change
            
        Returns:
            StateEvent for the change
        """
        with self._lock:
            player = self.get_player(player_id)
            if not player:
                raise ValueError(f"Player {player_id} not found")
            
            if npc_id not in player.relationships:
                player.relationships[npc_id] = 0
            
            old_value = player.relationships[npc_id]
            player.relationships[npc_id] = max(-100, min(100, old_value + change))
            player.last_active = time.time()
        
        return StateEvent(
            event_type=EventType.RELATIONSHIP_CHANGE,
            timestamp=time.time(),
            data={
                "old_value": old_value,
                "new_value": player.relationships[npc_id],
                "change": change,
                "reason": reason,
            },
            player_id=player_id,
            npc_id=npc_id,
        )
    
    def get_relationship(self, player_id: str, npc_id: str) -> int:
        """Get player-NPC relationship value."""
        player = self.get_player(player_id)
        if not player:
            return 0
        return player.relationships.get(npc_id, 0)
    
    def update_faction_reputation(
        self,
        faction: str,
        change: int,
        reason: str = "",
    ) -> StateEvent:
        """
        Update shared faction reputation.
        
        Args:
            faction: Faction name
            change: Reputation change (+/-)
            reason: Reason for change
            
        Returns:
            StateEvent for the change
        """
        with self._lock:
            if faction not in self.world.faction_reputation:
                self.world.faction_reputation[faction] = 0
            
            old_value = self.world.faction_reputation[faction]
            self.world.faction_reputation[faction] = max(-100, min(100, old_value + change))
            self.world.last_modified = time.time()
        
        return StateEvent(
            event_type=EventType.FACTION_CHANGE,
            timestamp=time.time(),
            data={
                "faction": faction,
                "old_value": old_value,
                "new_value": self.world.faction_reputation[faction],
                "change": change,
                "reason": reason,
            },
        )
    
    def get_faction_reputation(self, faction: str) -> int:
        """Get faction reputation."""
        return self.world.faction_reputation.get(faction, 0)
    
    # ============================================
    # QUEST STATE
    # ============================================
    
    def accept_quest(
        self,
        player_id: str,
        quest_id: str,
    ) -> StateEvent:
        """Player accepts a quest."""
        with self._lock:
            player = self.get_player(player_id)
            if not player:
                raise ValueError(f"Player {player_id} not found")
            
            player.active_quests.add(quest_id)
            player.last_active = time.time()
        
        return StateEvent(
            event_type=EventType.QUEST_ACCEPTED,
            timestamp=time.time(),
            data={"quest_id": quest_id},
            player_id=player_id,
        )
    
    def complete_quest(
        self,
        player_id: str,
        quest_id: str,
        shared: bool = True,
    ) -> StateEvent:
        """
        Complete a quest.
        
        Args:
            player_id: Player completing the quest
            quest_id: Quest ID
            shared: If True, marks quest as completed for all players
            
        Returns:
            StateEvent for the completion
        """
        with self._lock:
            player = self.get_player(player_id)
            if player:
                player.active_quests.discard(quest_id)
                player.completed_quests.add(quest_id)
            
            if shared:
                self.world.completed_quests.add(quest_id)
                self.world.last_modified = time.time()
        
        return StateEvent(
            event_type=EventType.QUEST_COMPLETED,
            timestamp=time.time(),
            data={
                "quest_id": quest_id,
                "shared": shared,
            },
            player_id=player_id,
        )
    
    def is_quest_completed(self, quest_id: str, player_id: str = None) -> bool:
        """Check if quest is completed (globally or for player)."""
        if quest_id in self.world.completed_quests:
            return True
        
        if player_id:
            player = self.get_player(player_id)
            if player and quest_id in player.completed_quests:
                return True
        
        return False
    
    def get_active_quests(self, player_id: str) -> Set[str]:
        """Get player's active quests."""
        player = self.get_player(player_id)
        if not player:
            return set()
        return player.active_quests.copy()
    
    # ============================================
    # NPC WORLD STATE
    # ============================================
    
    def register_npc(
        self,
        npc_id: str,
        name: str,
        zone: str = "default",
        **kwargs,
    ) -> NPCWorldState:
        """Register an NPC in the world."""
        with self._lock:
            npc = NPCWorldState(
                npc_id=npc_id,
                name=name,
                current_zone=zone,
                **kwargs,
            )
            self.npcs[npc_id] = npc
            return npc
    
    def get_npc(self, npc_id: str) -> Optional[NPCWorldState]:
        """Get NPC world state."""
        return self.npcs.get(npc_id)
    
    def update_npc_state(
        self,
        npc_id: str,
        **updates,
    ) -> StateEvent:
        """Update NPC world state."""
        with self._lock:
            npc = self.get_npc(npc_id)
            if not npc:
                raise ValueError(f"NPC {npc_id} not found")
            
            for key, value in updates.items():
                if hasattr(npc, key):
                    setattr(npc, key, value)
                else:
                    npc.custom_state[key] = value
        
        return StateEvent(
            event_type=EventType.NPC_STATE_CHANGE,
            timestamp=time.time(),
            data={"updates": updates},
            npc_id=npc_id,
        )
    
    def get_npcs_in_zone(self, zone_id: str) -> List[NPCWorldState]:
        """Get all NPCs in a zone."""
        return [n for n in self.npcs.values() if n.current_zone == zone_id]
    
    # ============================================
    # WORLD STATE
    # ============================================
    
    def add_world_event(
        self,
        event_type: str,
        description: str,
        data: Dict = None,
    ) -> StateEvent:
        """Add a world event to the log."""
        with self._lock:
            event = {
                "event_type": event_type,
                "description": description,
                "data": data or {},
                "timestamp": time.time(),
            }
            self.world.world_events.append(event)
            self.world.last_modified = time.time()
        
        return StateEvent(
            event_type=EventType.WORLD_EVENT,
            timestamp=time.time(),
            data=event,
        )
    
    def set_global_flag(self, key: str, value: Any):
        """Set a global world flag."""
        with self._lock:
            self.world.global_flags[key] = value
            self.world.last_modified = time.time()
    
    def get_global_flag(self, key: str, default: Any = None) -> Any:
        """Get a global world flag."""
        return self.world.global_flags.get(key, default)
    
    def add_active_condition(self, condition: str):
        """Add an active world condition."""
        with self._lock:
            self.world.active_conditions.add(condition)
            self.world.last_modified = time.time()
    
    def remove_active_condition(self, condition: str):
        """Remove an active world condition."""
        with self._lock:
            self.world.active_conditions.discard(condition)
            self.world.last_modified = time.time()
    
    def has_active_condition(self, condition: str) -> bool:
        """Check if a world condition is active."""
        return condition in self.world.active_conditions
    
    # ============================================
    # ZONE MANAGEMENT
    # ============================================
    
    def player_enter_zone(
        self,
        player_id: str,
        zone_id: str,
    ) -> StateEvent:
        """Player enters a zone."""
        with self._lock:
            player = self.get_player(player_id)
            if player:
                player.current_zone = zone_id
                player.last_active = time.time()
        
        return StateEvent(
            event_type=EventType.PLAYER_ENTER_ZONE,
            timestamp=time.time(),
            data={"zone_id": zone_id},
            player_id=player_id,
            zone_id=zone_id,
        )
    
    def player_exit_zone(
        self,
        player_id: str,
        zone_id: str,
    ) -> StateEvent:
        """Player exits a zone."""
        with self._lock:
            player = self.get_player(player_id)
            if player and player.current_zone == zone_id:
                player.current_zone = None
                player.last_active = time.time()
        
        return StateEvent(
            event_type=EventType.PLAYER_EXIT_ZONE,
            timestamp=time.time(),
            data={"zone_id": zone_id},
            player_id=player_id,
            zone_id=zone_id,
        )
    
    # ============================================
    # EVENT EMITTING
    # ============================================
    
    async def emit_event(self, event: StateEvent):
        """Emit an event to all registered callbacks."""
        await self.event_callback.emit(event)
    
    def on_event(self, event_type: EventType, callback: Callable):
        """Register callback for events."""
        self.event_callback.on(event_type, callback)
    
    def on_any_event(self, callback: Callable):
        """Register callback for all events."""
        self.event_callback.on_any(callback)
    
    # ============================================
    # PERSISTENCE
    # ============================================
    
    def save_state(self, filepath: str = None):
        """Save current state to file."""
        filepath = filepath or self.persist_dir / "state.json"
        
        with self._lock:
            data = {
                "players": {
                    pid: p.to_dict() for pid, p in self.players.items()
                },
                "npcs": {
                    nid: n.to_dict() for nid, n in self.npcs.items()
                },
                "world": self.world.to_dict(),
                "saved_at": time.time(),
            }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_state(self, filepath: str = None):
        """Load state from file."""
        filepath = filepath or self.persist_dir / "state.json"
        
        if not os.path.exists(filepath):
            return False
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        with self._lock:
            # Load players
            self.players = {}
            for pid, pdata in data.get("players", {}).items():
                player = PlayerState(player_id=pid)
                player.connected = pdata.get("connected", False)
                player.connected_at = pdata.get("connected_at", time.time())
                player.last_active = pdata.get("last_active", time.time())
                player.current_zone = pdata.get("current_zone")
                player.current_npc = pdata.get("current_npc")
                player.dialogue_history = pdata.get("dialogue_history", {})
                player.relationships = pdata.get("relationships", {})
                player.active_quests = set(pdata.get("active_quests", []))
                player.completed_quests = set(pdata.get("completed_quests", []))
                player.metadata = pdata.get("metadata", {})
                self.players[pid] = player
            
            # Load NPCs
            self.npcs = {}
            for nid, ndata in data.get("npcs", {}).items():
                npc = NPCWorldState(
                    npc_id=nid,
                    name=ndata.get("name", nid),
                    current_activity=ndata.get("current_activity", "idle"),
                    current_zone=ndata.get("current_zone", "default"),
                    in_conversation=ndata.get("in_conversation", False),
                    conversing_with=ndata.get("conversing_with"),
                    mood=ndata.get("mood", "neutral"),
                    available_quests=ndata.get("available_quests", []),
                    custom_state=ndata.get("custom_state", {}),
                )
                self.npcs[nid] = npc
            
            # Load world
            wdata = data.get("world", {})
            self.world = WorldState()
            self.world.completed_quests = set(wdata.get("completed_quests", []))
            self.world.world_events = wdata.get("world_events", [])
            self.world.faction_reputation = wdata.get("faction_reputation", {})
            self.world.global_flags = wdata.get("global_flags", {})
            self.world.active_conditions = set(wdata.get("active_conditions", []))
        
        return True
    
    # ============================================
    # UTILITY
    # ============================================
    
    def get_summary(self) -> Dict:
        """Get summary of current state."""
        return {
            "connected_players": len(self.get_connected_players()),
            "total_players": len(self.players),
            "registered_npcs": len(self.npcs),
            "completed_quests": len(self.world.completed_quests),
            "active_conditions": len(self.world.active_conditions),
            "world_events": len(self.world.world_events),
        }
    
    def export_player_data(self, player_id: str) -> Optional[Dict]:
        """Export all data for a specific player."""
        player = self.get_player(player_id)
        if not player:
            return None
        
        return {
            "player_id": player_id,
            "player_state": player.to_dict(),
            "world_state": {
                "completed_quests": list(self.world.completed_quests),
                "faction_reputation": self.world.faction_reputation,
            },
        }
