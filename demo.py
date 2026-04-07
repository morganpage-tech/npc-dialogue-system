#!/usr/bin/env python3
"""
Demo Script - Showcases NPC Dialogue System
Run this to see the system in action automatically
"""

import time
from npc_dialogue import NPCDialogue


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


def run_thorne_demo():
    """Demo conversation with Thorne the Blacksmith."""
    print_section("THORNE THE BLACKSMITH")
    
    npc = NPCDialogue(
        character_name="Thorne",
        character_card_path="character_cards/blacksmith.json",
        model="llama3.2:1b",
        temperature=0.8
    )
    
    # Print first message
    first_mes = npc.character_card.get('first_mes', '')
    print_npc_message("Thorne", first_mes)
    time.sleep(1)
    
    # Simulated conversation
    conversation = [
        "Can you fix my sword?",
        "How much will it cost?",
        "Can you also make me a shield?",
        "Thank you, Thorne!"
    ]
    
    for user_input in conversation:
        print_user_message(user_input)
        
        print(f"🤖 Thorne is thinking...", end="", flush=True)
        response = npc.generate_response(user_input, show_thinking=True)
        
        print_npc_message("Thorne", response)
        time.sleep(2)
    
    # Show stats
    stats = npc.get_stats()
    print(f"\n📊 Conversation Stats:")
    print(f"   Turns: {stats['turns']}")
    print(f"   NPC words: {stats['npc_words']}")
    
    return npc


def run_elara_demo():
    """Demo conversation with Elara the Merchant."""
    print_section("ELARA THE MERCHANT")
    
    npc = NPCDialogue(
        character_name="Elara",
        character_card_path="character_cards/merchant.json",
        model="llama3.2:1b",
        temperature=0.8
    )
    
    # Print first message
    first_mes = npc.character_card.get('first_mes', '')
    print_npc_message("Elara", first_mes)
    time.sleep(1)
    
    # Simulated conversation
    conversation = [
        "Do you have any healing potions?",
        "That's expensive! Can you give me a discount?",
        "What about this sword I found?",
        "I'll take the potions!"
    ]
    
    for user_input in conversation:
        print_user_message(user_input)
        
        print(f"🤖 Elara is thinking...", end="", flush=True)
        response = npc.generate_response(user_input, show_thinking=True)
        
        print_npc_message("Elara", response)
        time.sleep(2)
    
    # Show stats
    stats = npc.get_stats()
    print(f"\n📊 Conversation Stats:")
    print(f"   Turns: {stats['turns']}")
    print(f"   NPC words: {stats['npc_words']}")
    
    return npc


def run_zephyr_demo():
    """Demo conversation with Zephyr the Wizard."""
    print_section("ZEPHYR THE WIZARD")
    
    npc = NPCDialogue(
        character_name="Zephyr",
        character_card_path="character_cards/wizard.json",
        model="llama3.2:1b",
        temperature=0.8
    )
    
    # Print first message
    first_mes = npc.character_card.get('first_mes', '')
    print_npc_message("Zephyr", first_mes)
    time.sleep(1)
    
    # Simulated conversation
    conversation = [
        "I need help with a cursed item.",
        "Can you fix it?",
        "What kind of magic is this?",
        "Thank you for your help, Zephyr!"
    ]
    
    for user_input in conversation:
        print_user_message(user_input)
        
        print(f"🤖 Zephyr is thinking...", end="", flush=True)
        response = npc.generate_response(user_input, show_thinking=True)
        
        print_npc_message("Zephyr", response)
        time.sleep(2)
    
    # Show stats
    stats = npc.get_stats()
    print(f"\n📊 Conversation Stats:")
    print(f"   Turns: {stats['turns']}")
    print(f"   NPC words: {stats['npc_words']}")
    
    return npc


def main():
    """Run the full demo."""
    print("\n" + "="*60)
    print("  🎮 NPC DIALOGUE SYSTEM - AUTOMATED DEMO")
    print("  Showing AI-powered conversations with three characters")
    print("="*60)
    
    try:
        # Run Thorne demo
        run_thorne_demo()
        
        print("\n⏸️  Press Enter to continue to next character, or Ctrl+C to exit...")
        input()
        
        # Run Elara demo
        run_elara_demo()
        
        print("\n⏸️  Press Enter to continue to next character, or Ctrl+C to exit...")
        input()
        
        # Run Zephyr demo
        run_zephyr_demo()
        
        # Final summary
        print_section("DEMO COMPLETE")
        print("\n✅ All three characters demonstrated!")
        print("\n📚 What you saw:")
        print("   • Distinct personalities for each NPC")
        print("   • In-character responses every time")
        print("   • Natural, engaging dialogue")
        print("   • Fast local inference (no cloud!)")
        print("\n🚀 Try it yourself:")
        print("   python3 main.py")
        print("\n📖 Read the documentation:")
        print("   README.md - Full guide")
        print("   QUICKSTART.md - 5-minute setup")
        print("   INTEGRATION_GUIDE.md - Game engine examples")
        print("\n" + "="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n👋 Demo stopped. Thanks for watching!\n")


if __name__ == "__main__":
    main()
