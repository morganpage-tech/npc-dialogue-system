"""
Unit Tests for Dungeon Master AI
Tests initialization, event handling, narrative state, observations, tension, arcs, persistence.
"""

import unittest
import json
import tempfile
import shutil
import os
import time
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from npc_state_manager import StateEvent, EventType
from dm_rule_engine import DmRuleEngine
from dungeon_master import (
    DungeonMaster,
    DungeonMasterConfig,
    NarrativeState,
    StoryArc,
    Observation,
)


def make_event(
    event_type: EventType = EventType.QUEST_COMPLETED,
    player_id: str = "player1",
    npc_id: str = "Thorne",
    zone_id: str = "ironhold",
    **extra_data,
) -> StateEvent:
    data = {"quest_name": "Test Quest", "quest_type": "fetch"}
    data.update(extra_data)
    return StateEvent(
        event_type=event_type,
        timestamp=time.time(),
        data=data,
        player_id=player_id,
        npc_id=npc_id,
        zone_id=zone_id,
    )


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class MockLLMProvider:
    def __init__(self, response: dict = None):
        self.response = response or {"directive": "none"}
        self.calls = []

    def generate(self, messages, model, temperature=0.8, max_tokens=500):
        self.calls.append({"messages": messages, "model": model})
        content = json.dumps(self.response)
        return {"content": content, "tokens": 50, "total_duration": 100}


class TestDungeonMasterConfig(unittest.TestCase):

    def test_defaults(self):
        cfg = DungeonMasterConfig()
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.model, "llama3.2:3b")
        self.assertEqual(cfg.temperature, 0.6)
        self.assertEqual(cfg.max_active_rules, 50)
        self.assertEqual(cfg.min_observations, 5)
        self.assertEqual(cfg.tension_threshold, 0.8)

    def test_from_env(self):
        env = {
            "DM_ENABLED": "false",
            "DM_MODEL": "test-model",
            "DM_TEMPERATURE": "0.3",
        }
        with patch.dict(os.environ, env):
            cfg = DungeonMasterConfig.from_env()
            self.assertFalse(cfg.enabled)
            self.assertEqual(cfg.model, "test-model")
            self.assertEqual(cfg.temperature, 0.3)


class TestStoryArc(unittest.TestCase):

    def test_creation(self):
        arc = StoryArc(arc_id="arc_001", title="Test Arc", description="A test")
        self.assertEqual(arc.arc_id, "arc_001")
        self.assertEqual(arc.status, "active")
        self.assertEqual(arc.tension_level, 0.0)

    def test_add_event(self):
        arc = StoryArc(arc_id="arc_001", title="Test", description="")
        arc.add_event("quest_completed", "Completed a quest")
        self.assertEqual(len(arc.key_events), 1)
        self.assertEqual(arc.key_events[0]["event_type"], "quest_completed")
        self.assertEqual(arc.key_events[0]["summary"], "Completed a quest")

    def test_not_expired(self):
        arc = StoryArc(arc_id="arc_001", title="Test", description="")
        self.assertFalse(arc.is_expired())

    def test_expired(self):
        arc = StoryArc(
            arc_id="arc_001", title="Test", description="",
            last_event_at=time.time() - 73 * 3600,
        )
        self.assertTrue(arc.is_expired(ttl_hours=72))

    def test_serialization(self):
        arc = StoryArc(arc_id="arc_001", title="Test", description="desc", tension_level=0.5)
        d = arc.to_dict()
        restored = StoryArc.from_dict(d)
        self.assertEqual(restored.arc_id, arc.arc_id)
        self.assertEqual(restored.title, arc.title)
        self.assertEqual(restored.tension_level, 0.5)


class TestObservation(unittest.TestCase):

    def test_creation(self):
        obs = Observation(
            observation_id="obs_001",
            event_type="quest_failed",
            event_hash="abc123",
            event_summary="Quest failed for Thorne",
            context_snapshot={},
            llm_directive_type="npc_directive",
            llm_parameters={"npc": "Thorne"},
            llm_reasoning="Test",
            confidence=0.85,
        )
        self.assertEqual(obs.observation_id, "obs_001")
        self.assertEqual(obs.confidence, 0.85)

    def test_similarity_key(self):
        obs = Observation(
            observation_id="obs_001",
            event_type="quest_failed",
            event_hash="abc",
            event_summary="",
            context_snapshot={},
            llm_directive_type="npc_directive",
            llm_parameters={},
            llm_reasoning="",
        )
        self.assertEqual(obs.similarity_key(), "quest_failed:npc_directive")

    def test_serialization(self):
        obs = Observation(
            observation_id="obs_001",
            event_type="quest_completed",
            event_hash="hash",
            event_summary="Test",
            context_snapshot={"key": "val"},
            llm_directive_type="quest_suggestion",
            llm_parameters={"title": "Quest"},
            llm_reasoning="Because",
            confidence=0.9,
        )
        d = obs.to_dict()
        restored = Observation.from_dict(d)
        self.assertEqual(restored.observation_id, obs.observation_id)
        self.assertEqual(restored.confidence, 0.9)
        self.assertEqual(restored.llm_directive_type, "quest_suggestion")


class TestNarrativeState(unittest.TestCase):

    def test_defaults(self):
        state = NarrativeState()
        self.assertEqual(state.story_summary, "")
        self.assertEqual(state.active_arcs, {})
        self.assertEqual(state.tension_map, {})
        self.assertEqual(state.total_events_processed, 0)

    def test_serialization(self):
        state = NarrativeState(
            story_summary="A story",
            tension_map={"npc:Thorne": 0.5},
            world_conditions={"war"},
            total_events_processed=42,
        )
        d = state.to_dict()
        restored = NarrativeState.from_dict(d)
        self.assertEqual(restored.story_summary, "A story")
        self.assertEqual(restored.tension_map, {"npc:Thorne": 0.5})
        self.assertEqual(restored.world_conditions, {"war"})
        self.assertEqual(restored.total_events_processed, 42)

    def test_round_trip_with_arcs_and_observations(self):
        state = NarrativeState()
        arc = StoryArc(arc_id="arc_001", title="Test Arc", description="Desc")
        state.active_arcs["arc_001"] = arc
        obs = Observation(
            observation_id="obs_001",
            event_type="quest_completed",
            event_hash="h",
            event_summary="Test",
            context_snapshot={},
            llm_directive_type="none",
            llm_parameters={},
            llm_reasoning="",
        )
        state.recent_observations.append(obs)

        d = state.to_dict()
        restored = NarrativeState.from_dict(d)
        self.assertIn("arc_001", restored.active_arcs)
        self.assertIsInstance(restored.active_arcs["arc_001"], StoryArc)
        self.assertEqual(len(restored.recent_observations), 1)
        self.assertIsInstance(restored.recent_observations[0], Observation)


class TestDungeonMasterInit(unittest.TestCase):

    def test_initializes_with_defaults(self):
        tmpdir = tempfile.mkdtemp()
        try:
            dm = DungeonMaster(config=DungeonMasterConfig(state_dir=tmpdir, rules_dir=tmpdir))
            self.assertTrue(dm.config.enabled)
            self.assertIsNotNone(dm.state)
            self.assertEqual(dm.state.total_events_processed, 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_disabled_does_not_handle(self):
        tmpdir = tempfile.mkdtemp()
        try:
            dm = DungeonMaster(config=DungeonMasterConfig(enabled=False, state_dir=tmpdir, rules_dir=tmpdir))
            dm._running = True
            event = make_event()
            result = run_async(dm.handle_event(event))
            self.assertIsNone(result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_ignores_dm_events(self):
        tmpdir = tempfile.mkdtemp()
        try:
            dm = DungeonMaster(config=DungeonMasterConfig(state_dir=tmpdir, rules_dir=tmpdir))
            dm._running = True
            event = make_event(event_type=EventType.DM_NPC_DIRECTIVE)
            run_async(dm.handle_event(event))
            self.assertEqual(dm.state.total_events_processed, 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestEventHandling(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dm = DungeonMaster(
            config=DungeonMasterConfig(
                state_dir=self.tmpdir,
                rules_dir=self.tmpdir,
                auto_save_interval=0,
            ),
            rule_engine=DmRuleEngine(rules_dir=self.tmpdir),
        )
        self.dm._running = True

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ignores_ignored_event_types(self):
        for et in [EventType.DIALOGUE_START, EventType.DIALOGUE_END,
                    EventType.PLAYER_JOINED, EventType.PLAYER_LEFT,
                    EventType.QUEST_PROGRESS, EventType.DM_QUEST_SUGGESTION]:
            run_async(self.dm.handle_event(make_event(event_type=et)))
        self.assertEqual(self.dm.state.total_events_processed, 0)

    def test_ignores_dm_sourced_events(self):
        event = make_event()
        event.data["source"] = "dungeon_master"
        run_async(self.dm.handle_event(event))
        self.assertEqual(self.dm.state.total_events_processed, 0)

    def test_ignores_disabled_trigger(self):
        self.dm.config.enabled_triggers["dialogue_message"] = False
        event = make_event(event_type=EventType.DIALOGUE_MESSAGE)
        run_async(self.dm.handle_event(event))
        self.assertEqual(self.dm.state.total_events_processed, 0)

    def test_processes_enabled_event(self):
        event = make_event(event_type=EventType.QUEST_COMPLETED)
        run_async(self.dm.handle_event(event))
        self.assertEqual(self.dm.state.total_events_processed, 1)

    def test_uses_compiled_rule_when_matched(self):
        self.dm.rule_engine.active_rules = [{
            "rule_id": "dm_gen_001",
            "rule_name": "Test",
            "description": "Test",
            "trigger": {
                "event_type": "quest_completed",
                "conditions": [],
            },
            "actions": [
                {"type": "tension_adjust", "parameters": {"target": "{event.npc_id}", "delta": 0.1}},
            ],
            "priority": 5,
            "confidence": 0.95,
            "active": True,
        }]
        self.dm.event_callback = MagicMock()
        self.dm.event_callback.emit = AsyncMock()

        event = make_event(event_type=EventType.QUEST_COMPLETED)
        run_async(self.dm.handle_event(event))

        self.assertEqual(self.dm.state.total_events_processed, 1)

    def test_raw_events_stored(self):
        event = make_event(event_type=EventType.QUEST_COMPLETED)
        run_async(self.dm.handle_event(event))
        self.assertEqual(len(self.dm.raw_events), 1)

    def test_raw_events_capped(self):
        self.dm.config.max_raw_events = 5
        for i in range(10):
            run_async(self.dm.handle_event(make_event(
                event_type=EventType.QUEST_COMPLETED,
                quest_name=f"Quest {i}",
            )))
        self.assertLessEqual(len(self.dm.raw_events), 5)


class TestTension(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dm = DungeonMaster(
            config=DungeonMasterConfig(
                state_dir=self.tmpdir,
                rules_dir=self.tmpdir,
                auto_save_interval=0,
            ),
        )
        self.dm._running = True

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_tension_increases_on_negative_event(self):
        event = make_event(event_type=EventType.QUEST_FAILED, npc_id="Thorne")
        self.dm._update_tension(event)
        self.assertGreater(self.dm.state.tension_map.get("npc:Thorne", 0), 0)

    def test_tension_decreases_on_positive_event(self):
        self.dm.state.tension_map["npc:Thorne"] = 0.5
        event = make_event(event_type=EventType.QUEST_COMPLETED, npc_id="Thorne")
        self.dm._update_tension(event)
        self.assertLess(self.dm.state.tension_map.get("npc:Thorne", 0.5), 0.5)

    def test_tension_clamped_at_max(self):
        event = make_event(event_type=EventType.QUEST_FAILED, npc_id="Thorne")
        for _ in range(20):
            self.dm._update_tension(event)
        self.assertLessEqual(self.dm.state.tension_map.get("npc:Thorne", 0), 1.0)

    def test_tension_clamped_at_min(self):
        self.dm.state.tension_map["npc:Thorne"] = 0.01
        event = make_event(event_type=EventType.QUEST_COMPLETED, npc_id="Thorne")
        for _ in range(20):
            self.dm._update_tension(event)
        self.assertGreaterEqual(self.dm.state.tension_map.get("npc:Thorne", 0), 0.0)

    def test_world_overall_tension(self):
        self.dm.state.tension_map["npc:Thorne"] = 0.6
        self.dm.state.tension_map["npc:Elara"] = 0.4
        event = make_event(event_type=EventType.QUEST_COMPLETED, npc_id="Thorne")
        self.dm._update_tension(event)
        self.assertIn("world:overall", self.dm.state.tension_map)
        overall = self.dm.state.tension_map["world:overall"]
        self.assertGreaterEqual(overall, 0.0)
        self.assertLessEqual(overall, 1.0)


class TestArcManagement(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dm = DungeonMaster(
            config=DungeonMasterConfig(
                state_dir=self.tmpdir,
                rules_dir=self.tmpdir,
                auto_save_interval=0,
            ),
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_arc(self):
        arc = self.dm.create_arc("Test Arc", "A test arc", involved_npcs=["Thorne"])
        self.assertEqual(arc.arc_id, "arc_001")
        self.assertEqual(arc.title, "Test Arc")
        self.assertEqual(arc.status, "active")
        self.assertIn("arc_001", self.dm.state.active_arcs)

    def test_advance_arc(self):
        self.dm.create_arc("Test Arc", "Desc")
        ok = self.dm.advance_arc("arc_001", "Something happened", tension_delta=0.2)
        self.assertTrue(ok)
        arc = self.dm.state.active_arcs["arc_001"]
        self.assertEqual(len(arc.key_events), 1)
        self.assertAlmostEqual(arc.tension_level, 0.2)

    def test_advance_nonexistent_arc(self):
        ok = self.dm.advance_arc("arc_999", "Nope")
        self.assertFalse(ok)

    def test_resolve_arc(self):
        self.dm.create_arc("Test Arc", "Desc")
        ok = self.dm.resolve_arc("arc_001")
        self.assertTrue(ok)
        self.assertEqual(self.dm.state.active_arcs["arc_001"].status, "resolved")

    def test_resolve_nonexistent(self):
        ok = self.dm.resolve_arc("arc_999")
        self.assertFalse(ok)

    def test_max_active_arcs(self):
        self.dm.config.max_active_arcs = 2
        for i in range(3):
            self.dm.create_arc(f"Arc {i}", f"Desc {i}")
        self.dm._compress_narrative_sync()
        active = [a for a in self.dm.state.active_arcs.values() if a.status == "active"]
        self.assertLessEqual(len(active), 2)


class TestObservationsAndPatterns(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dm = DungeonMaster(
            config=DungeonMasterConfig(
                state_dir=self.tmpdir,
                rules_dir=self.tmpdir,
                auto_save_interval=0,
                min_observations=5,
            ),
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_log_observation(self):
        event = make_event(event_type=EventType.QUEST_FAILED)
        obs = self.dm._log_observation(event, "npc_directive", {"npc": "Thorne"}, "Test")
        self.assertIsNotNone(obs)
        self.assertEqual(len(self.dm.state.recent_observations), 1)

    def test_max_observations_capped(self):
        self.dm.config.max_observations = 5
        for i in range(10):
            event = make_event(event_type=EventType.QUEST_FAILED)
            self.dm._log_observation(event, "npc_directive", {}, "Test")
        self.assertLessEqual(len(self.dm.state.recent_observations), 5)

    def test_pattern_not_detected_below_threshold(self):
        for i in range(4):
            event = make_event(event_type=EventType.QUEST_FAILED)
            obs = self.dm._log_observation(event, "npc_directive", {}, "Test")
        self.assertFalse(self.dm._check_for_pattern(obs))

    def test_pattern_detected_at_threshold(self):
        obs = None
        for i in range(5):
            event = make_event(event_type=EventType.QUEST_FAILED)
            obs = self.dm._log_observation(event, "npc_directive", {}, "Test")
        self.assertTrue(self.dm._check_for_pattern(obs))

    def test_similarity_key_grouping(self):
        event1 = make_event(event_type=EventType.QUEST_FAILED, npc_id="Thorne")
        event2 = make_event(event_type=EventType.QUEST_FAILED, npc_id="Elara")
        obs1 = self.dm._log_observation(event1, "npc_directive", {}, "Test")
        obs2 = self.dm._log_observation(event2, "npc_directive", {}, "Test")
        self.assertEqual(obs1.similarity_key(), obs2.similarity_key())

    def test_different_directives_not_grouped(self):
        event = make_event(event_type=EventType.QUEST_FAILED)
        obs1 = self.dm._log_observation(event, "npc_directive", {}, "Test")
        obs2 = self.dm._log_observation(event, "quest_suggestion", {}, "Test")
        self.assertNotEqual(obs1.similarity_key(), obs2.similarity_key())


class TestLLMJudgment(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.provider = MockLLMProvider()
        self.dm = DungeonMaster(
            config=DungeonMasterConfig(
                state_dir=self.tmpdir,
                rules_dir=self.tmpdir,
                auto_save_interval=0,
            ),
            llm_provider=self.provider,
        )
        self.dm._running = True
        self.dm.event_callback = MagicMock()
        self.dm.event_callback.emit = AsyncMock()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_llm_none_directive_no_emission(self):
        self.provider.response = {"directive": "none"}
        event = make_event(event_type=EventType.QUEST_COMPLETED)
        run_async(self.dm.handle_event(event))
        self.dm.event_callback.emit.assert_not_called()

    def test_llm_directive_emits_event(self):
        self.provider.response = {
            "directive": "npc_directive",
            "parameters": {
                "npc": "Thorne",
                "directive": "express_joy",
                "prompt_modifier": "Be happy!",
            },
            "narrative_reason": "Quest completed",
        }
        event = make_event(event_type=EventType.QUEST_COMPLETED)
        run_async(self.dm.handle_event(event))
        self.dm.event_callback.emit.assert_called()

    def test_llm_failure_handled_gracefully(self):
        failing_provider = MockLLMProvider()
        failing_provider.generate = MagicMock(side_effect=Exception("LLM down"))
        self.dm.llm_provider = failing_provider

        event = make_event(event_type=EventType.QUEST_COMPLETED)
        run_async(self.dm.handle_event(event))
        self.assertEqual(self.dm.state.total_events_processed, 1)

    def test_malformed_llm_response_handled(self):
        self.provider.response = "not json at all"
        self.provider.generate = MagicMock(return_value={"content": "not json", "tokens": 5})
        event = make_event(event_type=EventType.QUEST_COMPLETED)
        run_async(self.dm.handle_event(event))
        self.assertEqual(self.dm.state.total_events_processed, 1)

    def test_llm_json_in_code_block(self):
        self.provider.generate = MagicMock(return_value={
            "content": '```json\n{"directive": "none"}\n```',
            "tokens": 10,
        })
        event = make_event(event_type=EventType.QUEST_COMPLETED)
        run_async(self.dm.handle_event(event))
        self.assertEqual(self.dm.state.total_events_processed, 1)


class TestPersistence(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_state(self):
        dm = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir,
            rules_dir=self.tmpdir,
            auto_save_interval=0,
        ))
        dm.state.story_summary = "Test story"
        dm.state.tension_map = {"npc:Thorne": 0.6}
        dm.state.world_conditions = {"war", "famine"}
        dm.state.total_events_processed = 42
        dm.save_state()

        dm2 = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir,
            rules_dir=self.tmpdir,
            auto_save_interval=0,
        ))
        dm2.load_state()
        self.assertEqual(dm2.state.story_summary, "Test story")
        self.assertEqual(dm2.state.tension_map["npc:Thorne"], 0.6)
        self.assertEqual(dm2.state.world_conditions, {"war", "famine"})
        self.assertEqual(dm2.state.total_events_processed, 42)

    def test_raw_events_persist(self):
        dm = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir,
            rules_dir=self.tmpdir,
            auto_save_interval=0,
        ))
        dm.raw_events = [{"event_type": "quest_completed", "npc_id": "Thorne"}]
        dm.save_state()

        dm2 = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir,
            rules_dir=self.tmpdir,
            auto_save_interval=0,
        ))
        dm2.load_state()
        self.assertEqual(len(dm2.raw_events), 1)

    def test_arc_seq_restored(self):
        dm = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir,
            rules_dir=self.tmpdir,
            auto_save_interval=0,
        ))
        dm.create_arc("Arc 1", "Desc")
        dm.create_arc("Arc 2", "Desc")
        dm.save_state()

        dm2 = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir,
            rules_dir=self.tmpdir,
            auto_save_interval=0,
        ))
        dm2.load_state()
        arc = dm2.create_arc("Arc 3", "Desc")
        self.assertEqual(arc.arc_id, "arc_003")

    def test_obs_seq_restored(self):
        dm = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir,
            rules_dir=self.tmpdir,
            auto_save_interval=0,
        ))
        dm._obs_seq = 5
        dm.state.recent_observations.append(Observation(
            observation_id="obs_005",
            event_type="quest_failed",
            event_hash="h",
            event_summary="",
            context_snapshot={},
            llm_directive_type="npc_directive",
            llm_parameters={},
            llm_reasoning="",
        ))
        dm.save_state()

        dm2 = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir,
            rules_dir=self.tmpdir,
            auto_save_interval=0,
        ))
        dm2.load_state()
        obs = dm2._log_observation(make_event(), "test", {}, "")
        self.assertEqual(obs.observation_id, "obs_006")

    def test_load_missing_files(self):
        dm = DungeonMaster(config=DungeonMasterConfig(
            state_dir=self.tmpdir + "/nonexistent",
            rules_dir=self.tmpdir + "/nonexistent",
            auto_save_interval=0,
        ))
        dm.load_state()
        self.assertEqual(dm.state.total_events_processed, 0)


class TestNarrativeCompression(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dm = DungeonMaster(
            config=DungeonMasterConfig(
                state_dir=self.tmpdir,
                rules_dir=self.tmpdir,
                auto_save_interval=0,
                compression_interval=5,
            ),
        )
        self.dm._running = True

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_compress_creates_summary(self):
        for i in range(10):
            self.dm.raw_events.append({"event_type": "quest_completed", "npc_id": "Thorne"})
        self.dm._compress_narrative_sync()
        self.assertGreater(len(self.dm.state.event_summaries), 0)

    def test_compress_trims_raw_events(self):
        for i in range(20):
            self.dm.raw_events.append({"event_type": "quest_completed", "npc_id": "Thorne"})
        self.dm._compress_narrative_sync()
        self.assertLessEqual(len(self.dm.raw_events), 10)

    def test_compress_trims_event_summaries(self):
        self.dm.config.max_event_summaries = 3
        for _ in range(10):
            self.dm.state.event_summaries.append({"summary": "test", "timestamp": time.time()})
        self.dm._compress_narrative_sync()
        self.assertLessEqual(len(self.dm.state.event_summaries), 3)

    def test_dormant_arc_on_expiry(self):
        arc = StoryArc(
            arc_id="arc_001", title="Old", description="",
            last_event_at=time.time() - 73 * 3600,
        )
        self.dm.state.active_arcs["arc_001"] = arc
        self.dm._compress_narrative_sync()
        self.assertEqual(self.dm.state.active_arcs["arc_001"].status, "dormant")


class TestGetStatus(unittest.TestCase):

    def test_status(self):
        tmpdir = tempfile.mkdtemp()
        try:
            dm = DungeonMaster(config=DungeonMasterConfig(state_dir=tmpdir, rules_dir=tmpdir))
            dm._running = True
            status = dm.get_status()
            self.assertTrue(status["enabled"])
            self.assertTrue(status["running"])
            self.assertEqual(status["active_arcs"], 0)
            self.assertEqual(status["total_events_processed"], 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestStartup(unittest.TestCase):

    def test_start_increments_session(self):
        tmpdir = tempfile.mkdtemp()
        try:
            dm = DungeonMaster(config=DungeonMasterConfig(
                state_dir=tmpdir, rules_dir=tmpdir, auto_save_interval=0,
            ))
            run_async(dm.start())
            self.assertTrue(dm._running)
            self.assertEqual(dm.state.session_count, 1)
            run_async(dm.stop())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_start_disabled(self):
        tmpdir = tempfile.mkdtemp()
        try:
            dm = DungeonMaster(config=DungeonMasterConfig(
                enabled=False, state_dir=tmpdir, rules_dir=tmpdir, auto_save_interval=0,
            ))
            run_async(dm.start())
            self.assertFalse(dm._running)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
