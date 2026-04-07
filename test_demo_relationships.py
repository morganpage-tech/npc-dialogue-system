#!/usr/bin/env python3
"""
Simplified Demo - Relationship Tracking System
Tests relationship tracking without requiring Ollama
"""

from relationship_tracking import RelationshipTracker, RelationshipLevel


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_relationship(npc_name, tracker):
    """Print relationship info."""
    score = tracker.get_relationship(npc_name).score
    level = tracker.get_level(npc_name)
    
    level_emoji = {
        "HATED": "😠",
        "DISLIKED": "😒",
        "NEUTRAL": "😐",
        "LIKED": "🙂",
        "LOVED": "😊",
        "ADORED": "😍"
    }
    emoji = level_emoji.get(level.name, "❓")
    print(f"💖 {npc_name}: {score:+.1f} ({emoji} {level.name})")


def main():
    """Run relationship tracking demo."""
    print("\n" + "="*60)
    print("  🎮 RELATIONSHIP TRACKING SYSTEM - DEMO")
    print("="*60)
    
    # Demo 1: Basic relationship tracking
    print_section("1. BASIC RELATIONSHIP TRACKING")
    
    tracker = RelationshipTracker(player_id="hero_001")
    
    print("\n📊 Initial state:")
    print_relationship("Thorne", tracker)
    
    print("\n--- Complete Quest: Repair Anvil ---")
    tracker.update_from_quest("Thorne", "repair_anvil", success=True, reward=15.0)
    print_relationship("Thorne", tracker)
    
    print("\n--- Give Gift: Rare Iron Ore ---")
    tracker.update_from_gift("Thorne", "rare_iron_ore", value=10.0)
    print_relationship("Thorne", tracker)
    
    print("\n--- Friendly Dialogue ---")
    tracker.update_from_dialogue("Thorne", "friendly")
    print_relationship("Thorne", tracker)
    
    # Demo 2: Multiple NPCs
    print_section("2. MULTIPLE NPC RELATIONSHIPS")
    
    print("\n--- Building Different Relationships ---")
    
    # Thorne: Quest-focused
    tracker.update_from_quest("Thorne", "forge_weapon", success=True, reward=20.0)
    tracker.update_from_quest("Thorne", "repair_armor", success=True, reward=15.0)
    print_relationship("Thorne", tracker)
    
    # Elara: Gift-focused
    tracker.update_from_gift("Elara", "rare_gem", value=15.0)
    tracker.update_from_gift("Elara", "exotic_spice", value=10.0)
    print_relationship("Elara", tracker)
    
    # Zephyr: Negative through hostile dialogue
    tracker.update_from_dialogue("Zephyr", "rude")
    tracker.update_from_dialogue("Zephyr", "hostile")
    tracker.update_from_dialogue("Zephyr", "insult")
    print_relationship("Zephyr", tracker)
    
    print("\n📊 Summary:")
    tracker.print_summary()
    
    # Demo 3: Temperature adjustment
    print_section("3. TEMPERATURE ADJUSTMENT")
    
    print("\nBase temperature: 0.8")
    print("Temperature changes based on relationship:")
    print()
    
    test_scores = [
        (-75, "Hated"),
        (-35, "Disliked"),
        (0, "Neutral"),
        (35, "Liked"),
        (65, "Loved"),
        (90, "Adored")
    ]
    
    for score, level in test_scores:
        tracker.update_score("TestNPC", score, "test")
        temp = tracker.get_temperature_adjustment("TestNPC", 0.8)
        print(f"   {level:10s} ({score:+3d}): temp = {temp:.2f}")
    
    print("\n💡 Higher relationship = Lower temperature (more consistent)")
    print("   Lower relationship = Higher temperature (more volatile)")
    
    # Demo 4: Factions
    print_section("4. FACTION RELATIONSHIPS")
    
    print("\n--- Faction Interactions ---")
    tracker.update_faction("Merchants Guild", 20.0, "helped merchant")
    tracker.update_faction("Traders Alliance", 15.0, "completed trade")
    tracker.update_faction("Circle of Mages", -10.0, "stole magic item")
    
    print("\n💰 Faction Bonuses:")
    thorne_bonus = tracker.get_npc_faction_bonus("Thorne", "Merchants Guild")
    print(f"   Thorne (Merchants Guild): +{thorne_bonus:.1f} bonus")
    
    elara_bonus = tracker.get_npc_faction_bonus("Elara", "Traders Alliance")
    print(f"   Elara (Traders Alliance): +{elara_bonus:.1f} bonus")
    
    # Demo 5: Query conditions
    print_section("5. QUERYING RELATIONSHIPS")
    
    print("\n📊 Current Relationships:")
    for npc in ["Thorne", "Elara", "Zephyr"]:
        print_relationship(npc, tracker)
    
    print("\n🔍 Query Results:")
    
    liked = tracker.get_npc_for_condition("> 20")
    print(f"   Liked or better (> 20): {', '.join(liked)}")
    
    disliked = tracker.get_npc_for_condition("< -20")
    print(f"   Disliked or worse (< -20): {', '.join(disliked)}")
    
    loved = tracker.get_npc_for_condition("== LOVED")
    print(f"   Loved level (50-80): {', '.join(loved)}")
    
    # Demo 6: Save/Load
    print_section("6. SAVE / LOAD PERSISTENCE")
    
    import os
    save_path = "/tmp/test_relationships.json"
    
    print(f"\n💾 Saving to: {save_path}")
    tracker.save(save_path)
    
    print("\n📂 Loading into new tracker...")
    new_tracker = RelationshipTracker(player_id="hero_001")
    new_tracker.load(save_path)
    
    print("\n✅ Restored relationships:")
    for npc in ["Thorne", "Elara", "Zephyr"]:
        print_relationship(npc, new_tracker)
    
    # Clean up
    if os.path.exists(save_path):
        os.remove(save_path)
        print(f"\n🗑️  Cleaned up: {save_path}")
    
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
    print("\n🚀 Run tests:")
    print("   python3 test_relationships.py")
    print("\n📖 Read the documentation:")
    print("   RELATIONSHIPS.md - Complete guide")
    print("   README.md - Quick start")
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
