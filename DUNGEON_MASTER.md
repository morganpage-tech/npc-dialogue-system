# Dungeon Master AI — Implementation Plan

> **Status:** Planning
> **Target Version:** v1.9.0
> **Dependencies:** `event_system.py`, `npc_state_manager.py`, `llm_providers.py`

---

## Table of Contents

1. [Overview & Philosophy](#1-overview--philosophy)
2. [Architecture](#2-architecture)
3. [NarrativeState Data Model](#3-narrativestate-data-model)
4. [Trigger Rules — Complete Table](#4-trigger-rules--complete-table)
5. [DM Directive Types](#5-dm-directive-types)
6. [Rule DSL Specification](#6-rule-dsl-specification)
7. [Rule Compilation Pipeline](#7-rule-compilation-pipeline)
8. [Narrative Memory Compression](#8-narrative-memory-compression)
9. [DM System Prompt](#9-dm-system-prompt)
10. [Integration Points](#10-integration-points)
11. [Configuration](#11-configuration)
12. [Persistence](#12-persistence)
13. [API Endpoints](#13-api-endpoints)
14. [Demo Script](#14-demo-script)
15. [Testing Strategy](#15-testing-strategy)
16. [Performance Considerations](#16-performance-considerations)
17. [File Structure](#17-file-structure)

---

## 1. Overview & Philosophy

### What the DM Is

An event-driven AI overseer that subscribes to the game's existing event system, maintains a rolling narrative understanding of the game world, and emits **directives** that subsystems act on. It also observes its own repeated LLM judgments and compiles them into **permanent structured rules**, eliminating the need for future LLM calls on recognized patterns.

### What the DM Is Not

- Not a dialogue generator — it does not write NPC lines
- Not a replacement for existing subsystems — quest_generator, relationship_tracking, conversation_manager all still do their own work
- Not a gate — all subsystems function identically without the DM enabled

### Design Principles

1. **Opt-in.** The system boots and runs perfectly without the DM. Setting `DM_ENABLED=false` changes nothing.
2. **Additive.** The DM only adds behavior. It never blocks or overrides a subsystem's normal response.
3. **No `exec()`.** Compiled rules are structured data (JSON) interpreted by a rule engine. No dynamically generated Python code is ever executed.
4. **Observable.** Every DM action is logged. Every compiled rule is inspectable via API. Every directive includes a human-readable `reasoning` field.
5. **Bounded.** Hard caps on rules (50 active), observations (200), and narrative state size prevent unbounded growth.

---

## 2. Architecture

### System Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        GAME EVENTS                           │
│  quest_completed, relationship_change, dialogue_message,     │
│  quest_failed, world_event, npc_state_change, ...           │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
    ┌──────────────────────┐        ┌──────────────────────┐
    │   EventCallback      │        │  EventBroadcaster    │
    │  (npc_state_mgr)     │        │  (event_system)      │
    └──────────┬───────────┘        └──────────┬───────────┘
               │                               │
               │  .on_any(dm.handle_event)     │  .broadcast()
               ▼                               ▼
    ┌──────────────────────────────────────────────────────┐
    │                   DUNGEON MASTER                      │
    │                                                       │
    │  ┌─────────────────┐    ┌─────────────────────────┐  │
    │  │  DmRuleEngine   │    │   NarrativeState        │  │
    │  │  - match()      │    │   - story_summary       │  │
    │  │  - validate()   │    │   - active_arcs         │  │
    │  │  - compile()    │    │   - tension_map          │  │
    │  └────────┬────────┘    │   - observations         │  │
    │           │             └─────────────────────────┘  │
    │           │ rule hit?                                │
    │           ├──── YES ────> emit directive             │
    │           │                                          │
    │           └──── NO ────> LLM judgment ──> directive  │
    │                                      │               │
    │                                      ▼               │
    │                              log observation          │
    │                              pattern detected?        │
    │                              compile rule             │
    └──────────────┬───────────────────────────────────────┘
                   │
                   ▼ emits StateEvent with DM_* EventType
    ┌──────────────────────────────────────────────────────┐
    │                   SUBSYSTEMS                          │
    │  quest_generator  │ conversation_manager │ lore_system│
    │  npc_dialogue     │ relationship_tracker │ api_server │
    └──────────────────────────────────────────────────────┘
```

### Data Flow

1. **Event fires.** Any subsystem emits a `StateEvent` via `EventCallback.emit()`.
2. **DM receives event.** The DM's `handle_event()` is registered via `event_callback.on_any()`.
3. **Rule check.** `DmRuleEngine.match()` evaluates all active compiled rules against the event. O(n) on active rules, no LLM call.
4. **Rule hit → directive.** If a rule matches, the DM emits the rule's configured directive(s) immediately.
5. **Rule miss → LLM judgment.** If no rule matches, the DM builds a prompt from `NarrativeState` + event context, calls the LLM, and parses the response into a directive.
6. **Directive emitted.** A new `StateEvent` with a `DM_*` event type is emitted back into the system.
7. **Observation logged.** The LLM's input hash + output are logged to the observations store.
8. **Pattern check.** If 5+ similar observations exist, the DM proposes a new rule via the compilation pipeline.

---

## 3. NarrativeState Data Model

### Core Dataclass

```python
@dataclass
class NarrativeState:
    """The DM's working memory of the game world."""

    story_summary: str
    active_arcs: Dict[str, StoryArc]
    tension_map: Dict[str, float]
    npc_mood_overrides: Dict[str, str]
    world_conditions: Set[str]
    recent_observations: List[Observation]
    session_count: int
    total_events_processed: int
    total_rules_compiled: int
    last_updated: float

    def to_dict(self) -> Dict: ...
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NarrativeState': ...
```

### StoryArc

Tracks an ongoing narrative thread across multiple events.

```python
@dataclass
class StoryArc:
    """A narrative arc spanning multiple events."""

    arc_id: str
    title: str
    description: str
    status: str                  # "active", "resolved", "dormant"
    involved_npcs: List[str]
    involved_players: List[str]
    key_events: List[Dict]       # [{event_type, timestamp, summary}]
    tension_level: float         # 0.0 - 1.0
    started_at: float
    last_event_at: float
    resolution_conditions: List[str]

    def add_event(self, event: StateEvent, summary: str): ...
    def is_expired(self, ttl_hours: int = 72) -> bool: ...
```

### TensionMap

Numeric tension levels per NPC and faction. Decays over time. Used by the DM to decide when to escalate or de-escalate narrative intensity.

```python
# Example tension_map:
{
    "npc:Thorne": 0.3,
    "npc:Elara": 0.7,        # High tension — something should happen
    "faction:Merchants Guild": 0.2,
    "world:overall": 0.4
}
```

- Tension increases on: quest failures, relationship drops, hostile NPC conversations, negative world events
- Tension decreases on: quest completions, relationship gains, gifts, peaceful NPC conversations, time decay
- Decay rate: configurable, default 5% per hour of game time
- When any tension exceeds a threshold (default 0.8), the DM is force-triggered to create a release event

### Observation

Logged each time the LLM makes a judgment. Used for pattern detection.

```python
@dataclass
class Observation:
    """A single LLM judgment observation."""

    observation_id: str
    event_type: str
    event_hash: str             # Hash of event data for similarity matching
    event_summary: str          # Human-readable summary
    context_snapshot: Dict      # Narrative state at time of observation
    llm_directive_type: str     # What directive the LLM chose
    llm_parameters: Dict        # Parameters of the directive
    llm_reasoning: str          # Why
    timestamp: float
    confidence: float           # 0.0 - 1.0

    def similarity_key(self) -> str:
        """Returns event_type + directive_type for grouping."""
        return f"{self.event_type}:{self.llm_directive_type}"
```

---

## 4. Trigger Rules — Complete Table

### Hardcoded Fast-Path Rules

These require no LLM call. The rule engine evaluates them directly from event data.

| # | Event Type | Condition | DM Action | Priority |
|---|-----------|-----------|-----------|----------|
| 1 | `RELATIONSHIP_CHANGE` | score crosses from Liked→Loved | `DM_NPC_DIRECTIVE` — NPC offers a personal gift or secret | 8 |
| 2 | `RELATIONSHIP_CHANGE` | score crosses from Neutral→Disliked | `DM_NPC_DIRECTIVE` — NPC becomes cold, raises prices | 8 |
| 3 | `RELATIONSHIP_CHANGE` | score crosses from Disliked→Hated | `DM_NPC_DIRECTIVE` — NPC refuses service; `DM_CONVERSATION_TRIGGER` — NPC gossips negatively about player to nearby NPCs | 9 |
| 4 | `RELATIONSHIP_CHANGE` | score crosses into Adored | `DM_NPC_DIRECTIVE` — NPC offers unique item/quest; `DM_LORE_UPDATE` — record legendary friendship | 9 |
| 5 | `QUEST_COMPLETED` | any completion | `DM_RELATIONSHIP_OVERRIDE` — cascade +5 to faction; check for arc progression | 5 |
| 6 | `QUEST_FAILED` | any failure | `DM_RELATIONSHIP_OVERRIDE` — cascade -10 to quest-giver; `DM_NPC_DIRECTIVE` — disappointment | 6 |
| 7 | `QUEST_COMPLETED` | 3+ quests completed in same zone | `DM_WORLD_EVENT` — zone prosperity increases (NPCs friendlier, new items available) | 4 |
| 8 | `PLAYER_ENTER_ZONE` | first time entering zone | `DM_LORE_UPDATE` — add zone discovery lore | 2 |
| 9 | `FACTION_CHANGE` | faction reputation crosses -50 | `DM_WORLD_EVENT` — faction sends enforcers; merchants refuse trade | 8 |
| 10 | `WORLD_EVENT` | event severity = "major" | `DM_NPC_DIRECTIVE` — all NPCs in affected zone react; `DM_CONVERSATION_TRIGGER` — NPCs discuss the event | 7 |

### LLM-Judged Rules

These require an LLM call because the correct response depends on narrative context that can't be reduced to simple thresholds.

| # | Event Type | When DM Consults LLM | Typical Response |
|---|-----------|---------------------|-----------------|
| 11 | `DIALOGUE_MESSAGE` | Player says something ambiguous that could be a threat, promise, or lie | `DM_NPC_DIRECTIVE` — adjust NPC suspicion level; possibly `DM_CONVERSATION_TRIGGER` |
| 12 | `QUEST_COMPLETED` | Quest has narrative significance (involves named NPC, location from lore, or active arc) | `DM_QUEST_SUGGESTION` — follow-up quest; `DM_LORE_UPDATE` — record event in lore |
| 13 | `QUEST_FAILED` | Failure has cascading consequences (escort NPC died, item destroyed) | `DM_WORLD_EVENT` — ripple effects; `DM_RELATIONSHIP_OVERRIDE` — multi-NPC cascade |
| 14 | `NPC_STATE_CHANGE` | NPC mood shifts dramatically without obvious cause | `DM_NPC_DIRECTIVE` — give NPC a reason (backstory motivation); `DM_CONVERSATION_TRIGGER` — NPC confides in another NPC |
| 15 | `WORLD_EVENT` | New world event that intersects with active story arcs | Advance arc; potentially resolve or escalate arc |
| 16 | `RELATIONSHIP_CHANGE` | Unusual pattern (e.g., rising with one NPC while falling with their ally) | `DM_CONVERSATION_TRIGGER` — NPCs discuss the player; `DM_NPC_DIRECTIVE` — ally becomes suspicious |
| 17 | NPC-to-NPC conversation completes | Conversation content is narratively significant | `DM_LORE_UPDATE` — record shared knowledge; `DM_RELATIONSHIP_OVERRIDE` — NPCs' relationship with each other changes |

### Event Types That Do NOT Trigger the DM

These fire too frequently or are purely mechanical:

- `DIALOGUE_START` / `DIALOGUE_END` — too frequent, no narrative content
- `PLAYER_JOINED` / `PLAYER_LEFT` — infrastructure events
- `PLAYER_ENTER_ZONE` / `PLAYER_EXIT_ZONE` — only first-entry triggers (rule #8 above)
- `QUEST_PROGRESS` — incremental, not narratively significant
- `DM_*` events — prevents infinite loops

---

## 5. DM Directive Types

### New EventType Values

Add these to the `EventType` enum in `npc_state_manager.py`:

```python
class EventType(Enum):
    # ... existing values ...

    # DM Directive Types
    DM_QUEST_SUGGESTION = "dm_quest_suggestion"
    DM_NPC_DIRECTIVE = "dm_npc_directive"
    DM_WORLD_EVENT = "dm_world_event"
    DM_CONVERSATION_TRIGGER = "dm_conversation_trigger"
    DM_LORE_UPDATE = "dm_lore_update"
    DM_RELATIONSHIP_OVERRIDE = "dm_relationship_override"
    DM_RULE_COMPILED = "dm_rule_compiled"
```

### Directive Specifications

#### DM_QUEST_SUGGESTION

Suggests a new quest to the quest system. The quest_generator decides whether to accept it.

```python
{
    "directive_type": "DM_QUEST_SUGGESTION",
    "quest_type": "fetch",                    # QuestType value
    "suggested_by": "narrative",              # "narrative" | "rule"
    "npc_name": "Thorne",
    "title": "Recover the Stolen Anvil",
    "description": "Thorne's master anvil was stolen by bandits. He needs someone brave enough to retrieve it.",
    "objectives": [
        {"action": "reach_location", "target": "Bandit Camp", "count": 1},
        {"action": "collect_item", "target": "Master Anvil", "count": 1},
        {"action": "deliver_item", "target": "Thorne", "count": 1}
    ],
    "rewards": {"gold": 50, "relationship_bonus": {"Thorne": 15}},
    "narrative_reason": "Thorne's relationship with the player is Loved. This quest deepens the bond and ties into the active 'Blacksmith's Legacy' arc.",
    "priority": 7
}
```

**Consumer:** `quest_generator.py` — receives suggestion via callback, creates quest if valid.

#### DM_NPC_DIRECTIVE

Gives an NPC a temporary behavioral instruction. This modifies the NPC's system prompt or response parameters for subsequent dialogue.

```python
{
    "directive_type": "DM_NPC_DIRECTIVE",
    "npc_name": "Elara",
    "directive": "express_suspicion",
    "context": "The player was seen talking to a known thief near Elara's shop.",
    "prompt_modifier": "You are suspicious of the player. You've heard rumors they've been consorting with thieves. Be guarded, ask probing questions, but don't outright accuse them.",
    "duration": "until_proven_otherwise",    # or a specific event trigger
    "expires_after_events": 5,               # Remove after N more events involving this NPC
    "narrative_reason": "NPC-to-NPC gossip propagated suspicion."
}
```

**Consumer:** `npc_dialogue.py` — checks for active directives before generating response, appends `prompt_modifier` to system prompt.

#### DM_WORLD_EVENT

Spawns a world event that affects multiple systems.

```python
{
    "directive_type": "DM_WORLD_EVENT",
    "event_name": "Merchant Caravan Attack",
    "severity": "major",                     # "minor", "moderate", "major", "catastrophic"
    "description": "A merchant caravan on the eastern road was attacked by bandits. Trade routes are disrupted.",
    "affected_zones": ["eastern_road", "ironhold_village"],
    "affected_factions": {"Merchants Guild": -10},
    "npc_reactions": {
        "Thorne": "Worried about supply shortages",
        "Elara": "Angry about lost inventory"
    },
    "duration_hours": 48,                    # Game hours
    "narrative_reason": "Tension with Merchants Guild exceeded 0.8 threshold."
}
```

**Consumer:** `api_server.py` — broadcasts to all connected clients; `npc_state_manager.py` — updates world conditions; `npc_dialogue.py` — NPCs reference the event.

#### DM_CONVERSATION_TRIGGER

Tells the conversation manager to start an NPC-to-NPC conversation.

```python
{
    "directive_type": "DM_CONVERSATION_TRIGGER",
    "npc1": "Thorne",
    "npc2": "Elara",
    "topic": "player_reputation",
    "reason": "Discuss the player's recent betrayal",
    "trigger_type": "event",                 # ConversationTrigger value
    "location": "ironhold_market",
    "player_can_overhear": true,
    "narrative_reason": "Both NPCs' relationships with the player dropped. They should discuss this."
}
```

**Consumer:** `npc_conversation.py` — `ConversationManager.start_conversation()` is called with these parameters.

#### DM_LORE_UPDATE

Injects new lore into the knowledge base.

```python
{
    "directive_type": "DM_LORE_UPDATE",
    "lore_id": "event_caravan_attack_001",
    "title": "The Eastern Road Ambush",
    "content": "A merchant caravan was ambushed on the eastern road. The Merchants Guild blames the town guard for inadequate protection.",
    "category": "events",
    "known_by": ["Thorne", "Elara", "Merchants Guild"],
    "importance": 0.8,
    "tags": ["trade", "conflict", "eastern_road"],
    "narrative_reason": "Major world event should be recorded in lore for future NPC reference."
}
```

**Consumer:** `lore_system.py` — `LoreSystem.add_entry()` is called with this data.

#### DM_RELATIONSHIP_OVERRIDE

Applies cascading relationship changes that go beyond a single NPC.

```python
{
    "directive_type": "DM_RELATIONSHIP_OVERRIDE",
    "changes": [
        {"npc": "Thorne", "delta": -10, "reason": "player_failed_escort_quest"},
        {"npc": "Elara", "delta": -5, "reason": "colleague_quest_failed"},
        {"faction": "Merchants Guild", "delta": -8, "reason": "guild_reputation_loss"}
    ],
    "narrative_reason": "Player failed an escort quest for the Merchants Guild. Cascading reputation loss."
}
```

**Consumer:** `relationship_tracking.py` — `RelationshipTracker.update_score()` called for each change.

#### DM_RULE_COMPILED

Notification that a new rule was auto-activated. Informational — no subsystem action needed.

```python
{
    "directive_type": "DM_RULE_COMPILED",
    "rule_id": "dm_gen_001",
    "rule_name": "Failed quest hostility cascade",
    "trigger_event": "quest_failed",
    "confidence": 0.92,
    "observations_used": 5,
    "auto_activated": true,
    "narrative_reason": "Pattern detected: failing escort quests consistently angers related NPCs."
}
```

**Consumer:** Logged and broadcast. Available via `GET /api/dm/rules`.

---

## 6. Rule DSL Specification

### Rule JSON Schema

Every compiled rule is a JSON object conforming to this structure:

```python
DRAFT_RULE_SCHEMA = {
    "rule_id": str,               # Auto-generated: "dm_gen_{seq:03d}"
    "rule_name": str,             # Human-readable name (LLM-generated)
    "description": str,           # What this rule does and why
    "trigger": {
        "event_type": str,        # EventType value to match
        "conditions": [           # All must pass (AND logic)
            {
                "field": str,     # Dot-path into event or state
                "operator": str,  # See operators below
                "value": Any      # Comparison value
            }
        ]
    },
    "actions": [                  # All executed on match
        {
            "type": str,          # Directive type (e.g., "npc_directive")
            "parameters": Dict    # Directive-specific params
        }
    ],
    "priority": int,              # 0-10, higher = evaluated first
    "confidence": float,          # 0.0-1.0, from LLM
    "times_observed": int,        # Observations before compilation
    "source_observations": [str], # Observation IDs
    "created_at": str,            # ISO 8601
    "expires_at": str | None,     # Optional TTL (ISO 8601)
    "active": bool,               # Can be deactivated without deletion
}
```

### Field Access Paths

The `field` in a condition uses dot-notation to traverse the event and narrative state:

| Path | Resolves To |
|------|------------|
| `event.event_type` | The EventType enum value (as string) |
| `event.player_id` | Player ID |
| `event.npc_id` | NPC ID |
| `event.zone_id` | Zone ID |
| `event.data.*` | Any key in the event's data dict |
| `state.tension.{npc_or_faction}` | Current tension level |
| `state.arc.{arc_id}.tension_level` | Arc tension |
| `state.relationship.{npc_name}` | Current relationship score |
| `state.world.conditions` | Set of active world conditions |

### Condition Operators

| Operator | Value Type | Description |
|----------|-----------|-------------|
| `eq` | any | Field equals value |
| `neq` | any | Field does not equal value |
| `gt` | number | Field greater than value |
| `lt` | number | Field less than value |
| `gte` | number | Field greater than or equal |
| `lte` | number | Field less than or equal |
| `in` | list | Field value is in the list |
| `contains` | any | Field (list/string) contains value |
| `not_contains` | any | Field does not contain value |
| `exists` | bool | Field exists (true) or doesn't (false) |
| `regex` | str | Field matches regex pattern |

### Action Types (Whitelist)

Only these action types are valid. The rule engine rejects any action with an unrecognized type.

| Action Type | Maps To | Parameters |
|-------------|---------|------------|
| `relationship_change` | `RelationshipTracker.update_score()` | `npc`, `delta`, `reason` |
| `faction_change` | `RelationshipTracker.update_faction()` | `faction`, `delta`, `reason` |
| `npc_directive` | `NPCDialogue` prompt modifier | `npc`, `directive`, `prompt_modifier`, `expires_after_events` |
| `world_event` | `NPCStateManager` world state update | `event_name`, `severity`, `affected_zones`, `duration_hours` |
| `conversation_trigger` | `ConversationManager.start_conversation()` | `npc1`, `npc2`, `topic`, `location` |
| `lore_update` | `LoreSystem.add_entry()` | `lore_id`, `title`, `content`, `category`, `known_by` |
| `quest_suggestion` | `QuestGenerator` quest creation | `quest_type`, `npc_name`, `title`, `description` |
| `tension_adjust` | `NarrativeState.tension_map` update | `target`, `delta` |
| `arc_advance` | `StoryArc.add_event()` | `arc_id`, `summary` |

### Example Rules

#### Example 1: Failed Escort Quest Cascade

```json
{
    "rule_id": "dm_gen_001",
    "rule_name": "Failed escort quest hostility cascade",
    "description": "When an escort quest fails, the quest-giver and their faction allies lose trust in the player.",
    "trigger": {
        "event_type": "quest_failed",
        "conditions": [
            {"field": "event.data.quest_type", "operator": "eq", "value": "escort"}
        ]
    },
    "actions": [
        {
            "type": "relationship_change",
            "parameters": {
                "npc": "{event.npc_id}",
                "delta": -25,
                "reason": "failed_escort_quest"
            }
        },
        {
            "type": "npc_directive",
            "parameters": {
                "npc": "{event.npc_id}",
                "directive": "express_disappointment",
                "prompt_modifier": "You are deeply disappointed in the player. They failed to escort someone safely. Be cold and distant, but not hostile — you trusted them and they let you down.",
                "expires_after_events": 3
            }
        },
        {
            "type": "tension_adjust",
            "parameters": {
                "target": "{event.npc_id}",
                "delta": 0.2
            }
        }
    ],
    "priority": 6,
    "confidence": 0.92,
    "times_observed": 5,
    "source_observations": ["obs_042", "obs_067", "obs_103", "obs_128", "obs_145"],
    "created_at": "2026-04-25T14:30:00Z",
    "expires_at": null,
    "active": true
}
```

#### Example 2: Merchant Price Gouging When Relationship Low

```json
{
    "rule_id": "dm_gen_002",
    "rule_name": "Merchant price increase for disliked players",
    "description": "When a player's relationship with a merchant NPC drops to Disliked, the merchant inflates prices and mentions their distrust.",
    "trigger": {
        "event_type": "relationship_change",
        "conditions": [
            {"field": "event.data.new_level", "operator": "eq", "value": "Disliked"},
            {"field": "event.data.npc_archetype", "operator": "in", "value": ["merchant", "trader"]}
        ]
    },
    "actions": [
        {
            "type": "npc_directive",
            "parameters": {
                "npc": "{event.npc_id}",
                "directive": "price_gouging",
                "prompt_modifier": "You don't trust this customer. Mention that prices have 'gone up' for them specifically. Be passive-aggressive about it.",
                "expires_after_events": 10
            }
        }
    ],
    "priority": 5,
    "confidence": 0.87,
    "times_observed": 5,
    "source_observations": ["obs_019", "obs_055", "obs_081", "obs_099", "obs_137"],
    "created_at": "2026-04-25T15:45:00Z",
    "expires_at": null,
    "active": true
}
```

#### Example 3: Repeated Quest Success Unlocks Legendary Quest

```json
{
    "rule_id": "dm_gen_003",
    "rule_name": "Legendary quest unlock after 5 completions for same NPC",
    "description": "When a player completes 5 quests for the same NPC, a special legendary quest becomes available.",
    "trigger": {
        "event_type": "quest_completed",
        "conditions": [
            {"field": "event.data.total_completed_for_npc", "operator": "gte", "value": 5}
        ]
    },
    "actions": [
        {
            "type": "quest_suggestion",
            "parameters": {
                "quest_type": "explore",
                "npc_name": "{event.npc_id}",
                "title": "The Hidden Masterwork",
                "description": "Having proven your worth many times over, {event.npc_id} trusts you with the location of their greatest secret."
            }
        },
        {
            "type": "lore_update",
            "parameters": {
                "lore_id": "legendary_{event.npc_id}_unlock",
                "title": "Trusted Ally of {event.npc_id}",
                "content": "A legendary adventurer has earned the complete trust of {event.npc_id}.",
                "category": "events",
                "known_by": ["{event.npc_id}"],
                "importance": 0.9
            }
        }
    ],
    "priority": 4,
    "confidence": 0.95,
    "times_observed": 5,
    "source_observations": ["obs_033", "obs_071", "obs_112", "obs_156", "obs_189"],
    "created_at": "2026-04-25T16:20:00Z",
    "expires_at": null,
    "active": true
}
```

---

## 7. Rule Compilation Pipeline

### Overview

```
Event arrives → No rule match → LLM judgment → Directive emitted
                                            → Observation logged
                                                → Similarity check
                                                    → Count >= 5?
                                                        → LLM generates rule
                                                            → Validate structure
                                                                → Confidence >= 0.9?
                                                                    → Auto-activate
                                                                → Confidence < 0.9?
                                                                    → Queue for review
```

### Step 1: Observation Logging

When the LLM makes a judgment (no compiled rule matched), an `Observation` is created and appended to `NarrativeState.recent_observations`.

The observation includes a **similarity key** — a hash of `(event_type, llm_directive_type, key_event_fields)`. This groups observations that are "the same kind of judgment."

```python
def _compute_similarity_key(self, event: StateEvent, directive_type: str) -> str:
    key_parts = [
        event.event_type.value,
        directive_type,
        str(event.npc_id or ""),
        str(event.zone_id or ""),
    ]
    return "|".join(key_parts)
```

### Step 2: Pattern Detection

After logging each observation, check if 5+ observations share the same similarity key:

```python
def _check_for_pattern(self, new_obs: Observation) -> bool:
    similar = [
        o for o in self.state.recent_observations
        if o.similarity_key() == new_obs.similarity_key()
        and o.confidence >= 0.7
    ]
    return len(similar) >= 5
```

### Step 3: Rule Proposal

When a pattern is detected, the DM calls the LLM with a **rule generation prompt** that includes:

- The 5+ observations (event summaries + directives chosen)
- The current narrative context
- A request to generalize into a structured rule

The LLM returns a JSON rule definition following the Rule DSL schema.

### Step 4: Structural Validation

`DmRuleEngine.validate()` checks the proposed rule:

1. **Schema conformance** — all required fields present, correct types
2. **Operator whitelist** — only recognized condition operators
3. **Action whitelist** — only recognized action types
4. **Field path validity** — dot-paths reference real data fields
5. **No circular triggers** — rule actions must not produce events that re-trigger the same rule
6. **No duplicate rules** — check existing rules for identical trigger conditions

If validation fails, the rule is discarded and the failure is logged.

### Step 5: Activation Decision

```python
if rule.confidence >= 0.9 and len(active_rules) < MAX_ACTIVE_RULES:
    rule.active = True
    save_rule(rule, "dm_rules/active/")
    emit(DM_RULE_COMPILED, rule)
elif rule.confidence < 0.9:
    save_rule(rule, "dm_rules/pending/")
    emit(DM_RULE_COMPILED, {"status": "pending_review", "rule_id": rule.rule_id})
```

### Step 6: Safety Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| Max active rules | 50 | Prevents unbounded rule accumulation |
| Max new rules per session | 5 | Prevents rapid rule explosion |
| Min observations to compile | 5 | Ensures pattern is real |
| Min confidence to auto-activate | 0.9 | Only high-confidence rules go live |
| Max observations stored | 200 | Bounded memory |
| Rule TTL (optional) | Configurable | Rules can expire after N hours |

When `MAX_ACTIVE_RULES` is reached, the oldest lowest-priority rule is deactivated to make room.

---

## 8. Narrative Memory Compression

### The Problem

The DM needs to provide the LLM with context about the story so far, but can't feed the entire event history into every LLM call. A 1B-3B model has limited context capacity.

### Three-Tier Architecture

```
Tier 3: Arc Summaries (always in context)
├── Persistent narrative threads
├── Updated when arcs advance or resolve
└── ~50-100 tokens per arc, max 5 active arcs

Tier 2: Event Summaries (rolling window)
├── Summaries of recent significant events
├── Compressed from raw events every N events (default: 10)
└── ~200-300 tokens total

Tier 1: Raw Events (not in context)
├── Last 100 raw events stored in NarrativeState
├── Used for observation logging and rule compilation
└── Never sent directly to LLM
```

### Compression Algorithm

Every 10 events (or when total context exceeds a token budget), the DM runs a **compression pass**:

```python
async def _compress_narrative(self):
    # 1. Update arc summaries
    for arc in self.state.active_arcs.values():
        recent_arc_events = [e for e in self.raw_events if arc.arc_id in e.get("arc_ids", [])]
        if recent_arc_events:
            arc_summary = await self._llm_summarize(
                f"Summarize these events for the '{arc.title}' story arc: {recent_arc_events}"
            )
            arc.description = arc_summary

    # 2. Compress raw events into event summaries
    if len(self.raw_events) > 10:
        batch = self.raw_events[-10:]
        summary = await self._llm_summarize(
            f"Summarize these game events in 2-3 sentences: {batch}"
        )
        self.state.event_summaries.append({"summary": summary, "timestamp": time.time()})
        self.raw_events = self.raw_events[-5:]  # Keep last 5 raw

    # 3. Trim summaries (keep last 20)
    self.state.event_summaries = self.state.event_summaries[-20:]
```

### Token Budget

| Tier | Budget | Content |
|------|--------|---------|
| Arc summaries | ~300 tokens | Active story arcs (max 5) |
| Event summaries | ~200 tokens | Last 10-20 compressed event summaries |
| Current event | ~100 tokens | The event being evaluated |
| DM instructions | ~150 tokens | System prompt, available actions |
| **Total** | **~750 tokens** | Fits comfortably in 2048-token context |

---

## 9. DM System Prompt

### Core Prompt Template

This prompt is designed to work on 1B-3B models. It uses structured JSON output to avoid parsing ambiguity.

```
You are the Dungeon Master for a fantasy RPG. You oversee the narrative and ensure the world feels alive and reactive.

## YOUR ROLE
You receive game events and decide if they should cause narrative consequences beyond what the game systems already handle. You do NOT write NPC dialogue. You emit DIRECTIVES that other systems act on.

## CURRENT WORLD STATE
{arc_summaries}

## RECENT EVENTS
{event_summaries}

## CURRENT EVENT
Type: {event_type}
Player: {player_id}
NPC: {npc_id}
Zone: {zone_id}
Data: {event_data}

## AVAILABLE DIRECTIVES
1. quest_suggestion — Suggest a narratively motivated quest (quest_type, npc_name, title, description, objectives, rewards, narrative_reason)
2. npc_directive — Give an NPC a behavioral instruction (npc, directive, prompt_modifier, expires_after_events, narrative_reason)
3. world_event — Spawn a world event (event_name, severity, description, affected_zones, affected_factions, duration_hours, narrative_reason)
4. conversation_trigger — Start an NPC-to-NPC conversation (npc1, npc2, topic, reason, location, player_can_overhear, narrative_reason)
5. lore_update — Record new lore (lore_id, title, content, category, known_by, importance, narrative_reason)
6. relationship_override — Cascade relationship changes (changes: [{npc/faction, delta, reason}], narrative_reason)
7. none — This event doesn't need DM intervention

## RULES
- Only act if the event has NARRATIVE significance beyond what game systems already handle
- Prefer "none" for routine events (normal quest progress, small relationship shifts)
- Always provide narrative_reason explaining WHY this matters for the story
- Keep responses concise and structured

## RESPONSE FORMAT
Respond with ONLY a JSON object:
{{"directive": "none"}}
OR
{{"directive": "quest_suggestion", "parameters": {{...}}, "narrative_reason": "..."}}
OR
{{"directive": "npc_directive", "parameters": {{...}}, "narrative_reason": "..."}}
(etc.)
```

### Rule Generation Prompt

Used when compiling observations into a rule:

```
You are analyzing repeated patterns in a fantasy RPG's Dungeon Master decisions.

## PATTERN OBSERVATIONS
{observations_json}

## TASK
These 5+ observations show the DM consistently making the same judgment for similar events. Create a GENERAL RULE that captures this pattern so the DM can skip the LLM call in the future.

## RULE FORMAT
Respond with ONLY a JSON object:
{{
    "rule_name": "short descriptive name",
    "description": "what this rule does and why",
    "trigger": {{
        "event_type": "event_type_value",
        "conditions": [
            {{"field": "event.data.field_name", "operator": "eq|gt|lt|in|contains", "value": ...}}
        ]
    }},
    "actions": [
        {{
            "type": "action_type",
            "parameters": {{...}}
        }}
    ],
    "priority": 0-10,
    "confidence": 0.0-1.0
}}

## RULES
- Generalize from the observations, don't overfit to specific NPC names (use {event.npc_id} placeholders)
- Use the narrowest conditions that cover all observations
- Use the minimum actions needed
- Set confidence based on how consistent the observations are
- Priority should reflect narrative impact (higher = more important)
```

---

## 10. Integration Points

### Changes to `npc_state_manager.py`

Add new EventType values:

```python
class EventType(Enum):
    # ... existing values ...

    DM_QUEST_SUGGESTION = "dm_quest_suggestion"
    DM_NPC_DIRECTIVE = "dm_npc_directive"
    DM_WORLD_EVENT = "dm_world_event"
    DM_CONVERSATION_TRIGGER = "dm_conversation_trigger"
    DM_LORE_UPDATE = "dm_lore_update"
    DM_RELATIONSHIP_OVERRIDE = "dm_relationship_override"
    DM_RULE_COMPILED = "dm_rule_compiled"
```

### Changes to `api_server.py`

**Startup** — in `startup_event()`:

```python
# After existing initialization...

# Initialize Dungeon Master
from dungeon_master import DungeonMaster
from dm_rule_engine import DmRuleEngine

dm_rule_engine = DmRuleEngine(rules_dir="dm_rules")
dungeon_master = DungeonMaster(
    state_manager=state_manager,
    event_callback=state_manager.event_callback,
    rule_engine=dm_rule_engine,
    model=model,                     # Can use a different model
    backend=backend,
)

# Register DM as an event listener
state_manager.event_callback.on_any(dungeon_master.handle_event)

# Load any previously compiled rules
dm_rule_engine.load_rules()

# Load DM narrative state
dungeon_master.load_state()
```

**Shutdown** — in `shutdown_event()`:

```python
if dungeon_master:
    dungeon_master.save_state()
    dm_rule_engine.save_rules()
```

### Directive Consumers

Each subsystem registers a callback for the DM directives it cares about:

```python
# In api_server.py startup, after DM initialization:

state_manager.event_callback.on(EventType.DM_QUEST_SUGGESTION, handle_dm_quest)
state_manager.event_callback.on(EventType.DM_NPC_DIRECTIVE, handle_dm_npc_directive)
state_manager.event_callback.on(EventType.DM_WORLD_EVENT, handle_dm_world_event)
state_manager.event_callback.on(EventType.DM_CONVERSATION_TRIGGER, handle_dm_conversation)
state_manager.event_callback.on(EventType.DM_LORE_UPDATE, handle_dm_lore_update)
state_manager.event_callback.on(EventType.DM_RELATIONSHIP_OVERRIDE, handle_dm_relationship)
```

#### `handle_dm_quest` handler:

```python
async def handle_dm_quest(event: StateEvent):
    """Handle DM quest suggestions."""
    params = event.data
    try:
        quest = quest_manager.generator.create_quest(
            quest_type=QuestType(params["quest_type"]),
            npc_name=params["npc_name"],
            title=params["title"],
            description=params["description"],
        )
        quest_manager.add_quest(quest, params["npc_name"])
    except Exception as e:
        print(f"DM quest suggestion failed: {e}")
```

#### `handle_dm_npc_directive` handler:

```python
async def handle_dm_npc_directive(event: StateEvent):
    """Handle DM NPC behavioral directives."""
    params = event.data
    npc_name = params["npc_name"]
    if npc_name in manager.npcs:
        npc = manager.npcs[npc_name]
        npc.set_dm_directive(
            directive=params["directive"],
            prompt_modifier=params["prompt_modifier"],
            expires_after=params.get("expires_after_events", 5),
        )
```

#### `handle_dm_conversation` handler:

```python
async def handle_dm_conversation(event: StateEvent):
    """Handle DM conversation triggers."""
    params = event.data
    if conversation_manager:
        await conversation_manager.start_conversation(
            npc1_name=params["npc1"],
            npc2_name=params["npc2"],
            topic=params["topic"],
            trigger=ConversationTrigger.EVENT,
            location=params.get("location"),
        )
```

#### `handle_dm_lore_update` handler:

```python
async def handle_dm_lore_update(event: StateEvent):
    """Handle DM lore updates."""
    params = event.data
    if lore_system:
        lore_system.add_entry(
            LoreEntry(
                id=params["lore_id"],
                title=params["title"],
                content=params["content"],
                category=params.get("category", "events"),
                known_by=params.get("known_by", ["everyone"]),
                importance=params.get("importance", 0.5),
            )
        )
```

#### `handle_dm_relationship` handler:

```python
async def handle_dm_relationship(event: StateEvent):
    """Handle DM relationship overrides."""
    params = event.data
    for change in params.get("changes", []):
        if "npc" in change:
            relationship_tracker.update_score(
                change["npc"], change["delta"], change.get("reason", "dm_override")
            )
        elif "faction" in change:
            relationship_tracker.update_faction(
                change["faction"], change["delta"], change.get("reason", "dm_override")
            )
```

### New Method on `NPCDialogue`

```python
class NPCDialogue:
    # ... existing code ...

    def set_dm_directive(self, directive: str, prompt_modifier: str, expires_after: int = 5):
        """Set a temporary DM directive that modifies NPC behavior."""
        self._dm_directive = {
            "directive": directive,
            "prompt_modifier": prompt_modifier,
            "expires_after": expires_after,
            "events_remaining": expires_after,
        }

    def _get_dm_directive_modifier(self) -> str:
        """Get active DM directive prompt modifier, if any."""
        if hasattr(self, '_dm_directive') and self._dm_directive:
            modifier = self._dm_directive["prompt_modifier"]
            self._dm_directive["events_remaining"] -= 1
            if self._dm_directive["events_remaining"] <= 0:
                self._dm_directive = None
            return modifier
        return ""
```

In `_build_messages()`, append the DM directive modifier to the system prompt when present.

---

## 11. Configuration

### DungeonMasterConfig

```python
@dataclass
class DungeonMasterConfig:
    """Configuration for the Dungeon Master system."""

    enabled: bool = True

    # LLM Configuration
    model: str = "llama3.2:3b"              # DM can use a larger model
    backend: str = "ollama"
    api_key: Optional[str] = None
    temperature: float = 0.6                # Lower = more consistent rulings
    max_tokens: int = 300                    # DM responses are concise

    # Trigger Configuration
    enabled_triggers: Dict[str, bool] = field(default_factory=lambda: {
        "relationship_change": True,
        "quest_completed": True,
        "quest_failed": True,
        "world_event": True,
        "npc_state_change": True,
        "dialogue_message": False,           # Off by default — too frequent
    })

    # Rule Compilation
    min_observations: int = 5                # Observations before compiling
    min_confidence_auto_activate: float = 0.9
    max_active_rules: int = 50
    max_pending_rules: int = 20
    max_new_rules_per_session: int = 5
    max_observations: int = 200
    rule_ttl_hours: Optional[int] = None     # None = rules don't expire

    # Narrative Memory
    max_active_arcs: int = 5
    max_raw_events: int = 100
    max_event_summaries: int = 20
    compression_interval: int = 10           # Compress every N events
    context_token_budget: int = 750

    # Tension
    tension_threshold: float = 0.8           # Force-trigger DM above this
    tension_decay_rate: float = 0.05         # 5% per hour
    tension_increase_default: float = 0.15   # Default increase on negative events

    # Persistence
    state_dir: str = "dm_state"
    rules_dir: str = "dm_rules"
    auto_save_interval: int = 120            # Seconds
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DM_ENABLED` | `true` | Enable/disable the DM entirely |
| `DM_MODEL` | `llama3.2:3b` | Model for DM LLM calls |
| `DM_BACKEND` | `ollama` | LLM backend |
| `DM_TEMPERATURE` | `0.6` | LLM temperature |
| `DM_MAX_RULES` | `50` | Maximum active compiled rules |
| `DM_MIN_OBSERVATIONS` | `5` | Observations needed to compile a rule |
| `DM_AUTO_ACTIVATE_THRESHOLD` | `0.9` | Min confidence to auto-activate rules |

---

## 12. Persistence

### File Layout

```
dm_state/
├── narrative_state.json       # Full NarrativeState
├── observations.json          # Recent observations for pattern detection
└── raw_events.json            # Last 100 raw events

dm_rules/
├── active/
│   ├── dm_gen_001.json        # Compiled rule
│   ├── dm_gen_002.json
│   └── ...
└── pending/
    ├── dm_gen_010.json        # Low-confidence, awaiting review
    └── ...
```

### Save Format — `narrative_state.json`

```json
{
    "story_summary": "The player has been helping the Merchants Guild with trade route problems. A recent bandit attack on the eastern road has increased tension. Thorne trusts the player deeply, but Elara is growing suspicious of their motives.",
    "active_arcs": {
        "arc_001": {
            "arc_id": "arc_001",
            "title": "The Blacksmith's Legacy",
            "description": "Thorne is preparing to pass on his forge to a worthy successor. The player has been helping him gather rare materials.",
            "status": "active",
            "involved_npcs": ["Thorne"],
            "involved_players": ["player"],
            "key_events": [
                {"event_type": "quest_completed", "timestamp": 1745..., "summary": "Player retrieved rare star-iron ore for Thorne"}
            ],
            "tension_level": 0.2,
            "started_at": 1745...,
            "last_event_at": 1745...,
            "resolution_conditions": ["player_completes_final_quest", "thorne_relationship_adored"]
        }
    },
    "tension_map": {
        "npc:Thorne": 0.2,
        "npc:Elara": 0.7,
        "faction:Merchants Guild": 0.4,
        "world:overall": 0.35
    },
    "npc_mood_overrides": {
        "Elara": "suspicious"
    },
    "world_conditions": [
        "eastern_road_unsafe",
        "merchants_guild_tensions"
    ],
    "session_count": 3,
    "total_events_processed": 47,
    "total_rules_compiled": 2,
    "last_updated": 1745...
}
```

### Save Triggers

- On server shutdown (`shutdown_event()`)
- Periodic auto-save (every 120 seconds)
- After rule compilation (immediate)
- After arc creation or resolution (immediate)

---

## 13. API Endpoints

### Status & Inspection

#### `GET /api/dm/status`

Returns DM status, narrative state summary, and rule counts.

```json
{
    "enabled": true,
    "model": "llama3.2:3b",
    "active_arcs": 2,
    "active_rules": 3,
    "pending_rules": 1,
    "total_observations": 47,
    "total_events_processed": 156,
    "total_rules_compiled": 5,
    "story_summary": "The player has been helping...",
    "world_conditions": ["eastern_road_unsafe"],
    "tension_highlights": {
        "npc:Elara": 0.7,
        "world:overall": 0.35
    }
}
```

#### `GET /api/dm/arcs`

List all story arcs (active, dormant, resolved within TTL).

```json
{
    "arcs": [
        {
            "arc_id": "arc_001",
            "title": "The Blacksmith's Legacy",
            "status": "active",
            "involved_npcs": ["Thorne"],
            "tension_level": 0.2,
            "event_count": 4,
            "last_event_at": "2026-04-25T10:30:00Z"
        }
    ]
}
```

#### `GET /api/dm/arcs/{arc_id}`

Full details for a specific arc.

#### `GET /api/dm/rules`

List all rules (active and pending).

```json
{
    "active": [
        {
            "rule_id": "dm_gen_001",
            "rule_name": "Failed escort quest hostility cascade",
            "trigger": "quest_failed",
            "priority": 6,
            "confidence": 0.92,
            "times_observed": 5,
            "created_at": "2026-04-25T14:30:00Z"
        }
    ],
    "pending": [
        {
            "rule_id": "dm_gen_010",
            "rule_name": "Low confidence rule...",
            "confidence": 0.75,
            "status": "awaiting_review"
        }
    ]
}
```

#### `GET /api/dm/rules/{rule_id}`

Full rule definition including conditions and actions.

### Manual Actions

#### `POST /api/dm/trigger`

Manually trigger a DM evaluation with a custom event.

```json
// Request
{
    "event_type": "world_event",
    "data": {
        "event_name": "Dragon Sighting",
        "severity": "major",
        "location": "northern_mountains"
    }
}

// Response
{
    "directive_issued": true,
    "directive_type": "DM_WORLD_EVENT",
    "directive_data": {...},
    "rule_matched": false,
    "llm_judgment": true
}
```

#### `POST /api/dm/arcs`

Manually create a story arc.

```json
// Request
{
    "title": "The Missing Princess",
    "description": "Rumors of a missing princess from a distant kingdom have reached the village.",
    "involved_npcs": ["Elara"],
    "resolution_conditions": ["player_discovers_princess_location"]
}

// Response
{
    "arc_id": "arc_003",
    "status": "active"
}
```

#### `POST /api/dm/rules/{rule_id}/approve`

Approve a pending rule, moving it to active.

```json
// Response
{
    "rule_id": "dm_gen_010",
    "status": "active",
    "activated_at": "2026-04-25T16:00:00Z"
}
```

#### `POST /api/dm/rules/{rule_id}/deactivate`

Deactivate an active rule (keeps it on disk, stops matching).

```json
// Response
{
    "rule_id": "dm_gen_001",
    "status": "inactive"
}
```

#### `DELETE /api/dm/rules/{rule_id}`

Permanently delete a rule.

#### `POST /api/dm/save`

Force-save DM state and rules.

#### `POST /api/dm/reset`

Reset all DM state (keep compiled rules, clear narrative state).

---

## 14. Demo Script

### `demo_dungeon_master.py`

A comprehensive demo showcasing all DM capabilities.

#### Scenario 1: Quest Completion Cascade

```
--- Scenario 1: Quest Completion Cascade ---

Player completes "Retrieve the Stolen Anvil" quest for Thorne.
→ Event: quest_completed (npc=Thorne, quest_type=fetch)
→ DM: No compiled rule matches. Consulting LLM...
→ DM Directive: DM_RELATIONSHIP_OVERRIDE
    - Thorne: +15 (quest reward)
    - Merchants Guild: +5 (guild reputation)
→ DM Directive: DM_QUEST_SUGGESTION
    - New quest: "The Secret Forge" (requires Loved relationship)
→ DM: Arc "The Blacksmith's Legacy" advanced.
→ DM: Observation logged (obs_001).

Player completes another 4 fetch quests for Thorne...
→ DM: Pattern detected! 5 similar observations.
→ DM: Compiling rule "Fetch quest reputation cascade"...
→ Rule auto-activated (confidence: 0.94).
→ Next fetch quest completion: rule fires instantly, no LLM call.
```

#### Scenario 2: Relationship Threshold Drama

```
--- Scenario 2: Relationship Threshold Drama ---

Player repeatedly offends Elara.
→ Event: relationship_change (Elara, score: 22→19, Liked→Neutral)
→ DM: Hardcoded rule fires (no LLM needed).
→ DM Directive: DM_NPC_DIRECTIVE
    - Elara: "neutral_distant" — less friendly, mentions past friendship wistfully
→ DM Directive: DM_CONVERSATION_TRIGGER
    - Elara talks to Thorne about the player's behavior
    - Player can overhear: "I'm not sure about that adventurer anymore, Thorne..."

Player continues to offend Elara.
→ Event: relationship_change (Elara, score: -5→-22, Neutral→Disliked)
→ DM: Hardcoded rule fires.
→ DM Directive: DM_NPC_DIRECTIVE
    - Elara: "cold_business" — raises prices, refuses gossip
→ DM: Tension increased (npc:Elara → 0.8)
→ DM: Tension threshold exceeded! Force-triggering narrative event...
→ DM Directive: DM_WORLD_EVENT
    - "Merchant Rivalry" — Elara spreads rumors, other merchants wary
```

#### Scenario 3: Rule Compilation in Action

```
--- Scenario 3: Rule Compilation ---

Simulating 5 repeated patterns of "player fails kill quest → nearby NPCs become wary"...

Event 1: quest_failed (kill quest in eastern_road)
→ DM: LLM judges → DM_NPC_DIRECTIVE (nearby NPCs become wary)
→ Observation logged (obs_010)

Event 2: quest_failed (kill quest in dark_forest)
→ DM: LLM judges → DM_NPC_DIRECTIVE (nearby NPCs become wary)
→ Observation logged (obs_018)
→ Pattern check: 2/5 observations

[...3 more similar events...]

Event 5: quest_failed (kill quest in mountain_pass)
→ DM: LLM judges → DM_NPC_DIRECTIVE (nearby NPCs become wary)
→ Observation logged (obs_045)
→ Pattern check: 5/5 observations!
→ DM: Compiling rule...
→ LLM generates rule: "Failed kill quest makes nearby NPCs wary"
→ Validation: PASSED
→ Confidence: 0.91 → AUTO-ACTIVATED

Event 6: quest_failed (kill quest in swamp)
→ DM: Compiled rule matches! No LLM call needed.
→ Directive issued instantly: DM_NPC_DIRECTIVE (nearby NPCs become wary)
→ Speed: 0.002s (vs 2.5s for LLM call)
```

#### Scenario 4: World Event Propagation

```
--- Scenario 4: World Event Propagation ---

DM spawns a world event: "Bandit Raid on Ironhold"
→ DM Directive: DM_WORLD_EVENT
    - Severity: major
    - Affected zones: ironhold_village, eastern_road
    - Affected factions: Merchants Guild (-15)
    - Duration: 24 game hours

→ Consequences propagate:
    - Thorne (in ironhold_village): DM_NPC_DIRECTIVE — worried, mentions needing weapons
    - Elara (in ironhold_village): DM_NPC_DIRECTIVE — stocking up supplies, prices fluctuate
    - DM_CONVERSATION_TRIGGER: Thorne and Elara discuss the raid
    - DM_LORE_UPDATE: "The Ironhold Bandit Raid" recorded in lore
    - DM_QUEST_SUGGESTION: "Clear the Bandit Camp" quest becomes available

→ Player enters ironhold_village:
    - NPCs reference the raid in dialogue
    - New quest available from Thorne
    - Faction reputation shifted
```

#### Scenario 5: Narrative Arc Tracking

```
--- Scenario 5: Narrative Arc Across Sessions ---

Session 1:
→ Player meets Thorne, completes "Repair the Anvil"
→ DM: Arc "The Blacksmith's Legacy" created (tension: 0.1)

Session 2:
→ Player completes "Retrieve Star Iron" for Thorne
→ DM: Arc advanced (tension: 0.2)
→ DM: Thorne mentions wanting to find an apprentice

Session 3:
→ Player fails "Escort the Smith's Nephew"
→ DM: Arc tension spike (0.6)
→ DM: Thorne is devastated, arc takes a darker turn
→ DM Directive: DM_CONVERSATION_TRIGGER
    - Thorne confides in Elara about his nephew

Session 4:
→ Player redeems by completing "Rescue the Nephew"
→ DM: Arc tension drops (0.1)
→ DM: Arc approaching resolution
→ DM Directive: DM_QUEST_SUGGESTION
    - "The Final Forge" — Thorne's masterwork quest (legendary)

Session 5:
→ Player completes "The Final Forge"
→ DM: Arc "The Blacksmith's Legacy" RESOLVED
→ DM Directive: DM_LORE_UPDATE — "Thorne's Greatest Work" recorded
→ DM Directive: DM_RELATIONSHIP_OVERRIDE — Thorne → Adored
→ DM Directive: DM_NPC_DIRECTIVE — Thorne at peace, mentions player as a true friend
→ DM: New arc potential: "The Merchant's Secret" (Elara noticed during previous sessions)
```

---

## 15. Testing Strategy

### `test_dungeon_master.py`

Tests for the core `DungeonMaster` class.

```
Test Categories:
├── Initialization
│   ├── test_dm_initializes_with_defaults
│   ├── test_dm_disabled_does_not_handle_events
│   └── test_dm_loads_state_from_disk
│
├── Event Handling
│   ├── test_dm_handles_ignored_event_types
│   ├── test_dm_uses_compiled_rule_when_matched
│   ├── test_dm_falls_back_to_llm_when_no_rule
│   └── test_dm_does_not_process_dm_events (no infinite loops)
│
├── Narrative State
│   ├── test_arc_creation
│   ├── test_arc_advancement
│   ├── test_arc_resolution
│   ├── test_arc_expiry_after_ttl
│   ├── test_tension_increase_on_negative_event
│   ├── test_tension_decay_over_time
│   ├── test_tension_threshold_force_trigger
│   └── test_max_active_arcs_limit
│
├── Observation & Compilation
│   ├── test_observation_logging
│   ├── test_similarity_key_computation
│   ├── test_pattern_detection_at_threshold
│   ├── test_pattern_not_detected_below_threshold
│   ├── test_rule_compilation_pipeline
│   ├── test_auto_activation_at_high_confidence
│   └── test_pending_queue_at_low_confidence
│
├── Persistence
│   ├── test_save_and_load_narrative_state
│   ├── test_observations_persist_across_sessions
│   └── test_state_survives_server_restart
│
└── Edge Cases
    ├── test_dm_handles_llm_failure_gracefully
    ├── test_dm_handles_malformed_llm_response
    ├── test_max_rules_limit_enforcement
    ├── test_max_observations_limit_enforcement
    └── test_concurrent_event_handling
```

### `test_dm_rule_engine.py`

Tests for the `DmRuleEngine` class.

```
Test Categories:
├── Condition Matching
│   ├── test_eq_operator
│   ├── test_neq_operator
│   ├── test_gt_lt_gte_lte_operators
│   ├── test_in_operator
│   ├── test_contains_operator
│   ├── test_exists_operator
│   ├── test_regex_operator
│   ├── test_multiple_conditions_and_logic
│   ├── test_nested_field_access
│   └── test_missing_field_handling
│
├── Rule Validation
│   ├── test_valid_rule_passes
│   ├── test_missing_required_field_fails
│   ├── test_unknown_operator_fails
│   ├── test_unknown_action_type_fails
│   ├── test_circular_trigger_detection
│   └── test_duplicate_rule_detection
│
├── Rule Matching
│   ├── test_single_rule_match
│   ├── test_no_rule_match
│   ├── test_priority_ordering
│   ├── test_multiple_rules_match_highest_priority_wins
│   ├── test_inactive_rules_ignored
│   └── test_expired_rules_ignored
│
├── Action Execution
│   ├── test_action_resolves_event_placeholders
│   ├── test_action_whitelist_enforcement
│   └── test_invalid_action_parameters_handled
│
└── Rule Lifecycle
    ├── test_rule_creation
    ├── test_rule_activation
    ├── test_rule_deactivation
    ├── test_rule_deletion
    ├── test_max_rules_eviction (oldest lowest-priority)
    └── test_rules_load_and_save
```

### Test Count Estimate

- `test_dungeon_master.py`: ~35-40 tests
- `test_dm_rule_engine.py`: ~30-35 tests
- **Total: ~65-75 tests**

---

## 16. Performance Considerations

### Latency Budget

| Operation | Time | LLM Call? |
|-----------|------|-----------|
| Rule match (10 active rules) | <1ms | No |
| Rule match (50 active rules) | <5ms | No |
| LLM judgment (1B model) | 1-3s | Yes |
| LLM judgment (3B model) | 2-5s | Yes |
| Narrative compression | 2-4s | Yes (periodic) |
| Rule compilation | 3-6s | Yes (rare) |
| State save to disk | <50ms | No |

### Frequency of LLM Calls

| Phase | Call Frequency | Context |
|-------|---------------|---------|
| First 5 hours of gameplay | ~2-4 per minute | No rules compiled yet, most events go to LLM |
| After 10+ hours | ~1-2 per minute | Many patterns compiled, most events hit rules |
| Rule compilation | ~1-2 per hour | Only when patterns detected |
| Narrative compression | ~1 per 10 events | Periodic, non-blocking |

### Optimization Strategies

1. **Async processing.** DM event handling is async. The DM never blocks NPC dialogue responses. If a player is talking to an NPC and a DM event fires in the background, the NPC responds immediately and the DM's consequences apply to the *next* interaction.

2. **Batched processing.** If multiple events fire in quick succession (e.g., quest completion triggers relationship change + faction change + world event), the DM batches them into a single LLM call rather than making 3 separate calls.

3. **Rule hit rate tracking.** The DM logs what percentage of events hit compiled rules vs. needing LLM calls. This is exposed via `GET /api/dm/status` for monitoring.

4. **Lazy compression.** Narrative compression only runs when the token budget is approached, not on every event.

5. **DM model separation.** The DM can use `llama3.2:3b` while NPCs use `llama3.2:1b`. Since the DM fires infrequently, the larger model's quality is worth the slower response time.

---

## 17. File Structure

### New Files

| File | Estimated Lines | Description |
|------|----------------|-------------|
| `dungeon_master.py` | 800-1000 | Core DM class, event handling, LLM judgment, observation logging |
| `dm_rule_engine.py` | 500-600 | Rule DSL interpreter, validation, matching, compilation |
| `demo_dungeon_master.py` | 400-500 | Comprehensive demo with 5 scenarios |
| `test_dungeon_master.py` | 400-500 | Unit tests for DM core |
| `test_dm_rule_engine.py` | 350-400 | Unit tests for rule engine |
| `DUNGEON_MASTER.md` | This file | Implementation plan |

### New Directories

```
dm_state/                  # Created at runtime
├── narrative_state.json
├── observations.json
└── raw_events.json

dm_rules/                  # Created at runtime
├── active/
│   └── (compiled rule JSON files)
└── pending/
    └── (low-confidence rule JSON files)
```

### Modified Files

| File | Change Description |
|------|-------------------|
| `api_server.py` | Add DM initialization, directive handlers, new API endpoints |
| `npc_state_manager.py` | Add 7 new `EventType` values (`DM_*`) |
| `npc_dialogue.py` | Add `set_dm_directive()`, `_get_dm_directive_modifier()`, integrate into `_build_messages()` |
| `TODO.md` | Add Phase 5e entry for Dungeon Master |

### Estimated Total

- **New code:** ~2,500-3,000 lines (Python)
- **Tests:** ~750-900 lines
- **Demo:** ~400-500 lines
- **Modified code:** ~150-200 lines across existing files

---

## Appendix A: Rule DSL — Full JSON Schema

For reference, the complete JSON schema that `DmRuleEngine.validate()` enforces:

```python
RULE_SCHEMA = {
    "type": "object",
    "required": ["rule_id", "rule_name", "description", "trigger", "actions", "priority", "confidence"],
    "properties": {
        "rule_id": {"type": "string", "pattern": "^dm_gen_\\d{3}$"},
        "rule_name": {"type": "string", "minLength": 1, "maxLength": 100},
        "description": {"type": "string", "minLength": 1, "maxLength": 500},
        "trigger": {
            "type": "object",
            "required": ["event_type", "conditions"],
            "properties": {
                "event_type": {"type": "string"},
                "conditions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["field", "operator", "value"],
                        "properties": {
                            "field": {"type": "string"},
                            "operator": {
                                "type": "string",
                                "enum": ["eq", "neq", "gt", "lt", "gte", "lte",
                                         "in", "contains", "not_contains", "exists", "regex"]
                            },
                            "value": {}
                        }
                    }
                }
            }
        },
        "actions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "parameters"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "relationship_change", "faction_change",
                            "npc_directive", "world_event",
                            "conversation_trigger", "lore_update",
                            "quest_suggestion", "tension_adjust",
                            "arc_advance"
                        ]
                    },
                    "parameters": {"type": "object"}
                }
            }
        },
        "priority": {"type": "integer", "minimum": 0, "maximum": 10},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "times_observed": {"type": "integer", "minimum": 1},
        "source_observations": {"type": "array", "items": {"type": "string"}},
        "created_at": {"type": "string", "format": "date-time"},
        "expires_at": {"type": ["string", "null"], "format": "date-time"},
        "active": {"type": "boolean"}
    }
}
```

---

## Appendix B: Circular Trigger Prevention

The DM must not create directives that trigger themselves. The rule engine enforces this:

```python
CIRCULAR_TRIGGERS = {
    # directive_type → event_types it could produce
    "relationship_change": {"RELATIONSHIP_CHANGE", "FACTION_CHANGE"},
    "npc_directive": {"NPC_STATE_CHANGE"},
    "world_event": {"WORLD_EVENT"},
    "conversation_trigger": set(),  # NPC conversations don't re-trigger DM
    "lore_update": set(),           # Lore updates don't re-trigger DM
    "quest_suggestion": {"QUEST_COMPLETED", "QUEST_ACCEPTED"},  # Indirectly, much later
}

def check_circular(rule) -> bool:
    """Return True if any rule action could re-trigger this rule."""
    for action in rule["actions"]:
        produced_events = CIRCULAR_TRIGGERS.get(action["type"], set())
        if rule["trigger"]["event_type"] in produced_events:
            return True
    return False
```

Additionally, the DM's `handle_event()` method checks event origin:

```python
async def handle_event(self, event: StateEvent):
    if event.event_type.value.startswith("dm_"):
        return  # Never process DM directives
    if event.data.get("source") == "dungeon_master":
        return  # Never process DM-generated events
    # ... proceed with handling
```
