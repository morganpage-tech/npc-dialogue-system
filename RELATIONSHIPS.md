# Relationship Tracking System

A comprehensive system for tracking player-NPC relationships in your game. NPCs remember player actions and respond differently based on trust, friendship, or enmity.

## Features

- Score-based relationships (-100 to +100)
- Six relationship levels with distinct behaviors
- Dynamic NPC personality based on relationship
- Quest completion tracking
- Gift giving mechanics
- Dialogue choice impact
- Faction support
- Time-based decay (optional)
- Full save/load persistence

## Relationship Levels

| Level | Score Range | NPC Behavior |
|-------|-------------|--------------|
| **Hated** | -100 to -50 | Hostile, dismissive, refuses help |
| **Disliked** | -50 to -20 | Suspicious, reluctant, overcharges |
| **Neutral** | -20 to 20 | Polite but distant, standard prices |
| **Liked** | 20 to 50 | Friendly, helpful, warm greetings |
| **Loved** | 50 to 80 | Very warm, shares secrets, special treatment |
| **Adored** | 80 to 100 | Deeply loyal, shares everything, unwavering support |

## Quick Start

### Basic Usage

```python
from npc_dialogue import NPCDialogue, NPCManager
from relationship_tracking import RelationshipTracker

# Create a relationship tracker
tracker = RelationshipTracker(player_id="hero_001")

# Create an NPC with relationship tracking
npc = NPCDialogue(
    character_name="Thorne",
    character_card_path="character_cards/blacksmith.json",
    model="llama3.2:1b",
    relationship_tracker=tracker
)

# Have a conversation
response = npc.generate_response("Can you fix my sword?")
print(f"Thorne: {response}")
print(f"Relationship: {npc.get_relationship_score()} ({npc.get_relationship_level()})")
```

### Updating Relationships

```python
# Complete a quest for the NPC
npc.update_from_quest("repair_anvil", success=True, reward=15.0)
# Thorne relationship: +15.0 (completed quest: repair_anvil)

# Give a gift
npc.update_from_gift("rare_iron_ore", value=10.0)
# Thorne relationship: +10.0 (gave gift: rare_iron_ore)

# Friendly dialogue choice
npc.update_from_dialogue("friendly")
# Thorne relationship: +2.0 (dialogue: friendly)

# Hostile dialogue choice
npc.update_from_dialogue("insult")
# Thorne relationship: -10.0 (dialogue: insult)
```

### Using with NPCManager

```python
# Create a manager with shared relationship tracking
tracker = RelationshipTracker(player_id="player_123")
manager = NPCManager(model="llama3.2:1b", relationship_tracker=tracker)

# Load multiple characters
manager.load_character("character_cards/blacksmith.json")
manager.load_character("character_cards/merchant.json")
manager.load_character("character_cards/wizard.json")

# Each NPC maintains separate relationships with the same player
thorne = manager.npcs["Thorne"]
elara = manager.npcs["Elara"]
zephyr = manager.npcs["Zephyr"]

# Update relationships independently
thorne.update_from_quest("forge_weapon", success=True, reward=20.0)
elara.update_from_gift("gold_coins", value=5.0)

# Save all relationships at once
manager.save_relationships()

# Load them back later
manager.load_relationships()

# View summary
manager.print_relationship_summary()
```

## Advanced Features

### Temperature Adjustment

NPC personality consistency changes based on relationship:

```python
# Good relationship = more consistent (lower temperature)
# Bad relationship = more unpredictable (higher temperature)

# Base temperature: 0.8
# Relationship score: +50 → Adjusted temperature: ~0.55 (more consistent)
# Relationship score: -50 → Adjusted temperature: ~1.05 (more volatile)
```

### Speaking Style Modifiers

The system automatically modifies the system prompt based on relationship level:

**Hated:**
```
You despise this player. Be hostile, dismissive, and short. 
Refuse to help if possible.
```

**Neutral:**
```
Treat this player as a stranger. Be polite but distant.
```

**Loved:**
```
You consider this player a friend. Be very warm, 
share personal stories, and go out of your way to help.
```

### Faction Support

Relationships can extend to entire factions:

```python
# Update faction relationship
tracker.update_faction("Merchants Guild", 10.0, "helped merchant")
# Merchants Guild faction: +10.0 (helped merchant)

# NPCs from this faction get a bonus
npc_faction_bonus = tracker.get_npc_faction_bonus("Thorne", "Merchants Guild")
# Returns: 3.0 (30% of faction score)

# This bonus affects how warmly NPCs treat you
# even before personal relationships are established
```

### Time Decay

Enable optional relationship decay:

```python
# Create tracker with time decay enabled
tracker = RelationshipTracker(
    player_id="player_001",
    enable_time_decay=True
)

# Relationships decay by 1% per day if not maintained
# Decay happens automatically when loading saves or calling apply_time_decay()
tracker.apply_time_decay()
```

### Custom Sentiment Values

For fine-grained dialogue control:

```python
# Use predefined dialogue types
npc.update_from_dialogue("flirt")      # +3.0
npc.update_from_dialogue("compliment")  # +2.0
npc.update_from_dialogue("rude")        # -4.0

# Or use custom sentiment values (-1.0 to 1.0)
npc.update_from_dialogue("custom", sentiment=0.5)  # Slight positive
npc.update_from_dialogue("custom", sentiment=-0.8) # Strong negative
```

### Gift Preferences

Character cards can define gift preferences:

```json
{
  "gift_preferences": {
    "loves": ["rare_iron_ore", "ancient_blueprints"],
    "likes": ["quality_iron", "coal"],
    "neutral": ["gold_coins", "weapons"],
    "dislikes": ["rusty_scrap"],
    "hates": ["stolen_goods"]
  }
}
```

Gifts matching preferences could have multipliers:
- Loved items: ×2 value
- Liked items: ×1.5 value
- Neutral items: ×1.0 value
- Disliked items: ×0.5 value
- Hated items: ×0.1 value

## Persistence

### Saving Relationships

```python
# Automatic filename (saves/<player_id>_relationships.json)
tracker.save()

# Custom filename
tracker.save("saves/hero_save1.json")
```

Save file format:
```json
{
  "player_id": "hero_001",
  "enable_time_decay": false,
  "relationships": {
    "Thorne": {
      "score": 45.0,
      "last_updated": 1712509200.0,
      "interaction_count": 15,
      "quests_completed": ["repair_anvil", "forge_weapon"],
      "gifts_given": ["rare_iron_ore"]
    }
  },
  "factions": {
    "Merchants Guild": 25.0,
    "Circle of Mages": 10.0
  },
  "saved_at": 1712595600.0
}
```

### Loading Relationships

```python
# Load automatically applies time decay if enabled
tracker.load()

# Load specific save
tracker.load("saves/hero_save1.json")

# Refresh all NPC temperatures after loading
manager.load_relationships()
```

## Querying Relationships

### Check Specific Conditions

```python
# Get all NPCs with score > 50
friendly_npcs = tracker.get_npc_for_condition("> 50")
# Returns: ["Thorne", "Elara"]

# Get all disliked NPCs
unfriendly_npcs = tracker.get_npc_for_condition("< -20")
# Returns: ["Zephyr"]

# Get all loved NPCs
loved_npcs = tracker.get_npc_for_condition(">= LOVED")
# Returns: ["Elara"]
```

### Get Detailed Summary

```python
summary = tracker.get_summary()

# Returns:
{
  "player_id": "hero_001",
  "npcs": {
    "Thorne": {
      "score": 45.0,
      "level": "LIKED",
      "interactions": 15,
      "quests": 2,
      "gifts": 1
    },
    "Elara": {
      "score": 85.0,
      "level": "ADORED",
      "interactions": 30,
      "quests": 5,
      "gifts": 3
    }
  },
  "factions": {
    "Merchants Guild": 25.0,
    "Traders Alliance": 40.0
  }
}
```

## Character Card Integration

Relationship-aware character cards include additional fields:

```json
{
  "name": "Thorne",
  "description": "A gruff but skilled blacksmith...",
  "personality": "Grumpy, skeptical...",
  "speaking_style": "Short, direct sentences...",
  "first_mes": "Hmph. Another customer...",
  
  "relationships": {
    "hated_dialogue": "I don't work for your kind.",
    "disliked_dialogue": "I can help you, but it'll cost extra.",
    "neutral_dialogue": "Show me your weapon or describe what you need.",
    "liked_dialogue": "Ah, you again. Good to see someone who appreciates proper craftsmanship.",
    "loved_dialogue": "Welcome, friend! I've been saving special iron for you.",
    "adored_dialogue": "My best customer! I've been experimenting with a new forging technique."
  },
  
  "gift_preferences": {
    "loves": ["rare ores", "ancient blueprints"],
    "likes": ["quality iron", "coal"],
    "neutral": ["gold coins", "weapons"],
    "dislikes": ["rusty scrap"],
    "hates": ["stolen goods"]
  },
  
  "faction": "Merchants Guild"
}
```

## Game Integration Patterns

### Quest System Integration

```python
def complete_quest(quest_id, npc_name, success=True):
    # Quest rewards
    gold_reward = 100 if success else 20
    
    # Update NPC relationship
    npc = manager.npcs[npc_name]
    relationship_change = npc.update_from_quest(quest_id, success, reward=15.0)
    
    # Quest-specific dialogue based on relationship
    if relationship_change > 10:
        return npc.generate_response(
            f"I'm impressed! Quest '{quest_id}' completed perfectly."
        )
    elif success:
        return npc.generate_response(
            f"Quest '{quest_id}' done. Here's your {gold_reward} gold."
        )
    else:
        return npc.generate_response(
            f"You failed quest '{quest_id}'. Better luck next time."
        )
```

### Shop System Integration

```python
def shop_with_npc(npc_name, item):
    npc = manager.npcs[npc_name]
    relationship = npc.get_relationship_score()
    
    # Calculate price based on relationship
    base_price = item['price']
    
    if relationship < -20:
        # Disliked: 150% price
        price = base_price * 1.5
    elif relationship < 20:
        # Neutral: 100% price
        price = base_price
    elif relationship < 50:
        # Liked: 90% price
        price = base_price * 0.9
    elif relationship < 80:
        # Loved: 80% price
        price = base_price * 0.8
    else:
        # Adored: 70% price
        price = base_price * 0.7
    
    return npc.generate_response(
        f"That {item['name']} will cost you {int(price)} gold."
    )
```

### Dialogue Choice System

```python
def handle_dialogue_choice(npc_name, choice_data):
    npc = manager.npcs[npc_name]
    
    # Update relationship based on choice
    dialogue_type = choice_data.get('type')
    sentiment = choice_data.get('sentiment', 0.0)
    npc.update_from_dialogue(dialogue_type, sentiment)
    
    # Refresh NPC temperature for next response
    npc.refresh_temperature()
    
    # Generate relationship-aware response
    response = npc.generate_response(choice_data['message'])
    
    return {
        "response": response,
        "relationship_score": npc.get_relationship_score(),
        "relationship_level": npc.get_relationship_level()
    }
```

## Best Practices

1. **Start Neutral**: Always begin relationships at 0 (neutral) unless story requires otherwise
2. **Meaningful Changes**: Use significant changes (±5-20) for major events, small changes (±1-3) for dialogue
3. **Clamp Scores**: The system automatically clamps to -100/+100, but design rewards accordingly
4. **Track Progression**: Consider relationship level when unlocking content:
   - Liked (20+): Unlock special dialogue options
   - Loved (50+): Access to exclusive items/quests
   - Adored (80+): Character-specific storyline/quests
5. **Faction First**: Establish faction relationships early, then build individual connections
6. **Gift Economy**: Make gifts meaningful but not game-breaking
7. **Consequences**: Ensure negative relationships have real gameplay impact (refusals, higher prices, combat)

## Troubleshooting

**NPC not responding to relationship changes:**
```python
# Ensure temperature is refreshed after relationship updates
npc.update_from_quest("example_quest", success=True)
npc.refresh_temperature()  # Important!
```

**Relationship scores not persisting:**
```python
# Always save relationships to disk
tracker.save()

# Or use NPCManager for batch operations
manager.save_relationships()
```

**NPC dialogue seems generic:**
```python
# Check that relationship_tracker is properly initialized
if npc.relationship_tracker is None:
    print("Warning: No relationship tracker - NPC won't remember player")

# Verify character card has relationship fields
print(npc.character_card.get('relationships', {}))
```

## API Reference

See `relationship_tracking.py` for full API documentation. Key classes:

- `RelationshipTracker`: Main relationship management class
- `RelationshipLevel`: Enum of relationship levels
- `RelationshipState`: Dataclass for NPC relationship state

## Examples

See `demo_relationships.py` for a complete working example demonstrating:
- Multiple NPCs with relationship tracking
- Quest completion rewards
- Gift giving mechanics
- Dialogue choice impact
- Faction support
- Save/load persistence
- Time decay

## License

MIT License - See LICENSE file for details.
