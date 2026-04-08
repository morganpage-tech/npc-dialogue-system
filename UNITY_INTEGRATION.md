# Unity Integration Guide

This guide explains how to integrate the NPC Dialogue System into Unity games.

## Prerequisites

- Unity 2021.3 or later
- Python 3.9+ installed
- Ollama running locally

## Quick Start

### 1. Start the API Server

```bash
cd ~/npc-dialogue-system
python api_server.py
```

The server will start at `http://localhost:8000`.

### 2. Import Unity Package

Copy the `unity_client/` folder into your Unity project's `Assets/` directory:

```
Assets/
└── NPCDialogue/
    ├── NPCDialogueClient.cs
    ├── NPCCharacter.cs
    ├── DialogueUI.cs
    ├── NPCSceneManager.cs
    ├── RelationshipTracker.cs
    └── Editor/
        └── NPCDialogueWindow.cs
```

### 3. Setup in Unity

1. **Create NPCDialogueClient GameObject**
   - Right-click in Hierarchy → Create Empty
   - Name it "NPCDialogueClient"
   - Add `NPCDialogueClient` component
   - Set Server URL to `http://localhost:8000`

2. **Create an NPC**
   - Create a 3D object (Cube, Sphere, etc.)
   - Add `NPCCharacter` component
   - Set Character Name (e.g., "Thorne")
   - Set Character Card Path (e.g., "blacksmith.json")

3. **Setup Dialogue UI**
   - Create Canvas with Panel
   - Add `DialogueUI` component
   - Link Text elements for NPC name and dialogue
   - Add Input Field for player input
   - Add Send and Close buttons

## Components

### NPCDialogueClient

Main client for API communication. Should be a singleton in your scene.

```csharp
// Get reference
var client = FindObjectOfType<NPCDialogueClient>();

// Check connection
bool connected = await client.CheckConnectionAsync();

// Generate response
var response = await client.GenerateResponseAsync(
    "Thorne",                    // NPC name
    "Can you fix my sword?",     // Player input
    "player",                    // Player ID
    new Dictionary<string, object> {
        { "location", "Blacksmith Shop" },
        { "time", "Evening" }
    }
);

Debug.Log(response.response);
```

### NPCCharacter

Attach to NPC GameObjects for easy interaction.

```csharp
// Get NPC component
var npc = GetComponent<NPCCharacter>();

// Send message (regular)
npc.SendMessage("Hello there!");

// Send message (streaming)
npc.SendMessageStream("Hello!", (token) => {
    dialogueText.text += token;
});

// Update relationship
npc.UpdateRelationship(10, "Saved from goblins");

// Save conversation
npc.SaveHistory();
```

### DialogueUI

Handles dialogue display with typewriter effect.

```csharp
var dialogueUI = FindObjectOfType<DialogueUI>();

// Show dialogue
dialogueUI.Show("Thorne", npcCharacter);

// Append token (for streaming)
dialogueUI.AppendToken("Hello");

// Clear dialogue
dialogueUI.ClearDialogue();
```

### RelationshipTracker

Client-side relationship tracking.

```csharp
var tracker = FindObjectOfType<RelationshipTracker>();

// Get score
int score = tracker.GetScore("Thorne");

// Get level
string level = tracker.GetLevel("Thorne");

// Update from actions
tracker.ProcessDialogue("Thorne", "friendly");      // +3
tracker.ProcessGift("Thorne", "Gold Ring", 10);    // +10
tracker.ProcessQuest("Thorne", "quest_001", true); // +15

// Get color for UI
Color color = RelationshipTracker.GetColorForScore(score);
```

## Streaming Responses

For real-time token-by-token display:

```csharp
// Using NPCCharacter
npc.SendMessageStream("Tell me about the village", (token) => {
    // Called for each token
    dialogueText.text += token;
}, (fullResponse) => {
    // Called when complete
    Debug.Log("Generation complete!");
});

// Using client directly
client.GenerateResponseStream(
    "Thorne",
    "Hello!",
    onToken: (token) => dialogueText.text += token,
    onComplete: (response) => Debug.Log("Done!")
);
```

## Game State Integration

Pass game context for more contextual responses:

```csharp
var gameState = new GameState {
    location = "Village Square",
    timeOfDay = "Night",
    currentQuest = "Find the Lost Sword",
    playerHealth = 75,
    playerGold = 150
};

var response = await client.GenerateWithGameStateAsync(
    "Elara",
    "Have you seen anything strange?",
    gameState
);
```

## Relationships

### Updating Relationships

```csharp
// Direct update
await client.UpdateRelationshipAsync("Thorne", 10, "Saved from bandits");

// Get current relationship
var info = await client.GetRelationshipAsync("Thorne");
Debug.Log($"Relationship: {info.level} ({info.score})");

// Get all relationships
var allRelationships = await client.GetPlayerRelationshipsAsync();
foreach (var kvp in allRelationships) {
    Debug.Log($"{kvp.Key}: {kvp.Value.level}");
}
```

### Relationship Levels

| Level | Score Range | Behavior |
|-------|-------------|----------|
| Hated | -100 to -50 | Hostile, refuses to help |
| Disliked | -50 to -20 | Cold, reluctant |
| Neutral | -20 to 20 | Polite but guarded |
| Liked | 20 to 50 | Friendly, helpful |
| Loved | 50 to 80 | Very supportive, loyal |
| Adored | 80 to 100 | Will do almost anything |

### Factions

NPCs can belong to factions. Actions affecting one NPC can affect their faction:

```csharp
// Set NPC faction (server-side)
await client.PostAsync("/api/factions/set", new {
    npc_name = "Thorne",
    faction = "Merchants Guild"
});
```

## Save/Load

### Conversation History

```csharp
// Save
await client.SaveHistoryAsync("Thorne");

// Load
await client.LoadHistoryAsync("Thorne");
```

### Player Data Export (for Save Games)

```csharp
// Export all player data
var playerData = await client.ExportPlayerDataAsync("player");
string json = JsonUtility.ToJson(playerData);
PlayerPrefs.SetString("NPCData", json);

// Import
string savedJson = PlayerPrefs.GetString("NPCData");
var data = JsonUtility.FromJson<PlayerExportData>(savedJson);
await client.ImportPlayerDataAsync(data);
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Server status |
| `/api/dialogue/generate` | POST | Generate response |
| `/api/dialogue/generate/stream` | POST | Stream response (SSE) |
| `/api/characters` | GET | List characters |
| `/api/characters/load` | POST | Load character |
| `/api/characters/{name}` | GET | Get character info |
| `/api/characters/{name}` | DELETE | Unload character |
| `/api/relationships/{npc}/{player}` | GET | Get relationship |
| `/api/relationships/update` | POST | Update relationship |
| `/api/history/save` | POST | Save history |
| `/api/history/load` | POST | Load history |
| `/api/save-all` | POST | Save all data |
| `/api/export/{player}` | POST | Export player data |
| `/api/import` | POST | Import player data |

## Example Scene Setup

```
Scene Hierarchy:
├── NPCDialogueClient (GameObject + NPCDialogueClient)
├── NPCSceneManager (GameObject + NPCSceneManager)
├── Canvas
│   └── DialoguePanel
│       ├── NPCNameText
│       ├── DialogueText
│       ├── PlayerInputField
│       ├── SendButton
│       └── CloseButton
│       └── (DialogueUI component)
├── Player
│   └── (Player movement script)
└── NPCs
    ├── Thorne (GameObject + NPCCharacter)
    │   └── InteractionTrigger
    ├── Elara (GameObject + NPCCharacter)
    └── Zephyr (GameObject + NPCCharacter)
```

## Performance Tips

1. **Pre-load Characters**: Load NPCs at scene start to avoid delays
2. **Use Streaming**: Better UX than waiting for full response
3. **Cache Relationships**: Store locally for quick UI updates
4. **Auto-save**: Save periodically to avoid data loss
5. **Connection Pooling**: Reuse client instance

## Troubleshooting

### Server Not Found
- Ensure `api_server.py` is running
- Check URL matches (default: `http://localhost:8000`)
- Verify firewall allows local connections

### Characters Not Loading
- Check character cards exist in `character_cards/` directory
- Verify JSON format is correct
- Check console for error messages

### Slow Responses
- Use smaller model (`llama3.2:1b`)
- Reduce `max_tokens` in NPCDialogue
- Close other applications

### Streaming Not Working
- Ensure server has streaming enabled
- Check CORS settings on server
- Verify Unity supports the endpoint

## Editor Tools

Open the NPC Dialogue Manager window:

**Tools → NPC Dialogue → Manager Window**

Features:
- Server connection testing
- Character management
- Dialogue testing
- Settings configuration

## Next Steps

1. Create custom character cards for your game
2. Add lore/knowledge base (RAG)
3. Implement voice synthesis
4. Create visual dialogue system

## Support

- GitHub Issues: https://github.com/morganpage-tech/npc-dialogue-system/issues
- Documentation: See README.md and PROJECT_SUMMARY.md
