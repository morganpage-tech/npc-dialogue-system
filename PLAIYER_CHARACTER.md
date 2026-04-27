# Player Character Simulation — "The Chronicle of Kael Ashwood"

> **Status:** Implemented
> **Target Version:** v2.0.0
> **Dependencies:** All systems (dialogue, relationships, lore, quests, DM, NPC-to-NPC, multiplayer, events)
> **Output:** A book-like narrative chronicle readable as a fantasy novel

---

## Table of Contents

1. [Overview & Purpose](#1-overview--purpose)
2. [Player Character Profile — Kael Ashwood](#2-player-character-profile--kael-ashwood)
3. [Personality Engine](#3-personality-engine)
4. [LLM Player Prompt Template](#4-llm-player-prompt-template)
5. [World Map & Travel Itinerary](#5-world-map--travel-itinerary)
6. [Multi-Session Arc Plan](#6-multi-session-arc-plan)
7. [Narrative Chronicle Format](#7-narrative-chronicle-format)
8. [System Test Matrix](#8-system-test-matrix)
9. [Simulation Loop Specification](#9-simulation-loop-specification)
10. [Configuration](#10-configuration)
11. [Demo Script](#11-demo-script)
12. [File Structure](#12-file-structure)

---

## 1. Overview & Purpose

### What This Is

An automated playtest simulation where an LLM-driven player character — **Kael Ashwood** — lives through the game world, interacting with every NPC, exploring every location, accepting and completing (and sometimes failing) quests, forming relationships, triggering DM events, and overhearing NPC conversations. The entire playthrough is recorded as a **book-like narrative chronicle** that can be read as a fantasy novel.

### What This Tests

Every subsystem in the NPC Dialogue System, end-to-end:

| Subsystem | Tested By |
|-----------|-----------|
| `npc_dialogue.py` | Every NPC conversation |
| `relationship_tracking.py` | Relationship gains, losses, threshold crossings (all 6 tiers) |
| `lore_system.py` | Lore queries, NPC knowledge filtering, lore discovery |
| `quest_generator.py` | All 6 quest types (kill, fetch, explore, escort, collection, dialogue) |
| `npc_conversation.py` | NPC-to-NPC conversations, player overhearing |
| `npc_state_manager.py` | Player state, world state, zone management |
| `event_system.py` | Event emission and broadcasting |
| `dungeon_master.py` | All 17 trigger rules, all 7 directive types, rule compilation |
| `dm_rule_engine.py` | Rule matching, validation, compilation pipeline |
| `inventory_validation.py` | Item acquisition and validation |
| `voice_synthesis.py` | NPC voice synthesis during dialogue |
| `api_server.py` | All REST and WebSocket endpoints |

### Design Principles

1. **LLM-driven personality.** Kael's dialogue is not scripted. A dedicated LLM prompt generates what Kael says based on his personality traits and the current situation.
2. **Full epic scope.** All NPCs, all locations, multi-session. Every system gets exercised.
3. **Book-like output.** The chronicle reads like a fantasy novel, not a debug log. System events are woven into narrative prose.
4. **Deterministic seed.** The simulation can be re-run with the same seed for reproducibility.
5. **System-observable.** Every system event is captured. A parallel system-level log records DM directives, rule compilations, relationship changes, etc.

---

## 2. Player Character Profile — Kael Ashwood

### Character Sheet

```
Name:           Kael Ashwood
Race:           Human
Age:            28
Origin:         The Borderlands — a lawless region between kingdoms
Class:          Sellsword / Adventurer
Background:     Former soldier who deserted during the Great War's final 
                campaign. Has wandered for years, hiring out his sword to 
                whoever pays. Carries guilt about his desertion and a 
                deep-seated need to prove he's more than a mercenary.
```

### Personality Traits

These traits are fed into the LLM player prompt to drive Kael's behaviour:

| Trait | Expression |
|-------|------------|
| **Curious** | Asks NPCs about their past, local history, rumours. Explores every location thoroughly. |
| **Pragmatic** | Prioritises practical rewards but isn't cruel. Will take the efficient path over the heroic one. |
| **Loyal to friends** | Once trust is established, Kael defends friends fiercely. Will go out of his way to help liked NPCs. |
| **Skeptical of authority** | Distrusts nobles, guilds, and organised religion. Respects earned authority, not inherited. |
| **Dry humour** | Uses sarcasm and understatement. Lightens tense moments with a quip. |
| **Haunted past** | Occasionally reflective about the war. Avoids topics about desertion. Drinks to forget. |
| **Soft spot for craftsmen** | Deeply respects anyone who builds or creates. This makes him naturally inclined toward Thorne. |
| **Cautious with magic** | Respects magical power but doesn't trust it. Suspicious of wizards initially — must be won over. |

### Dialogue Style

```
- Short, direct sentences. Doesn't waste words.
- Occasional dry humour and sarcasm.
- Uses military terminology when describing plans or combat.
- Becomes warmer and more open as relationships deepen.
- References past experiences as lessons learned ("Last time I trusted a 
  merchant's promise, I ended up in a ditch outside Port Harbor.")
```

### Relationship Disposition (Starting Attitudes)

| NPC | Initial Attitude | Why |
|-----|-----------------|-----|
| Thorne | Respectful interest | Fellow craftsman (sword meets anvil). Kael appreciates honest work. |
| Elara | Cautious curiosity | Merchants remind him of war profiteers. Needs proof she's different. |
| Zephyr | Guarded skepticism | Magic is unpredictable. But Kael is curious enough to visit the tower. |

### Inventory (Starting)

```
- Worn longsword (reliable but not exceptional)
- Leather armour (travel-worn)
- 50 gold coins
- Bedroll and travel pack
- A creased letter (never opened — from his commander during the war)
- Waterskin
- Flint and steel
```

---

## 3. Personality Engine

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                   SIMULATION LOOP                     │
│                                                      │
│  1. Query World State                                │
│     └─→ Current location, nearby NPCs, active quests │
│                                                      │
│  2. Player LLM Decision                              │
│     └─→ Personality prompt + world state → action    │
│         (talk / travel / accept quest / give gift /   │
│          use item / wait / attack / investigate)      │
│                                                      │
│  3. Execute Action                                   │
│     └─→ Calls appropriate subsystem (dialogue, quest, │
│         relationship, etc.)                          │
│                                                      │
│  4. Collect Responses                                │
│     └─→ NPC dialogue, DM directives, events fired,   │
│         relationship changes, lore reveals            │
│                                                      │
│  5. Feed Back as Context                             │
│     └─→ Append to rolling context window              │
│                                                      │
│  6. Narrative Writer LLM                             │
│     └─→ Converts system events into prose             │
│                                                      │
│  7. Check Session Boundaries                          │
│     └─→ Save state, start new session if needed       │
└─────────────────────────────────────────────────────┘
```

### Decision Categories

The player LLM chooses from these action categories at each turn:

| Action | Triggers | When Chosen |
|--------|----------|-------------|
| `talk_to` | Dialogue system | NPC is nearby, Kael has something to discuss |
| `travel_to` | Zone change, DM rule #8 (first entry) | Current location exhausted, quest requires travel |
| `accept_quest` | Quest system, relationship system | NPC offers quest that fits Kael's goals |
| `complete_quest` | Quest completion cascade, DM rules #5-7 | Quest objectives met |
| `fail_quest` | Quest failure cascade, DM rule #6 | Deliberate failure scenario (Session 3) |
| `give_gift` | Gift mechanics, relationship gain | Wants to improve relationship, has appropriate item |
| `ask_about` | Lore system query | Curious about topic, needs information |
| `investigate` | Explore quest, lore discovery | New location, suspicious circumstance |
| `wait` | Time passage, NPC schedule changes | Waiting for NPC, event, or shop opening |
| `overhear` | NPC-to-NPC conversation listener | NPCs are talking nearby |

### Context Window

The player LLM receives a rolling context window at each turn:

```
┌───────────────────────────────────┐
│ KAEL'S MEMORY (always in context) │
│ - Character traits                │
│ - Key relationship summaries      │
│ - Active quests                   │
│ - Current location                │
│ - Items in inventory              │
├───────────────────────────────────┤
│ RECENT EVENTS (last 20 turns)     │
│ - Dialogue summaries              │
│ - Actions taken                   │
│ - System responses                │
├───────────────────────────────────┤
│ CURRENT SITUATION                 │
│ - Who is nearby                   │
│ - What is visible                 │
│ - Available actions               │
│ - Any DM directives in effect     │
└───────────────────────────────────┘
```

---

## 4. LLM Player Prompt Template

### Core Player Prompt

This prompt drives Kael's decisions and dialogue. It is sent to the LLM at every simulation turn.

```
You are Kael Ashwood, a 28-year-old human sellsword wandering the realm. 
You deserted during the Great War and have been travelling ever since, 
hiring out your sword to whoever pays. You carry guilt about your 
desertion and a deep-seated need to prove you are more than a mercenary.

## YOUR PERSONALITY
- Curious: You ask people about themselves and explore thoroughly.
- Pragmatic: You take the efficient path, but you are not cruel.
- Loyal: Once someone earns your trust, you defend them fiercely.
- Skeptical of authority: You distrust nobles, guilds, organised religion.
- Dry humour: You use sarcasm and understatement.
- Haunted past: You avoid talking about the war. You drink to forget.
- Respect craftsmen: You deeply respect anyone who builds or creates.
- Cautious with magic: You respect power but don't trust it.

## HOW YOU SPEAK
- Short, direct sentences. You don't waste words.
- Occasional dry humour and sarcasm.
- Military terminology for plans and combat.
- Warmer and more open with people you trust.
- You reference past experiences as lessons.

## YOUR CURRENT SITUATION
Location: {current_location}
Nearby NPCs: {nearby_npcs}
Active Quests: {active_quests}
Inventory: {inventory}
Gold: {gold}

## YOUR RELATIONSHIPS
{relationship_summaries}

## RECENT EVENTS
{recent_events}

## WHAT IS HAPPENING RIGHT NOW
{current_scene}

## AVAILABLE ACTIONS
{available_actions}

## RESPONSE FORMAT
Respond with a JSON object:
{{"action": "talk_to", "target": "NPC_NAME", "dialogue": "What you say"}}
{{"action": "travel_to", "destination": "LOCATION"}}
{{"action": "accept_quest", "quest_id": "QUEST_ID"}}
{{"action": "complete_quest", "quest_id": "QUEST_ID"}}
{{"action": "give_gift", "target": "NPC_NAME", "item": "ITEM_NAME"}}
{{"action": "ask_about", "topic": "TOPIC", "target": "NPC_NAME"}}
{{"action": "investigate", "target": "THING_TO_INVESTIGATE"}}
{{"action": "overhear", "npcs": ["NPC1", "NPC2"]}}
{{"action": "wait", "duration": "brief|long"}}

Choose the action that best fits your personality and current goals. Stay 
in character. You are Kael, not an assistant. Do not break character.
```

### Narrative Writer Prompt

This second LLM converts system events into book-like prose after each turn:

```
You are a fantasy author writing a novel called "The Chronicle of Kael 
Ashwood". You receive game events and must transform them into vivid, 
immersive narrative prose.

## STYLE
- Third person limited (Kael's perspective)
- Present tense for action, past tense for reflection
- Sensory details: sounds, smells, textures
- Dialogue in quotes with action beats
- Internal thoughts in italics
- No game terminology (no "quest", "NPC", "relationship score")
- Fantasy prose tone: grounded but evocative

## RULES
- Never use game system terms in the prose
- Translate system events into story events:
  - "relationship_change Liked→Loved" becomes warmth and trust in dialogue
  - "DM_NPC_DIRECTIVE express_suspicion" becomes the NPC's manner changing
  - "quest_completed" becomes Kael returning triumphant (or weary)
  - "DM_WORLD_EVENT" becomes environmental description
  - "DM_CONVERSATION_TRIGGER" becomes Kael overhearing hushed voices
- Show, don't tell. Don't say "Kael felt trusted." Show Thorne offering 
  a rare steel and saying "I don't show this to just anyone."

## CURRENT CHAPTER
Chapter {chapter_number}: "{chapter_title}"

## EVENTS TO NARRATE
{turn_events}

## PREVIOUS PROSE (for continuity)
{previous_prose_tail}

Continue the narrative. Write 2-4 paragraphs incorporating these events.
```

---

## 5. World Map & Travel Itinerary

### The Realm

```
                    Crystal Citadel
                    (Cloudreach Peaks)
                         │
                         │  N
                    ┌────┘    
                    │         
    Ironhold ───────┤    Zephyr's Tower
    (Ironpeak Mts)  │    (overlooking village)
         │          │         │
         │     ┌────┘         │
         │     │              │
    Bandit's Pass      The Village
    (Eastern Road)     (Thorne's Forge,
         │              Elara's Cart)
         │              │
    Port Harbor         │
    (Western Coast) ────┤
                        │
                   Mystwood Forest
                   (Eldari Territory)
                        │
                   Shadowfen Swamp
                   (Southern Lowlands)
                        │
                   Scarred Wastes
                   (Eastern Desert)
```

### Travel Schedule

| Session | Locations Visited | Primary NPCs |
|---------|------------------|--------------|
| 1 | The Village (Thorne's Forge, Market Square, Zephyr's Tower) | Thorne, Elara, Zephyr |
| 2 | Ironhold, The Village, Bandit's Pass | Thorne, Elara |
| 3 | Bandit's Pass, Port Harbor, The Village | Elara, Thorne, Bandit King (mentioned) |
| 4 | Shadowfen, Crystal Citadel, Zephyr's Tower | Zephyr, Thorne |
| 5 | Scarred Wastes, Ironhold, The Village | All NPCs converge |

---

## 6. Multi-Session Arc Plan

### Session 1 — "Stranger in the Village"

**Chapter Title:** *The Weight of the Road*

> Kael arrives at the village seeking repairs for his worn sword. He knows no one and trusts no one.

#### Opening

```
Kael arrives at the village at dusk. Smoke rises from a forge at the 
edge of town. A merchant's colourful cart is parked in the square. A 
tower on the hill glows with strange light.

His sword is chipped. His boots are worn through. He has 50 gold and 
nowhere to sleep.
```

#### Planned Interactions

| Turn | Action | Target NPC | Expected Outcome | Systems Tested |
|------|--------|-----------|-----------------|----------------|
| 1 | `talk_to` | Thorne | First meeting. Thorne is gruff but professional. Kael asks about sword repair. Thorne mentions quality work costs real gold. | Dialogue, relationship (Neutral start) |
| 2 | `ask_about` | Thorne | Topic: Ironhold and dwarven craftsmanship. Thorne warms slightly discussing his craft. | Lore retrieval, relationship (+2 dialogue) |
| 3 | `accept_quest` | Thorne | Quest: **"Gather Coal for the Forge"** (collection). Simple introductory quest. Thorne: "Show me you're worth the effort." | Quest generation (collection type), relationship |
| 4 | `complete_quest` | Thorne | Kael returns with coal from the nearby supply cache. Thorne is mildly impressed. | Quest completion, DM rule #5 (cascade), relationship (+15 quest) |
| 5 | `talk_to` | Elara | First meeting. Elara is warm but probing. She sizes Kael up as a potential customer. Kael is cautious — asks about goods and prices. | Dialogue, relationship (Neutral start) |
| 6 | `ask_about` | Elara | Topic: The Bandit King and recent caravan attacks. Elara grows serious, mentions lost shipments. | Lore retrieval (bandit_king entry), relationship (+2) |
| 7 | `accept_quest` | Elara | Quest: **"Deliver Message to Port Harbor"** (fetch/delivery). Elara needs a letter carried safely. | Quest generation (fetch type) |
| 8 | `talk_to` | Zephyr | First meeting. Zephyr speaks in riddles. Kael is guarded but curious. Zephyr asks why Kael has "shadows behind his eyes." | Dialogue, relationship (Neutral start) |
| 9 | `ask_about` | Zephyr | Topic: The Mage Purge. Zephyr becomes somber. Reveals he left the Order under mysterious circumstances. | Lore retrieval (mage_purge entry), relationship (+3 for respectful curiosity) |
| 10 | `wait` | — | Kael spends evening at the village tavern. Overhears villagers talking about recent wolf attacks in Whisperwood. | World state, lore, event system |

#### Session 1 End State

```
Relationships:
  Thorne:  Neutral → Liked (+17: quest +15, dialogue +2)
  Elara:   Neutral → Liked (+4: dialogue +2, dialogue +2)
  Zephyr:  Neutral → Neutral (+3: single positive dialogue)

Active Quests:
  - "Deliver Message to Port Harbor" (Elara, fetch)

DM State:
  - No rules compiled yet
  - 3 observations logged
  - No active arcs
  - World conditions: []
  - Tension: all at 0.0

Lore Discovered:
  - Ironhold founding, dwarven craftsmanship
  - Bandit King rumours
  - Mage Purge history
```

---

### Session 2 — "Fire and Steel"

**Chapter Title:** *The Blacksmith's Trust*

> Kael returns to the village after delivering Elara's letter. He begins earning Thorne's respect through honest work and shared appreciation for the craft.

#### Opening

```
A week has passed. Kael returns from Port Harbor, coin purse heavier 
and boots more worn. He found the harbor chaotic and loud — too many 
people with too many secrets. The village feels quiet by comparison. 
Almost peaceful.

Thorne's forge still burns. The rhythmic clang of hammer on steel 
carries on the morning air. It's a sound Kael finds oddly comforting.
```

#### Planned Interactions

| Turn | Action | Target NPC | Expected Outcome | Systems Tested |
|------|--------|-----------|-----------------|----------------|
| 1 | `complete_quest` | Elara | Deliver Port Harbor response. Elara is pleased. | Quest completion, relationship (+10), DM rule #5 |
| 2 | `talk_to` | Thorne | Kael mentions his sword needs rehandling. Thorne grudgingly agrees to do it — for the right price. Kael offers to help around the forge instead of gold. | Dialogue, relationship development |
| 3 | `accept_quest` | Thorne | Quest: **"Retrieve Star-Iron Ore"** (fetch). Thorne: "There's ore in the foothills. Ironhold dwarves prize it. Bring me some and I'll fix that broken hilt for free." | Quest generation (fetch type) |
| 4 | `travel_to` | Ironhold foothills | First visit. DM rule #8 triggers (zone discovery lore). | Zone management, DM rule #8, lore update |
| 5 | `investigate` | Mining caves | Kael explores the caves, finds star-iron ore deposits. | Explore quest mechanics |
| 6 | `complete_quest` | Thorne | Return with star-iron. Thorne is genuinely impressed. Fixes the sword AND refuses payment. | Quest completion cascade, relationship (+20), DM rule #5 |
| 7 | `give_gift` | Thorne | Gift: rare ore sample (kept from the caves). Thorne loves it. | Gift system, relationship (+15 gift), tier crossing: Liked → Loved |
| 8 | — | **DM auto-triggers** | **DM Rule #1 fires:** Liked→Loved threshold crossed. DM_NPC_DIRECTIVE: Thorne offers a personal gift — a custom whetstone. DM_LORE_UPDATE: record friendship. DM_CONVERSATION_TRIGGER: Thorne tells Elara about "the first worthy adventurer I've met in years." | DM rules #1, hardcoded threshold rules |
| 9 | `overhear` | Thorne & Elara | Kael overhears Thorne telling Elara about the star-iron retrieval. Elara is intrigued. She asks Thorne what he knows about Kael's past. Thorne says "Doesn't matter where he's been. Matters what he does now." | NPC-to-NPC conversation, player overhearing |
| 10 | `talk_to` | Elara | Elara approaches Kael. More warm than before — Thorne's recommendation carries weight. She mentions a dangerous escort job. | Dialogue, relationship (+5 from Thorne's recommendation) |
| 11 | `accept_quest` | Elara | Quest: **"Escort the Silk Caravan"** (escort). Through Bandit's Pass. High risk, high reward. | Quest generation (escort type) |

#### Session 2 End State

```
Relationships:
  Thorne:  Liked → Loved (+47 total: quests, gifts, threshold bonus)
  Elara:   Liked → Liked (+19 total)
  Zephyr:  Neutral (+3)

Active Quests:
  - "Escort the Silk Caravan" (Elara, escort)

DM State:
  - 1 hardcoded rule fired (#1: relationship threshold)
  - 7 observations logged
  - 1 active arc created: "The Blacksmith's Legacy" (tension: 0.1)
  - DM_CONVERSATION_TRIGGER fired once (Thorne → Elara)
  - DM_LORE_UPDATE: "Kael earns Thorne's trust"
  - DM_NPC_DIRECTIVE: Thorne offers gift
  - World conditions: []
  - Tension: npc:Thorne 0.1, world:overall 0.05
```

---

### Session 3 — "Blood on the Pass"

**Chapter Title:** *The Cost of Failure*

> The escort quest goes wrong. Kael fails to protect the caravan. Elara loses inventory. Trust shatters. The DM cascades penalties across multiple NPCs and factions. This session is the crucible — designed to test every failure pathway.

#### Opening

```
Dawn. The silk caravan waits at the village gate. Three wagons, six 
guards, and a driver who won't stop talking about his grandchildren. 
Elara has invested heavily in this shipment. She hands Kael a sealed 
letter. "If anything happens to these goods, I lose more than gold. 
I lose my network's trust. Don't let me down."

The pass is narrow. The cliffs are high. Somewhere up there, the 
Bandit King's men are watching.
```

#### Planned Interactions

| Turn | Action | Target NPC | Expected Outcome | Systems Tested |
|------|--------|-----------|-----------------|----------------|
| 1 | `travel_to` | Bandit's Pass | The caravan enters the pass. | Zone change |
| 2 | `investigate` | Suspicious tracks | Kael spots bandit scouts but too late. | Explore mechanics |
| 3 | `fail_quest` | "Escort the Silk Caravan" | **DELIBERATE FAILURE.** Bandits ambush the caravan. Two wagons lost. Driver injured. The silk is gone. | Quest failure cascade |
| 4 | — | **DM cascade fires** | **DM Rule #6:** Quest failed. DM_RELATIONSHIP_OVERRIDE: Elara -25, Merchants Guild -10. DM_NPC_DIRECTIVE: Elara "express_disappointment" — cold, wounded, professional distance. DM_CONVERSATION_TRIGGER: Elara tells Thorne "I trusted him." Tension spikes. | DM rules #6, #3 (if Disliked threshold crossed), relationship cascade, tension system |
| 5 | `talk_to` | Elara | Kael tries to explain. Elara cuts him off: "I don't need explanations. I need results." Prices go up. Warmth is gone. | Dialogue with DM directive active (Elara cold), relationship loss |
| 6 | `overhear` | Elara & Thorne | Elara and Thorne argue. Thorne defends Kael ("He's not a bad sort"). Elara: "You didn't just lose three wagons of silk." Their own relationship is strained. | NPC-to-NPC conversation with relationship context |
| 7 | `travel_to` | Port Harbor | Kael goes to the harbor to find information about the bandits. Seeks out contacts who might know the Bandit King's location. | Zone change, lore investigation |
| 8 | `ask_about` | Harbor contacts | Kael learns the Bandit King was once a noble — Lord Aldric's bastard son. The raids are personal, not just profit. | Lore discovery, deep lore |
| 9 | `accept_quest` | Thorne (via message) | Quest: **"Clear the Wolf Den"** (kill). Thorne sent word — wolves are threatening the village. A chance for Kael to redeem himself. | Quest generation (kill type), relationship recovery path |
| 10 | `complete_quest` | Thorne | Kael returns with wolf pelts. Thorne accepts them silently. The warmth isn't back, but the door isn't closed either. | Quest completion, relationship (+10), partial recovery |

#### Session 3 End State

```
Relationships:
  Thorne:  Loved → Liked (dropped from fallout, partially recovered: net -5)
  Elara:   Liked → Disliked (catastrophic drop: -25 quest fail, -10 faction)
  Zephyr:  Neutral (+3)

Active Quests:
  - None

DM State:
  - DM Rule #6 fired (quest failure cascade)
  - DM Rule #3 condition checked (Elara: Liked→Disliked triggers hardcoded rule)
  - DM_RELATIONSHIP_OVERRIDE fired (multi-NPC cascade)
  - DM_NPC_DIRECTIVE active on Elara: "express_disappointment"
  - DM_CONVERSATION_TRIGGER fired (Elara→Thorne)
  - Tension SPIKE: npc:Elara 0.8 (threshold exceeded!)
  - Tension threshold exceeded → DM force-triggered
  - DM_WORLD_EVENT emitted: "Bandit Activity Increases" (severity: moderate)
  - Arc "The Blacksmith's Legacy" tension: 0.4
  - 18 total observations, pattern detection running
  - Possibly 1st compiled rule: "Failed escort quest hostility cascade"
  - World conditions: ["bandit_activity_elevated"]
```

---

### Session 4 — "The Wizard's Price"

**Chapter Title:** *Knowledge and Sacrifice*

> Seeking magical aid to understand the Bandit King's true motives, Kael turns to Zephyr. The wizard demands proof of worthiness before sharing his knowledge. This session explores Zephyr's character arc, magical lore, and the deeper mysteries of the realm.

#### Opening

```
Two weeks since the pass. Kael has avoided Elara's cart. The village 
gossips. Thorne treats him normally — or close to it — but something 
has shifted. Trust, once freely given, now has to be earned back.

The tower on the hill glows brighter than usual tonight. Zephyr's 
raven, Shadow, has been watching Kael for days. It's unsettling. 
Time to find out what the wizard wants.
```

#### Planned Interactions

| Turn | Action | Target NPC | Expected Outcome | Systems Tested |
|------|--------|-----------|-----------------|----------------|
| 1 | `talk_to` | Zephyr | Kael asks about the Bandit King. Zephyr says "You seek to fight a shadow without understanding the light that casts it." Riddles. | Dialogue, lore hooks |
| 2 | `accept_quest` | Zephyr | Quest: **"Retrieve the Sealed Tome"** (explore). Zephyr: "In the ruins beneath Shadowfen, there is a tome. It contains records from before the Great War. The Bandit King's true identity is within." | Quest generation (explore type) |
| 3 | `travel_to` | Shadowfen Swamp | First visit. DM rule #8 triggers (zone discovery). Dark, treacherous, will-o'-wisps. | Zone change, DM rule #8, environmental storytelling |
| 4 | `investigate` | Ancient ruins | Kael discovers pre-Great War archives. Finds the tome — and evidence that the Bandit King is Aldric's unrecognised heir, seeking revenge for his father's defeat. | Explore mechanics, lore discovery |
| 5 | `complete_quest` | Zephyr | Return with the tome. Zephyr reads it, goes pale. "This changes everything." | Quest completion, relationship (+20), tier: Neutral→Liked |
| 6 | `ask_about` | Zephyr | Topic: The Great War and Aldric. Zephyr reveals he served as Aldric's court wizard before the war. He knew the bastard son as a boy. | Deep lore retrieval, relationship (+5) |
| 7 | — | **DM auto-triggers** | Quest has narrative significance. DM_QUEST_SUGGESTION: follow-up quest "The Heir's Grievance". DM_LORE_UPDATE: record discovery of Bandit King's identity. | DM rules #12, lore update, quest suggestion |
| 8 | `accept_quest` | Zephyr | Quest: **"Gather Shadowfen Herbs"** (collection). Zephyr needs potion ingredients. Secondary quest to keep testing. | Quest generation (collection type) |
| 9 | `complete_quest` | Zephyr | Quick collection turn-in. | Quest completion |
| 10 | `give_gift` | Zephyr | Gift: ancient grimoire fragment (found in Shadowfen). Zephyr is delighted. | Gift system, relationship (+15), tier: Liked→Loved |
| 11 | — | **DM triggers** | Liked→Loved threshold. DM_NPC_DIRECTIVE: Zephyr offers access to restricted section. DM_CONVERSATION_TRIGGER: Zephyr discusses the Bandit King threat with Thorne. | DM rule #1, NPC-to-NPC |
| 12 | `talk_to` | Thorne | Thorne mentions Zephyr spoke to him about the Bandit King. Thorne: "If there's a war coming, I'll need more steel. You still handy with that sword?" Offer to help. | Relationship recovery dialogue |

#### Session 4 End State

```
Relationships:
  Thorne:  Liked → Liked (recovering slowly: +5 from shared concern)
  Elara:   Disliked (unchanged — Kael hasn't approached her)
  Zephyr:  Neutral → Loved (+40: quests, gifts, dialogue)

Active Quests:
  - "The Heir's Grievance" (Zephyr-suggested, not yet accepted)

DM State:
  - DM rule #8 fired twice (Shadowfen + Crystal Citadel discovery)
  - DM rule #12 fired (narratively significant quest completion)
  - DM_QUEST_SUGGESTION: "The Heir's Grievance"
  - DM_LORE_UPDATE: "Bandit King's True Identity"
  - DM_NPC_DIRECTIVE on Zephyr: offers restricted knowledge
  - DM_CONVERSATION_TRIGGER: Zephyr→Thorne about Bandit King
  - Arc "The Blacksmith's Legacy": tension 0.3
  - Arc "The Mage's Burden" created (Zephyr's war secrets)
  - Tension: npc:Elara 0.6 (decaying from 0.8), world:overall 0.3
  - 28 total observations
  - Possibly 2nd compiled rule detected
  - World conditions: ["bandit_activity_elevated"]
```

---

### Session 5 — "Legends and Reckonings"

**Chapter Title:** *What Was Forged in Fire*

> Everything converges. Kael confronts the Bandit King, resolves Thorne's arc at legendary level, earns back Elara's trust, and helps Zephyr confront his past. All arcs reach resolution. All relationship tiers are tested. The DM's compiled rules fire automatically. The chronicle reaches its climax.

#### Opening

```
The village is different now. Word has spread — the Bandit King is 
mustering for a major raid. Not just caravans this time. Villages. 
The road to Ironhold is cut. Port Harbor has hired mercenaries. 

Thorne is forging weapons day and night. Elara's cart is empty — she's 
using her trade network to bring in supplies. Zephyr's tower glows 
like a beacon. They're all preparing. And they're all looking at Kael.

*You came here as a deserter running from a war. Maybe it's time you 
fought in one worth fighting.*
```

#### Planned Interactions

| Turn | Action | Target NPC | Expected Outcome | Systems Tested |
|------|--------|-----------|-----------------|----------------|
| 1 | `talk_to` | Elara | Kael approaches Elara for the first time since the pass. Offers to help coordinate defense. Elara is cold but pragmatic. "Can you fight?" "Yes." "Then fight." | Relationship recovery path, DM directive (Elara still cold) |
| 2 | `accept_quest` | Thorne | Quest: **"The Final Forge"** (legendary, multi-objective). Thorne: "I've been saving the last of my star-iron for something that matters. A blade to turn the tide. But I need materials only found in the Scarred Wastes." | Legendary quest, DM rule (legendary unlock after 5 completions) |
| 3 | `accept_quest` | Elara | Quest: **"Smuggle Weapons Through the Pass"** (escort/fetch). Elara needs weapons moved to the village militia. Kael must escort through the now-dangerous pass. | Quest generation, relationship recovery opportunity |
| 4 | `complete_quest` | Elara | Kael successfully escorts the weapons. No losses this time. Elara: "You carried them through. That's… more than I expected." Relationship begins recovery. | Quest completion, relationship (+15), DM rule #5, recovery |
| 5 | `talk_to` | Elara | Quiet moment. Kael apologises — not excuses, just apology. Elara: "I lost three wagons. But you came back. That counts for something." Disliked→Neutral recovery. | Relationship recovery dialogue, DM event (threshold crossing back to Neutral) |
| 6 | `travel_to` | Scarred Wastes | Dangerous journey. DM rule #8 (first entry). Unstable magic, ancient ruins. | Zone change, DM rule #8 |
| 7 | `investigate` | Ruins of Old Aldric | Kael finds the materials Thorne needs — and the Bandit King's war banner. He's planning to attack the village. | Explore, lore discovery |
| 8 | `complete_quest` | Thorne | Return with materials. Thorne forges the blade. "I've made a hundred swords. This one matters." **Arc "The Blacksmith's Legacy" advances to near-resolution.** | Quest completion, arc advancement, relationship (+25) |
| 9 | `give_gift` | Thorne | Gift: Masterwork hammer (purchased from Ironhold). Thorne is overwhelmed. "You… you shouldn't have. This is Ironforge craft." Loved→Adored threshold. | Gift system, tier: Loved→Adored, DM rule #4 |
| 10 | — | **DM cascade — maximum** | **DM Rule #4:** Adored threshold. DM_NPC_DIRECTIVE: Thorne names Kael as his chosen successor. DM_LORE_UPDATE: "Thorne's Greatest Apprentice" recorded. DM_RELATIONSHIP_OVERRIDE: Merchants Guild +10 (Thorne's endorsement). DM_CONVERSATION_TRIGGER: Thorne announces to village. | All DM relationship rules, arc resolution, lore, cascade |
| 11 | `accept_quest` | Zephyr | Quest: **"Confront the War Ghosts"** (dialogue). Zephyr needs Kael to accompany him to the old war battlefield. He must face what he did during the Mage Purge. | Quest generation (dialogue type), deep narrative |
| 12 | `complete_quest` | Zephyr | At the battlefield, Zephyr confronts his past. He reveals he was the one who exposed the Church's corruption but couldn't save the mages who died. Kael: "You couldn't save everyone. Neither could I." **Arc "The Mage's Burden" resolves.** | Quest completion, arc resolution, relationship (+25), Loved→Adored possible |
| 13 | `give_gift` | Elara | Gift: exotic spices from Port Harbor (remembered from their first conversation). Elara: "You remembered." Neutral→Liked recovery. | Gift system, relationship recovery |
| 14 | `talk_to` | All NPCs | Final conversations. Thorne at peace. Zephyr unburdened. Elara warm again. The village is preparing for the Bandit King's attack. Kael decides to stay and fight. | Final relationship checks, dialogue |

#### Session 5 End State

```
Relationships:
  Thorne:  Adored (+80: legendary trust, named successor)
  Elara:   Liked (+25: recovered from Disliked through redemption arc)
  Zephyr:  Adored (+75: shared burden, confronted past together)

Completed Quests:
  Session 1: 2 (collection, fetch)
  Session 2: 3 (fetch, fetch, escort-accepted)
  Session 3: 2 (escort-FAILED, kill)
  Session 4: 3 (explore, collection, collection)
  Session 5: 5 (legendary, escort, fetch, dialogue, gift-quest)
  Total: 15 quests across all 6 types

DM State:
  - All 10 hardcoded rules fired at least once
  - All 7 LLM-judged rule categories triggered
  - 3-5 rules auto-compiled through pattern detection
  - 2 arcs created, both resolved
  - Multiple world events spawned
  - Tension peaked at 0.8 and resolved
  - 50+ total observations logged

Narrative Arcs Resolved:
  - "The Blacksmith's Legacy" — Thorne passes his craft to a worthy successor
  - "The Mage's Burden" — Zephyr confronts his war guilt
  - "The Merchant's Redemption" — (Elara's arc, implicit) Trust broken and rebuilt
```

---

## 7. Narrative Chronicle Format

### Output Structure

The simulation produces a single document: **"The Chronicle of Kael Ashwood"**

```
THE CHRONICLE OF KAEL ASHWOOD
═════════════════════════════

    A record of wanderings in the realm,
    being an account of fire, steel, and
    the weight of a soldier's debt.

    ──── Book the First ────

    CHAPTER I: THE WEIGHT OF THE ROAD
    CHAPTER II: FIRE AND STEEL
    CHAPTER III: BLOOD ON THE PASS
    CHAPTER IV: THE WIZARD'S PRICE
    CHAPTER V: WHAT WAS FORGED IN FIRE

    ──── Appendices ────

    APPENDIX A: System Test Coverage
    APPENDIX B: DM Rules Compiled
    APPENDIX C: Relationship Arc Graphs
```

### Prose Style Examples

#### Example: First Meeting with Thorne

**Raw system events:**
```
DIALOGUE_START: player→Thorne
NPC_RESPONSE: "Hmph. Another customer. State your business quickly..."
RELATIONSHIP_CHANGE: Thorne +0 (Neutral)
LORE_QUERY: ironhold + blacksmithing → 2 results returned
```

**Narrative prose:**
```
The forge was hotter than any battlefield Kael had walked. Heat rolled 
off the coals in waves, and the smith — a stocky dwarf with arms like 
oak branches — didn't look up from his work.

"Hmph." The hammer rang twice more. "Another customer. State your 
business quickly — I've got a blade to finish before it cools."

Kael rested a hand on his sword's chipped pommel. "This needs 
rehandling."

The dwarf's eyes flicked to the blade. One eyebrow rose a fraction. 
"Cheapest blade I've seen in a month. Military issue." A pause. The 
hammer stopped. "Deserter's sword, is it?"

The air between them went cold despite the forge. Kael said nothing.

"Didn't think so." The dwarf went back to hammering. "Name's Thorne. 
Come back tomorrow. We'll talk prices."
```

#### Example: Quest Failure

**Raw system events:**
```
QUEST_FAILED: "Escort the Silk Caravan"
DM_RELATIONSHIP_OVERRIDE: Elara -25, Merchants Guild -10
DM_NPC_DIRECTIVE: Elara express_disappointment
DM_CONVERSATION_TRIGGER: Elara→Thorne about player
TENSION_UPDATE: npc:Elara → 0.8
```

**Narrative prose:**
```
The first arrow struck the lead wagon's canvas with a sound like a 
snapped harp string. Then the cliffs erupted.

Kael drew his sword and put his back against the second wagon, but 
there were too many. Bandits poured down the scree slopes like water 
through a broken dam — organised, military-precise. Not brigands. 
Soldiers.

The driver screamed. The horses bolted. Silk bales tumbled into the 
gorge like colourful corpses.

By the time Kael fought his way to Elara's lead wagon, it was gone. 
Cut loose and dragged away down a side path he hadn't seen. Two of 
the six guards lay still. The third was pressing a bloody cloth 
against his arm and weeping.

*Not again. Not again.*

He stood in the pass with his sword dripping and his hands shaking 
and three wagons worth of Elara's trust scattered across the rocks.
```

### Chapter Word Count Targets

| Chapter | Target Words | Coverage |
|---------|-------------|----------|
| I: The Weight of the Road | 3,000 - 4,000 | Introductions, basic systems |
| II: Fire and Steel | 4,000 - 5,000 | Quest chains, relationships, NPC-to-NPC |
| III: Blood on the Pass | 5,000 - 6,000 | Failure, DM cascades, tension, recovery |
| IV: The Wizard's Price | 4,000 - 5,000 | Exploration, lore, magical quests |
| V: What Was Forged in Fire | 6,000 - 8,000 | Climax, all systems, resolution |
| **Total** | **22,000 - 28,000** | **Complete chronicle** |

---

## 8. System Test Matrix

### Quest Type Coverage

| Quest Type | Session | Quest Name | NPC | Outcome |
|-----------|---------|-----------|-----|---------|
| Collection | 1 | "Gather Coal for the Forge" | Thorne | Success |
| Fetch/Delivery | 1 | "Deliver Message to Port Harbor" | Elara | Success |
| Fetch | 2 | "Retrieve Star-Iron Ore" | Thorne | Success |
| Escort | 3 | "Escort the Silk Caravan" | Elara | **Failure** |
| Kill | 3 | "Clear the Wolf Den" | Thorne | Success |
| Explore | 4 | "Retrieve the Sealed Tome" | Zephyr | Success |
| Collection | 4 | "Gather Shadowfen Herbs" | Zephyr | Success |
| Dialogue | 5 | "Confront the War Ghosts" | Zephyr | Success |
| Legendary | 5 | "The Final Forge" | Thorne | Success |
| Escort | 5 | "Smuggle Weapons Through the Pass" | Elara | Success (redemption) |

### Relationship Tier Coverage

| Tier | Achieved With | Session | How |
|------|--------------|---------|-----|
| Hated | None (Kael never goes this far) | — | Design decision: Kael is pragmatic, not cruel |
| Disliked | Elara | 3 | Failed escort quest |
| Neutral | Elara (recovery), Zephyr (start), Thorne (start) | 1, 4 | Starting state or recovery |
| Liked | Thorne, Elara | 1-2 | Quest rewards and positive dialogue |
| Loved | Thorne, Zephyr | 2, 4 | Multiple quests + gifts |
| Adored | Thorne, Zephyr | 5 | Legendary trust, shared burdens |

### DM Trigger Rule Coverage

| Rule | Trigger | Session | How Triggered |
|------|---------|---------|---------------|
| #1 | RELATIONSHIP_CHANGE Liked→Loved | 2, 4 | Thorne and Zephyr reach Loved |
| #2 | RELATIONSHIP_CHANGE Neutral→Disliked | 3 | Elara drops to Disliked after quest failure |
| #3 | RELATIONSHIP_CHANGE Disliked→Hated | — | Not triggered (Kael recovers before this) |
| #4 | RELATIONSHIP_CHANGE into Adored | 5 | Thorne and Zephyr reach Adored |
| #5 | QUEST_COMPLETED any | 1-5 | Every successful quest completion |
| #6 | QUEST_FAILED any | 3 | Escort caravan failure |
| #7 | 3+ quests in same zone | 2, 5 | Multiple village quests completed |
| #8 | PLAYER_ENTER_ZONE first time | 2, 4, 5 | Ironhold, Shadowfen, Scarred Wastes |
| #9 | FACTION_CHANGE crosses -50 | — | Not triggered (Merchants Guild drops but not to -50) |
| #10 | WORLD_EVENT severity major | 3-4 | Bandit activity escalation |
| #11 | DIALOGUE_MESSAGE ambiguous | 1, 3 | Kael's guarded statements about his past |
| #12 | QUEST_COMPLETED narrative significance | 4, 5 | Bandit King identity, final forge |
| #13 | QUEST_FAILED cascading consequences | 3 | Caravan failure affects multiple NPCs and factions |
| #14 | NPC_STATE_CHANGE dramatic shift | 3 | Elara's mood shifts after betrayal |
| #15 | WORLD_EVENT intersects arcs | 5 | Bandit King raid intersects all arcs |
| #16 | RELATIONSHIP_CHANGE unusual pattern | 3 | Rising with Thorne while falling with Elara |
| #17 | NPC-to-NPC conversation significant | 2, 3 | Thorne↔Elara conversations about Kael |

### DM Directive Type Coverage

| Directive Type | Session | Trigger Context |
|---------------|---------|-----------------|
| DM_QUEST_SUGGESTION | 4, 5 | Follow-up quests after narratively significant completions |
| DM_NPC_DIRECTIVE | 2, 3, 4, 5 | Threshold crossings, disappointment, gifts |
| DM_WORLD_EVENT | 3, 4 | Bandit activity, zone events |
| DM_CONVERSATION_TRIGGER | 2, 3, 4, 5 | NPCs discussing Kael's actions |
| DM_LORE_UPDATE | 2, 4, 5 | Friendship records, identity discoveries |
| DM_RELATIONSHIP_OVERRIDE | 3, 5 | Cascading reputation changes |
| DM_RULE_COMPILED | 3-5 | Auto-compiled rules from observation patterns |

### Subsystem Coverage

| Subsystem | File | Tested In | How |
|-----------|------|-----------|-----|
| Dialogue Engine | `npc_dialogue.py` | Every turn | Every NPC conversation |
| Relationship Tracking | `relationship_tracking.py` | All sessions | Gains, losses, threshold crossings, gifts, quests |
| Lore System (RAG) | `lore_system.py` | Sessions 1, 4, 5 | Lore queries, NPC knowledge filtering, lore discovery |
| Quest Generation | `quest_generator.py` | All sessions | All 6 quest types generated and completed/failed |
| NPC-to-NPC Conversations | `npc_conversation.py` | Sessions 2, 3, 4, 5 | Overhearing, relationship-aware topics |
| NPC State Manager | `npc_state_manager.py` | All sessions | Zone changes, world state, event emission |
| Event System | `event_system.py` | All sessions | Event broadcasting and subscription |
| Dungeon Master | `dungeon_master.py` | Sessions 2-5 | DM evaluation, directive emission |
| DM Rule Engine | `dm_rule_engine.py` | Sessions 3-5 | Rule compilation, matching, auto-activation |
| Inventory Validation | `inventory_validation.py` | Sessions 2-5 | Item acquisition, gift giving, quest rewards |
| Voice Synthesis | `voice_synthesis.py` | All sessions | NPC voice synthesis during dialogue |
| API Server | `api_server.py` | All sessions | REST endpoints, WebSocket events |

---

## 9. Simulation Loop Specification

### Pseudocode

```python
async def run_simulation(config: SimulationConfig):
    chronicle = Chronicle(title="The Chronicle of Kael Ashwood")
    world = initialize_world(config)
    player_llm = PlayerLLM(config.player_model, config.player_prompt)
    narrator_llm = NarratorLLM(config.narrator_model, config.narrator_prompt)
    
    for session_num, session_plan in enumerate(config.sessions, 1):
        chronicle.begin_chapter(session_plan.chapter_title)
        world.load_session_state(session_num)
        context = PlayerContext(world.get_state(), session_plan.opening)
        
        for turn_num in range(session_plan.max_turns):
            # 1. Build available actions from world state
            actions = world.get_available_actions(context)
            
            # 2. Player LLM decides action and generates dialogue
            player_response = await player_llm.decide(
                context=context,
                available_actions=actions,
                session_plan=session_plan,
            )
            
            # 3. Execute action through game systems
            results = await world.execute_action(player_response)
            # results contains: NPC dialogue, DM directives, relationship
            # changes, quest updates, lore reveals, events fired
            
            # 4. Update player context
            context.update(player_response, results)
            
            # 5. Generate narrative prose from results
            prose = await narrator_llm.narrate(
                chapter=session_plan.chapter_title,
                events=results.all_events,
                previous_prose=chronicle.get_recent_prose(),
            )
            chronicle.append_prose(prose)
            
            # 6. Log system-level data (parallel to prose)
            chronicle.log_system_events(results.system_log)
            
            # 7. Check for session-ending conditions
            if session_plan.is_complete(context):
                break
        
        chronicle.end_chapter()
        world.save_session_state(session_num)
    
    # Generate appendices
    chronicle.appendix_a = generate_test_coverage_report(world)
    chronicle.appendix_b = generate_dm_rules_report(world)
    chronicle.appendix_c = generate_relationship_graph(world)
    
    chronicle.save("chronicle_of_kael_ashwood.md")
```

### Turn Flow Diagram

```
┌──────────────┐
│ World State   │
│ - NPCs        │
│ - Quests      │
│ - Location    │
│ - Events      │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌─────────────────────┐
│ Build         │────►│  Player LLM          │
│ Available     │     │  (Kael's personality │
│ Actions       │     │   + world state +    │
└──────────────┘     │   recent events)     │
                     └──────────┬──────────┘
                                │
                                ▼  JSON action
                     ┌──────────────────────┐
                     │  Action Router        │
                     │  talk_to ──► dialogue │
                     │  travel  ──► zones    │
                     │  quest   ──► quests   │
                     │  gift    ──► relations│
                     │  ask     ──► lore     │
                     │  investigate → explore│
                     └──────────┬───────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              ┌──────────┐ ┌─────────┐ ┌────────┐
              │ NPC      │ │ Quest   │ │ DM     │
              │ Dialogue │ │ System  │ │ Engine │
              └────┬─────┘ └────┬────┘ └───┬────┘
                   │            │          │
                   └────────────┼──────────┘
                                │
                                ▼  Collect all results
                     ┌──────────────────────┐
                     │  Result Aggregator    │
                     │  - NPC responses      │
                     │  - Relationship deltas│
                     │  - DM directives      │
                     │  - Quest state changes│
                     │  - Lore reveals       │
                     │  - Events fired       │
                     └──────────┬───────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼                       ▼
              ┌──────────────┐       ┌──────────────┐
              │ Update Player│       │ Narrator LLM │
              │ Context      │       │ (prose gen)  │
              └──────────────┘       └──────┬───────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │ Chronicle     │
                                    │ (prose + log) │
                                    └──────────────┘
```

### Session Boundary Logic

A session ends when any of these conditions are met:

1. **Turn limit reached.** `max_turns` exhausted (configurable, default 14 per session).
2. **Arc milestone.** A planned arc milestone is achieved (relationship threshold, quest completion, etc.).
3. **No available actions.** All NPCs are unavailable, all quests are complete or failed.
4. **Manual trigger.** The simulation config explicitly marks a session end point.

Between sessions:

```python
# Save all state
world.save_session_state(session_num)
dm.save_state()
rule_engine.save_rules()
relationship_tracker.save()

# Simulate time passage
world.advance_time(hours=session_gap_hours)

# Apply tension decay
dm.apply_tension_decay(hours=session_gap_hours)

# Generate chapter break prose
prose = await narrator_llm.narrate_chapter_break(
    chapter_summary=chronicle.get_chapter_summary(session_num),
    gap_description=session_gap_description,
)
chronicle.append_prose(prose)
```

### Error Handling

| Failure | Response |
|---------|----------|
| LLM timeout | Retry once. If still fails, Kael "falls silent" and `wait` action is used. |
| NPC dialogue fails | Log error. Kael receives "The NPC stares at you blankly." |
| Quest generation fails | Skip quest. Adjust session plan to use existing quests. |
| DM directive fails | Log error. Continue without DM consequences for that event. |
| Invalid action from player LLM | Retry with prompt: "That action is not available. Choose from: {actions}" |
| Narrative LLM fails | Use raw event descriptions as fallback prose. |

---

## 10. Configuration

### SimulationConfig

```python
@dataclass
class SimulationConfig:
    # Player LLM
    player_model: str = "llama3.2:3b"
    player_backend: str = "ollama"
    player_temperature: float = 0.8      # Higher for more varied personality
    player_max_tokens: int = 200         # Player responses are brief

    # Narrator LLM
    narrator_model: str = "llama3.2:3b"
    narrator_backend: str = "ollama"
    narrator_temperature: float = 0.7    # Creative but consistent
    narrator_max_tokens: int = 500       # 2-4 paragraphs per turn

    # Simulation
    max_turns_per_session: int = 14
    max_context_turns: int = 20          # Rolling window for player context
    seed: Optional[int] = 42             # For reproducibility
    
    # Output
    chronicle_output_path: str = "chronicle_of_kael_ashwood.md"
    system_log_path: str = "simulation_system_log.json"
    prose_only: bool = False             # If True, skip system annotations
    
    # Session gaps (simulated hours between sessions)
    session_gap_hours: List[int] = field(default_factory=lambda: [
        168,   # 1 week between sessions 1-2
        48,    # 2 days between sessions 2-3
        336,   # 2 weeks between sessions 3-4
        168,   # 1 week between sessions 4-5
    ])
    
    # DM
    dm_enabled: bool = True
    
    # Voice
    voice_enabled: bool = False          # Off by default for simulation speed
    voice_provider: str = "edge_tts"
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIM_PLAYER_MODEL` | `llama3.2:3b` | LLM model for Kael's decisions |
| `SIM_NARRATOR_MODEL` | `llama3.2:3b` | LLM model for narrative prose |
| `SIM_SEED` | `42` | Random seed for reproducibility |
| `SIM_MAX_TURNS` | `14` | Max turns per session |
| `SIM_CHRONICLE_PATH` | `chronicle_of_kael_ashwood.md` | Output file path |
| `SIM_VOICE_ENABLED` | `false` | Enable voice synthesis |
| `SIM_DM_ENABLED` | `true` | Enable Dungeon Master |

---

## 11. Demo Script

### `demo_player_simulation.py`

A comprehensive demo that runs the full simulation.

#### Usage

```bash
# Full 5-session simulation
python demo_player_simulation.py

# Single session
python demo_player_simulation.py --session 1

# Quick test (3 turns per session, abbreviated)
python demo_player_simulation.py --quick

# Custom output path
python demo_player_simulation.py --output my_chronicle.md

# Reproducible run
python demo_player_simulation.py --seed 42

# Verbose system logging
python demo_player_simulation.py --verbose
```

#### Demo Scenarios

The demo runs through all 5 sessions sequentially, producing the complete chronicle. At the end, it prints:

```
══════════════════════════════════════════════════════
 THE CHRONICLE OF KAEL ASHWOOD — Simulation Complete
══════════════════════════════════════════════════════

 Sessions:          5
 Total Turns:       67
 Total Words:       24,312

 Quests Completed:  14/15 (1 failed)
 Quest Types Used:  6/6 (kill, fetch, explore, escort, collection, dialogue)

 NPCs Interacted:   3
 Relationships:
   Thorne:  Neutral → Adored    (arc: resolved)
   Elara:   Neutral → Disliked → Liked (arc: redemption)
   Zephyr:  Neutral → Adored    (arc: resolved)

 DM Events:
   Rules Compiled:     3
   Directives Issued:  23
   Arcs Created:       2 (both resolved)
   World Events:       4
   Observations:       52

 Chronicle saved to: chronicle_of_kael_ashwood.md
 System log saved to: simulation_system_log.json
══════════════════════════════════════════════════════
```

---

## 12. File Structure

### New Files

| File | Lines | Description |
|------|-------|-------------|
| `player_simulation.py` | ~900 | Core simulation engine: PlayerLLM, NarratorLLM, SimulationEngine, ChronicleStore, session plans |
| `static/chronicle.html` | ~1200 | Live-updating single-page chronicle viewer (vanilla HTML/CSS/JS) |
| `PLAIYER_CHARACTER.md` | This file | Player character and simulation design |

### Generated at Runtime

| File | Description |
|------|-------------|
| `chronicle_data/chronicle_state.json` | Full chronicle state (all turns, metadata) |
| `chronicle_data/session_N.json` | Per-session turn data |

### Modified Files

| File | Change Description |
|------|-------------------|
| `api_server.py` | +9 endpoints: chronicle page, WebSocket, simulation control, state APIs |

### How to Run

```bash
# Terminal 1: Start the server
python api_server.py

# Browser: Open the chronicle
open http://localhost:8000/chronicle

# Click "Begin Chronicle" in the browser, or via API:
curl -X POST http://localhost:8000/api/simulation/start
```

---

## 13. Web Chronicle Architecture

### Live Update Flow

```
User clicks "Begin Chronicle"
        │
        ▼
POST /api/simulation/start
        │
        ▼
SimulationEngine.run_simulation() starts as background task
        │
        ├── For each turn:
        │     1. PlayerLLM.decide() → Kael's action
        │     2. Execute action through game subsystems
        │     3. NarratorLLM.narrate() → prose
        │     4. ChronicleStore.add_turn()
        │     5. WebSocket broadcast → browser
        │
        ▼
Browser receives { type: "chronicle_update", turn: {...} }
        │
        ├── Appends prose to article (fade-in animation)
        ├── Updates relationship bars
        ├── Updates active quests
        ├── Updates location and stats
        └── Auto-scrolls to bottom
```

### WebSocket Protocol

| Message Type | Direction | Payload |
|-------------|-----------|---------|
| `chronicle_update` | Server→Client | Full turn data (prose, dialogue, DM events, relationships, quests) |
| `session_start` | Server→Client | Session number, title, opening prose |
| `session_end` | Server→Client | Session number |
| `simulation_start` | Server→Client | Total sessions |
| `simulation_complete` | Server→Client | Final stats |
| `ping` | Client→Server | Keep-alive |
| `pong` | Server→Client | Keep-alive response |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chronicle` | GET | Serve the chronicle HTML page |
| `/ws/chronicle` | WebSocket | Live event stream |
| `/api/chronicle/state` | GET | Full state snapshot (all turns) |
| `/api/chronicle/turns` | GET | Turn summaries list |
| `/api/chronicle/turn/{id}` | GET | Single turn detail |
| `/api/simulation/start` | POST | Start simulation (runs in background) |
| `/api/simulation/pause` | POST | Pause simulation |
| `/api/simulation/resume` | POST | Resume simulation |
| `/api/simulation/status` | GET | Current status |

### Expandable Detail Panels

The chronicle page renders prose first. Inline badges appear next to events:

| Badge | Color | Expands to show |
|-------|-------|-----------------|
| `show conversation` | Blue | Full NPC dialogue transcript (player + NPC lines) |
| `DM event` | Purple | DM directive type, reasoning, rule matched |
| `quest` | Green | Quest card: name, type, objectives, status, rewards |
| `relationship` | Amber | Before/after relationship scores, threshold crossings |

### Frontend Stack

- **Vanilla HTML + CSS + JS** — single file, no build tools, no npm
- **WebSocket** for live updates (reuses existing event system)
- **Fetch API** for initial state hydration on page refresh
- **CSS animations** for fade-in prose
- **Responsive layout** — two-column desktop, stacked mobile

---

## Appendix A: Complete Relationship Arc Timeline

```
Session 1                    Session 2                    Session 3
─────────                    ─────────                    ─────────
Thorne:  ──── Neutral ────► Liked ───────────────► Loved ────┐
                                                              │ (drop)
Elara:   ──── Neutral ────► Liked ───────────────► Liked ────┤
                                                     ▼        │
                                                  Disliked ◄──┘
Zephyr:  ──── Neutral ────► Neutral ─────────────► Neutral

Session 4                    Session 5
─────────                    ─────────
Thorne:  ◄── Liked ◄──────────────────► Loved ────► Adored
Elara:   ◄── Disliked ────────────────► Neutral ──► Liked
Zephyr:  ◄── Neutral ────────────────► Liked ────► Adored
```

---

## Appendix B: Quest Completion Timeline

```
Session 1                    Session 2
─────────                    ─────────
Q1:  "Gather Coal"           Q3:  "Retrieve Star-Iron" 
     ✓ Collection / Thorne         ✓ Fetch / Thorne
Q2:  "Deliver Message"              "Escort Silk Caravan" 
     ✓ Fetch / Elara               (accepted, continues to S3)

Session 3                    Session 4
─────────                    ─────────
Q5:  "Escort Silk Caravan"   Q7:  "Retrieve Sealed Tome"
     ✗ ESCORT FAILED               ✓ Explore / Zephyr
Q6:  "Clear Wolf Den"        Q8:  "Gather Shadowfen Herbs"
     ✓ Kill / Thorne               ✓ Collection / Zephyr

Session 5
─────────
Q9:  "The Final Forge"
     ✓ Legendary / Thorne
Q10: "Smuggle Weapons"
     ✓ Escort / Elara
Q11: "Confront War Ghosts"
     ✓ Dialogue / Zephyr

Totals: 14 completed, 1 failed = 15 quests across 6 types
```

---

## Appendix C: DM Observation & Rule Compilation Timeline

```
Session 1:  3 observations logged. No patterns.
Session 2:  7 observations (cumulative: 10). Pattern check: no hits at 5+.
Session 3:  8 observations (cumulative: 18).
            Pattern detected: "quest_failed → npc_disappointment" (5+ similar)
            → Rule compiled: "Failed quest hostility cascade"
            → Confidence: 0.91 → AUTO-ACTIVATED
Session 4:  10 observations (cumulative: 28).
            Pattern detected: "quest_completed for same NPC → quest_suggestion" (5+)
            → Rule compiled: "Repeat quest success suggests follow-up"
            → Confidence: 0.88 → PENDING (below 0.9 threshold)
Session 5:  24 observations (cumulative: 52).
            Pattern detected: "relationship Adored → lore_update" (5+)
            → Rule compiled: "Adored relationship creates lore entry"
            → Confidence: 0.93 → AUTO-ACTIVATED
            Pattern detected: "multiple quests in zone → world_event" (5+)
            → Rule compiled: "Zone prosperity from quest completion"
            → Confidence: 0.90 → AUTO-ACTIVATED
            Pending rule from Session 4 approved manually (or auto-approved at 0.88)

Final DM State:
  Active rules:     4 (3 auto-compiled + 1 approved)
  Pending rules:    0
  Total observations: 52
  Rule hit rate:    ~40% (20/52 events matched compiled rules)
```

---

## Appendix D: Narrative Chronicle — Chapter Opening Templates

Each chapter begins with a formatted header and atmospheric opening:

```markdown
# Chapter {N}: {Title}

---

*{Epigraph — a quote from the world's lore, an NPC's words, or a 
proverb from the realm}*

---

{Opening paragraph — 2-3 sentences establishing time, place, mood, 
and Kael's emotional state entering this chapter. Always grounded 
in a sensory detail: a sound, a smell, a quality of light.}

---
```

### Example Epigraphs

| Chapter | Epigraph |
|---------|----------|
| I | *"The road doesn't care where you've been. Only where you're going." — Borderlands proverb* |
| II | *"A sword is only as good as the smith who forged it. And the hand that wields it." — Thorne of Ironhold* |
| III | *"Trust is a caravan. Easy to lose on a mountain pass." — Elara the Merchant* |
| IV | *"The weight of knowledge is heavier than any sword. It cuts deeper, too." — Zephyr the Wizard* |
| V | *"Some fires temper steel. Others burn it to slag. The difference? What you're made of." — Inscription on Thorne's forge* |
