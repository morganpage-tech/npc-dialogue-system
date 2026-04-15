# Player Inventory Validation — Implementation Plan

## Problem

The NPC dialogue system has no player inventory model. When a player says "I give you an opal," the LLM has no information about what the player actually possesses, so it roleplays accepting the item. No validation exists at any layer — not in the prompt, not server-side, not during quest acceptance or gift recording.

## Solution Overview

Add a `player_inventory` data field throughout the stack, inject it into the LLM prompt so the NPC can refuse items in-character, and add server-side validation to enforce it programmatically.

---

## Layer 1 — Data Model

### `npc_state_manager.py` — `PlayerState` dataclass (line 87)

Add `inventory` field:
```python
inventory: Dict[str, int] = field(default_factory=dict)  # item_name -> quantity
```

Update `to_dict()` (line 111) to serialize it:
```python
"inventory": self.inventory,
```

Update `load_state` deserialization to restore inventory from saved data.

### `api_server.py` — Request models

**`GenerateRequest`** (line 62):
```python
player_inventory: Optional[Dict[str, int]] = None
```

**`GameEventRequest`** (line 998):
```python
player_inventory: Optional[Dict[str, int]] = None
```

**`generate_with_game_state()`** (line 698) — add parameter:
```python
player_inventory: Optional[Dict[str, int]] = None
```
Inject into game_state:
```python
if player_inventory:
    game_state["player_inventory"] = player_inventory
```

---

## Layer 2 — System Prompt (LLM Awareness)

### `npc_dialogue.py` — `_build_system_prompt()` (line 158)

After the quest context block (~line 199), inject inventory information:

```
PLAYER'S INVENTORY:
- iron sword x1
- health potion x3

IMPORTANT: The player can only give/trade items they actually possess. If they
claim to offer something NOT listed in their inventory, refuse and point out
they don't have it. Stay in character while doing so.
```

Add a `_format_inventory(inventory: Dict[str, int]) -> str` helper method to format the dict into a bullet list.

---

## Layer 3 — Pre-Generation Validation (Server-Side Guard)

### `api_server.py` — `generate_dialogue()` (line 256)

Before calling `npc.generate_response()` (line 356):

1. Check if `game_state.get("player_inventory")` exists
2. Use regex/keyword matching to detect item-giving phrases in `request.player_input`:
   - Patterns: "give you", "here's a", "take this", "hand you", "i've got you a/an", "brought you"
3. Extract the mentioned item name
4. If the item is NOT in the inventory dict, inject an override into game_state:
   ```python
   game_state["_inventory_override"] = f"The player claims to offer '{mentioned_item}' but they do NOT have it in their inventory. Refuse the offer in character."
   ```
   This is included in the prompt so the NPC refuses naturally in-character, rather than returning a hard error.

### `main.py` — CLI loop (line 415-418)

Apply the same validation logic before calling `active_npc.generate_response()`.

---

## Layer 4 — Quest Acceptance Validation

### `quest_generator.py` — `Quest.accept()` (line 215)

```python
def accept(self, player_inventory: Optional[Dict[str, int]] = None) -> bool:
    if self.status != QuestStatus.AVAILABLE:
        return False
    if self.is_expired():
        return False
    if self.required_items and player_inventory is not None:
        for item in self.required_items:
            if item not in player_inventory or player_inventory[item] <= 0:
                return False
    self.status = QuestStatus.ACTIVE
    self.accepted_at = time.time()
    return True
```

### `quest_generator.py` — `QuestManager.accept_quest()` (~line 909)

Add `player_inventory` parameter and pass it through to `quest.accept()`.

### Callers

- `api_server.py` line 277: pass inventory from game_state
- `main.py` line 397: pass inventory from game_state

---

## Layer 5 — Gift Validation

### `relationship_tracking.py` — `update_from_gift()` (line 197)

```python
def update_from_gift(self, npc_name: str, item_name: str, value: float = 5.0,
                     player_inventory: Optional[Dict[str, int]] = None) -> Optional[float]:
    if player_inventory is not None:
        if item_name not in player_inventory or player_inventory[item] <= 0:
            return None  # Player doesn't have the item
    # ... rest of existing logic
```

### `npc_dialogue.py` — `update_from_gift()` (line 452)

Add `player_inventory` parameter and forward it to `self.relationship_tracker.update_from_gift()`.

---

## Layer 6 — Unity Client

### `unity_client/NPCDialogueClient.cs`

- `GameState` class (~line 729): add `public List<string> playerInventory`
- `GenerateRequest` class (~line 600): add `public List<string> player_inventory`
- `GenerateResponseAsync` (~line 83): populate inventory from game state

---

## Implementation Order

| Step | File(s) | Description |
|------|---------|-------------|
| 1 | `npc_state_manager.py` | Add `inventory` field to `PlayerState` |
| 2 | `api_server.py` | Add `player_inventory` to request models and endpoints |
| 3 | `npc_dialogue.py` | Add `_format_inventory()`, inject into system prompt |
| 4 | `api_server.py`, `main.py` | Pre-generation validation with override injection |
| 5 | `quest_generator.py` | Quest acceptance inventory checks |
| 6 | `relationship_tracking.py`, `npc_dialogue.py` | Gift validation |
| 7 | `unity_client/NPCDialogueClient.cs` | Unity client inventory field |

## Notes

- The inventory is a `Dict[str, int]` mapping item names to quantities (e.g., `{"starlight opal": 1, "health potion": 3}`).
- The prompt injection (Layer 2) is the highest-impact single change — it makes the LLM refuse items in-character even without server-side guards.
- The server-side guard (Layer 3) is the reliable enforcement layer — it works even if the LLM is tricked.
- For fuzzy item name matching (e.g., "opal" vs "starlight opal"), use substring matching or a simple similarity check.
