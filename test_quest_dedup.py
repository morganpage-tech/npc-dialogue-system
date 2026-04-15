"""
Tests for Quest Extractor deduplication logic.
Ensures the same quest is not extracted multiple times from ongoing NPC dialogue.
"""

import json
import unittest
from unittest.mock import MagicMock, patch
from quest_extractor import QuestExtractor
from quest_generator import (
    Quest, QuestManager, QuestType, QuestStatus, QuestReward,
    Objective, ObjectiveType,
)


def _make_quest(
    name: str,
    description: str,
    quest_giver: str,
    quest_type: QuestType = QuestType.FETCH,
    target: str = "scales",
    status: QuestStatus = QuestStatus.ACTIVE,
) -> Quest:
    return Quest(
        id=f"quest_existing",
        name=name,
        description=description,
        quest_giver=quest_giver,
        quest_type=quest_type,
        objectives=[
            Objective(
                id="obj_0",
                type=ObjectiveType.COLLECT_ITEM,
                description=f"Collect Item: {target}",
                target=target,
                required=1,
                current=0,
            )
        ],
        rewards=QuestReward(gold=10, xp=50),
        status=status,
    )


class TestIsDuplicateQuest(unittest.TestCase):
    """Test the _is_duplicate_quest static method."""

    def test_same_type_and_target_is_duplicate(self):
        existing = _make_quest("Fetch Scales", "Get scales from the blacksmith", "Elara", target="finely crafted scales")
        new = _make_quest("Scales Delivery", "Bring scales to Elara", "Elara", target="finely crafted scales")
        self.assertTrue(QuestExtractor._is_duplicate_quest(new, existing))

    def test_different_type_not_duplicate(self):
        existing = _make_quest("Fetch Scales", "Get scales from the blacksmith", "Elara", QuestType.FETCH, target="scales")
        new = _make_quest("Kill Rats", "Kill rats in the cellar", "Elara", QuestType.KILL, target="scales")
        self.assertFalse(QuestExtractor._is_duplicate_quest(new, existing))

    def test_different_npc_not_duplicate(self):
        existing = _make_quest("Fetch Scales", "Get scales from the blacksmith", "Elara", target="scales")
        new = _make_quest("Fetch Scales", "Get scales from the blacksmith", "Thorne", target="scales")
        self.assertFalse(QuestExtractor._is_duplicate_quest(new, existing))

    def test_different_target_not_duplicate(self):
        existing = _make_quest("Fetch Scales", "Get scales from the blacksmith", "Elara", target="scales")
        new = _make_quest("Fetch Sword", "Retrieve a legendary sword from the dungeon", "Elara", target="sword")
        self.assertFalse(QuestExtractor._is_duplicate_quest(new, existing))

    def test_similar_description_is_duplicate(self):
        existing = _make_quest("Fetch Scales", "Elara wants finely crafted scales to weigh precious spices and gems", "Elara", target="scales")
        new = _make_quest("Get Scales", "Elara needs finely crafted scales for weighing her spices", "Elara", target="trading scales")
        self.assertTrue(QuestExtractor._is_duplicate_quest(new, existing))


class TestExtractQuestPendingSkip(unittest.TestCase):
    """Test that extraction is skipped when a pending quest exists."""

    def setUp(self):
        self.extractor = QuestExtractor(enabled=True)

    def test_skips_when_pending_quest_exists(self):
        self.extractor._pending_quests["Elara"] = _make_quest(
            "Fetch Scales", "Get scales", "Elara"
        )
        result = self.extractor.extract_quest("Elara", "Go get those scales!")
        self.assertIsNone(result)

    def test_extracts_when_no_pending_quest(self):
        self.extractor._pending_quests.pop("Elara", None)
        mock_response = '{"has_quest": false}'
        with patch.object(self.extractor, '_call_llm', return_value=mock_response):
            result = self.extractor.extract_quest("Elara", "Hello there!")
            self.assertIsNone(result)


class TestExtractQuestActiveDedup(unittest.TestCase):
    """Test post-extraction deduplication against active quests."""

    def setUp(self):
        self.extractor = QuestExtractor(enabled=True)
        self.extractor._pending_quests.clear()

    def _mock_llm_quest(self, name, desc, qtype="fetch", target="scales"):
        return json.dumps({
            "has_quest": True,
            "name": name,
            "type": qtype,
            "description": desc,
            "objectives": [{"action": "collect_item", "target": target, "count": 1}],
            "rewards": {"gold": 0, "items": []},
        })

    def test_duplicate_active_quest_returned_as_none(self):
        active = [_make_quest("Finely Crafted Scales", "Get scales from blacksmith", "Elara", target="finely crafted scales")]
        llm_response = self._mock_llm_quest("Fetch Scales", "Get scales from Ryker", target="finely crafted scales")
        with patch.object(self.extractor, '_call_llm', return_value=llm_response):
            result = self.extractor.extract_quest("Elara", "I need those scales!", active_quests=active)
            self.assertIsNone(result)

    def test_new_quest_not_blocked(self):
        active = [_make_quest("Finely Crafted Scales", "Get scales from blacksmith", "Elara", target="scales")]
        llm_response = self._mock_llm_quest("Kill Wolves", "Kill wolves near the village", qtype="kill", target="wolves")
        with patch.object(self.extractor, '_call_llm', return_value=llm_response):
            result = self.extractor.extract_quest("Elara", "There are wolves!", active_quests=active)
            self.assertIsNotNone(result)

    def test_no_active_quests_extracts_normally(self):
        llm_response = self._mock_llm_quest("Fetch Scales", "Get scales from Ryker")
        with patch.object(self.extractor, '_call_llm', return_value=llm_response):
            result = self.extractor.extract_quest("Elara", "I need scales!", active_quests=None)
            self.assertIsNotNone(result)


class TestFormatExistingQuestsSection(unittest.TestCase):
    """Test prompt enrichment with existing quest info."""

    def setUp(self):
        self.extractor = QuestExtractor(enabled=True)

    def test_empty_when_no_active_quests(self):
        section = self.extractor._format_existing_quests_section("Elara", None)
        self.assertEqual(section, "")

    def test_empty_when_no_matching_npc(self):
        active = [_make_quest("Fetch Scales", "Get scales", "Thorne")]
        section = self.extractor._format_existing_quests_section("Elara", active)
        self.assertEqual(section, "")

    def test_contains_quest_info(self):
        active = [_make_quest("Finely Crafted Scales", "Get scales from blacksmith", "Elara", target="scales")]
        section = self.extractor._format_existing_quests_section("Elara", active)
        self.assertIn("EXISTING QUESTS", section)
        self.assertIn("Finely Crafted Scales", section)
        self.assertIn("do NOT re-extract", section)


class TestE2EAcceptPreventsRedup(unittest.TestCase):
    """
    End-to-end test reproducing the exact scenario from the user's bug report:
    
    1. Elara offers quest for Starlight's Breath → extracted
    2. Quest registered with QuestManager → available_quests populated
    3. Player accepts → quest moves to active_quests
    4. Elara's follow-up mentions the same quest → should NOT re-extract
    
    This FAILS until QuestManager.register_quest() is implemented and
    main.py uses it to register extracted quests.
    """

    def setUp(self):
        self.extractor = QuestExtractor(enabled=True)
        self.extractor._pending_quests.clear()
        self.manager = QuestManager()

    def _quest_json(self, name, desc, target):
        return json.dumps({
            "has_quest": True,
            "name": name,
            "type": "fetch",
            "description": desc,
            "objectives": [{"action": "collect_item", "target": target, "count": 1}],
            "rewards": {"gold": 0, "items": []},
        })

    def _accept_json(self):
        return json.dumps({"action": "accept"})

    def test_accept_then_redup_blocked(self):
        npc = "Elara"
        target = "Starlight's Breath"

        # --- Turn 1: NPC offers quest ---
        quest_llm = self._quest_json("Starlight's Breath", f"Procure {target} from the forest", target)
        with patch.object(self.extractor, '_call_llm', return_value=quest_llm):
            extracted = self.extractor.extract_quest(npc, f"I need {target} from the forest")
        self.assertIsNotNone(extracted, "First extraction should succeed")

        # Register with QuestManager (fix: QuestManager.register_quest)
        self.manager.register_quest(extracted)

        # --- Turn 2: Player accepts ---
        with patch.object(self.extractor, '_call_llm', return_value=self._accept_json()):
            action = self.extractor.detect_acceptance("i can get that", npc, extracted)
        self.assertEqual(action, "accept")

        accepted = self.manager.accept_quest(extracted.id)
        self.assertIsNotNone(accepted, "accept_quest should find the registered quest")

        # Quest should now be in active_quests
        self.assertIn(extracted.id, self.manager.active_quests)

        # --- Turn 2 (cont): NPC follow-up mentions same quest ---
        followup_llm = self._quest_json("Acquire Starlight's Breath", f"Get the elusive {target}", target)
        active = list(self.manager.active_quests.values())
        with patch.object(self.extractor, '_call_llm', return_value=followup_llm):
            redup = self.extractor.extract_quest(
                npc,
                f"I'll hold the cuirass, when you return with {target} we'll trade",
                active_quests=active,
            )
        self.assertIsNone(redup, "Should NOT re-extract a quest already in active_quests")

    def test_register_prevents_duplicate_registration(self):
        target = "Starlight's Breath"
        quest_llm = self._quest_json("Starlight's Breath", f"Get {target}", target)
        with patch.object(self.extractor, '_call_llm', return_value=quest_llm):
            quest = self.extractor.extract_quest("Elara", "I need it")
        self.manager.register_quest(quest)
        self.manager.register_quest(quest)
        self.assertEqual(
            len(self.manager.available_quests.get("Elara", [])),
            1,
            "Same quest should not be registered twice",
        )

    def test_accept_fails_without_registration(self):
        """
        Documents the root cause: accept_quest() returns None when the quest
        hasn't been registered with available_quests via register_quest().
        """
        npc = "Elara"
        target = "Starlight's Breath"

        quest_llm = self._quest_json("Starlight's Breath", f"Procure {target}", target)
        with patch.object(self.extractor, '_call_llm', return_value=quest_llm):
            extracted = self.extractor.extract_quest(npc, f"I need {target}")

        accepted = self.manager.accept_quest(extracted.id)
        self.assertIsNone(accepted, "accept_quest fails when quest not registered")
        self.assertEqual(len(self.manager.active_quests), 0, "No quest should be active")


if __name__ == "__main__":
    unittest.main(verbosity=2)
