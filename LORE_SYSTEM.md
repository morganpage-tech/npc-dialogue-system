# Lore System Documentation

The Lore System provides RAG (Retrieval Augmented Generation) capabilities for NPCs, enabling them to reference game world knowledge during conversations.

## Overview

### What is RAG?

RAG combines information retrieval with text generation. When an NPC needs to respond to a player:

1. **Query** - The player's question is analyzed
2. **Retrieve** - Relevant lore is found in the knowledge base
3. **Augment** - The lore is injected into the NPC's context
4. **Generate** - The LLM generates a response using the lore

### Why Use a Lore System?

- **Consistency** - All NPCs reference the same world facts
- **Depth** - NPCs can discuss history, locations, factions, etc.
- **Control** - You decide what each NPC knows
- **Scalability** - Add new lore without retraining models

## Quick Start

### 1. Install Dependencies

```bash
pip install chromadb sentence-transformers
```

### 2. Create Lore Files

Add JSON files to `lore_templates/`:

```json
{
  "category": "history",
  "entries": [
    {
      "id": "great_war",
      "title": "The Great War",
      "content": "100 years ago, the five kingdoms fought...",
      "known_by": ["everyone"],
      "importance": 0.9,
      "tags": ["war", "history"]
    }
  ]
}
```

### 3. Use in NPC Dialogue

```python
from lore_system import LoreSystem
from npc_dialogue import NPCDialogue

# Initialize lore system
lore = LoreSystem()

# Get context for an NPC
context = lore.get_context_for_npc(
    npc_name="Thorne",
    query="What do you know about the war?",
    max_tokens=300
)

# Include in NPC prompt (handled automatically if integrated)
npc = NPCDialogue(
    character_name="Thorne",
    character_card_path="character_cards/blacksmith.json"
)

# The lore context is automatically injected
response = npc.generate_response("What do you know about the war?")
```

## Lore Entry Structure

Each lore entry has the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `title` | string | Display title |
| `content` | string | The actual lore text |
| `category` | string | Category for filtering |
| `known_by` | list | Who knows this (NPC names, factions, "everyone") |
| `importance` | float | 0-1, affects retrieval priority |
| `tags` | list | Search keywords |
| `metadata` | dict | Additional data (optional) |

### Categories

- `history` - Historical events
- `locations` - Places and geography
- `characters` - People and creatures
- `items` - Objects and artifacts
- `factions` - Organizations and groups
- `events` - Current or recurring events
- `quests` - Quest-related information
- `legends` - Myths and rumors
- `general` - Miscellaneous knowledge

### Known By

The `known_by` field controls knowledge access:

```json
"known_by": ["everyone"]           // Common knowledge
"known_by": ["Thorne"]             // Only Thorne knows
"known_by": ["wizards"]            // Any wizard knows
"known_by": ["Thorne", "Elara"]    // Multiple NPCs
"known_by": ["historians", "nobles"]  // Multiple groups
```

## API Reference

### LoreSystem

```python
lore = LoreSystem(
    persist_directory="lore_database",  # ChromaDB storage
    embedding_model="all-MiniLM-L6-v2"  # Embedding model
)
```

#### Adding Lore

```python
# Single entry
entry = lore.add_lore(
    id="unique_id",
    title="Title",
    content="The lore content...",
    category="history",
    known_by=["everyone"],
    importance=0.8,
    tags=["keyword1", "keyword2"]
)

# Batch add
entries = [
    {"id": "entry1", "title": "...", "content": "..."},
    {"id": "entry2", "title": "...", "content": "..."}
]
lore.add_lore_batch(entries)
```

#### Searching

```python
# Basic search
results = lore.search(
    query="dragons and ancient magic",
    n_results=5
)

# With filters
results = lore.search(
    query="treasure",
    n_results=5,
    category="legends",
    known_by="Zephyr",
    min_importance=0.5
)

# Returns list of (LoreEntry, score) tuples
for entry, score in results:
    print(f"{entry.title}: {score:.2f}")
```

#### NPC Context Generation

```python
# Get formatted context for NPC prompts
context = lore.get_context_for_npc(
    npc_name="Thorne",
    query="What happened during the war?",
    max_tokens=500,
    categories=["history", "characters"]
)
```

#### Data Management

```python
# Get specific entry
entry = lore.get_entry("great_war")

# Get all in category
entries = lore.get_entries_by_category("locations")

# Get what an NPC knows
entries = lore.get_entries_known_by("Thorne")

# Update entry
lore.update_entry("great_war", importance=0.95)

# Delete entry
lore.delete_entry("old_entry")

# Save/load
lore.save_to_file("my_lore.json")
lore.load_from_file("my_lore.json")

# Statistics
stats = lore.get_stats()
```

## Integration with NPCs

### Automatic Integration

The `NPCDialogue` class can automatically use lore:

```python
from lore_system import LoreSystem
from npc_dialogue import NPCDialogue

# Create lore system
lore = LoreSystem()

# Pass to NPC
npc = NPCDialogue(
    character_name="Zephyr",
    character_card_path="character_cards/wizard.json",
    lore_system=lore  # Lore will be auto-injected
)

# Now Zephyr has access to relevant knowledge
response = npc.generate_response(
    "Tell me about the ancient dragons"
)
```

### Manual Integration

For more control:

```python
# Get relevant lore before generation
query = player_input
context = lore.get_context_for_npc(
    npc_name="Thorne",
    query=query,
    known_by="Thorne"
)

# Add to game state
game_state = {
    "lore_context": context,
    "location": "Blacksmith Shop"
}

response = npc.generate_response(
    player_input,
    game_state=game_state
)
```

## Example Lore Files

### World History (`lore_templates/world_history.json`)

```json
{
  "category": "history",
  "entries": [
    {
      "id": "great_war",
      "title": "The Great War",
      "content": "100 years ago, the five kingdoms fought...",
      "known_by": ["everyone"],
      "importance": 0.9
    }
  ]
}
```

### Locations (`lore_templates/locations.json`)

```json
{
  "category": "locations",
  "entries": [
    {
      "id": "ironhold",
      "title": "Ironhold - The Mountain City",
      "content": "A vast dwarven city carved into the mountains...",
      "known_by": ["everyone"],
      "importance": 0.8
    }
  ]
}
```

## Performance Tips

1. **Batch Loading** - Load all lore at startup
2. **Importance Scores** - Set high importance for critical lore
3. **Specific Tags** - Use specific tags for better retrieval
4. **Known By Groups** - Use groups instead of listing every NPC
5. **Entry Length** - Keep entries focused (200-500 words)

## Vector Embeddings

The system uses sentence transformers for semantic search:

- **Model**: `all-MiniLM-L6-v2` (default, ~80MB)
- **Dimensions**: 384
- **Speed**: ~1000 docs/second

To use a different model:

```python
lore = LoreSystem(
    embedding_model="all-mpnet-base-v2"  # Larger, more accurate
)
```

## Fallback Mode

If ChromaDB/sentence-transformers aren't available, the system uses keyword matching:

```python
# Still works without dependencies
lore = LoreSystem()  # Will use in-memory + keyword search
```

## Best Practices

### Organizing Lore

```
lore_templates/
├── world_history.json    # Historical events
├── locations.json        # Places and geography
├── characters.json       # NPCs and important figures
├── factions.json         # Organizations
├── items.json            # Notable objects
└── quests.json           # Quest-related lore
```

### Writing Good Lore

1. **Be Specific** - "The sword was forged in 1245" vs "The sword is old"
2. **Include Context** - Who, what, when, where, why
3. **Use Tags** - Help retrieval with relevant keywords
4. **Set Importance** - Critical lore = 0.8+, minor = 0.3-0.5
5. **Consider Access** - Who should know this?

### NPC Knowledge Design

| NPC Type | Knowledge Access |
|----------|------------------|
| Commoner | "everyone", common locations |
| Merchant | Trade routes, factions, items |
| Guard | Local area, wanted criminals |
| Wizard | Magic, history, ancient lore |
| Noble | Politics, factions, history |
| Traveler | Multiple regions, rumors |

## Troubleshooting

### ChromaDB Errors

```
pip install chromadb --upgrade
```

### Embedding Model Not Found

```
# Download model manually
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Slow Searches

- Reduce `n_results`
- Set `min_importance` threshold
- Use category filtering
- Consider smaller embedding model

## Future Enhancements

- [ ] Quest trigger integration
- [ ] Dynamic lore updates from gameplay
- [ ] Multi-language support
- [ ] Lore versioning for game saves
- [ ] NPC-to-NPC knowledge sharing

## API Endpoints

When using with the API server:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/lore/search` | POST | Search lore |
| `/api/lore/add` | POST | Add lore entry |
| `/api/lore/{id}` | GET | Get specific entry |
| `/api/lore/context/{npc}` | POST | Get NPC context |

---

For more information, see:
- `PROJECT_SUMMARY.md` - Overall project overview
- `UNITY_INTEGRATION.md` - Unity integration guide
- `demo_lore.py` - Working examples
