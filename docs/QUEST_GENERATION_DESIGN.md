# Dynamic Quest Generation System - Design Document

## Overview

This document outlines the design for a procedural quest generation system integrated with the NPC Dialogue System. The system generates contextually appropriate quests based on NPC personality, player relationships, world state, and lore.

**Target Version:** v1.5.0  
**Phase:** 5 (Advanced Features)  
**Status:** Design Phase

---

## Core Philosophy

1. **Context-Driven** - Quests emerge naturally from NPC backgrounds, relationships, and world events
2. **Modular** - Quest templates can be combined and extended
3. **Scalable** - Difficulty adjusts based on player progression
4. **Persistent** - Quest state integrates with save systems
5. **Meaningful** - Every quest has narrative purpose, not just fetch tasks

---

## Quest Types

### 1. Kill/Defeat
Eliminate hostile targets (enemies, monsters, bandits).

```
Template Variables:
- target_type: enemy category
- target_count: number to defeat
- location: spawn area
- reason: narrative justification
- time_limit: optional deadline
```

**Example:** "The wolves in Whisperwood have grown bold. Thin their pack by 5 before they attack the village."

### 2. Fetch/Delivery
Transport items between NPCs or locations.

```
Template Variables:
- item: object to transport
- source: origin location/NPC
- destination: target location/NPC
- urgency: time sensitivity
- fragile: special handling needed
```

**Example:** "Deliver this healing salve to Elder Theron at the northern outpost. He needs it before nightfall."

### 3. Explore/Discover
Investigate locations, find hidden objects, uncover secrets.

```
Template Variables:
- location: area to explore
- objective: what to find/learn
- clues: hints provided
- danger_level: expected encounters
```

**Example:** "Scout the abandoned mines. Rumor speaks of a forgotten dwarven forge in the depths."

### 4. Escort/Protect
Guide NPCs or defend locations/objects.

```
Template Variables:
- escort_target: NPC/object to protect
- route: path to follow
- threats: expected enemies
- duration: time or distance
```

**Example:** "Guard the merchant caravan through Bandit's Pass. They'll pay well for safe passage."

### 5. Collection
Gather specific resources or items.

```
Template Variables:
- resource: item type
- quantity: amount needed
- source_hints: where to find
- purpose: why it's needed
```

**Example:** "I need 10 moonpetals for the ritual. They bloom only in the grove at midnight."

### 6. Dialogue/Information
Gather intelligence, negotiate, or persuade NPCs.

```
Template Variables:
- target_npc: who to contact
- information_needed: what to learn
- method: persuade/charm/intimidate
- relationship_required: minimum affinity
```

**Example:** "Speak with the harbor master. He knows which ship carried the stolen artifacts."

---

## System Architecture

```
quest_generator.py
├── QuestGenerator (main class)
│   ├── generate_quest(npc, player_state, world_state)
│   ├── validate_quest(quest)
│   └── scale_difficulty(quest, player_level)
│
├── QuestTemplate (base class)
│   ├── KillQuest
│   ├── FetchQuest
│   ├── ExploreQuest
│   ├── EscortQuest
│   ├── CollectionQuest
│   └── DialogueQuest
│
├── QuestManager (state management)
│   ├── active_quests: Dict[quest_id, Quest]
│   ├── completed_quests: Set[quest_id]
│   ├── save_state() / load_state()
│   └── check_completion(player_action)
│
└── QuestIntegrator (NPC integration)
    ├── get_available_quests(npc_id)
    ├── quest_dialogue_hooks()
    └── reward_delivery()
```

---

## Quest Properties

Every quest contains these core properties:

```python
@dataclass
class Quest:
    id: str                    # Unique identifier
    name: str                  # Display name
    description: str           # Player-facing description
    quest_giver: str           # NPC who gave the quest
    
    # Objectives
    objectives: List[Objective]
    current_progress: Dict[str, int]
    
    # Rewards
    gold_reward: int
    xp_reward: int
    item_rewards: List[str]
    relationship_bonus: Dict[str, int]  # NPC_id -> affinity change
    
    # Constraints
    time_limit: Optional[int]  # Seconds, None = no limit
    prerequisites: List[str]   # Required quests/items/relationships
    
    # State
    status: QuestStatus  # Available/Active/Completed/Failed
    
    # Metadata
    difficulty: int           # 1-5 scale
    generated_at: datetime
    expires_at: Optional[datetime]
```

---

## NPC Integration

### Quest Availability Logic

```python
def get_available_quests(npc: NPC, player: PlayerState) -> List[Quest]:
    """Determine which quests an NPC can offer."""
    
    available = []
    
    # Check relationship level
    affinity = get_relationship(npc.id, player.id)
    
    # NPC personality affects quest types
    personality = npc.personality
    
    # World state triggers
    world_events = get_active_events()
    
    # Generate based on NPC archetype
    if npc.archetype == "merchant":
        available += generate_fetch_quests(npc, player)
        available += generate_collection_quests(npc, player)
    
    elif npc.archetype == "guard":
        available += generate_kill_quests(npc, player)
        available += generate_escort_quests(npc, player)
    
    elif npc.archetype == "scholar":
        available += generate_explore_quests(npc, player)
        available += generate_dialogue_quests(npc, player)
    
    # Filter by prerequisites
    return [q for q in available if check_prerequisites(q, player)]
```

### Quest Dialogue Hooks

Quests integrate into NPC dialogue naturally:

```python
QUEST_DIALOGUE_PROMPT = """
You are {npc_name}. The player approaches you.

{npc_backstory}

You have a task that needs doing: {quest_description}

Ask if the player would be willing to help. Be in character. 
If they accept, provide any relevant information they need.
If they decline, respond appropriately to your personality.
"""
```

---

## Difficulty Scaling

Quests scale based on player progression:

```python
def scale_quest(quest: Quest, player_level: int) -> Quest:
    """Adjust quest difficulty to player level."""
    
    # Scale enemy counts
    if quest.type == "kill":
        base_count = quest.objectives[0].count
        scaled_count = base_count + (player_level // 3)
        quest.objectives[0].count = min(scaled_count, base_count * 3)
    
    # Scale rewards
    reward_multiplier = 1 + (player_level * 0.1)
    quest.gold_reward = int(quest.gold_reward * reward_multiplier)
    quest.xp_reward = int(quest.xp_reward * reward_multiplier)
    
    # Scale time limits (harder = less time)
    if quest.difficulty >= 4:
        quest.time_limit = int(quest.time_limit * 0.75)
    
    return quest
```

---

## Lore Integration

Quests pull from the lore system for contextual generation:

```python
def generate_contextual_quest(npc: NPC, lore_system: LoreSystem) -> Quest:
    """Generate quest based on world lore."""
    
    # Get relevant lore
    location_lore = lore_system.query(f"locations near {npc.location}")
    faction_tensions = lore_system.query(f"conflicts involving {npc.faction}")
    
    # Generate quest that fits the world
    if "monster" in location_lore:
        return generate_kill_quest(target=location_lore["monster"])
    
    if faction_tensions:
        return generate_escort_quest(reason=faction_tensions)
    
    # Fallback to NPC-specific quests
    return generate_default_quest(npc)
```

---

## Save/Load Integration

Quest state persists with game saves:

```python
# Save format
{
    "active_quests": [
        {
            "id": "quest_001",
            "progress": {"wolves_killed": 3, "wolves_needed": 5},
            "started_at": "2026-04-12T10:30:00Z"
        }
    ],
    "completed_quests": ["quest_intro", "quest_tutorial"],
    "failed_quests": ["quest_timed_escort"]
}
```

---

## File Structure

```
npc-dialogue-system/
├── quest_generator.py         # Core generation logic
├── quest_manager.py           # State management
├── quest_templates/
│   ├── kill.json              # Kill/defeat templates
│   ├── fetch.json             # Delivery templates
│   ├── explore.json           # Discovery templates
│   ├── escort.json            # Protection templates
│   ├── collection.json        # Gathering templates
│   └── dialogue.json          # Information templates
├── quest_hooks.py             # NPC dialogue integration
└── demo_quest.py              # Working demo
```

---

## API Endpoints

```python
# REST API additions

GET  /npc/{npc_id}/quests        # Available quests from NPC
POST /quest/{quest_id}/accept    # Accept a quest
POST /quest/{quest_id}/abandon   # Abandon a quest
GET  /player/quests              # Player's active quests
POST /quest/{quest_id}/progress  # Update progress
POST /quest/{quest_id}/complete  # Complete and claim rewards
```

---

## Unity Integration

```csharp
// Unity client additions
public class QuestManager : MonoBehaviour
{
    public void AcceptQuest(string questId);
    public void AbandonQuest(string questId);
    public List<Quest> GetActiveQuests();
    public void UpdateProgress(string objectiveId, int amount);
    
    // Events
    public event Action<Quest> OnQuestAccepted;
    public event Action<Quest> OnQuestCompleted;
    public event Action<Quest> OnQuestFailed;
}
```

---

## Implementation Order

1. **Core Quest Classes** - Quest data structures, objectives, rewards
2. **Template System** - JSON templates for each quest type
3. **Quest Generator** - Generation logic with NPC integration
4. **Quest Manager** - State tracking, save/load
5. **API Endpoints** - REST endpoints for quest operations
6. **Unity Client** - C# quest management
7. **Demo & Testing** - Working examples and validation

---

## Success Metrics

- Quests feel contextual and meaningful (not generic)
- NPC personality clearly influences quest types
- Difficulty feels appropriate to player progression
- Quest state persists correctly across sessions
- Performance: quest generation < 500ms

---

## Future Enhancements

- **Quest Chains** - Multi-part storylines
- **Procedural Dungeons** - Quests that generate instances
- **Dynamic Events** - World events trigger mass quests
- **Quest Board** - Central location for available quests
- **Recurring Quests** - Daily/weekly repeatable tasks

---

## Notes

- This is a design document; implementation will follow
- Quest generation should enhance, not replace, handcrafted quests
- Balance procedural variety with narrative coherence
- Consider player preferences (some dislike escort quests)

---

**Document Version:** 1.0  
**Created:** April 12, 2026  
**Author:** Morgan Page (Rogues Studio)
