#!/usr/bin/env python3
"""
Multiplayer NPC System Demo

Demonstrates:
- Multiple simulated players connecting
- Player-isolated dialogue history
- Shared world state (quests, faction reputation)
- Real-time event broadcasting
- Zone-based subscriptions
"""

import asyncio
import json
import random
import time
from typing import Dict, List
from dataclasses import dataclass

# For demo without actual WebSocket server
from npc_state_manager import NPCStateManager, StateEvent, EventType
from event_system import EventSystem, EventBroadcaster


@dataclass
class SimulatedPlayer:
    """Simulated multiplayer client."""
    player_id: str
    current_zone: str
    active: bool = True
    messages_received: List[Dict] = None
    
    def __post_init__(self):
        if self.messages_received is None:
            self.messages_received = []


class MultiplayerDemo:
    """
    Demonstrates the multiplayer NPC system.
    
    Scenarios:
    1. Multiple players connect and interact with NPCs
    2. Each player has isolated dialogue history
    3. Quest completion is shared across all players
    4. Faction reputation changes affect everyone
    5. Zone changes trigger appropriate subscriptions
    """
    
    def __init__(self):
        self.event_system = EventSystem()
        self.simulated_players: Dict[str, SimulatedPlayer] = {}
        
        # Track events for demo output
        self.events_log: List[StateEvent] = []
        
        # Register event listener
        self.event_system.state_manager.on_any_event(self._on_event)
    
    async def _on_event(self, event: StateEvent):
        """Log all events."""
        self.events_log.append(event)
    
    async def setup(self):
        """Initialize the demo."""
        await self.event_system.start()
        
        # Register NPCs
        print("\n" + "="*60)
        print("REGISTERING NPCs")
        print("="*60)
        
        npcs = [
            ("blacksmith", "Gareth the Blacksmith", "village"),
            ("merchant", "Elena the Merchant", "village"),
            ("elder", "Wise Elder Theron", "temple"),
            ("guard", "Captain Marcus", "castle"),
            ("herbalist", "Mira the Herbalist", "forest"),
        ]
        
        for npc_id, name, zone in npcs:
            self.event_system.state_manager.register_npc(npc_id, name, zone)
            print(f"  Registered: {name} (Zone: {zone})")
    
    async def simulate_player_connect(self, player_id: str, zone: str = "village"):
        """Simulate a player connecting."""
        player = SimulatedPlayer(player_id=player_id, current_zone=zone)
        self.simulated_players[player_id] = player
        
        # Register in state manager
        self.event_system.state_manager.player_connect(player_id)
        self.event_system.state_manager.player_enter_zone(player_id, zone)
        
        print(f"\n[CONNECT] Player '{player_id}' joined in zone '{zone}'")
        
        return player
    
    async def simulate_dialogue(
        self,
        player_id: str,
        npc_id: str,
        message: str,
    ):
        """Simulate a dialogue interaction."""
        event = await self.event_system.dialogue(
            player_id=player_id,
            npc_id=npc_id,
            role="user",
            content=message,
        )
        
        print(f"\n[DIALOGUE] {player_id} -> {npc_id}: \"{message}\"")
        
        # Simulate NPC response
        npc_responses = {
            "blacksmith": [
                "Aye, what can I forge for ye today?",
                "The finest blades in all the land, I craft!",
                "Need your armor repaired? I'm your man.",
            ],
            "merchant": [
                "Welcome, traveler! See anything you fancy?",
                "I've got wares from distant lands!",
                "Everything's for sale, at the right price.",
            ],
            "elder": [
                "Ah, young one. Seek wisdom, do you?",
                "The ancient texts speak of great trials ahead...",
                "Patience is the key to all doors.",
            ],
            "guard": [
                "State your business, citizen!",
                "The castle is well protected, fear not.",
                "I've served the king for thirty years.",
            ],
            "herbalist": [
                "The forest provides all we need for healing.",
                "This herb cures many ailments...",
                "Nature's bounty is endless, if you know where to look.",
            ],
        }
        
        response = random.choice(npc_responses.get(npc_id, ["..."]))
        
        await self.event_system.dialogue(
            player_id=player_id,
            npc_id=npc_id,
            role="assistant",
            content=response,
        )
        
        print(f"[DIALOGUE] {npc_id} -> {player_id}: \"{response}\"")
    
    async def simulate_zone_change(self, player_id: str, new_zone: str):
        """Simulate a player changing zones."""
        player = self.simulated_players.get(player_id)
        if not player:
            return
        
        old_zone = player.current_zone
        player.current_zone = new_zone
        
        event = self.event_system.state_manager.player_enter_zone(player_id, new_zone)
        
        print(f"\n[ZONE] {player_id} moved from '{old_zone}' to '{new_zone}'")
    
    async def simulate_relationship_change(
        self,
        player_id: str,
        npc_id: str,
        change: int,
        reason: str,
    ):
        """Simulate a relationship change."""
        event = self.event_system.state_manager.update_relationship(
            player_id=player_id,
            npc_id=npc_id,
            change=change,
            reason=reason,
        )
        
        new_value = self.event_system.state_manager.get_relationship(player_id, npc_id)
        
        print(f"\n[RELATIONSHIP] {player_id} <-> {npc_id}: {change:+d} ({reason})")
        print(f"  New relationship: {new_value}")
    
    async def simulate_quest_accept(self, player_id: str, quest_id: str):
        """Simulate a player accepting a quest."""
        event = self.event_system.state_manager.accept_quest(player_id, quest_id)
        
        print(f"\n[QUEST] {player_id} accepted quest: {quest_id}")
    
    async def simulate_quest_complete(
        self,
        player_id: str,
        quest_id: str,
        shared: bool = True,
    ):
        """Simulate quest completion."""
        event = self.event_system.state_manager.complete_quest(
            player_id=player_id,
            quest_id=quest_id,
            shared=shared,
        )
        
        scope = "shared (all players)" if shared else "personal"
        print(f"\n[QUEST] {player_id} completed quest: {quest_id} ({scope})")
    
    async def simulate_faction_change(self, faction: str, change: int, reason: str):
        """Simulate faction reputation change."""
        event = self.event_system.state_manager.update_faction_reputation(
            faction=faction,
            change=change,
            reason=reason,
        )
        
        new_value = self.event_system.state_manager.get_faction_reputation(faction)
        
        print(f"\n[FACTION] {faction}: {change:+d} ({reason})")
        print(f"  New reputation: {new_value}")
    
    def show_player_dialogue_history(self, player_id: str, npc_id: str):
        """Show dialogue history for a player-NPC pair."""
        history = self.event_system.state_manager.get_dialogue_history(player_id, npc_id)
        
        print(f"\n[PLAYER HISTORY] {player_id} <-> {npc_id}:")
        for msg in history:
            role = msg["role"].upper()
            content = msg["content"]
            print(f"  [{role}] {content}")
    
    def show_player_state(self, player_id: str):
        """Show complete state for a player."""
        player = self.event_system.state_manager.get_player(player_id)
        if not player:
            print(f"Player {player_id} not found")
            return
        
        print(f"\n[PLAYER STATE] {player_id}:")
        print(f"  Zone: {player.current_zone}")
        print(f"  Active Quests: {list(player.active_quests)}")
        print(f"  Completed Quests: {list(player.completed_quests)}")
        print(f"  Relationships: {player.relationships}")
    
    def show_world_state(self):
        """Show shared world state."""
        world = self.event_system.state_manager.world
        
        print(f"\n[WORLD STATE]:")
        print(f"  Completed Quests (shared): {list(world.completed_quests)}")
        print(f"  Faction Reputation: {world.faction_reputation}")
        print(f"  Active Conditions: {list(world.active_conditions)}")
        print(f"  World Events: {len(world.world_events)} logged")
    
    def show_npc_states(self):
        """Show all NPC states."""
        print(f"\n[NPC STATES]:")
        for npc_id, npc in self.event_system.state_manager.npcs.items():
            status = "in conversation" if npc.in_conversation else "available"
            print(f"  {npc.name} ({npc_id}):")
            print(f"    Zone: {npc.current_zone}")
            print(f"    Status: {status}")
            if npc.in_conversation:
                print(f"    Talking to: {npc.conversing_with}")


async def run_demo():
    """Run the multiplayer demonstration."""
    demo = MultiplayerDemo()
    await demo.setup()
    
    print("\n" + "="*60)
    print("MULTIPLAYER SIMULATION")
    print("="*60)
    
    # Scenario 1: Multiple players connect
    print("\n--- SCENARIO 1: Players Connect ---")
    
    await demo.simulate_player_connect("alice", "village")
    await demo.simulate_player_connect("bob", "village")
    await demo.simulate_player_connect("charlie", "castle")
    
    # Scenario 2: Players interact with NPCs
    print("\n--- SCENARIO 2: Dialogue Interactions ---")
    
    await demo.simulate_dialogue("alice", "blacksmith", "Hello! Can you repair my sword?")
    await demo.simulate_dialogue("bob", "merchant", "What do you have for sale?")
    await demo.simulate_dialogue("charlie", "guard", "I need to speak with the king.")
    
    # Each player has isolated history
    print("\n--- Isolated Dialogue History ---")
    demo.show_player_dialogue_history("alice", "blacksmith")
    demo.show_player_dialogue_history("bob", "merchant")
    
    # Scenario 3: Relationship changes
    print("\n--- SCENARIO 3: Relationship Changes ---")
    
    await demo.simulate_relationship_change("alice", "blacksmith", 10, "paid for repairs")
    await demo.simulate_relationship_change("bob", "merchant", -5, "haggled too much")
    await demo.simulate_relationship_change("alice", "blacksmith", 15, "generous tip")
    
    # Alice's relationship is different from Bob's
    demo.show_player_state("alice")
    demo.show_player_state("bob")
    
    # Scenario 4: Quests
    print("\n--- SCENARIO 4: Quest System ---")
    
    # Alice accepts a personal quest
    await demo.simulate_quest_accept("alice", "gather_herbs")
    
    # Bob accepts a different quest
    await demo.simulate_quest_accept("bob", "deliver_package")
    
    # Alice completes a SHARED quest - affects everyone
    await demo.simulate_quest_complete("alice", "defeat_goblin_boss", shared=True)
    
    # Bob completes a personal quest
    await demo.simulate_quest_complete("bob", "deliver_package", shared=False)
    
    demo.show_player_state("alice")
    demo.show_player_state("bob")
    demo.show_world_state()
    
    # Scenario 5: Faction reputation (shared)
    print("\n--- SCENARIO 5: Faction Reputation (Shared) ---")
    
    await demo.simulate_faction_change("village_guild", 10, "Alice helped villagers")
    await demo.simulate_faction_change("village_guild", 5, "Bob donated gold")
    
    # Charlie has access to the same faction rep
    demo.show_player_state("charlie")
    demo.show_world_state()
    
    # Scenario 6: Zone changes
    print("\n--- SCENARIO 6: Zone Changes ---")
    
    await demo.simulate_zone_change("alice", "forest")
    await demo.simulate_dialogue("alice", "herbalist", "Can you teach me about herbs?")
    
    demo.show_npc_states()
    
    # Scenario 7: World events
    print("\n--- SCENARIO 7: World Events ---")
    
    event = demo.event_system.state_manager.add_world_event(
        event_type="dragon_sighting",
        description="A dragon was spotted near the mountains!",
        data={"location": "mountain_pass", "danger_level": "high"},
    )
    
    demo.show_world_state()
    
    # Final state summary
    print("\n" + "="*60)
    print("FINAL STATE SUMMARY")
    print("="*60)
    
    print(f"\nTotal events logged: {len(demo.events_log)}")
    print("\nEvent breakdown:")
    event_counts = {}
    for event in demo.events_log:
        event_type = event.event_type.value
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    
    for event_type, count in sorted(event_counts.items()):
        print(f"  {event_type}: {count}")
    
    summary = demo.event_system.state_manager.get_summary()
    print(f"\nState Manager Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Cleanup
    await demo.event_system.stop()


def demo_api_usage():
    """Print example API usage for Unity/WebSocket clients."""
    
    print("\n" + "="*60)
    print("API USAGE EXAMPLES")
    print("="*60)
    
    print("""
# WebSocket Connection (for real-time events)
ws://localhost:8000/ws/{player_id}

# WebSocket Protocol:
# Connect as player 'alice':
ws://localhost:8000/ws/alice

# Subscribe to zone events:
{"action": "subscribe", "topic": "zone:village"}

# Subscribe to NPC events:
{"action": "subscribe", "topic": "npc:blacksmith"}

# Subscribe to all events:
{"action": "subscribe", "topic": "all"}

# Change zone:
{"action": "zone_change", "zone_id": "forest"}

# Send dialogue:
{"action": "dialogue", "npc_id": "blacksmith", "message": "Hello!"}

# Accept quest:
{"action": "quest_accept", "quest_id": "gather_herbs"}

# Complete quest (shared=true affects all players):
{"action": "quest_complete", "quest_id": "defeat_boss", "shared": true}

# Pong (keepalive):
{"action": "pong"}


# REST API Endpoints:

# Get multiplayer status:
GET /api/multiplayer/status

# Get connected players:
GET /api/multiplayer/players

# Get specific player state:
GET /api/multiplayer/players/alice

# Get world state:
GET /api/multiplayer/world

# Get all NPCs:
GET /api/multiplayer/npcs

# Register NPC:
POST /api/multiplayer/npcs/blacksmith/register?name=Gareth&zone=village

# Save state:
POST /api/multiplayer/save

# Load state:
POST /api/multiplayer/load
""")


if __name__ == "__main__":
    print("="*60)
    print("MULTIPLAYER NPC DIALOGUE SYSTEM DEMO")
    print("="*60)
    
    # Run async demo
    asyncio.run(run_demo())
    
    # Show API usage
    demo_api_usage()
    
    print("\nDemo complete!")
