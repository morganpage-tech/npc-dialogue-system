#!/usr/bin/env python3
"""
Demo: Lore System for NPC Knowledge
Shows how NPCs can use RAG for contextual dialogue
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lore_system import LoreSystem


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def demo_basic_search():
    """Demo basic lore search functionality."""
    print_header("Demo 1: Basic Lore Search")
    
    lore = LoreSystem()
    
    # Search for war-related lore
    print("Searching for: 'war and battles'")
    results = lore.search("war and battles", n_results=3)
    
    for entry, score in results:
        print(f"\n📄 [{entry.category}] {entry.title}")
        print(f"   Relevance: {score:.2f}")
        print(f"   Content: {entry.content[:150]}...")
    
    # Search for locations
    print("\n" + "-"*40)
    print("\nSearching for: 'mountains and cities'")
    results = lore.search("mountains and cities", n_results=3)
    
    for entry, score in results:
        print(f"\n📄 [{entry.category}] {entry.title}")
        print(f"   Relevance: {score:.2f}")


def demo_npc_context():
    """Demo NPC-specific knowledge retrieval."""
    print_header("Demo 2: NPC-Specific Knowledge")
    
    lore = LoreSystem()
    
    # What does Thorne know?
    print("NPC: Thorne (Blacksmith)")
    print("Query: 'Tell me about dwarves and iron'")
    
    thorne_lore = lore.search(
        "dwarves and iron",
        n_results=3,
        known_by="Thorne"
    )
    
    print("\n📜 Knowledge Thorne has access to:")
    for entry, score in thorne_lore:
        print(f"   - {entry.title}: {entry.content[:100]}...")
    
    # What does Zephyr know?
    print("\n" + "-"*40)
    print("\nNPC: Zephyr (Wizard)")
    print("Query: 'ancient magic and spells'")
    
    zephyr_lore = lore.search(
        "ancient magic and spells",
        n_results=3,
        known_by="Zephyr"
    )
    
    print("\n📜 Knowledge Zephyr has access to:")
    for entry, score in zephyr_lore:
        print(f"   - {entry.title}: {entry.content[:100]}...")


def demo_context_injection():
    """Demo lore context injection for prompts."""
    print_header("Demo 3: Context Injection for NPCs")
    
    lore = LoreSystem()
    
    # Generate context for Thorne
    print("Player asks Thorne: 'Do you know anything about the war?'")
    
    context = lore.get_context_for_npc(
        npc_name="Thorne",
        query="war history battles",
        max_tokens=300
    )
    
    print("\n📝 Generated context for Thorne's prompt:")
    print(context)
    
    # Generate context for Zephyr
    print("\n" + "-"*40)
    print("\nPlayer asks Zephyr: 'What do you know about dragons?'")
    
    context = lore.get_context_for_npc(
        npc_name="Zephyr",
        query="dragons dragonriders ancient",
        max_tokens=300
    )
    
    print("\n📝 Generated context for Zephyr's prompt:")
    print(context)


def demo_adding_lore():
    """Demo adding custom lore entries."""
    print_header("Demo 4: Adding Custom Lore")
    
    lore = LoreSystem()
    
    print("Adding new lore entry: 'The Lost Treasure of King Aldric'")
    
    entry = lore.add_lore(
        id="lost_treasure",
        title="The Lost Treasure of King Aldric",
        content="When King Aldric fell during the Great War, his legendary treasure hoard was never found. Rumors place it somewhere in the Scarred Wastes, protected by ancient magic. The treasure is said to include the Crown of Command and the Scepter of Elements.",
        category="legends",
        known_by=["Zephyr", "historians", "treasure hunters"],
        importance=0.8,
        tags=["treasure", "king", "artifact", "legend"]
    )
    
    print(f"\n✅ Added: {entry.title}")
    print(f"   Category: {entry.category}")
    print(f"   Known by: {', '.join(entry.known_by)}")
    
    # Search for the new entry
    print("\nSearching for: 'treasure and artifacts'")
    results = lore.search("treasure and artifacts", n_results=3)
    
    for e, score in results:
        print(f"\n📄 {e.title} (relevance: {score:.2f})")


def demo_statistics():
    """Demo lore database statistics."""
    print_header("Demo 5: Lore Database Statistics")
    
    lore = LoreSystem()
    stats = lore.get_stats()
    
    print(f"📊 Total Entries: {stats['total_entries']}")
    print(f"\n📁 By Category:")
    for cat, count in stats['categories'].items():
        print(f"   - {cat}: {count}")
    
    print(f"\n👥 Knowledge Distribution:")
    for knower, count in stats['known_by_counts'].items():
        print(f"   - {knower}: {count} entries")


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           NPC Dialogue System - Lore Demo                 ║
║                                                           ║
║   Demonstrates RAG-based knowledge retrieval for NPCs     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    try:
        demo_basic_search()
        demo_npc_context()
        demo_context_injection()
        demo_adding_lore()
        demo_statistics()
        
        print_header("Demo Complete!")
        print("The lore system can be integrated with NPCs to provide")
        print("contextual knowledge during conversations.")
        print("\nTo use in your game:")
        print("  1. Create lore entries in lore_templates/")
        print("  2. Use lore.get_context_for_npc() in NPC prompts")
        print("  3. Each NPC will only know relevant lore")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
