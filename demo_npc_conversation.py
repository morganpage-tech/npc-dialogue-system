#!/usr/bin/env python3
"""
NPC-to-NPC Conversation Demo

Demonstrates the conversation system between NPCs:
- Starting conversations
- Turn-by-turn dialogue
- Proximity-based triggers
- Player overhearing
- Topic selection
"""

import asyncio
import sys
from pathlib import Path
from npc_dialogue import NPCManager
from relationship_tracking import RelationshipTracker
from npc_conversation import (
    ConversationManager, ConversationTrigger, ConversationState
)


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")


def print_exchange(speaker: str, listener: str, message: str, topic: str = None):
    """Print a conversation exchange."""
    topic_str = f" [{topic}]" if topic else ""
    print(f"  {speaker} -> {listener}{topic_str}:")
    print(f"    \"{message}\"\n")


async def demo_basic_conversation(conv_manager: ConversationManager):
    """Demo: Basic NPC-to-NPC conversation."""
    print_header("Demo 1: Basic NPC Conversation")
    
    print("Starting conversation between Blacksmith and Merchant...")
    print("-" * 40)
    
    # Set up callback to print exchanges in real-time
    def on_exchange(conv, exchange):
        print_exchange(exchange.speaker, exchange.listener, exchange.message, exchange.topic)
    
    conv_manager.on_exchange = on_exchange
    
    # Run full conversation
    conversation = await conv_manager.run_full_conversation(
        npc1_name="Blacksmith",
        npc2_name="Merchant",
        trigger=ConversationTrigger.FORCED,
        max_turns=6,
        turn_delay=1.5
    )
    
    print("-" * 40)
    print(f"Conversation completed!")
    print(f"  Duration: {conversation.get_duration():.1f}s")
    print(f"  Exchanges: {len(conversation.exchanges)}")
    print(f"  Topics discussed: {', '.join(conversation.topics_discussed) or 'None'}")
    
    return conversation


async def demo_topic_selection(conv_manager: ConversationManager):
    """Demo: Topic selection and relationship effects."""
    print_header("Demo 2: Topic Selection")
    
    topics = conv_manager.engine.topic_registry.topics
    
    print(f"Available topics ({len(topics)}):")
    for topic in sorted(topics.values(), key=lambda t: t.priority, reverse=True):
        print(f"  - {topic.name} (priority: {topic.priority})")
        print(f"    Min relationship: {topic.min_relationship}")
        print(f"    {topic.description}")
    
    print("\n" + "-" * 40)
    
    # Show how relationship affects available topics
    print("\nTopics available at different relationship levels:")
    for rel_score in [-50, 0, 30, 60]:
        available = conv_manager.engine.topic_registry.get_available_topics(
            "Blacksmith", "Merchant", rel_score, []
        )
        names = [t.name for t in available]
        print(f"  Relationship {rel_score:+.0f}: {', '.join(names) if names else 'None'}")


async def demo_proximity_conversation(conv_manager: ConversationManager):
    """Demo: Proximity-triggered conversations."""
    print_header("Demo 3: Proximity-Based Conversations")
    
    # Update NPC locations
    conv_manager.update_npc_location("Blacksmith", "town_square")
    conv_manager.update_npc_location("Merchant", "town_square")
    conv_manager.update_npc_location("Wizard", "tower")
    
    print("NPC Locations:")
    for npc, loc in conv_manager.npc_locations.items():
        print(f"  {npc}: {loc}")
    
    print("\nNPCs at town_square:", conv_manager.get_npcs_at_location("town_square"))
    print("NPCs at tower:", conv_manager.get_npcs_at_location("tower"))
    
    print("\nChecking for proximity conversations...")
    await conv_manager.check_proximity_conversations()
    
    # Note: Proximity has 10% random chance, may not trigger
    active = conv_manager.get_active_conversations()
    if active:
        print(f"Started {len(active)} proximity conversation(s)")
    else:
        print("No proximity conversations started (10% chance per check)")
        print("Manually starting one for demo...")
        
        conversation = await conv_manager.run_full_conversation(
            npc1_name="Blacksmith",
            npc2_name="Merchant",
            trigger=ConversationTrigger.PROXIMITY,
            location="town_square",
            max_turns=4,
            turn_delay=1.0
        )
        print(f"Conversation completed with {len(conversation.exchanges)} exchanges")


async def demo_player_overhearing(conv_manager: ConversationManager):
    """Demo: Player overhearing NPC conversations."""
    print_header("Demo 4: Player Overhearing")
    
    # Start a conversation
    print("Starting a conversation at the tavern...")
    conversation = conv_manager.start_conversation(
        npc1_name="Blacksmith",
        npc2_name="Merchant",
        trigger=ConversationTrigger.FORCED,
        location="tavern",
        max_turns=4
    )
    
    # Add player as listener
    conv_manager.add_player_listener(conversation.conversation_id, "player1")
    print(f"Player 'player1' is now listening to conversation at tavern")
    
    # Run a few turns
    print("\nConversation (player can overhear):")
    print("-" * 40)
    
    for _ in range(3):
        exchange = await conv_manager.run_conversation_turn(conversation.conversation_id)
        if exchange:
            print_exchange(exchange.speaker, exchange.listener, exchange.message)
    
    # Show overhearable conversations
    print("\nConversations player can hear at tavern:")
    overhearable = conv_manager.get_overhearable_conversations("tavern")
    for conv in overhearable:
        print(f"  - {conv.npc1_name} & {conv.npc2_name} ({conv.state.value})")
    
    # End conversation
    conv_manager.end_conversation(conversation.conversation_id)
    print("\nConversation ended.")


async def demo_conversation_history(conv_manager: ConversationManager):
    """Demo: Saving and loading conversation history."""
    print_header("Demo 5: Conversation History")
    
    print(f"Conversations in history: {len(conv_manager.conversation_history)}")
    
    # Save history
    save_path = "conversation_history/npc_conversations.json"
    conv_manager.save_history(save_path)
    print(f"History saved to {save_path}")
    
    # Show summary
    print("\nRecent conversations:")
    for conv in conv_manager.conversation_history[-5:]:
        print(f"  - {conv.npc1_name} & {conv.npc2_name}")
        print(f"    Turns: {len(conv.exchanges)}, Duration: {conv.get_duration():.1f}s")
        print(f"    Topics: {', '.join(conv.topics_discussed) or 'None'}")


async def demo_conversation_states(conv_manager: ConversationManager):
    """Demo: Conversation state management."""
    print_header("Demo 6: Conversation States")
    
    # Start a conversation manually
    conversation = conv_manager.start_conversation(
        npc1_name="Wizard",
        npc2_name="Merchant",
        trigger=ConversationTrigger.FORCED,
        max_turns=4
    )
    
    print(f"Conversation ID: {conversation.conversation_id}")
    print(f"Initial state: {conversation.state.value}")
    
    # Check if NPCs are in conversation
    print(f"\nWizard in conversation: {conv_manager.is_npc_in_conversation('Wizard')}")
    print(f"Merchant in conversation: {conv_manager.is_npc_in_conversation('Merchant')}")
    print(f"Blacksmith in conversation: {conv_manager.is_npc_in_conversation('Blacksmith')}")
    
    # Get active conversations
    active = conv_manager.get_active_conversations()
    print(f"\nActive conversations: {len(active)}")
    for conv in active:
        print(f"  - {conv.conversation_id}: {conv.npc1_name} & {conv.npc2_name}")
    
    # End conversation
    conv_manager.end_conversation(conversation.conversation_id)
    print(f"\nAfter ending:")
    print(f"  Wizard in conversation: {conv_manager.is_npc_in_conversation('Wizard')}")
    print(f"  Final state: {conversation.state.value}")


async def run_all_demos():
    """Run all demos."""
    print_header("NPC-to-NPC Conversation System Demo")
    
    # Initialize manager
    manager = NPCManager(model="llama3.2:1b")
    
    # Load characters
    cards_dir = Path("character_cards")
    print("Loading NPC characters...")
    
    try:
        manager.load_character(str(cards_dir / "blacksmith.json"))
        manager.load_character(str(cards_dir / "merchant.json"))
        manager.load_character(str(cards_dir / "wizard.json"))
        print(f"Loaded: {', '.join(manager.list_characters())}")
    except FileNotFoundError as e:
        print(f"Error: Could not load character cards: {e}")
        print("Make sure you're running from the npc-dialogue-system directory")
        return
    
    # Create relationship tracker
    relationship_tracker = RelationshipTracker()
    
    # Set some initial relationships between NPCs
    relationship_tracker.update("Blacksmith", 20.0, "neighbors")
    relationship_tracker.update("Merchant", 15.0, "business_partner")
    
    # Create conversation manager
    conv_manager = ConversationManager(
        npc_manager=manager,
        relationship_tracker=relationship_tracker
    )
    
    print("\n" + "=" * 60)
    print(" Conversation Manager Initialized")
    print("=" * 60)
    
    # Check Ollama availability
    if conv_manager.engine.ollama_available:
        print("Ollama: Connected")
    else:
        print("Ollama: Not available (using template responses)")
    
    # Run demos
    try:
        await demo_basic_conversation(conv_manager)
        await demo_topic_selection(conv_manager)
        await demo_proximity_conversation(conv_manager)
        await demo_player_overhearing(conv_manager)
        await demo_conversation_states(conv_manager)
        await demo_conversation_history(conv_manager)
        
        print_header("All Demos Complete!")
        print("The NPC-to-NPC conversation system is working.")
        print("\nKey features demonstrated:")
        print("  - Basic turn-taking conversations")
        print("  - Topic selection based on relationship")
        print("  - Proximity-based triggers")
        print("  - Player overhearing")
        print("  - State management")
        print("  - History persistence")
        
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    # Check for command line args
    if len(sys.argv) > 1:
        if sys.argv[1] == "--quick":
            # Quick demo - just one conversation
            print("Running quick demo...")
            asyncio.run(demo_basic_conversation(
                ConversationManager(
                    npc_manager=NPCManager(model="llama3.2:1b")
                )
            ))
            return
    
    # Run full demo
    asyncio.run(run_all_demos())


if __name__ == "__main__":
    main()
