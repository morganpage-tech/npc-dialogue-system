#!/usr/bin/env python3
"""
NPC Dialogue System - Interactive Demo
A command-line interface for testing AI-powered NPC conversations
"""

import sys
import os
from npc_dialogue import NPCDialogue, NPCManager


def print_banner():
    """Print a welcome banner."""
    print("\n" + "="*60)
    print("  🎮 LORE-ALIVE NPC DIALOGUE SYSTEM")
    print("  Local LLM-Powered Game Characters")
    print("="*60 + "\n")


def print_help():
    """Print available commands."""
    print("\n📋 COMMANDS:")
    print("  /list          - List all available characters")
    print("  /switch <name> - Switch to a different character")
    print("  /info          - Show current character info")
    print("  /history       - Show conversation statistics")
    print("  /reset         - Clear conversation history")
    print("  /save          - Save conversation to disk")
    print("  /load          - Load saved conversation")
    print("  /quit or /exit - Exit the program")
    print("  /help          - Show this help message")
    print()


def main():
    """Main interactive loop."""
    print_banner()
    
    # Initialize NPC manager
    manager = NPCManager(model="llama3.2:1b")
    
    # Load all available characters
    character_dir = "character_cards"
    if not os.path.exists(character_dir):
        print(f"⚠️  Character cards directory not found: {character_dir}")
        print("   Creating default character cards...")
        create_default_characters()
    
    # Load all characters from directory
    characters_loaded = []
    for filename in os.listdir(character_dir):
        if filename.endswith('.json'):
            path = os.path.join(character_dir, filename)
            npc = manager.load_character(path, player_id="player")
            characters_loaded.append(npc.character_name)
    
    if not characters_loaded:
        print("❌ No character cards found!")
        print("   Add JSON character files to the 'character_cards/' directory")
        return
    
    print(f"✅ Loaded {len(characters_loaded)} characters: {', '.join(characters_loaded)}")
    
    # Set first character as active
    manager.set_active(characters_loaded[0])
    active_npc = manager.get_active()
    
    print(f"\n🎭 Talking to: {active_npc.character_name}")
    print(f"   Type your message and press Enter")
    print(f"   Type /help for commands\n")
    
    # Print first message from character
    first_mes = active_npc.character_card.get('first_mes', '')
    if first_mes:
        print(f"👤 {active_npc.character_name}:")
        print(f"   {first_mes}\n")
    
    # Main conversation loop
    while True:
        try:
            # Get user input
            prompt = f"💬 You ({active_npc.character_name}): "
            user_input = input(prompt).strip()
            
            # Handle commands
            if user_input.startswith('/'):
                command = user_input.lower().split()
                cmd = command[0]
                
                if cmd in ['/quit', '/exit']:
                    print("\n👋 Goodbye!\n")
                    # Auto-save before exit
                    manager.save_all_histories()
                    break
                
                elif cmd == '/help':
                    print_help()
                
                elif cmd == '/list':
                    print(f"\n📜 Available Characters:")
                    for name in manager.list_characters():
                        prefix = "→ " if name == active_npc.character_name else "  "
                        print(f"{prefix}• {name}")
                    print()
                
                elif cmd == '/switch':
                    if len(command) > 1:
                        target = ' '.join(command[1:])
                        if target in manager.npcs:
                            manager.set_active(target)
                            active_npc = manager.get_active()
                            print(f"\n🔄 Switched to: {active_npc.character_name}\n")
                            # Print first message
                            first_mes = active_npc.character_card.get('first_mes', '')
                            if first_mes:
                                print(f"👤 {active_npc.character_name}:")
                                print(f"   {first_mes}\n")
                        else:
                            print(f"❌ Character '{target}' not found")
                    else:
                        print("Usage: /switch <character_name>")
                
                elif cmd == '/info':
                    active_npc.print_character_info()
                
                elif cmd == '/history':
                    stats = active_npc.get_stats()
                    print(f"\n📊 Conversation Statistics:")
                    print(f"   Character: {stats['character']}")
                    print(f"   Model: {stats['model']}")
                    print(f"   Turns: {stats['turns']}")
                    print(f"   NPC words spoken: {stats['npc_words']}")
                    print(f"   History size: {stats['history_size']} messages\n")
                
                elif cmd == '/reset':
                    confirm = input("Clear conversation history? (y/n): ").lower()
                    if confirm == 'y':
                        active_npc.reset_history()
                
                elif cmd == '/save':
                    manager.save_all_histories()
                    print("✅ All conversations saved\n")
                
                elif cmd == '/load':
                    manager.load_all_histories()
                    print("✅ All conversations loaded\n")
                
                else:
                    print(f"❌ Unknown command: {cmd}")
                    print("   Type /help for available commands\n")
                
                continue
            
            # Generate NPC response
            if user_input:
                print(f"🤖 {active_npc.character_name} is thinking...", end="", flush=True)
                
                response = active_npc.generate_response(
                    user_input,
                    show_thinking=True
                )
                
                print(f"👤 {active_npc.character_name}:")
                print(f"   {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Saving conversations...")
            manager.save_all_histories()
            print("✅ Saved. Goodbye!\n")
            break
        
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


def create_default_characters():
    """Create default character cards if they don't exist."""
    os.makedirs("character_cards", exist_ok=True)
    
    # Thorne the Blacksmith
    thorne = {
        "name": "Thorne",
        "description": "A gruff but kind dwarven blacksmith in the village of Ironhold. Weather-beaten face, soot-stained apron, and arms like tree trunks from decades of hammering steel.",
        "personality": "Gruff exterior, warm heart, values craftsmanship, remembers customers and their deeds, uses smithing metaphors, proud of his work, slightly old-fashioned but wise",
        "speaking_style": "Uses colorful metaphors about metalworking, speaks with a rough working-class cadence, occasionally drops dwarven phrases, emphasizes words for effect",
        "first_mes": "*The forge bellows roar as a burly dwarf hammers a glowing blade* 'Ah, another traveler seeking steel! Well, iron doesn't sharpen itself, so what can ol' Thorne forge for ye today?'",
        "mes_example": "<START>\nUser: Can you fix my sword?\nThorne: 'That there sword tells a story, laddy! See these nicks? That's where ye stood yer ground against a goblin! I'll temper it proper-like, but remember: steel needs fire to grow strong, just as a warrior needs trials!'\n\nUser: How much will it cost?\nThorne: '*chuckles* Gold? Nay, yer coin's good enough, but a tale of adventure's worth more to me. Tell me how ye got that dent in yer armor while I work!'"
    }
    
    # Elara the Merchant
    elara = {
        "name": "Elara",
        "description": "A shrewd but fair human merchant who travels between kingdoms. Sharp eyes that miss nothing, nimble fingers that have counted more gold than most see in a lifetime, and a ready smile that can charm a dragon.",
        "personality": "Business-minded but honest, observant, loves a good bargain, remembers faces and names, worldly and well-traveled, has connections everywhere, values fairness over profit (usually)",
        "speaking_style": "Speaks with confidence and polish, uses merchant terminology lightly, quick-witted and occasionally sarcastic, gets excited about rare items, diplomatic but firm",
        "first_mes": "*A woman in fine but practical robes leans against her wagon, examining a gemstone* 'Welcome, traveler! Elara's Emporium of Wonders has everything you need—and some things you didn't know you needed. What catches your eye today?'",
        "mes_example": "<START>\nUser: Do you have any healing potions?\nElara: '*raises an eyebrow* Healing potions? A common request from someone who's seen trouble. I've three vials of Phoenix Tears—best in three kingdoms, harvested from the flaming nests themselves. Fifty gold each, or make it interesting with a story from your travels.'\n\nUser: That's expensive!\nElara: '*smiles knowingly* Quality isn't cheap, my friend. But I see you're counting your coppers carefully. How about this: I give you one vial now, and when you return with payment—or a story worth as much—you tell me what happened out there in the wilds. Deal?'"
    }
    
    # Zephyr the Wizard
    zephyr = {
        "name": "Zephyr",
        "description": "An eccentric elven wizard who lives in a tower that appears and disappears. Robes covered in moving constellations, hair that floats as if underwater, and eyes that see through time itself. Brilliant, scattered, and endlessly curious.",
        "personality": "Brilliant but absent-minded, sees connections others miss, speaks in riddles sometimes but can be direct when needed, fascinated by magic and its consequences, somewhat disconnected from mundane concerns, genuinely cares about the world but shows it oddly",
        "speaking_style": "Uses elevated vocabulary mixed with odd metaphors, pauses in strange places, references magical theory casually, occasionally drifts into tangents, becomes intense when magic is discussed",
        "first_mes": "*A wall of books floats past as you enter. An elf looks up from a levitating crystal, telescopic spectacles sliding down his nose* 'Oh! You found me! Or I found you? Temporal mechanics are so... wibbly today. What brings you to the Tower That Sometimes Is?'",
        "mes_example": "<START>\nUser: I need help with a cursed item.\nZephyr: '*eyes light up, crystal forgotten* A curse? Fascinating! Is it Siphonic entropy, or perhaps Entropy binding? No, let me see—*snatches the item* Ah, beautiful! A minor geas with temporal leakage. It's not harmful, simply... confused about when it should exist. Hand me that moon-phasing chalk and the seventh-dimensional prism!'\n\nUser: Can you fix it?\nZephyr: '*waves hand dismissively* Fix? No, no, no. You don't 'fix' magic, you... renegotiate with it. This poor item is merely displaced in probability. Watch closely—' *begins drawing glowing patterns in the air*"
    }
    
    # Write character files
    import json
    
    characters = [thorne, elara, zephyr]
    for char in characters:
        path = os.path.join("character_cards", f"{char['name'].lower()}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(char, f, indent=2, ensure_ascii=False)
        print(f"   Created: {path}")
    
    print("\n   Default characters created successfully!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
