# 🎮 Integration Guide

This guide shows how to integrate the NPC Dialogue System into your game engine.

---

## Python Integration

### Basic Usage

```python
from npc_dialogue import NPCDialogue, NPCManager

# Initialize manager
npc_manager = NPCManager(model="llama3.2:1b")

# Load characters
npc_manager.load_character("character_cards/blacksmith.json", player_id="player1")
npc_manager.load_character("character_cards/merchant.json", player_id="player1")

# Set active NPC (when player approaches)
npc_manager.set_active("Thorne")
npc = npc_manager.get_active()

# Get dialogue response
user_input = "Can you fix my sword?"
game_state = {
    "location": "Village Forge",
    "time": "Morning",
    "player_reputation": "Trusted"
}

response = npc.generate_response(user_input, game_state=game_state)
print(response)
```

### Game Loop Integration

```python
class GameNPC:
    def __init__(self, character_path):
        self.dialogue = NPCDialogue(
            character_name=self.get_name_from_file(character_path),
            character_card_path=character_path,
            model="llama3.2:1b"
        )
        self.dialogue.load_history()
    
    def on_player_approach(self, player):
        # Play first message
        first_mes = self.dialogue.character_card.get('first_mes', 'Hello!')
        self.display_dialogue(first_mes)
    
    def on_player_speak(self, player, message):
        # Get game state
        game_state = {
            "location": player.location,
            "time": self.get_game_time(),
            "player_reputation": player.get_reputation(self.dialogue.character_name),
            "current_quest": player.active_quest
        }
        
        # Generate response
        response = self.dialogue.generate_response(message, game_state=game_state)
        self.display_dialogue(response)
    
    def on_scene_exit(self, player):
        # Save conversation
        self.dialogue.save_history()
```

---

## Unity Integration

### Method 1: Python Bridge (Recommended)

1. **Install Python for Unity**
   - Use Python.NET or similar bridge
   - Or communicate via HTTP API

2. **Create Python Backend**
   ```python
   # npc_server.py - Run as separate process
   from flask import Flask, request, jsonify
   from npc_dialogue import NPCManager
   
   app = Flask(__name__)
   npc_manager = NPCManager(model="llama3.2:1b")
   npc_manager.load_character("character_cards/blacksmith.json")
   
   @app.route('/dialogue', methods=['POST'])
   def get_dialogue():
       data = request.json
       npc_manager.set_active(data['npc_name'])
       npc = npc_manager.get_active()
       
       response = npc.generate_response(
           data['message'],
           game_state=data.get('game_state', {})
       )
       
       return jsonify({'response': response})
   
   if __name__ == '__main__':
       app.run(port=5000)
   ```

3. **Unity C# Script**
   ```csharp
   using UnityEngine;
   using UnityEngine.Networking;
   
   public class NPCDialogue : MonoBehaviour
   {
       private const string SERVER_URL = "http://localhost:5000/dialogue";
       
       public string npcName = "Thorne";
       public TMPro.TextMeshProUGUI dialogueText;
       
       public async void Speak(string message, GameState gameState)
       {
           var data = new {
               npc_name = npcName,
               message = message,
               game_state = gameState
           };
           
           using (UnityWebRequest req = UnityWebRequest.Post(SERVER_URL, JsonUtility.ToJson(data)))
           {
               await req.SendWebRequest();
               
               if (req.result == UnityWebRequest.Result.Success)
               {
                   var response = JsonUtility.FromJson<DialogueResponse>(req.downloadHandler.text);
                   dialogueText.text = response.response;
               }
           }
       }
   }
   
   [System.Serializable]
   public class DialogueResponse
   {
       public string response;
   }
   ```

### Method 2: Ollama Direct (No Python)

Call Ollama API directly from Unity:

```csharp
public class DirectOllamaDialogue
{
    private const string OLLAMA_URL = "http://localhost:11434/api/chat";
    
    public async System.Threading.Tasks.Task<string> GenerateDialogue(
        string systemPrompt, 
        string userMessage)
    {
        var payload = new {
            model = "llama3.2:1b",
            messages = new[] {
                new { role = "system", content = systemPrompt },
                new { role = "user", content = userMessage }
            },
            stream = false
        };
        
        using (UnityWebRequest req = UnityWebRequest.Post(OLLAMA_URL, JsonUtility.ToJson(payload)))
        {
            req.SetRequestHeader("Content-Type", "application/json");
            await req.SendWebRequest();
            
            if (req.result == UnityWebRequest.Result.Success)
            {
                var response = JsonUtility.FromJson<OllamaResponse>(req.downloadHandler.text);
                return response.message.content;
            }
        }
        
        return "Error generating response";
    }
}
```

---

## Godot Integration

### GDScript with HTTP Request

```gdscript
# NPCDialogue.gd
extends Node3D

@export var character_name := "Thorne"
@export var character_file := "res://character_cards/blacksmith.json"

var dialogue_system
var http_request = HTTPRequest.new()

func _ready():
    # Initialize Python backend or use HTTP directly
    dialogue_system = preload("res://npc_dialogue.gd").new()
    
    # Setup HTTP for direct Ollama calls
    add_child(http_request)
    http_request.request_completed.connect(_on_dialogue_response)

func talk(player_message: String, game_state: Dictionary):
    var system_prompt = load_character_prompt()
    
    var payload = {
        "model": "llama3.2:1b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": player_message}
        ],
        "stream": false
    }
    
    var json = JSON.new().stringify(payload)
    var headers = ["Content-Type: application/json"]
    
    http_request.request(
        "http://localhost:11434/api/chat",
        headers,
        HTTPClient.METHOD_POST,
        json
    )

func _on_dialogue_response(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
    if result == HTTPRequest.RESULT_SUCCESS:
        var json = JSON.new().parse(body.get_string_from_utf8())
        var response_text = json.message.content
        show_dialogue(response_text)
```

---

## Web Integration (JavaScript)

### Browser-based Game

```javascript
class NPCDialogue {
    constructor(characterCard) {
        this.character = characterCard;
        this.history = [];
        this.apiUrl = 'http://localhost:11434/api/chat';
        this.model = 'llama3.2:1b';
    }
    
    async generateResponse(userInput, gameState = {}) {
        const messages = [
            { role: 'system', content: this.buildSystemPrompt() },
            ...this.history,
            { role: 'user', content: userInput }
        ];
        
        const payload = {
            model: this.model,
            messages: messages,
            stream: false
        };
        
        const response = await fetch(this.apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        const npcResponse = data.message.content;
        
        // Update history
        this.history.push(
            { role: 'user', content: userInput },
            { role: 'assistant', content: npcResponse }
        );
        
        return npcResponse;
    }
    
    buildSystemPrompt() {
        return `You are ${this.character.name}. 
        ${this.character.description}
        ${this.character.personality}`;
    }
}

// Usage
const blacksmith = new NPCDialogue(blacksmithCard);
const response = await blacksmith.generateResponse("Can you fix my sword?");
console.log(response);
```

---

## Performance Optimization

### Pre-load Models

```python
# Load all NPCs into memory at game startup
npc_manager = NPCManager()

for character_file in glob("character_cards/*.json"):
    npc_manager.load_character(character_file)

# All NPCs now in memory, fast switching
```

### Batch Requests

```python
# Process multiple NPCs in parallel
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def talk_to_multiple_npcs(npcs, message):
    with ThreadPoolExecutor(max_workers=3) as executor:
        responses = list(executor.map(
            lambda npc: npc.generate_response(message),
            npcs
        ))
    return responses
```

### Streaming Responses

```python
# Show dialogue as it generates
def generate_streaming_response(user_input):
    payload = {
        "model": "llama3.2:1b",
        "messages": self._format_messages(user_input),
        "stream": True
    }
    
    response = requests.post(self.api_url, json=payload, stream=True)
    
    full_response = ""
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'content' in data.get('message', {}):
                content = data['message']['content']
                full_response += content
                yield content  # Yield for display
    
    return full_response

# Usage
for chunk in npc.generate_streaming_response("Hello"):
    display_chunk(chunk)  # Show as it types
```

---

## Saving/Loading Game State

### Save All Conversations

```python
# On game save
def save_game(save_slot):
    npc_manager.save_all_histories(f"saves/{save_slot}/npcs/")
    
    # Save additional game state
    game_state = {
        "player_position": player.position,
        "inventory": player.inventory,
        "quests": quests.active,
        "timestamp": time.time()
    }
    
    with open(f"saves/{save_slot}/gamestate.json", 'w') as f:
        json.dump(game_state, f)
```

### Load All Conversations

```python
# On game load
def load_game(save_slot):
    npc_manager.load_all_histories(f"saves/{save_slot}/npcs/")
    
    with open(f"saves/{save_slot}/gamestate.json", 'r') as f:
        game_state = json.load(f)
    
    player.position = game_state['player_position']
    player.inventory = game_state['inventory']
    # etc.
```

---

## Error Handling

### Graceful Degradation

```python
def safe_dialogue_request(npc, user_input, game_state):
    try:
        response = npc.generate_response(user_input, game_state)
        return response, None
    except requests.ConnectionError:
        # Ollama not running
        fallback = get_fallback_response(npc.character_name)
        return fallback, "LLM_UNAVAILABLE"
    except Exception as e:
        # Other errors
        fallback = get_error_response(npc.character_name)
        return fallback, str(e)

def get_fallback_response(character_name):
    fallbacks = {
        "Thorne": "*busy at forge* Can't talk now, friend!",
        "Elara": "Come back when you have gold to spend!",
        "Zephyr": "Reality is unstable... try again later."
    }
    return fallbacks.get(character_name, "I can't speak right now.")
```

---

## Advanced Features

### Quest Triggers in Dialogue

```python
def check_quest_triggers(npc_response):
    quest_keywords = {
        "sword": "QUEST_FIND_SWORD",
        "dragon": "QUEST_KILL_DRAGON",
        "treasure": "QUEST_FIND_TREASURE"
    }
    
    for keyword, quest_id in quest_keywords.items():
        if keyword.lower() in npc_response.lower():
            if not has_quest(quest_id):
                offer_quest(quest_id)
```

### Relationship Tracking

```python
class RelationshipTracker:
    def __init__(self):
        self.relationships = {}  # {npc_name: score}
    
    def update_relationship(self, npc_name, change):
        if npc_name not in self.relationships:
            self.relationships[npc_name] = 0
        
        self.relationships[npc_name] += change
        
        # Clamp between -100 (hated) and 100 (loved)
        self.relationships[npc_name] = max(-100, min(100, self.relationships[npc_name]))
    
    def get_relationship_level(self, npc_name):
        score = self.relationships.get(npc_name, 0)
        
        if score >= 80:
            return "Adored"
        elif score >= 50:
            return "Loved"
        elif score >= 20:
            return "Liked"
        elif score >= -20:
            return "Neutral"
        elif score >= -50:
            return "Disliked"
        else:
            return "Hated"
```

### Dynamic Personality Adjustment

```python
def adjust_npc_temperature(npc, relationship_score):
    # High relationship = more open/warm
    # Low relationship = more cold/hostile
    
    base_temp = 0.7
    adjustment = relationship_score / 200  # Max ±0.5
    
    npc.temperature = max(0.3, min(1.0, base_temp + adjustment))
    
    # Example:
    # Relationship +80 → temperature 1.1 (capped to 1.0) → warm, friendly
    # Relationship -50 → temperature 0.45 → cold, guarded
```

---

## Production Checklist

### Before Release

- [ ] Test all character cards thoroughly
- [ ] Implement graceful fallback for LLM failures
- [ ] Add conversation save/load for game saves
- [ ] Optimize for target hardware
- [ ] Add content filters if needed
- [ ] Implement relationship tracking
- [ ] Test with multiple simultaneous NPCs
- [ ] Add dialogue caching for common responses
- [ ] Monitor token usage and performance
- [ ] Create character editor tool

### Performance Targets

- **Response time**: <5 seconds for standard dialogue
- **Memory usage**: <3GB per active NPC
- **Concurrent conversations**: 3-5 NPCs simultaneously
- **Save/load time**: <1 second for all NPCs

---

## Troubleshooting

### Common Issues

**Problem**: NPCs don't remember conversations
**Solution**: Call `npc.load_history()` on game load, `npc.save_history()` on game save

**Problem**: Responses break character
**Solution**: Improve system prompt, lower temperature, better character card

**Problem**: Too slow for real-time
**Solution**: Use 1B model, reduce max_tokens, implement streaming

**Problem**: Running out of memory
**Solution**: Load NPCs on-demand, limit history size, use smaller model

---

## Support

- **Documentation**: See README.md and QUICKSTART.md
- **Examples**: Check main.py for full working demo
- **Issues**: Run `python setup_check.py` for diagnostics

---

Happy game building! 🎮✨
