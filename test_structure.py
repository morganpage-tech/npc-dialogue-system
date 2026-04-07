#!/usr/bin/env python3
"""
Quick test to verify the project structure and imports work
"""

import os
import sys

def test_project_structure():
    """Verify all files exist and imports work."""
    
    print("🔍 Testing NPC Dialogue System Structure\n")
    print("="*50)
    
    # Check required files
    required_files = [
        "npc_dialogue.py",
        "main.py",
        "setup_check.py",
        "requirements.txt",
        "README.md",
        "QUICKSTART.md"
    ]
    
    print("\n📁 Checking files...")
    all_exist = True
    for f in required_files:
        exists = os.path.exists(f)
        status = "✅" if exists else "❌"
        print(f"   {status} {f}")
        if not exists:
            all_exist = False
    
    # Check imports
    print("\n📦 Checking Python imports...")
    try:
        import json
        print("   ✅ json")
    except ImportError:
        print("   ❌ json")
        all_exist = False
    
    try:
        import requests
        print("   ✅ requests")
    except ImportError:
        print("   ❌ requests (install with: pip install requests)")
        all_exist = False
    
    try:
        from npc_dialogue import NPCDialogue, NPCManager
        print("   ✅ npc_dialogue")
    except Exception as e:
        print(f"   ❌ npc_dialogue: {e}")
        all_exist = False
    
    # Test character card creation
    print("\n🎭 Testing character card system...")
    try:
        import json
        test_char = {
            "name": "TestNPC",
            "description": "A test character",
            "personality": "Test personality",
            "speaking_style": "Normal",
            "first_mes": "Hello!",
            "mes_example": "Example"
        }
        
        # Create directory if needed
        os.makedirs("character_cards", exist_ok=True)
        
        # Write test file
        with open("character_cards/test.json", "w") as f:
            json.dump(test_char, f)
        
        print("   ✅ Can write character cards")
        
        # Read it back
        with open("character_cards/test.json", "r") as f:
            loaded = json.load(f)
        
        assert loaded["name"] == "TestNPC"
        print("   ✅ Can read character cards")
        
        # Clean up
        os.remove("character_cards/test.json")
        print("   ✅ Character card system works")
        
    except Exception as e:
        print(f"   ❌ Character card test failed: {e}")
        all_exist = False
    
    # Summary
    print("\n" + "="*50)
    if all_exist:
        print("✅ All tests passed! System is ready.")
        print("\n📝 Next steps:")
        print("   1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh")
        print("   2. Start Ollama: ollama serve")
        print("   3. Pull a model: ollama pull llama3.2:1b")
        print("   4. Run the demo: python main.py")
    else:
        print("❌ Some tests failed. See errors above.")
    
    print("="*50)
    
    return all_exist


if __name__ == "__main__":
    success = test_project_structure()
    sys.exit(0 if success else 1)
