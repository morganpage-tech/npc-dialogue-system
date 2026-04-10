#!/usr/bin/env python3
"""
Demo: Streaming Responses for NPC Dialogue
Shows real-time token-by-token dialogue generation
"""

import sys
import time
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def demo_streaming_cli():
    """Demo streaming in CLI using requests."""
    import requests
    
    print_header("Demo: Streaming Dialogue via API")
    
    # API endpoint
    api_url = "http://localhost:8000/api/dialogue/generate/stream"
    
    # Request payload
    payload = {
        "npc_name": "Thorne",
        "player_input": "Tell me about your blacksmith work",
        "player_id": "player"
    }
    
    print(f"Player: {payload['player_input']}")
    print(f"NPC ({payload['npc_name']}): ", end="", flush=True)
    
    try:
        # Make streaming request
        with requests.post(api_url, json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()
            
            # Process SSE events
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            
                            # Print token
                            if "token" in data:
                                print(data["token"], end="", flush=True)
                            
                            # Check if done
                            if data.get("done"):
                                print()  # Newline
                                print(f"\n✅ Generation complete ({len(data.get('full_response', ''))} chars)")
                                
                        except json.JSONDecodeError:
                            pass
                            
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server. Start it with: python api_server.py")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


def demo_direct_streaming():
    """Demo streaming directly via Ollama."""
    import requests
    
    print_header("Demo: Direct Ollama Streaming")
    
    # Ollama API endpoint
    api_url = "http://localhost:11434/api/chat"
    
    # Simple prompt
    payload = {
        "model": "llama3.2:1b",
        "messages": [
            {"role": "system", "content": "You are Thorne, a gruff but friendly blacksmith. Be brief."},
            {"role": "user", "content": "Hello!"}
        ],
        "stream": True,
        "options": {
            "temperature": 0.8,
            "num_predict": 100
        }
    }
    
    print("Player: Hello!")
    print("NPC (Thorne): ", end="", flush=True)
    
    try:
        with requests.post(api_url, json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()
            
            full_response = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    
                    if 'message' in data:
                        token = data['message'].get('content', '')
                        if token:
                            full_response += token
                            print(token, end="", flush=True)
                    
                    if data.get('done', False):
                        print()
                        print(f"\n✅ Generated {len(full_response)} characters")
                        break
                        
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to Ollama. Start it with: ollama serve")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


def demo_streaming_with_timing():
    """Demo streaming with timing information."""
    import requests
    
    print_header("Demo: Streaming with Timing")
    
    api_url = "http://localhost:11434/api/chat"
    
    payload = {
        "model": "llama3.2:1b",
        "messages": [
            {"role": "system", "content": "You are Zephyr, a wise wizard. Speak mysteriously but briefly."},
            {"role": "user", "content": "What do you know about dragons?"}
        ],
        "stream": True,
        "options": {
            "temperature": 0.9,
            "num_predict": 150
        }
    }
    
    print("Player: What do you know about dragons?")
    print("NPC (Zephyr): ", end="", flush=True)
    
    start_time = time.time()
    token_count = 0
    first_token_time = None
    
    try:
        with requests.post(api_url, json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    
                    if 'message' in data:
                        token = data['message'].get('content', '')
                        if token:
                            if first_token_time is None:
                                first_token_time = time.time()
                            
                            token_count += 1
                            print(token, end="", flush=True)
                    
                    if data.get('done', False):
                        elapsed = time.time() - start_time
                        tps = token_count / elapsed if elapsed > 0 else 0
                        first_latency = (first_token_time - start_time) * 1000 if first_token_time else 0
                        
                        print()
                        print(f"\n📊 Stats:")
                        print(f"   First token: {first_latency:.0f}ms")
                        print(f"   Total time: {elapsed:.2f}s")
                        print(f"   Tokens: {token_count}")
                        print(f"   Speed: {tps:.1f} tokens/sec")
                        break
                        
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to Ollama. Start it with: ollama serve")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           NPC Dialogue System - Streaming Demo            ║
║                                                           ║
║   Demonstrates real-time token-by-token responses         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Prerequisites:
- Ollama running (ollama serve)
- API server running (python api_server.py) for API demo

""")
    
    print("Select demo:")
    print("1. Streaming via API Server (SSE)")
    print("2. Direct Ollama Streaming")
    print("3. Streaming with Timing Info")
    print("4. Run all demos")
    print()
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        return demo_streaming_cli()
    elif choice == "2":
        return demo_direct_streaming()
    elif choice == "3":
        return demo_streaming_with_timing()
    elif choice == "4":
        result = demo_direct_streaming()
        if result == 0:
            result = demo_streaming_with_timing()
        return result
    else:
        print("Invalid choice")
        return 1


if __name__ == "__main__":
    sys.exit(main())
