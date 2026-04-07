#!/usr/bin/env python3
"""
Demo Script - Relationship Tracking System
Shows how NPCs remember and respond to player actions
"""

import time
import os
from npc_dialogue import NPCDialogue, NPCManager
from relationship_tracking import RelationshipTracker


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_npc_message(npc_name, message):
    """Print an NPC message with formatting."""
    print(f"\n👤 {npc_name}:")
    for line in message.split('\n'):
        print(f"   {line}")


def print_user_message(message):
    """Print a user message."""
    print(f"\n💬 You: {message}")


def print_relationship_update(npc_name, score, level):
    """Print relationship update."""
    level_emoji = {
        "HATED": "😠",
        "DISLIKED": "😒",
        "NEUTRAL": "😐",
        "LIKED": "🙂",
        "LOVED": "😊",
        "ADORED": "😍"
    }
    emoji = level_emoji.get(level, "❓")
    print(f"💖 {npc_name} Relationship: {score:+.1f} ({emoji} {level})")


def demo_basic_relationship():
    """Demo basic relationship tracking."""
    print_section("BASIC RELATIONSHIP TRACKING")
    
    # Create a relationship tracker
    tracker = RelationshipTracker(player_id="hero_001")
    
    # Create NPC with relationship tracking
    npc = NPCDialogue(
        character_name="Thorne",
        character_card_path="character_cards/blacksmith.json",
        model="llama3.2:1b",
        relationship_tracker=tracker
    )
    
    print("\n📊 Initial Relationship:")
    print_relationship_update("Thorne", npc.get_relationship_score(), npc.get_relationship_level())
    
    # Complete a quest
    print("\n--- Quest: Repair Anvil ---")
    score = npc.update_from_quest("repair_anvil", success=True, reward=15.0)
    print_relationship_update("Thorne", score, npc.get_relationship_level())
    
    # Give a gift
    print("\n--- Gift: Rare Iron Ore ---")
    score = npc.update_from_gift("rare_iron_ore", value=10.0)
    print_relationship_update("Thorne", score, npc.get_relationship_level())
    
    # Friendly dialogue
    print("\n--- Dialogue Choice: Friendly ---")
    score = npc.update_from_dialogue("friendly")
    print_relationship_update("Thorne", score, npc.get_relationship_level())
    
    # Show character info with relationship
    npc.print_character_info()
    
    return npc, tracker


def demo_multiple_npcs():
    """Demo tracking relationships with multiple NPCs."""
    print_section("MULTIPLE NPC RELATIONSHIPS")
    
    # Create shared tracker
    tracker = RelationshipTracker(player_id="player_123")
    
    # Create manager with relationship tracking
    manager = NPCManager(model="llama3.2:1b", relationship_tracker=tracker)
    
    # Load characters
    print("\n📜 Loading characters...")
    manager.load_character("character_cards/blacksmith.json")
    manager.load_character("character_cards/merchant.json")
    manager.load_character("character_cards/wizard.json")
    
    # Update relationships differently
    print("\n--- Building Relationships ---")
    
    # Thorne: Positive through quests
    thorne = manager.npcs["Thorne"]
    thorne.update_from_quest("forge_weapon", success=True, reward=20.0)
    thorne.update_from_quest("repair_armor", success=True, reward=15.0)
    print_relationship_update("Thorne", thorne.get_relationship_score(), thorne.get_relationship_level())
    
    # Elara: Positive through gifts
    elara = manager.npcs["Elara"]
    elara.update_from_gift("rare_gem", value=15.0)
    elara.update_from_gift("exotic_spice", value=10.0)
    print_relationship_update("Elara", elara.get_relationship_score(), elara.get_relationship_level())
    
    # Zephyr: Negative through rude dialogue
    zephyr = manager.npcs["Zephyr"]
    zephyr.update_from_dialogue("rude")
    zephyr.update_from_dialogue("hostile")
    print_relationship_update("Zephyr", zephyr.get_relationship_score(), zephyr.get_relationship_level())
    
    # Show summary
    print("\n📊 Relationship Summary:")
    manager.print_relationship_summary()
    
    return manager, tracker


def demo_factions():
    """Demo faction relationship support."""
    print_section("FACTION RELATIONSHIPS")
    
    tracker = RelationshipTracker(player_id="player_456")
    
    # Update faction relationships
    print("\n--- Faction Interactions ---")
    
    tracker.update_faction("Merchants Guild", 20.0, "helped merchant")
    tracker.update_faction("Traders Alliance", 15.0, "completed trade deal")
    tracker.update_faction("Circle of Mages", -10.0, "stole magic item")
    
    # Create NPCs and apply faction bonuses
    manager = NPCManager(model="llama3.2:1b", relationship_tracker=tracker)
    manager.load_character("character_cards/blacksmith.json")
    manager.load_character("character_cards/merchant.json")
    
    thorne = manager.npcs["Thorne"]
    elara = manager.npcs["Elara"]
    
    # Add some personal relationship
    thorne.update_from_quest("personal_quest", success=True, reward=10.0)
    elara.update_from_gift("personal_gift", value=5.0)
    
    # Show how faction bonuses affect things
    print("\n💰 Faction Bonuses:")
    
    thorne_bonus = tracker.get_npc_faction_bonus("Thorne", "Merchants Guild")
    thorne_total = thorne.get_relationship_score() + thorne_bonus
    print(f"   Thorne: Personal {thorne.get_relationship_score():+.1f} + Faction {thorne_bonus:+.1f} = {thorne_total:+.1f}")
    
    elara_bonus = tracker.get_npc_faction_bonus("Elara", "Traders Alliance")
    elara_total = elara.get_relationship_score() + elara_bonus
    print(f"   Elara: Personal {elara.get_relationship_score():+.1f} + Faction {elara_bonus:+.1f} = {elara_total:+.1f}")
    
    print("\n📊 Full Summary:")
    manager.print_relationship_summary()
    
    return manager, tracker


def demo_temperature_changes():
    """Demo how temperature changes with relationship."""
    print_section("TEMPERATURE ADJUSTMENT")
    
    tracker = RelationshipTracker(player_id="temp_demo")
    npc = NPCDialogue(
        character_name="Thorne",
        character_card_path="character_cards/blacksmith.json",
        model="llama3.2:1b",
        base_temperature=0.8,
        relationship_tracker=tracker
    )
    
    print(f"\nBase Temperature: {npc.base_temperature}")
    print("\n🌡️  Temperature by Relationship Level:")
    
    # Test different relationship levels
    scores = [-75, -35, 0, 35, 65, 90]
    levels = ["Hated", "Disliked", "Neutral", "Liked", "Loved", "Adored"]
    
    for score, level in zip(scores, levels):
        tracker.update_score("Thorne", score, "test")
        npc.refresh_temperature()
        temp = npc.temperature
        
        print(f"   {level:10s} ({score:+3d}): {temp:.2f}")
    
    print("\n💡 Higher relationship = Lower temperature (more consistent personality)")
    print("   Lower relationship = Higher temperature (more volatile personality)")


def demo_save_load():
    """Demo saving and loading relationships."""
    print_section("SAVE / LOAD PERSISTENCE")
    
    # Create tracker and add relationships
    tracker = RelationshipTracker(player_id="save_demo")
    npc = NPCDialogue(
        character_name="Thorne",
        character_card_path="character_cards/blacksmith.json",
        model="llama3.2:1b",
        relationship_tracker=tracker
    )
    
    print("\n📝 Creating relationships...")
    npc.update_from_quest("quest_001", success=True, reward=15.0)
    npc.update_from_gift("gift_001", value=10.0)
    npc.update_from_dialogue("friendly")
    
    print("\n💾 Saving relationships...")
    tracker.save()
    
    # Create new tracker and load
    print("\n📂 Creating new tracker and loading...")
    new_tracker = RelationshipTracker(player_id="save_demo")
    new_tracker.load()
    
    print("\n✅ Loaded relationships:")
    new_tracker.print_relationship_summary()


def demo_query_conditions():
    """Demo querying NPCs by relationship conditions."""
    print_section("QUERYING RELATIONSHIPS")
    
    tracker = RelationshipTracker(player_id="query_demo")
    
    # Create NPCs with different relationship levels
    npcs = [
        ("Thorne", 75),
        ("Elara", 55),
        ("Zephyr", -30),
        ("Garrick", 10),
        ("Lyra", -70),
        ("Marcus", 25)
    ]
    
    for npc_name, score in npcs:
        tracker.update_score(npc_name, score, "test")
    
    print("\n📊 All Relationship Scores:")
    for npc_name, score in npcs:
        level = tracker.get_level(npc_name).name
        print(f"   {npc_name:10s}: {score:+3d} ({level})")
    
    print("\n🔍 Querying NPCs:")
    
    # Get liked or better
    liked = tracker.get_npc_for_condition("> 20")
    print(f"\n   Liked or better (> 20): {', '.join(liked)}")
    
    # Get disliked or worse
    disliked = tracker.get_npc_for_condition("< -20")
    print(f"   Disliked or worse (< -20): {', '.join(disliked)}")
    
    # Get loved NPCs
    loved = tracker.get_npc_for_condition("== LOVED")
    print(f"   Loved level (50-80): {', '.join(loved)}")
    
    # Get hated NPCs
    hated = tracker.get_npc_for_condition("== HATED")
    print(f"   Hated level (-100 to -50): {', '.join(hated)}")


def main():
    """Run all relationship tracking demos."""
    print("\n" + "="*60)
    print("  🎮 RELATIONSHIP TRACKING SYSTEM - DEMONSTRATION")
    print("  Showing how NPCs remember player actions")
    print("="*60)
    
    try:
        # Demo 1: Basic relationship tracking
        demo_basic_relationship()
        
        input("\n⏸️  Press Enter to continue to multiple NPCs...")
        
        # Demo 2: Multiple NPCs
        demo_multiple_npcs()
        
        input("\n⏸️  Press Enter to continue to factions...")
        
        # Demo 3: Factions
        demo_factions()
        
        input("\n⏸️  Press Enter to continue to temperature...")
        
        # Demo 4: Temperature adjustment
        demo_temperature_changes()
        
        input("\n⏸️  Press Enter to continue to save/load...")
        
        # Demo 5: Save/Load
        demo_save_load()
        
        input("\n⏸️  Press Enter to continue to queries...")
        
        # Demo 6: Query conditions
        demo_query_conditions()
        
        # Final summary
        print_section("DEMO COMPLETE")
        print("\n✅ All relationship tracking features demonstrated!")
        print("\n📚 Features shown:")
        print("   • Score tracking (-100 to +100)")
        print("   • Six relationship levels")
        print("   • Temperature adjustment")
        print("   • Quest completion rewards")
        print("   • Gift giving mechanics")
        print("   • Dialogue choice impact")
        print("   • Faction support")
        print("   • Save/load persistence")
        print("   • Query conditions")
        print("\n🚀 Try it yourself:")
        print("   python3 main.py")
        print("   python3 demo_relationships.py")
        print("\n📖 Read the documentation:")
        print("   RELATIONSHIPS.md - Complete guide")
        print("   README.md - Quick start")
        print("\n" + "="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n👋 Demo stopped. Thanks for watching!\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
