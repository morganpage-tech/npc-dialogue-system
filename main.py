#!/usr/bin/env python3
"""
NPC Dialogue System - Interactive Demo
A command-line interface for testing AI-powered NPC conversations
with natural quest detection and game event simulation.
"""

import sys
import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from npc_dialogue import NPCDialogue, NPCManager
from quest_generator import QuestGenerator, QuestManager, QuestType, ObjectiveType
from quest_extractor import QuestExtractor


def print_banner():
    print("\n" + "="*60)
    print("  🎮 LORE-ALIVE NPC DIALOGUE SYSTEM")
    print("  Local LLM-Powered Game Characters + Natural Quests")
    print("="*60 + "\n")


def print_help():
    print("\n📋 COMMANDS:")
    print("  /list          - List all available characters")
    print("  /switch <name> - Switch to a different character")
    print("  /info          - Show current character info")
    print("  /history       - Show conversation statistics")
    print("  /reset         - Clear conversation history")
    print("  /save          - Save conversation to disk")
    print("  /load          - Load saved conversation")
    print("")
    print("  🗡️  QUEST COMMANDS:")
    print("  /quests        - Show available quests from current NPC")
    print("  /active        - Show active quests + progress")
    print("  /accept <id>   - Accept a quest")
    print("  /turnin [id]   - Complete a quest (auto-detect if one active)")
    print("  /abandon <id>  - Abandon a quest")
    print("")
    print("  🎮 GAME EVENT SIMULATION:")
    print("  /do <action> <target> [amount] - Simulate a gameplay event")
    print(f"    Actions: {', '.join(sorted(set(EVENT_ALIASES.keys())))}")
    print("    Example: /do collect healing_herb")
    print("             /do travel dark_forest")
    print("             /do kill wolf 3")
    print("")
    print("  /quit or /exit - Exit the program")
    print("  /help          - Show this help message")
    print()


EVENT_ALIASES = {
    "collect": ObjectiveType.COLLECT_ITEM,
    "gather": ObjectiveType.COLLECT_ITEM,
    "pickup": ObjectiveType.COLLECT_ITEM,
    "kill": ObjectiveType.KILL_TARGET,
    "defeat": ObjectiveType.KILL_TARGET,
    "reach": ObjectiveType.REACH_LOCATION,
    "travel": ObjectiveType.REACH_LOCATION,
    "go": ObjectiveType.REACH_LOCATION,
    "deliver": ObjectiveType.DELIVER_ITEM,
    "give": ObjectiveType.DELIVER_ITEM,
    "talk": ObjectiveType.TALK_TO_NPC,
    "speak": ObjectiveType.TALK_TO_NPC,
    "escort": ObjectiveType.ESCORT_NPC,
    "boss": ObjectiveType.DEFEAT_BOSS,
}


def format_quest_brief(quest):
    lines = [
        f"  📋 Quest: {quest.name}",
        f"     ID: {quest.id}",
        f"     Type: {quest.quest_type.value}",
        f"     Status: {quest.status.value}",
        f"     {quest.description}",
    ]
    for obj in quest.objectives:
        opt = " (optional)" if obj.optional else ""
        done = "✓" if obj.is_complete() else f"{obj.current}/{obj.required}"
        lines.append(f"     [{done}] {obj.description}{opt}")
    if quest.rewards.gold or quest.rewards.xp:
        lines.append(f"     Reward: {quest.rewards.gold} gold, {quest.rewards.xp} XP")
    if quest.time_limit:
        remaining = quest.get_time_remaining()
        if remaining is not None:
            mins, secs = divmod(remaining, 60)
            lines.append(f"     Time: {mins}:{secs:02d}")
    return "\n".join(lines)


def build_game_state_for_npc(npc_name, quest_manager, quest_extractor):
    game_state = {}

    if quest_manager:
        active = quest_manager.get_active_quests()
        npc_quests = [q for q in active if q.quest_giver == npc_name]
        if npc_quests:
            game_state["active_quests"] = [
                {
                    "name": q.name,
                    "quest_type": q.quest_type.value,
                    "progress": q.progress_percent(),
                    "is_complete": q.is_complete(),
                    "objectives": [o.to_dict() for o in q.objectives],
                }
                for q in npc_quests
            ]

    if quest_extractor:
        pending = quest_extractor.get_pending_quest(npc_name)
        if pending:
            game_state["pending_quest"] = {
                "name": pending.name,
                "description": pending.description,
            }

    return game_state if game_state else None


def main():
    print_banner()

    backend = os.getenv("LLM_BACKEND", "ollama")
    manager = NPCManager(backend=backend)

    print(f"   Backend: {backend}")
    print(f"   Model: {manager.model}\n")

    # Initialize quest system
    quest_manager = QuestManager(save_dir="saves")
    quest_extractor = QuestExtractor(
        model=manager.model,
        backend=backend,
    )
    print("✅ Quest system initialized\n")

    # Load all available characters
    character_dir = "character_cards"
    if not os.path.exists(character_dir):
        print(f"⚠️  Character cards directory not found: {character_dir}")
        print("   Creating default character cards...")
        create_default_characters()

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

    manager.set_active(characters_loaded[0])
    active_npc = manager.get_active()

    print(f"\n🎭 Talking to: {active_npc.character_name}")
    print(f"   Type your message and press Enter")
    print(f"   Type /help for commands\n")

    first_mes = active_npc.character_card.get('first_mes', '')
    if first_mes:
        print(f"👤 {active_npc.character_name}:")
        print(f"   {first_mes}\n")

    while True:
        try:
            prompt = f"💬 You ({active_npc.character_name}): "
            user_input = input(prompt).strip()

            if user_input.startswith('/'):
                command = user_input.split()
                cmd = command[0].lower()

                if cmd in ['/quit', '/exit']:
                    print("\n👋 Goodbye!\n")
                    manager.save_all_histories()
                    quest_manager.save("player")
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
                    quest_manager.save("player")
                    print("✅ All conversations + quests saved\n")

                elif cmd == '/load':
                    manager.load_all_histories()
                    quest_manager.load("player")
                    print("✅ All conversations + quests loaded\n")

                elif cmd == '/quests':
                    npc_name = active_npc.character_name
                    available = quest_manager.get_available_quests(npc_name)
                    pending = quest_extractor.get_pending_quest(npc_name)
                    npc_active = [q for q in quest_manager.get_active_quests() if q.quest_giver == npc_name]
                    has_any = available or pending or npc_active

                    if not has_any:
                        print(f"\n💡 No quests from {npc_name}.")
                        print("   Talk naturally and the NPC may offer quests!\n")
                    else:
                        if available:
                            print(f"\n📜 Available quests from {npc_name}:")
                            for q in available:
                                print(format_quest_brief(q))
                                print()
                        if pending:
                            print(f"⏳ Pending quest from {npc_name}:")
                            print(format_quest_brief(pending))
                            print("   Respond naturally to accept or decline!\n")
                        if npc_active:
                            print(f"🗡️  Active quests from {npc_name}:")
                            for q in npc_active:
                                print(format_quest_brief(q))
                                print()
                            print("   Use /active for all quests, /do to update progress.\n")

                elif cmd == '/active':
                    active_quests = quest_manager.get_active_quests()
                    if not active_quests:
                        print("\n📋 No active quests. Talk to NPCs to find work!\n")
                    else:
                        print(f"\n📋 Active Quests ({len(active_quests)}):")
                        for q in active_quests:
                            print(format_quest_brief(q))
                            print()
                    summary = quest_manager.get_summary()
                    print(f"   Completed: {summary['completed']} | Failed: {summary['failed']}")

                elif cmd == '/accept':
                    if len(command) < 2:
                        print("Usage: /accept <quest_id>")
                    else:
                        quest_id = command[1]
                        accepted = quest_manager.accept_quest(quest_id)
                        if accepted:
                            print(f"\n✅ Quest accepted: {accepted.name}")
                            print(format_quest_brief(accepted))
                            print()
                        else:
                            print(f"❌ Quest '{quest_id}' not found or not available\n")

                elif cmd == '/turnin':
                    quest_id = command[1] if len(command) > 1 else None
                    if quest_id:
                        quest = quest_manager.get_quest(quest_id)
                    else:
                        active_quests = quest_manager.get_active_quests()
                        if len(active_quests) == 1:
                            quest = active_quests[0]
                        elif len(active_quests) == 0:
                            print("No active quests to turn in.\n")
                            continue
                        else:
                            print("Multiple active quests. Specify an ID:")
                            for q in active_quests:
                                print(f"  {q.id} - {q.name}")
                            print()
                            continue

                    if not quest:
                        print(f"❌ Quest not found\n")
                        continue

                    if not quest.is_complete():
                        print(f"❌ '{quest.name}' objectives not complete:")
                        for obj in quest.objectives:
                            if not obj.optional:
                                status = "✓" if obj.is_complete() else f"{obj.current}/{obj.required}"
                                print(f"   [{status}] {obj.description}")
                        print()
                        continue

                    rewards = quest_manager.complete_quest(quest.id)
                    if rewards:
                        print(f"\n🎉 Quest Complete: {quest.name}")
                        print(f"   Gold: {rewards.get('gold', 0)}")
                        print(f"   XP: {rewards.get('xp', 0)}")
                        if rewards.get('items'):
                            print(f"   Items: {', '.join(rewards['items'])}")
                        print()
                    else:
                        print(f"❌ Could not complete quest\n")

                elif cmd == '/abandon':
                    if len(command) < 2:
                        print("Usage: /abandon <quest_id>")
                    else:
                        quest_id = command[1]
                        success = quest_manager.abandon_quest(quest_id)
                        if success:
                            print(f"🗑️  Quest abandoned: {quest_id}\n")
                        else:
                            print(f"❌ Quest '{quest_id}' not found or not active\n")

                elif cmd == '/do':
                    if len(command) < 3:
                        print("Usage: /do <action> <target> [amount]")
                        print(f"Actions: {', '.join(sorted(set(EVENT_ALIASES.keys())))}")
                        print("Example: /do collect healing_herb")
                        print("         /do travel dark_forest")
                        print("         /do kill wolf 3")
                        continue

                    action = command[1].lower()
                    target = command[2]
                    amount = 1
                    for token in command[3:]:
                        try:
                            amount = int(token)
                            break
                        except ValueError:
                            continue

                    obj_type = EVENT_ALIASES.get(action)
                    if not obj_type:
                        print(f"❌ Unknown action: {action}")
                        print(f"   Valid: {', '.join(sorted(set(EVENT_ALIASES.keys())))}\n")
                        continue

                    updates = quest_manager.update_progress(obj_type, target, amount)

                    if updates:
                        print(f"\n🎮 Event: {action} {target} x{amount}")
                        for qid, progress in updates.items():
                            quest = quest_manager.get_quest(qid)
                            if quest:
                                complete = " ✅ COMPLETE!" if quest.is_complete() else ""
                                print(f"   {quest.name}: {progress:.0f}%{complete}")
                        print()
                    else:
                        print(f"   No active quests matched '{action} {target}'\n")

                else:
                    print(f"❌ Unknown command: {cmd}")
                    print("   Type /help for available commands\n")

                continue

            if user_input:
                npc_name = active_npc.character_name

                # --- Quest acceptance/rejection detection ---
                pending = quest_extractor.get_pending_quest(npc_name)
                if pending:
                    action = quest_extractor.detect_acceptance(
                        player_input=user_input,
                        npc_name=npc_name,
                        quest=pending,
                    )
                    if action == "accept":
                        accepted = quest_manager.accept_quest(pending.id)
                        if not accepted:
                            pending.accept()
                            quest_manager.active_quests[pending.id] = pending
                            accepted = pending
                        if accepted:
                            print(f"✅ Quest accepted: {accepted.name}")
                            print(f"   Use /quests to review, /do to update progress, /active for all quests.\n")
                    elif action == "reject":
                        pending.abandon()
                        quest_extractor.clear_pending(npc_name)
                        print(f"🗑️  Quest declined: {pending.name}\n")

                # --- Build game state with quest context ---
                game_state = build_game_state_for_npc(
                    npc_name, quest_manager, quest_extractor
                )

                # --- Generate NPC response ---
                print(f"🤖 {npc_name} is thinking...", end="", flush=True)

                response = active_npc.generate_response(
                    user_input,
                    game_state=game_state,
                    show_thinking=True,
                )

                print(f"👤 {npc_name}:")
                print(f"   {response}\n")

                # --- Quest extraction from NPC response ---
                active = list(quest_manager.active_quests.values())
                extracted = quest_extractor.extract_quest(npc_name, response, active_quests=active)
                if extracted:
                    quest_manager.register_quest(extracted)
                    print(f"📋 Quest detected: {extracted.name}")
                    print(f"   Type: {extracted.quest_type.value}")
                    print(f"   {extracted.description}")
                    for obj in extracted.objectives:
                        print(f"   Objective: {obj.description} ({obj.current}/{obj.required})")
                    print(f"   Respond naturally to accept or decline!\n")

                # --- Auto-update TALK_TO_NPC ---
                quest_manager.update_progress(ObjectiveType.TALK_TO_NPC, npc_name, 1)

                # --- Check for auto-completable quests ---
                for quest in list(quest_manager.active_quests.values()):
                    if quest.quest_giver == npc_name and quest.is_complete():
                        rewards = quest_manager.complete_quest(quest.id)
                        if rewards:
                            print(f"🎉 Quest Complete: {quest.name}")
                            print(f"   Gold: {rewards.get('gold', 0)} | XP: {rewards.get('xp', 0)}")
                            if rewards.get('items'):
                                print(f"   Items: {', '.join(rewards['items'])}")
                            print()

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Saving...")
            manager.save_all_histories()
            quest_manager.save("player")
            print("✅ Saved. Goodbye!\n")
            break

        except Exception as e:
            print(f"\n❌ Error: {e}\n")


def create_default_characters():
    os.makedirs("character_cards", exist_ok=True)

    thorne = {
        "name": "Thorne",
        "archetype": "blacksmith",
        "description": "A gruff but kind dwarven blacksmith in the village of Ironhold. Weather-beaten face, soot-stained apron, and arms like tree trunks from decades of hammering steel.",
        "personality": "Gruff exterior, warm heart, values craftsmanship, remembers customers and their deeds, uses smithing metaphors, proud of his work, slightly old-fashioned but wise",
        "speaking_style": "Uses colorful metaphors about metalworking, speaks with a rough working-class cadence, occasionally drops dwarven phrases, emphasizes words for effect",
        "first_mes": "*The forge bellows roar as a burly dwarf hammers a glowing blade* 'Ah, another traveler seeking steel! Well, iron doesn't sharpen itself, so what can ol' Thorne forge for ye today?'",
        "mes_example": "<START>\nUser: Can you fix my sword?\nThorne: 'That there sword tells a story, laddy! See these nicks? That's where ye stood yer ground against a goblin! I'll temper it proper-like, but remember: steel needs fire to grow strong, just as a warrior needs trials!'\n\nUser: How much will it cost?\nThorne: '*chuckles* Gold? Nay, yer coin's good enough, but a tale of adventure's worth more to me. Tell me how ye got that dent in yer armor while I work!'"
    }

    elara = {
        "name": "Elara",
        "archetype": "merchant",
        "description": "A shrewd but fair human merchant who travels between kingdoms. Sharp eyes that miss nothing, nimble fingers that have counted more gold than most see in a lifetime, and a ready smile that can charm a dragon.",
        "personality": "Business-minded but honest, observant, loves a good bargain, remembers faces and names, worldly and well-traveled, has connections everywhere, values fairness over profit (usually)",
        "speaking_style": "Speaks with confidence and polish, uses merchant terminology lightly, quick-witted and occasionally sarcastic, gets excited about rare items, diplomatic but firm",
        "first_mes": "*A woman in fine but practical robes leans against her wagon, examining a gemstone* 'Welcome, traveler! Elara's Emporium of Wonders has everything you need—and some things you didn't know you needed. What catches your eye today?'",
        "mes_example": "<START>\nUser: Do you have any healing potions?\nElara: '*raises an eyebrow* Healing potions? A common request from someone who's seen trouble. I've three vials of Phoenix Tears—best in three kingdoms, harvested from the flaming nests themselves. Fifty gold each, or make it interesting with a story from your travels.'\n\nUser: That's expensive!\nElara: '*smiles knowingly* Quality isn't cheap, my friend. But I see you're counting your coppers carefully. How about this: I give you one vial now, and when you return with payment—or a story worth as much—you tell me what happened out there in the wilds. Deal?'"
    }

    zephyr = {
        "name": "Zephyr",
        "archetype": "mage",
        "description": "An eccentric elven wizard who lives in a tower that appears and disappears. Robes covered in moving constellations, hair that floats as if underwater, and eyes that see through time itself. Brilliant, scattered, and endlessly curious.",
        "personality": "Brilliant but absent-minded, sees connections others miss, speaks in riddles sometimes but can be direct when needed, fascinated by magic and its consequences, somewhat disconnected from mundane concerns, genuinely cares about the world but shows it oddly",
        "speaking_style": "Uses elevated vocabulary mixed with odd metaphors, pauses in strange places, references magical theory casually, occasionally drifts into tangents, becomes intense when magic is discussed",
        "first_mes": "*A wall of books floats past as you enter. An elf looks up from a levitating crystal, telescopic spectacles sliding down his nose* 'Oh! You found me! Or I found you? Temporal mechanics are so... wibbly today. What brings you to the Tower That Sometimes Is?'",
        "mes_example": "<START>\nUser: I need help with a cursed item.\nZephyr: '*eyes light up, crystal forgotten* A curse? Fascinating! Is it Siphonic entropy, or perhaps Entropy binding? No, let me see—*snatches the item* Ah, beautiful! A minor geas with temporal leakage. It's not harmful, simply... confused about when it should exist. Hand me that moon-phasing chalk and the seventh-dimensional prism!'\n\nUser: Can you fix it?\nZephyr: '*waves hand dismissively* Fix? No, no, no. You don't 'fix' magic, you... renegotiate with it. This poor item is merely displaced in probability. Watch closely—' *begins drawing glowing patterns in the air*"
    }

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
