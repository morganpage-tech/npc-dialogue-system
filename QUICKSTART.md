# Quick Start Guide

## Step 1: Install Ollama

Open Terminal and run:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## Step 2: Start Ollama

```bash
ollama serve
```

*Keep this terminal window open! Ollama needs to stay running.*

## Step 3: Pull a Model

Open a NEW terminal window and run:

**For 8GB RAM:**
```bash
ollama pull llama3.2:1b
```

**For 16GB RAM:**
```bash
ollama pull llama3.2:3b
```

This will download ~1-2GB of data. Takes 2-5 minutes.

## Step 4: Check Setup

```bash
cd ~/npc-dialogue-system
python setup_check.py
```

This will verify everything is installed correctly.

## Step 5: Run the Demo!

```bash
cd ~/npc-dialogue-system
python main.py
```

## Example Session

```
🎮 LORE-ALIVE NPC DIALOGUE SYSTEM
  Local LLM-Powered Game Characters
============================================================

✅ Loaded 3 characters: Thorne, Elara, Zephyr

🎭 Talking to: Thorne
   Type your message and press Enter
   Type /help for commands

👤 Thorne:
   *The forge bellows roar as a burly dwarf hammers a glowing blade* 
   'Ah, another traveler seeking steel! Well, iron doesn't sharpen 
   itself, so what can ol' Thorne forge for ye today?'

💬 You (Thorne): Can you fix my sword?
🤖 Thorne is thinking... ✓ (42 tokens, 3.2s, 13.1 tok/s)
👤 Thorne:
   '*inspects the blade closely* Aye, this sword's seen battle! Edge 
   is dull from too many goblins, I wager. I can sharpen it proper 
   for you, lad, but remember—steel needs fire to grow strong, just 
   as a warrior needs trials! Twenty gold and a tale of how you got 
   these nicks!'

💬 You (Thorne): /switch Elara

🔄 Switched to: Elara

👤 Elara:
   *A woman in fine but practical robes leans against her wagon, 
   examining a gemstone* 'Welcome, traveler! Elara's Emporium of 
   Wonders has everything you need—and some things you didn't know 
   you needed. What catches your eye today?'

💬 You (Elara): Do you have any healing potions?
🤖 Elara is thinking... ✓ (38 tokens, 2.8s, 13.6 tok/s)
👤 Elara:
   '*raises an eyebrow* Healing potions? A common request from 
   someone who's seen trouble. I've three vials of Phoenix 
   Tears—best in three kingdoms! Fifty gold each, or make it 
   interesting with a story from your travels. I've always found 
   stories worth more than coin!'

💬 You (Elara): /quit

👋 Goodbye!
✅ All conversations saved
```

## Common Issues

**Ollama not found:**
- Make sure Ollama is installed
- Try running `which ollama` to verify

**Connection refused:**
- Make sure `ollama serve` is running in a terminal
- Check that port 11434 is not blocked

**Model not found:**
- Run `ollama pull llama3.2:1b` (or 3b)
- Check installed models with `ollama list`

**Slow responses:**
- Close other apps to free RAM
- Try the 1B model instead of 3B
- Make sure laptop is plugged in

## Next Steps

1. **Create your own characters** - Add JSON files to `character_cards/`
2. **Modify the code** - Edit `npc_dialogue.py` to add features
3. **Integrate with a game engine** - Use the NPCDialogue class in Unity, Godot, etc.
4. **Add lore retrieval** - Implement RAG with ChromaDB for world knowledge

## Character Card Format

Create `character_cards/your_npc.json`:

```json
{
  "name": "Your NPC",
  "description": "A brief description of appearance and role",
  "personality": "Traits, quirks, values, fears, desires",
  "speaking_style": "How they talk, accent, vocabulary",
  "first_mes": "Opening greeting when player approaches",
  "mes_example": "Example dialogue showing their voice"
}
```

## Performance Expectations

On M1 MacBook Air (8GB RAM):
- Llama 3.2 1B: 15-30 tokens/second
- Response time: 2-5 seconds for typical dialogue
- Can handle 2-3 simultaneous conversations

On M1 MacBook Air (16GB RAM):
- Llama 3.2 3B: 10-20 tokens/second
- Response time: 3-8 seconds
- Better quality, more nuanced responses
- Can handle 3-5 simultaneous conversations

## Need Help?

- Check Ollama docs: https://ollama.com/docs
- Try the setup checker: `python setup_check.py`
- Review conversation history in `conversation_history/` folder

Happy game building! 🎮
