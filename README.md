# Lore-Alive NPC Dialogue System

A prototype AI-powered NPC dialogue system for games, running locally on M1 MacBook Air.

## Features

- Local LLM inference (no cloud costs or latency)
- Character-specific personalities via system prompts
- Conversation memory (NPCs remember past interactions)
- Swappable character cards (SillyTavern format)
- Simple CLI interface for testing

## Requirements

- macOS with M1/M2/M3 (Apple Silicon)
- 8GB+ RAM recommended
- Python 3.9+
- Ollama

## Quick Start

### 1. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull a model

For 8GB RAM:
```bash
ollama pull llama3.2:1b
```

For 16GB RAM:
```bash
ollama pull llama3.2:3b
```

### 3. Install Python dependencies

```bash
cd ~/npc-dialogue-system
pip install -r requirements.txt
```

### 4. Run the demo

```bash
python main.py
```

## Project Structure

```
npc-dialogue-system/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── main.py                  # Main CLI demo
├── npc_dialogue.py          # Core dialogue system
├── character_cards/         # Character definitions
│   ├── blacksmith.json
│   ├── merchant.json
│   └── wizard.json
└── conversation_history/     # Persistent conversation storage
    └── (auto-created)
```

## Usage Examples

### Basic Conversation

```python
from npc_dialogue import NPCDialogue

# Create an NPC
npc = NPCDialogue(
    character_name="Thorne",
    character_card="character_cards/blacksmith.json",
    model="llama3.2:1b",
    player_id="player_001"
)

# Generate responses
response = npc.generate_response("Can you fix my sword?")
print(response)
```

### Loading Conversation History

```python
# NPC remembers previous conversations
npc.load_history()

# Continue from last interaction
response = npc.generate_response("Remember when we fought the dragon together?")
```

## Character Card Format

Character cards use a JSON format based on SillyTavern's popular format:

```json
{
  "name": "Character Name",
  "description": "Brief character description",
  "personality": "Personality traits, speaking style",
  "first_mes": "Opening greeting message",
  "mes_example": "Example dialogue exchanges",
  "system_prompt": "Custom system instructions"
}
```

## Performance Tips

- **8GB RAM**: Use 1B models, limit context to 2048 tokens
- **16GB RAM**: Use 3B models, 4096 tokens context
- Close browser tabs while running
- Keep laptop plugged in for max performance
- Use smaller models for ambient NPCs, larger for quest-givers

## Next Steps

- Add lore/knowledge base (RAG with ChromaDB)
- Implement relationship tracking system
- Add quest triggers in dialogue
- Create character personality fine-tuning (LoRA)
- Add voice synthesis integration

## License

MIT License - Free for commercial game development
