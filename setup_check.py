#!/usr/bin/env python3
"""
Setup Check Script
Verifies Ollama installation and model availability
"""

import subprocess
import sys
import time


def check_command(command):
    """Check if a command exists."""
    try:
        subprocess.run(
            [command, "--version"],
            capture_output=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_ollama_running():
    """Check if Ollama daemon is running."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def get_installed_models():
    """Get list of installed Ollama models."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return [m['name'] for m in models]
    except Exception:
        pass
    return []


def pull_model(model_name):
    """Pull a model using ollama CLI."""
    print(f"📥 Pulling model: {model_name}")
    print("   This may take a few minutes...")
    
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=False,
            timeout=600
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("   ❌ Pull timed out")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("  🔍 NPC DIALOGUE SYSTEM - SETUP CHECK")
    print("="*60 + "\n")
    
    # Check Python version
    python_version = sys.version_info
    if python_version >= (3, 9):
        print(f"✅ Python: {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"⚠️  Python: {python_version.major}.{python_version.minor}.{python_version.micro}")
        print("   Recommended: Python 3.9 or higher")
    
    print()
    
    # Check Ollama CLI
    print("Checking Ollama CLI...")
    if check_command("ollama"):
        print("✅ Ollama CLI is installed")
        
        # Check if Ollama is running
        print("\nChecking Ollama daemon...")
        if check_ollama_running():
            print("✅ Ollama daemon is running")
            
            # Check installed models
            print("\nInstalled models:")
            models = get_installed_models()
            if models:
                for model in models:
                    print(f"   • {model}")
            else:
                print("   No models found")
        else:
            print("❌ Ollama daemon is not running")
            print("\n📝 To start Ollama:")
            print("   Run: ollama serve")
            print("   (Or open the Ollama app if installed)")
    else:
        print("❌ Ollama CLI is not installed")
        print("\n📝 To install Ollama:")
        print("   curl -fsSL https://ollama.com/install.sh | sh")
    
    print()
    
    # Recommend model based on system
    print("🎮 Recommended Models:")
    print("   For 8GB RAM:  ollama pull llama3.2:1b")
    print("   For 16GB RAM: ollama pull llama3.2:3b")
    print()
    
    # Ask if user wants to pull a model
    if check_command("ollama") and check_ollama_running():
        response = input("Do you want to pull a model now? (y/n): ").lower()
        
        if response == 'y':
            ram = input("How much RAM does your Mac have? (8/16): ").strip()
            
            if ram == '8':
                model = "llama3.2:1b"
            elif ram == '16':
                model = "llama3.2:3b"
            else:
                print("Defaulting to 1B model...")
                model = "llama3.2:1b"
            
            print()
            if pull_model(model):
                print(f"\n✅ Successfully installed: {model}")
                print("\n🎉 Setup complete! Run: python main.py")
            else:
                print(f"\n❌ Failed to install: {model}")
    
    print()


if __name__ == "__main__":
    main()
