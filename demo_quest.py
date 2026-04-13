#!/usr/bin/env python3
"""
Quest Generation System Demo

Demonstrates procedural quest generation with NPC integration,
difficulty scaling, and state management.
"""

import json
import time
from quest_generator import (
    QuestGenerator,
    QuestManager,
    QuestType,
    QuestStatus,
    ObjectiveType,
    Quest,
    generate_quest_for_npc,
)


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'-'*60}\n")


def demo_basic_generation():
    """Demonstrate basic quest generation."""
    print_separator("BASIC QUEST GENERATION")
    
    generator = QuestGenerator()
    
    # Generate quests for different NPC archetypes
    npcs = [
        ("Greta the Blacksmith", "blacksmith"),
        ("Captain Marcus", "guard"),
        ("Elder Theron", "scholar"),
        ("Lydia the Merchant", "merchant"),
    ]
    
    for npc_name, archetype in npcs:
        npc_data = {"archetype": archetype}
        player_state = {"level": 3, "completed_quests": []}
        
        quest = generator.generate_quest(
            npc_name=npc_name,
            npc_data=npc_data,
            player_state=player_state,
        )
        
        if quest:
            print(f"NPC: {npc_name} ({archetype})")
            print(f"Quest: {quest.name}")
            print(f"Type: {quest.quest_type.value}")
            print(f"Difficulty: {quest.difficulty}/5")
            print(f"Description: {quest.description}")
            print(f"Narrative: {quest.narrative_context}")
            print(f"Objectives:")
            for obj in quest.objectives:
                print(f"  - {obj.description} ({obj.current}/{obj.required})")
            print(f"Rewards: {quest.rewards.gold} gold, {quest.rewards.xp} XP")
            print()


def demo_quest_types():
    """Demonstrate all quest types."""
    print_separator("ALL QUEST TYPES")
    
    generator = QuestGenerator()
    
    for quest_type in QuestType:
        quest = generator.generate_quest(
            npc_name="Test NPC",
            npc_data={},
            player_state={"level": 2},
            quest_type=quest_type,
        )
        
        if quest:
            print(f"[{quest_type.value.upper()}]")
            print(f"  Name: {quest.name}")
            print(f"  Description: {quest.description}")
            print(f"  Time Limit: {quest.time_limit}s" if quest.time_limit else "  No time limit")
            print()


def demo_difficulty_scaling():
    """Demonstrate difficulty scaling based on player level."""
    print_separator("DIFFICULTY SCALING")
    
    generator = QuestGenerator()
    
    levels = [1, 3, 5, 10, 15]
    
    for level in levels:
        quest = generator.generate_quest(
            npc_name="Captain Marcus",
            npc_data={"archetype": "guard"},
            player_state={"level": level},
            quest_type=QuestType.KILL,
        )
        
        if quest:
            print(f"Player Level {level}:")
            print(f"  Quest: {quest.name}")
            print(f"  Difficulty: {quest.difficulty}/5")
            print(f"  Gold Reward: {quest.rewards.gold}")
            print(f"  XP Reward: {quest.rewards.xp}")
            total_enemies = sum(o.required for o in quest.objectives)
            print(f"  Enemies to defeat: {total_enemies}")
            print()


def demo_quest_lifecycle():
    """Demonstrate full quest lifecycle."""
    print_separator("QUEST LIFECYCLE")
    
    manager = QuestManager()
    
    # Generate quests for an NPC
    print("1. Generating quests for NPC...")
    quests = manager.generate_quests_for_npc(
        npc_name="Greta the Blacksmith",
        npc_data={"archetype": "blacksmith", "location": "Ironforge"},
        player_state={"level": 2},
        count=2,
    )
    
    for quest in quests:
        print(f"   Generated: {quest.name} (ID: {quest.id})")
    
    # Show available quests
    print("\n2. Available quests from Greta:")
    available = manager.get_available_quests("Greta the Blacksmith")
    for quest in available:
        print(f"   - {quest.name}")
    
    # Accept a quest
    if quests:
        quest_id = quests[0].id
        print(f"\n3. Accepting quest: {quest_id}")
        accepted = manager.accept_quest(quest_id)
        
        if accepted:
            print(f"   Accepted: {accepted.name}")
            print(f"   Status: {accepted.status.value}")
            if accepted.time_limit:
                print(f"   Time remaining: {accepted.get_time_remaining()}s")
    
    # Simulate progress
    if quests:
        quest = manager.get_quest(quest_id)
        if quest and quest.objectives:
            obj = quest.objectives[0]
            print(f"\n4. Simulating progress on: {obj.target}")
            
            for i in range(obj.required):
                updates = manager.update_progress(obj.type, obj.target, 1)
                for qid, progress in updates.items():
                    print(f"   Progress: {progress:.0f}%")
    
    # Complete the quest
    if quests:
        print(f"\n5. Completing quest: {quest_id}")
        rewards = manager.complete_quest(quest_id)
        
        if rewards:
            print(f"   Quest completed!")
            print(f"   Rewards: {rewards['gold']} gold, {rewards['xp']} XP")
            if rewards.get('items'):
                print(f"   Items: {', '.join(rewards['items'])}")
        else:
            print("   Could not complete quest (objectives not met)")
    
    # Show summary
    manager.print_summary()


def demo_save_load():
    """Demonstrate quest state persistence."""
    print_separator("SAVE/LOAD PERSISTENCE")
    
    # Create manager with some quests
    manager1 = QuestManager(save_dir="saves")
    
    quests = manager1.generate_quests_for_npc(
        npc_name="Elder Theron",
        npc_data={"archetype": "scholar"},
        player_state={"level": 5},
        count=2,
    )
    
    if quests:
        manager1.accept_quest(quests[0].id)
        manager1.save("demo_player")
    
    # Load into new manager
    print("\nLoading saved state into new manager...")
    manager2 = QuestManager(save_dir="saves")
    manager2.load("demo_player")
    
    manager2.print_summary()


def demo_quick_generation():
    """Demonstrate convenience function."""
    print_separator("QUICK QUEST GENERATION")
    
    # Using the convenience function
    quest = generate_quest_for_npc(
        npc_name="Village Elder",
        npc_archetype="scholar",
        player_level=4,
    )
    
    if quest:
        print(f"Quest: {quest.name}")
        print(f"Type: {quest.quest_type.value}")
        print(f"Description: {quest.description}")
        print(f"Rewards: {quest.rewards.gold} gold, {quest.rewards.xp} XP")


def demo_quest_json():
    """Demonstrate JSON serialization."""
    print_separator("JSON SERIALIZATION")
    
    quest = generate_quest_for_npc(
        npc_name="Merchant Lydia",
        npc_archetype="merchant",
        player_level=3,
    )
    
    if quest:
        # Convert to JSON
        quest_dict = quest.to_dict()
        print("Quest as JSON:")
        print(json.dumps(quest_dict, indent=2))
        
        # Reconstruct from JSON
        print("\nReconstructing from JSON...")
        quest2 = Quest.from_dict(quest_dict)
        print(f"  Name: {quest2.name}")
        print(f"  Type: {quest2.quest_type.value}")
        print(f"  Objectives: {len(quest2.objectives)}")


def demo_multiple_objectives():
    """Demonstrate quest with multiple objectives."""
    print_separator("MULTI-OBJECTIVE QUEST")
    
    # Create a custom quest with multiple objectives
    from quest_generator import Objective, QuestReward, Quest
    
    quest = Quest(
        id="quest_multi_001",
        name="Clear the Bandit Camp",
        description="Eliminate the bandit threat at Bandit's Pass and recover the stolen goods.",
        quest_giver="Guard Captain Marcus",
        quest_type=QuestType.KILL,
        objectives=[
            Objective(
                id="obj_1",
                type=ObjectiveType.KILL_TARGET,
                description="Defeat bandits",
                target="bandit",
                required=5,
            ),
            Objective(
                id="obj_2",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Defeat the bandit leader",
                target="bandit_chief",
                required=1,
            ),
            Objective(
                id="obj_3",
                type=ObjectiveType.COLLECT_ITEM,
                description="Recover stolen goods",
                target="stolen_crate",
                required=3,
                optional=True,
            ),
        ],
        rewards=QuestReward(
            gold=150,
            xp=300,
            items=["guard_badge", "silver_ring"],
            relationship_bonus={"Guard Captain Marcus": 15},
        ),
        difficulty=3,
        location="Bandit's Pass",
        narrative_context="The bandits have been raiding merchant caravans for weeks. Captain Marcus needs them eliminated.",
    )
    
    print(f"Quest: {quest.name}")
    print(f"Difficulty: {quest.difficulty}/5")
    print(f"Location: {quest.location}")
    print(f"\nObjectives:")
    for obj in quest.objectives:
        optional = " (Optional)" if obj.optional else ""
        print(f"  [{obj.id}] {obj.description}{optional}")
        print(f"        Target: {obj.target} x{obj.required}")
    
    print(f"\nRewards:")
    print(f"  Gold: {quest.rewards.gold}")
    print(f"  XP: {quest.rewards.xp}")
    print(f"  Items: {', '.join(quest.rewards.items)}")
    print(f"  Relationship: +{quest.rewards.relationship_bonus.get('Guard Captain Marcus', 0)} with Guard Captain Marcus")


def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("  QUEST GENERATION SYSTEM DEMO")
    print("  NPC Dialogue System v1.5.0")
    print("="*60)
    
    demo_basic_generation()
    demo_quest_types()
    demo_difficulty_scaling()
    demo_quest_lifecycle()
    demo_save_load()
    demo_quick_generation()
    demo_quest_json()
    demo_multiple_objectives()
    
    print_separator("DEMO COMPLETE")
    print("The Quest Generation System provides:")
    print("  - 6 quest types (kill, fetch, explore, escort, collection, dialogue)")
    print("  - Difficulty scaling based on player level")
    print("  - NPC archetype-based quest selection")
    print("  - Time-limited quests with automatic failure")
    print("  - Multi-objective quests with optional goals")
    print("  - Save/load persistence")
    print("  - JSON serialization for API integration")
    print()


if __name__ == "__main__":
    main()
