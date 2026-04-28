"""
Integration tests for inventory validation across all modified modules.
Tests prompt injection, quest acceptance, gift validation, and state persistence.
"""

import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch, PropertyMock

from inventory_validation import validate_inventory_for_input
from relationship_tracking import RelationshipTracker, RelationshipLevel
from quest_generator import (
    Quest, QuestManager, QuestType, QuestStatus, QuestReward,
    Objective, ObjectiveType,
)
from npc_state_manager import PlayerState

try:
    from api_server import GenerateRequest, GameEventRequest
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quest(
    name: str = "Test Quest",
    description: str = "A test quest",
    quest_giver: str = "Elara",
    required_items: list = None,
    status: QuestStatus = QuestStatus.AVAILABLE,
) -> Quest:
    return Quest(
        id="quest_test_1",
        name=name,
        description=description,
        quest_giver=quest_giver,
        quest_type=QuestType.FETCH,
        objectives=[
            Objective(
                id="obj_0",
                type=ObjectiveType.COLLECT_ITEM,
                description="Collect test item",
                target="test_item",
                required=1,
                current=0,
            )
        ],
        rewards=QuestReward(gold=10, xp=50),
        required_items=required_items or [],
        status=status,
    )


# ---------------------------------------------------------------------------
# _format_inventory (npc_dialogue.py)
# ---------------------------------------------------------------------------

class TestFormatInventory(unittest.TestCase):
    """Test NPCDialogue._format_inventory helper."""

    def _make_npc(self):
        from npc_dialogue import NPCDialogue
        with patch.object(NPCDialogue, '__init__', lambda self, *a, **kw: None):
            npc = NPCDialogue.__new__(NPCDialogue)
            return npc

    def test_empty_inventory(self):
        """Empty dict returns '(empty)'."""
        npc = self._make_npc()
        result = npc._format_inventory({})
        self.assertEqual(result, "- (empty)")

    def test_single_item_qty_one(self):
        """Item with qty 1 shows no count."""
        npc = self._make_npc()
        result = npc._format_inventory({"sword": 1})
        self.assertEqual(result, "- sword")

    def test_single_item_qty_multiple(self):
        """Item with qty > 1 shows count."""
        npc = self._make_npc()
        result = npc._format_inventory({"arrow": 50})
        self.assertEqual(result, "- arrow x50")

    def test_multiple_items(self):
        """Multiple items each appear on their own line."""
        npc = self._make_npc()
        result = npc._format_inventory({"sword": 1, "arrow": 10})
        self.assertIn("- sword", result)
        self.assertIn("- arrow x10", result)


# ---------------------------------------------------------------------------
# _build_system_prompt inventory injection (npc_dialogue.py)
# ---------------------------------------------------------------------------

class TestBuildSystemPromptInventory(unittest.TestCase):
    """Test that inventory context is correctly injected into the system prompt."""

    def _make_npc(self):
        from npc_dialogue import NPCDialogue
        with patch.object(NPCDialogue, '__init__', lambda self, *a, **kw: None):
            npc = NPCDialogue.__new__(NPCDialogue)
            npc.character_name = "Elara"
            npc.character_card = {
                "description": "A merchant",
                "personality": "Shrewd",
                "speaking_style": "Polished",
            }
            npc.relationship_tracker = None
            npc.lore_system = None
            npc._dm_directive = None
            return npc

    def test_inventory_included_when_present(self):
        """Inventory appears in prompt when provided."""
        npc = self._make_npc()
        prompt = npc._build_system_prompt(game_state={
            "player_inventory": {"sword": 1}
        })
        self.assertIn("PLAYER'S INVENTORY:", prompt)
        self.assertIn("sword", prompt)

    def test_inventory_not_included_when_absent(self):
        """No inventory section when game_state has no inventory."""
        npc = self._make_npc()
        prompt = npc._build_system_prompt(game_state={})
        self.assertNotIn("PLAYER'S INVENTORY:", prompt)

    def test_inventory_not_included_when_empty_dict(self):
        """Empty inventory dict does not trigger the section."""
        npc = self._make_npc()
        prompt = npc._build_system_prompt(game_state={
            "player_inventory": {}
        })
        self.assertNotIn("PLAYER'S INVENTORY:", prompt)

    def test_inventory_important_instruction_present(self):
        """IMPORTANT instruction about only offering owned items is present."""
        npc = self._make_npc()
        prompt = npc._build_system_prompt(game_state={
            "player_inventory": {"sword": 1}
        })
        self.assertIn("IMPORTANT:", prompt)
        self.assertIn("can only give", prompt)

    def test_override_included_when_present(self):
        """_inventory_override appears as CRITICAL in prompt."""
        npc = self._make_npc()
        prompt = npc._build_system_prompt(game_state={
            "_inventory_override": "The player lies about having a diamond."
        })
        self.assertIn("CRITICAL:", prompt)
        self.assertIn("diamond", prompt)

    def test_override_absent_when_not_set(self):
        """No CRITICAL section when no override is set."""
        npc = self._make_npc()
        prompt = npc._build_system_prompt(game_state={})
        self.assertNotIn("CRITICAL:", prompt)

    def test_player_inventory_excluded_from_game_state_section(self):
        """player_inventory and _inventory_override don't appear in CURRENT SITUATION."""
        npc = self._make_npc()
        prompt = npc._build_system_prompt(game_state={
            "player_inventory": {"sword": 1},
            "_inventory_override": "fraud",
            "location": "tavern",
        })
        self.assertIn("CURRENT SITUATION:", prompt)
        lines_after_situation = prompt.split("CURRENT SITUATION:")[1].split("PLAYER'S INVENTORY:")[0]
        self.assertNotIn("player_inventory", lines_after_situation)
        self.assertNotIn("_inventory_override", lines_after_situation)
        self.assertIn("location", lines_after_situation)

    def test_both_inventory_and_override_present(self):
        """Both inventory section and CRITICAL override can coexist."""
        npc = self._make_npc()
        prompt = npc._build_system_prompt(game_state={
            "player_inventory": {"sword": 1},
            "_inventory_override": "Player lies about diamond."
        })
        self.assertIn("PLAYER'S INVENTORY:", prompt)
        self.assertIn("CRITICAL:", prompt)


# ---------------------------------------------------------------------------
# update_from_gift with inventory (npc_dialogue.py + relationship_tracking.py)
# ---------------------------------------------------------------------------

class TestUpdateFromGiftWithInventory(unittest.TestCase):
    """Test that gift validation checks player inventory."""

    def setUp(self):
        self.tracker = RelationshipTracker()
        self.inventory = {"gem": 1, "rare gem": 1}

    def test_gift_accepted_item_in_inventory(self):
        """Gift accepted when player has the item."""
        result = self.tracker.update_from_gift(
            "Elara", "gem", value=5.0, player_inventory=self.inventory
        )
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    def test_gift_rejected_item_not_in_inventory(self):
        """Gift rejected when player doesn't have the item — returns None."""
        before = self.tracker.get_relationship("Elara").score
        result = self.tracker.update_from_gift(
            "Elara", "sword", value=5.0, player_inventory=self.inventory
        )
        self.assertIsNone(result)
        self.assertEqual(self.tracker.get_relationship("Elara").score, before)

    def test_gift_accepted_no_inventory_param(self):
        """Legacy behavior: no inventory check when param is None."""
        result = self.tracker.update_from_gift(
            "Elara", "sword", value=5.0, player_inventory=None
        )
        self.assertIsNotNone(result)

    def test_gift_fuzzy_match_in_inventory(self):
        """Fuzzy match: 'gem' matches 'rare gem' in inventory."""
        inv = {"rare gem": 1}
        result = self.tracker.update_from_gift(
            "Elara", "gem", value=5.0, player_inventory=inv
        )
        self.assertIsNotNone(result)

    def test_gift_empty_inventory_blocks(self):
        """Empty inventory blocks all gifts."""
        result = self.tracker.update_from_gift(
            "Elara", "gem", value=5.0, player_inventory={}
        )
        self.assertIsNone(result)

    def test_gift_with_inventory_tracks_in_gifts_given(self):
        """Accepted gift is recorded in gifts_given."""
        self.tracker.update_from_gift(
            "Elara", "gem", value=5.0, player_inventory=self.inventory
        )
        rel = self.tracker.get_relationship("Elara")
        self.assertIn("gem", rel.gifts_given)

    def test_gift_with_inventory_diminishing_returns(self):
        """Second gift of same item gets diminishing returns."""
        first = self.tracker.update_from_gift(
            "Elara", "gem", value=10.0, player_inventory=self.inventory
        )
        second = self.tracker.update_from_gift(
            "Elara", "gem", value=10.0, player_inventory=self.inventory
        )
        self.assertLess(abs(second - first), abs(first))


class TestNPCDialogueUpdateFromGift(unittest.TestCase):
    """Test NPCDialogue.update_from_gift passes inventory through."""

    def test_passes_inventory_to_tracker(self):
        from npc_dialogue import NPCDialogue
        with patch.object(NPCDialogue, '__init__', lambda self, *a, **kw: None):
            npc = NPCDialogue.__new__(NPCDialogue)
            npc.character_name = "Elara"
            npc.relationship_tracker = MagicMock()
            npc.relationship_tracker.update_from_gift.return_value = 5.0
            result = npc.update_from_gift(
                "sword", value=3.0, player_inventory={"sword": 1}
            )
            npc.relationship_tracker.update_from_gift.assert_called_once_with(
                "Elara", "sword", 3.0, player_inventory={"sword": 1}
            )
            self.assertEqual(result, 5.0)

    def test_returns_none_no_tracker(self):
        from npc_dialogue import NPCDialogue
        with patch.object(NPCDialogue, '__init__', lambda self, *a, **kw: None):
            npc = NPCDialogue.__new__(NPCDialogue)
            npc.relationship_tracker = None
            result = npc.update_from_gift("sword", player_inventory={"sword": 1})
            self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Quest.accept with inventory (quest_generator.py)
# ---------------------------------------------------------------------------

class TestQuestAcceptWithInventory(unittest.TestCase):
    """Test Quest.accept checks required_items against player inventory."""

    def test_accept_with_required_items_in_inventory(self):
        """Quest accepted when all required items are present."""
        quest = _make_quest(required_items=["scroll"])
        result = quest.accept(player_inventory={"scroll": 1})
        self.assertTrue(result)
        self.assertEqual(quest.status, QuestStatus.ACTIVE)

    def test_accept_with_required_items_not_in_inventory(self):
        """Quest rejected when required item is missing."""
        quest = _make_quest(required_items=["scroll"])
        result = quest.accept(player_inventory={"sword": 1})
        self.assertFalse(result)
        self.assertEqual(quest.status, QuestStatus.AVAILABLE)

    def test_accept_with_required_items_no_inventory_provided(self):
        """When player_inventory is None, required_items check is skipped."""
        quest = _make_quest(required_items=["scroll"])
        result = quest.accept(player_inventory=None)
        self.assertTrue(result)

    def test_accept_without_required_items_always_succeeds(self):
        """Quest with empty required_items succeeds regardless of inventory."""
        quest = _make_quest(required_items=[])
        result = quest.accept(player_inventory={})
        self.assertTrue(result)

    def test_accept_checks_all_required_items(self):
        """Fails if not ALL required items are present."""
        quest = _make_quest(required_items=["scroll", "ink"])
        result = quest.accept(player_inventory={"scroll": 1})
        self.assertFalse(result)

    def test_accept_case_insensitive(self):
        """Required item match is case-insensitive."""
        quest = _make_quest(required_items=["Scroll"])
        result = quest.accept(player_inventory={"scroll": 1})
        self.assertTrue(result)

    def test_accept_qty_zero_is_missing(self):
        """Required item with qty 0 is treated as missing."""
        quest = _make_quest(required_items=["scroll"])
        result = quest.accept(player_inventory={"scroll": 0})
        self.assertFalse(result)

    def test_accept_already_active_fails(self):
        """Already-active quest cannot be accepted again."""
        quest = _make_quest(status=QuestStatus.ACTIVE)
        result = quest.accept(player_inventory={})
        self.assertFalse(result)

    def test_accept_expired_fails(self):
        """Expired quest cannot be accepted."""
        quest = _make_quest()
        quest.expires_at = 0  # In the past
        result = quest.accept(player_inventory={})
        self.assertFalse(result)

    def test_accept_fuzzy_substring_match(self):
        """Required item matches via substring."""
        quest = _make_quest(required_items=["scroll"])
        result = quest.accept(player_inventory={"ancient scroll": 1})
        self.assertTrue(result)

    def test_accept_all_required_items_present(self):
        """Accepts when all required items are present."""
        quest = _make_quest(required_items=["scroll", "ink"])
        result = quest.accept(player_inventory={"scroll": 1, "ink": 2})
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# QuestManager.accept_quest with inventory (quest_generator.py)
# ---------------------------------------------------------------------------

class TestQuestManagerAcceptWithInventory(unittest.TestCase):
    """Test QuestManager.accept_quest passes inventory through."""

    def setUp(self):
        self.manager = QuestManager(save_dir=tempfile.mkdtemp())
        self.quest = _make_quest(required_items=["scroll"])
        self.manager.register_quest(self.quest)

    def test_manager_passes_inventory_to_accept(self):
        """accept_quest passes player_inventory to quest.accept."""
        result = self.manager.accept_quest(
            "quest_test_1", player_inventory={"scroll": 1}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, QuestStatus.ACTIVE)

    def test_manager_blocks_accept_missing_items(self):
        """accept_quest returns None when required items are missing."""
        result = self.manager.accept_quest(
            "quest_test_1", player_inventory={"sword": 1}
        )
        self.assertIsNone(result)

    def test_manager_accept_without_inventory_skips_check(self):
        """accept_quest with no inventory param skips required_items check."""
        result = self.manager.accept_quest("quest_test_1")
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# PlayerState inventory (npc_state_manager.py)
# ---------------------------------------------------------------------------

class TestPlayerStateInventory(unittest.TestCase):
    """Test PlayerState inventory field and serialization."""

    def test_default_inventory_empty(self):
        """New PlayerState has empty inventory."""
        state = PlayerState(player_id="p1")
        self.assertEqual(state.inventory, {})

    def test_inventory_in_to_dict(self):
        """to_dict includes inventory key."""
        state = PlayerState(player_id="p1", inventory={"sword": 1})
        d = state.to_dict()
        self.assertIn("inventory", d)
        self.assertEqual(d["inventory"], {"sword": 1})

    def test_inventory_preserved_in_to_dict(self):
        """Multiple items are preserved exactly."""
        state = PlayerState(
            player_id="p1",
            inventory={"sword": 1, "arrow": 50, "health potion": 3},
        )
        d = state.to_dict()
        self.assertEqual(d["inventory"]["sword"], 1)
        self.assertEqual(d["inventory"]["arrow"], 50)
        self.assertEqual(d["inventory"]["health potion"], 3)

    def test_empty_inventory_in_to_dict(self):
        """Empty inventory serializes as empty dict."""
        state = PlayerState(player_id="p1")
        d = state.to_dict()
        self.assertEqual(d["inventory"], {})


class TestPlayerStateLoadInventory(unittest.TestCase):
    """Test inventory persistence through save/load cycle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_state_restores_inventory(self):
        """Inventory is preserved through save and load."""
        from npc_state_manager import NPCStateManager
        mgr = NPCStateManager(persist_dir=self.tmpdir)
        player = mgr.player_connect("p1")
        player.inventory = {"sword": 2, "gem": 5}
        mgr.save_state()

        mgr2 = NPCStateManager(persist_dir=self.tmpdir)
        mgr2.load_state()
        loaded = mgr2.get_player("p1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.inventory, {"sword": 2, "gem": 5})

    def test_load_state_default_empty_inventory(self):
        """Missing inventory key in save data defaults to empty dict."""
        from npc_state_manager import NPCStateManager
        mgr = NPCStateManager(persist_dir=self.tmpdir)
        player = mgr.player_connect("p1")
        mgr.save_state()

        mgr2 = NPCStateManager(persist_dir=self.tmpdir)
        mgr2.load_state()
        loaded = mgr2.get_player("p1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.inventory, {})


# ---------------------------------------------------------------------------
# API server models (api_server.py)
# ---------------------------------------------------------------------------

class TestGenerateRequestInventory(unittest.TestCase):
    """Test GenerateRequest pydantic model accepts player_inventory."""

    @unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
    def test_player_inventory_default_none(self):
        """player_inventory defaults to None."""
        req = GenerateRequest(npc_name="Elara", player_input="hello")
        self.assertIsNone(req.player_inventory)

    @unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
    def test_player_inventory_accepts_dict(self):
        """player_inventory accepts Dict[str, int]."""
        req = GenerateRequest(
            npc_name="Elara",
            player_input="hello",
            player_inventory={"sword": 1},
        )
        self.assertEqual(req.player_inventory, {"sword": 1})


class TestGameEventRequestInventory(unittest.TestCase):
    """Test GameEventRequest pydantic model accepts player_inventory."""

    @unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
    def test_player_inventory_default_none(self):
        """player_inventory defaults to None."""
        req = GameEventRequest(event_type="collect", target="herb")
        self.assertIsNone(req.player_inventory)

    @unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
    def test_player_inventory_accepts_dict(self):
        """player_inventory accepts Dict[str, int]."""
        req = GameEventRequest(
            event_type="collect",
            target="herb",
            player_inventory={"herb": 3},
        )
        self.assertEqual(req.player_inventory, {"herb": 3})


# ---------------------------------------------------------------------------
# build_game_state_for_npc (main.py)
# ---------------------------------------------------------------------------

class TestBuildGameStateForNPC(unittest.TestCase):
    """Test that build_game_state_for_npc injects player_inventory."""

    def test_inventory_injected_when_present(self):
        """Non-empty inventory is added to game_state."""
        from main import build_game_state_for_npc
        state = build_game_state_for_npc(
            "Elara", None, None, player_inventory={"sword": 1}
        )
        self.assertIsNotNone(state)
        self.assertEqual(state.get("player_inventory"), {"sword": 1})

    def test_inventory_not_injected_when_empty(self):
        """Empty inventory is not added to game_state."""
        from main import build_game_state_for_npc
        state = build_game_state_for_npc(
            "Elara", None, None, player_inventory={}
        )
        self.assertIsNone(state)

    def test_inventory_not_injected_when_none(self):
        """None inventory is not added to game_state."""
        from main import build_game_state_for_npc
        state = build_game_state_for_npc(
            "Elara", None, None, player_inventory=None
        )
        self.assertIsNone(state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
