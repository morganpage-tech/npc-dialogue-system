"""
Unit Tests for Relationship Tracking System
Tests score tracking, level calculation, temperature adjustment, and persistence
"""

import unittest
import os
import json
import tempfile
import shutil
from relationship_tracking import (
    RelationshipTracker,
    RelationshipLevel,
    RelationshipState
)


class TestRelationshipState(unittest.TestCase):
    """Test RelationshipState dataclass."""
    
    def test_default_state(self):
        """Test default relationship state."""
        state = RelationshipState()
        self.assertEqual(state.score, 0.0)
        self.assertEqual(state.last_updated, 0.0)
        self.assertEqual(state.interaction_count, 0)
        self.assertEqual(state.quests_completed, [])
        self.assertEqual(state.gifts_given, [])
    
    def test_state_with_values(self):
        """Test relationship state with custom values."""
        state = RelationshipState(
            score=50.0,
            last_updated=1234567890.0,
            interaction_count=10,
            quests_completed=["quest1", "quest2"],
            gifts_given=["gift1"]
        )
        self.assertEqual(state.score, 50.0)
        self.assertEqual(state.last_updated, 1234567890.0)
        self.assertEqual(state.interaction_count, 10)
        self.assertEqual(len(state.quests_completed), 2)
        self.assertEqual(len(state.gifts_given), 1)


class TestRelationshipLevel(unittest.TestCase):
    """Test relationship level detection."""
    
    def test_hated_level(self):
        """Test hated level range."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", -75, "test")
        self.assertEqual(tracker.get_level("NPC1"), RelationshipLevel.HATED)
    
    def test_disliked_level(self):
        """Test disliked level range."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", -35, "test")
        self.assertEqual(tracker.get_level("NPC1"), RelationshipLevel.DISLIKED)
    
    def test_neutral_level(self):
        """Test neutral level range."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 0, "test")
        self.assertEqual(tracker.get_level("NPC1"), RelationshipLevel.NEUTRAL)
    
    def test_liked_level(self):
        """Test liked level range."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 35, "test")
        self.assertEqual(tracker.get_level("NPC1"), RelationshipLevel.LIKED)
    
    def test_loved_level(self):
        """Test loved level range."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 65, "test")
        self.assertEqual(tracker.get_level("NPC1"), RelationshipLevel.LOVED)
    
    def test_adored_level(self):
        """Test adored level range."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 90, "test")
        self.assertEqual(tracker.get_level("NPC1"), RelationshipLevel.ADORED)
    
    def test_boundary_conditions(self):
        """Test level boundary conditions."""
        tracker = RelationshipTracker()
        
        # Lower boundary of each level
        tracker.update_score("NPC1", -100)
        self.assertEqual(tracker.get_level("NPC1"), RelationshipLevel.HATED)
        
        tracker.update_score("NPC2", -51)
        self.assertEqual(tracker.get_level("NPC2"), RelationshipLevel.HATED)
        
        tracker.update_score("NPC3", -50)
        self.assertEqual(tracker.get_level("NPC3"), RelationshipLevel.DISLIKED)
        
        tracker.update_score("NPC4", -21)
        self.assertEqual(tracker.get_level("NPC4"), RelationshipLevel.DISLIKED)
        
        tracker.update_score("NPC5", -20)
        self.assertEqual(tracker.get_level("NPC5"), RelationshipLevel.NEUTRAL)
        
        tracker.update_score("NPC6", 19)
        self.assertEqual(tracker.get_level("NPC6"), RelationshipLevel.NEUTRAL)
        
        tracker.update_score("NPC7", 20)
        self.assertEqual(tracker.get_level("NPC7"), RelationshipLevel.LIKED)
        
        tracker.update_score("NPC8", 49)
        self.assertEqual(tracker.get_level("NPC8"), RelationshipLevel.LIKED)
        
        tracker.update_score("NPC9", 50)
        self.assertEqual(tracker.get_level("NPC9"), RelationshipLevel.LOVED)
        
        tracker.update_score("NPC10", 79)
        self.assertEqual(tracker.get_level("NPC10"), RelationshipLevel.LOVED)
        
        tracker.update_score("NPC11", 80)
        self.assertEqual(tracker.get_level("NPC11"), RelationshipLevel.ADORED)


class TestScoreTracking(unittest.TestCase):
    """Test score tracking functionality."""
    
    def setUp(self):
        """Set up test tracker."""
        self.tracker = RelationshipTracker(player_id="test_player")
    
    def test_initial_score(self):
        """Test initial score is 0."""
        score = self.tracker.get_relationship("NPC1").score
        self.assertEqual(score, 0.0)
    
    def test_positive_update(self):
        """Test positive score update."""
        new_score = self.tracker.update_score("NPC1", 10.0, "helpful")
        self.assertEqual(new_score, 10.0)
        self.assertEqual(self.tracker.get_relationship("NPC1").score, 10.0)
    
    def test_negative_update(self):
        """Test negative score update."""
        new_score = self.tracker.update_score("NPC1", -5.0, "rude")
        self.assertEqual(new_score, -5.0)
        self.assertEqual(self.tracker.get_relationship("NPC1").score, -5.0)
    
    def test_score_clamping_max(self):
        """Test score is clamped at maximum."""
        self.tracker.update_score("NPC1", 50.0)
        self.tracker.update_score("NPC1", 100.0)
        self.assertEqual(self.tracker.get_relationship("NPC1").score, 100.0)
    
    def test_score_clamping_min(self):
        """Test score is clamped at minimum."""
        self.tracker.update_score("NPC1", -50.0)
        self.tracker.update_score("NPC1", -100.0)
        self.assertEqual(self.tracker.get_relationship("NPC1").score, -100.0)
    
    def test_multiple_updates(self):
        """Test multiple score updates."""
        self.tracker.update_score("NPC1", 10.0)
        self.tracker.update_score("NPC1", 5.0)
        self.tracker.update_score("NPC1", -3.0)
        self.assertEqual(self.tracker.get_relationship("NPC1").score, 12.0)
    
    def test_multiple_npcs(self):
        """Test tracking multiple NPCs separately."""
        self.tracker.update_score("NPC1", 10.0)
        self.tracker.update_score("NPC2", -5.0)
        self.tracker.update_score("NPC3", 25.0)
        
        self.assertEqual(self.tracker.get_relationship("NPC1").score, 10.0)
        self.assertEqual(self.tracker.get_relationship("NPC2").score, -5.0)
        self.assertEqual(self.tracker.get_relationship("NPC3").score, 25.0)
    
    def test_interaction_count(self):
        """Test interaction count increments."""
        self.tracker.update_score("NPC1", 5.0)
        self.tracker.update_score("NPC1", 3.0)
        self.tracker.update_score("NPC1", -2.0)
        self.assertEqual(self.tracker.get_relationship("NPC1").interaction_count, 3)


class TestTemperatureAdjustment(unittest.TestCase):
    """Test temperature adjustment based on relationship."""
    
    def test_base_temperature(self):
        """Test base temperature (neutral relationship)."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 0.0)
        temp = tracker.get_temperature_adjustment("NPC1", 0.8)
        self.assertAlmostEqual(temp, 0.8, places=2)
    
    def test_positive_relationship_lower_temp(self):
        """Test positive relationship lowers temperature."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 50.0)
        temp = tracker.get_temperature_adjustment("NPC1", 0.8)
        self.assertLess(temp, 0.8)
        self.assertGreater(temp, 0.3)
    
    def test_negative_relationship_higher_temp(self):
        """Test negative relationship raises temperature."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", -50.0)
        temp = tracker.get_temperature_adjustment("NPC1", 0.8)
        self.assertGreater(temp, 0.8)
        self.assertLessEqual(temp, 1.0)
    
    def test_extreme_positive(self):
        """Test extreme positive relationship."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 100.0)
        temp = tracker.get_temperature_adjustment("NPC1", 0.8)
        self.assertLess(temp, 0.5)
        self.assertGreaterEqual(temp, 0.3)
    
    def test_extreme_negative(self):
        """Test extreme negative relationship."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", -100.0)
        temp = tracker.get_temperature_adjustment("NPC1", 0.8)
        self.assertEqual(temp, 1.0)  # Capped at max


class TestSpeakingStyleModifier(unittest.TestCase):
    """Test speaking style modifiers based on relationship."""
    
    def test_hated_modifier(self):
        """Test hated relationship modifier."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", -75.0)
        modifier = tracker.get_speaking_style_modifier("NPC1")
        self.assertIn("despise", modifier.lower())
        self.assertIn("hostile", modifier.lower())
    
    def test_liked_modifier(self):
        """Test liked relationship modifier."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 35.0)
        modifier = tracker.get_speaking_style_modifier("NPC1")
        self.assertIn("friend", modifier.lower())
        self.assertIn("warm", modifier.lower())
    
    def test_adored_modifier(self):
        """Test adored relationship modifier."""
        tracker = RelationshipTracker()
        tracker.update_score("NPC1", 90.0)
        modifier = tracker.get_speaking_style_modifier("NPC1")
        self.assertIn("deeply admire", modifier.lower())
        self.assertIn("loyal", modifier.lower())


class TestQuestUpdates(unittest.TestCase):
    """Test quest completion relationship updates."""
    
    def setUp(self):
        """Set up test tracker."""
        self.tracker = RelationshipTracker()
    
    def test_successful_quest(self):
        """Test successful quest increases relationship."""
        new_score = self.tracker.update_from_quest("NPC1", "quest_001", success=True, reward=15.0)
        self.assertEqual(new_score, 15.0)
        self.assertIn("quest_001", self.tracker.get_relationship("NPC1").quests_completed)
    
    def test_failed_quest(self):
        """Test failed quest decreases relationship."""
        new_score = self.tracker.update_from_quest("NPC1", "quest_001", success=False, reward=15.0)
        self.assertEqual(new_score, -7.5)  # -reward/2
        self.assertNotIn("quest_001", self.tracker.get_relationship("NPC1").quests_completed)
    
    def test_duplicate_quest(self):
        """Test duplicate quest doesn't give double reward."""
        self.tracker.update_from_quest("NPC1", "quest_001", success=True, reward=15.0)
        first_score = self.tracker.get_relationship("NPC1").score
        
        self.tracker.update_from_quest("NPC1", "quest_001", success=True, reward=15.0)
        second_score = self.tracker.get_relationship("NPC1").score
        
        self.assertEqual(first_score, second_score)  # No change


class TestGiftUpdates(unittest.TestCase):
    """Test gift giving relationship updates."""
    
    def setUp(self):
        """Set up test tracker."""
        self.tracker = RelationshipTracker()
    
    def test_gift_increases_relationship(self):
        """Test giving a gift increases relationship."""
        new_score = self.tracker.update_from_gift("NPC1", "gold_coins", value=10.0)
        self.assertEqual(new_score, 10.0)
        self.assertIn("gold_coins", self.tracker.get_relationship("NPC1").gifts_given)
    
    def test_duplicate_gift_diminishing_returns(self):
        """Test duplicate gifts have diminishing returns."""
        first_score = self.tracker.update_from_gift("NPC1", "gold_coins", value=10.0)
        second_score = self.tracker.update_from_gift("NPC1", "gold_coins", value=10.0)
        
        # Second gift should have 30% value (3.0 instead of 10.0)
        self.assertAlmostEqual(second_score, first_score + 3.0, places=2)
    
    def test_high_relationship_less_impact(self):
        """Test gifts have less impact at high relationship levels."""
        # Get to loved level
        self.tracker.update_score("NPC1", 60.0)
        base_score = self.tracker.get_relationship("NPC1").score
        
        # Gift should have 70% value at loved level
        new_score = self.tracker.update_from_gift("NPC1", "gold_coins", value=10.0)
        expected = base_score + 7.0  # 10.0 * 0.7
        
        self.assertAlmostEqual(new_score, expected, places=2)


class TestDialogueUpdates(unittest.TestCase):
    """Test dialogue choice relationship updates."""
    
    def setUp(self):
        """Set up test tracker."""
        self.tracker = RelationshipTracker()
    
    def test_friendly_dialogue(self):
        """Test friendly dialogue increases relationship."""
        new_score = self.tracker.update_from_dialogue("NPC1", "friendly")
        self.assertEqual(new_score, 2.0)
    
    def test_hostile_dialogue(self):
        """Test hostile dialogue decreases relationship."""
        new_score = self.tracker.update_from_dialogue("NPC1", "hostile")
        self.assertEqual(new_score, -5.0)
    
    def test_custom_sentiment(self):
        """Test custom sentiment value."""
        new_score = self.tracker.update_from_dialogue("NPC1", "custom", sentiment=0.5)
        self.assertEqual(new_score, 0.5)
    
    def test_negative_custom_sentiment(self):
        """Test negative custom sentiment value."""
        new_score = self.tracker.update_from_dialogue("NPC1", "custom", sentiment=-0.8)
        self.assertEqual(new_score, -0.8)


class TestFactionSupport(unittest.TestCase):
    """Test faction relationship tracking."""
    
    def setUp(self):
        """Set up test tracker."""
        self.tracker = RelationshipTracker()
    
    def test_faction_update(self):
        """Test updating faction relationship."""
        new_score = self.tracker.update_faction("Merchants", 10.0, "helped merchant")
        self.assertEqual(new_score, 10.0)
        self.assertEqual(self.tracker.factions["Merchants"], 10.0)
    
    def test_multiple_factions(self):
        """Test tracking multiple factions."""
        self.tracker.update_faction("Merchants", 10.0)
        self.tracker.update_faction("Mages", -5.0)
        self.tracker.update_faction("Guards", 20.0)
        
        self.assertEqual(len(self.tracker.factions), 3)
    
    def test_faction_bonus(self):
        """Test faction bonus calculation."""
        self.tracker.update_faction("Merchants", 50.0)
        bonus = self.tracker.get_npc_faction_bonus("NPC1", "Merchants")
        self.assertEqual(bonus, 15.0)  # 50.0 * 0.3


class TestPersistence(unittest.TestCase):
    """Test save and load functionality."""
    
    def setUp(self):
        """Set up test tracker and temp directory."""
        self.tracker = RelationshipTracker(player_id="test_player")
        self.temp_dir = tempfile.mkdtemp()
        self.save_path = os.path.join(self.temp_dir, "test_save.json")
    
    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load(self):
        """Test saving and loading relationships."""
        # Add some relationships
        self.tracker.update_score("NPC1", 25.0)
        self.tracker.update_score("NPC2", -15.0)
        self.tracker.update_faction("Merchants", 30.0)
        
        # Save
        self.tracker.save(self.save_path)
        self.assertTrue(os.path.exists(self.save_path))
        
        # Load into new tracker
        new_tracker = RelationshipTracker(player_id="test_player")
        new_tracker.load(self.save_path)
        
        # Verify loaded data
        self.assertEqual(new_tracker.get_relationship("NPC1").score, 25.0)
        self.assertEqual(new_tracker.get_relationship("NPC2").score, -15.0)
        self.assertEqual(new_tracker.factions["Merchants"], 30.0)
    
    def test_save_format(self):
        """Test save file format."""
        self.tracker.update_score("NPC1", 10.0)
        self.tracker.save(self.save_path)
        
        with open(self.save_path, 'r') as f:
            data = json.load(f)
        
        self.assertIn("player_id", data)
        self.assertIn("relationships", data)
        self.assertIn("factions", data)
        self.assertIn("saved_at", data)
        self.assertEqual(data["player_id"], "test_player")


class TestTimeDecay(unittest.TestCase):
    """Test time-based relationship decay."""
    
    def setUp(self):
        """Set up test tracker with decay enabled."""
        self.tracker = RelationshipTracker(player_id="test_player", enable_time_decay=True)
    
    def test_no_decay_immediately(self):
        """Test no decay happens immediately."""
        self.tracker.update_score("NPC1", 50.0)
        score_before = self.tracker.get_relationship("NPC1").score
        
        self.tracker.apply_time_decay()
        score_after = self.tracker.get_relationship("NPC1").score
        
        # Should be the same (no time passed)
        self.assertEqual(score_before, score_after)
    
    def test_decay_towards_neutral(self):
        """Test relationships decay towards neutral."""
        self.tracker.update_score("NPC1", 50.0)
        
        # Manually set last_updated to 2 days ago
        import time
        self.tracker.relationships["NPC1"].last_updated = time.time() - (86400 * 2)
        
        self.tracker.apply_time_decay()
        score = self.tracker.get_relationship("NPC1").score
        
        # Should have decayed but still be positive
        self.assertGreater(score, 0)
        self.assertLess(score, 50)
    
    def test_decay_disabled(self):
        """Test decay doesn't happen when disabled."""
        tracker = RelationshipTracker(player_id="test_player", enable_time_decay=False)
        tracker.update_score("NPC1", 50.0)
        
        # Manually set last_updated to 2 days ago
        import time
        tracker.relationships["NPC1"].last_updated = time.time() - (86400 * 2)
        
        tracker.apply_time_decay()
        score = tracker.get_relationship("NPC1").score
        
        # Should be unchanged
        self.assertEqual(score, 50.0)


class TestConditionQueries(unittest.TestCase):
    """Test querying NPCs by relationship conditions."""
    
    def setUp(self):
        """Set up test tracker with various relationship scores."""
        self.tracker = RelationshipTracker()
        self.tracker.update_score("NPC1", 75.0)
        self.tracker.update_score("NPC2", -30.0)
        self.tracker.update_score("NPC3", 10.0)
        self.tracker.update_score("NPC4", 55.0)
        self.tracker.update_score("NPC5", -75.0)
    
    def test_greater_than_condition(self):
        """Test > condition."""
        results = self.tracker.get_npc_for_condition("> 50")
        self.assertIn("NPC1", results)
        self.assertIn("NPC4", results)
        self.assertEqual(len(results), 2)
    
    def test_less_than_condition(self):
        """Test < condition."""
        results = self.tracker.get_npc_for_condition("< 0")
        self.assertIn("NPC2", results)
        self.assertIn("NPC5", results)
        self.assertEqual(len(results), 2)
    
    def test_range_condition(self):
        """Test range condition."""
        results = self.tracker.get_npc_for_condition("> 10")
        self.assertIn("NPC1", results)
        self.assertIn("NPC4", results)
        self.assertNotIn("NPC2", results)
        self.assertNotIn("NPC3", results)
    
    def test_level_condition(self):
        """Test level name condition."""
        results = self.tracker.get_npc_for_condition("== LOVED")
        self.assertIn("NPC1", results)  # 75 is LOVED (50-80)
        self.assertIn("NPC4", results)  # 55 is LOVED (50-80)
        self.assertEqual(len(results), 2)


class TestSummary(unittest.TestCase):
    """Test relationship summary generation."""
    
    def setUp(self):
        """Set up test tracker."""
        self.tracker = RelationshipTracker()
        self.tracker.update_score("NPC1", 25.0)
        self.tracker.update_score("NPC2", 75.0)
        self.tracker.update_faction("Merchants", 30.0)
    
    def test_summary_structure(self):
        """Test summary has correct structure."""
        summary = self.tracker.get_summary()
        
        self.assertIn("player_id", summary)
        self.assertIn("npcs", summary)
        self.assertIn("factions", summary)
    
    def test_summary_npc_data(self):
        """Test summary includes NPC data."""
        summary = self.tracker.get_summary()
        
        self.assertIn("NPC1", summary["npcs"])
        self.assertIn("NPC2", summary["npcs"])
        
        npc1_data = summary["npcs"]["NPC1"]
        self.assertEqual(npc1_data["score"], 25.0)
        self.assertEqual(npc1_data["level"], "LIKED")
        self.assertIn("interactions", npc1_data)
    
    def test_summary_faction_data(self):
        """Test summary includes faction data."""
        summary = self.tracker.get_summary()
        
        self.assertIn("Merchants", summary["factions"])
        self.assertEqual(summary["factions"]["Merchants"], 30.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
