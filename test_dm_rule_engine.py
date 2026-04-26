"""
Unit Tests for DM Rule Engine
Tests validation, condition matching, action execution, rule lifecycle, and persistence.
"""

import unittest
import json
import tempfile
import shutil
import os
import time
from pathlib import Path
from dm_rule_engine import DmRuleEngine, RuleValidationResult, RuleMatchResult


def make_valid_rule(**overrides) -> dict:
    rule = {
        "rule_id": "dm_gen_001",
        "rule_name": "Test Rule",
        "description": "A test rule for unit testing",
        "trigger": {
            "event_type": "quest_failed",
            "conditions": [
                {"field": "event.data.quest_type", "operator": "eq", "value": "escort"}
            ],
        },
        "actions": [
            {
                "type": "relationship_change",
                "parameters": {
                    "npc": "{event.npc_id}",
                    "delta": -25,
                    "reason": "failed_escort_quest",
                },
            }
        ],
        "priority": 6,
        "confidence": 0.92,
        "times_observed": 5,
        "source_observations": ["obs_001", "obs_002", "obs_003", "obs_004", "obs_005"],
        "created_at": "2026-04-25T14:30:00Z",
        "expires_at": None,
        "active": True,
    }
    rule.update(overrides)
    return rule


def make_event(event_type: str = "quest_failed", **extra) -> dict:
    data = {"event_type": event_type, "npc_id": "Thorne", "player_id": "player1", "zone_id": "ironhold"}
    data["data"] = {"quest_type": "escort", "quest_name": "Escort the Merchant"}
    data.update(extra)
    return data


class TestRuleValidation(unittest.TestCase):

    def setUp(self):
        self.engine = DmRuleEngine(rules_dir=tempfile.mkdtemp())

    def test_valid_rule_passes(self):
        result = self.engine.validate(make_valid_rule())
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_missing_required_field(self):
        for field in ["rule_id", "rule_name", "description", "trigger", "actions", "priority", "confidence"]:
            rule = make_valid_rule()
            del rule[field]
            result = self.engine.validate(rule)
            self.assertFalse(result.valid, f"Should fail without {field}")

    def test_invalid_rule_id_format(self):
        result = self.engine.validate(make_valid_rule(rule_id="bad_id"))
        self.assertFalse(result.valid)

    def test_empty_rule_name(self):
        result = self.engine.validate(make_valid_rule(rule_name=""))
        self.assertFalse(result.valid)

    def test_priority_out_of_range(self):
        result = self.engine.validate(make_valid_rule(priority=11))
        self.assertFalse(result.valid)
        result = self.engine.validate(make_valid_rule(priority=-1))
        self.assertFalse(result.valid)

    def test_confidence_out_of_range(self):
        result = self.engine.validate(make_valid_rule(confidence=1.5))
        self.assertFalse(result.valid)
        result = self.engine.validate(make_valid_rule(confidence=-0.1))
        self.assertFalse(result.valid)

    def test_unknown_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"][0]["operator"] = "unknown_op"
        result = self.engine.validate(rule)
        self.assertFalse(result.valid)

    def test_unknown_action_type(self):
        rule = make_valid_rule()
        rule["actions"][0]["type"] = "hack_the_mainframe"
        result = self.engine.validate(rule)
        self.assertFalse(result.valid)

    def test_circular_trigger_detected(self):
        rule = make_valid_rule()
        rule["trigger"]["event_type"] = "relationship_change"
        rule["actions"] = [
            {"type": "relationship_change", "parameters": {"npc": "x", "delta": -5, "reason": "test"}}
        ]
        result = self.engine.validate(rule)
        self.assertFalse(result.valid)

    def test_non_circular_trigger_passes(self):
        rule = make_valid_rule()
        rule["trigger"]["event_type"] = "quest_failed"
        rule["actions"] = [
            {"type": "lore_update", "parameters": {"lore_id": "x", "title": "t", "content": "c"}}
        ]
        result = self.engine.validate(rule)
        self.assertTrue(result.valid)

    def test_empty_actions_list(self):
        rule = make_valid_rule()
        rule["actions"] = []
        result = self.engine.validate(rule)
        self.assertFalse(result.valid)

    def test_action_missing_parameters(self):
        rule = make_valid_rule()
        del rule["actions"][0]["parameters"]
        result = self.engine.validate(rule)
        self.assertFalse(result.valid)

    def test_trigger_missing_event_type(self):
        rule = make_valid_rule()
        del rule["trigger"]["event_type"]
        result = self.engine.validate(rule)
        self.assertFalse(result.valid)

    def test_condition_missing_field(self):
        rule = make_valid_rule()
        del rule["trigger"]["conditions"][0]["field"]
        result = self.engine.validate(rule)
        self.assertFalse(result.valid)

    def test_rule_must_be_dict(self):
        result = self.engine.validate("not a dict")
        self.assertFalse(result.valid)

    def test_actions_parameters_must_be_dict(self):
        rule = make_valid_rule()
        rule["actions"][0]["parameters"] = "not a dict"
        result = self.engine.validate(rule)
        self.assertFalse(result.valid)

    def test_all_valid_operators(self):
        from dm_rule_engine import VALID_OPERATORS
        for op in VALID_OPERATORS:
            rule = make_valid_rule()
            rule["trigger"]["conditions"][0]["operator"] = op
            if op == "exists":
                rule["trigger"]["conditions"][0]["value"] = True
            elif op == "regex":
                rule["trigger"]["conditions"][0]["value"] = ".*"
            elif op == "in":
                rule["trigger"]["conditions"][0]["value"] = ["escort"]
            result = self.engine.validate(rule)
            self.assertTrue(result.valid, f"Operator '{op}' should be valid")


class TestConditionMatching(unittest.TestCase):

    def setUp(self):
        self.engine = DmRuleEngine(rules_dir=tempfile.mkdtemp())

    def test_eq_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.quest_type", "operator": "eq", "value": "escort"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)

    def test_eq_operator_no_match(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.quest_type", "operator": "eq", "value": "fetch"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_neq_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.quest_type", "operator": "neq", "value": "fetch"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)

    def test_gt_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.damage", "operator": "gt", "value": 50}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"damage": 75}))
        self.assertTrue(result.matched)

    def test_lt_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.score", "operator": "lt", "value": 0}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"score": -5}))
        self.assertTrue(result.matched)

    def test_gte_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.count", "operator": "gte", "value": 5}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"count": 5}))
        self.assertTrue(result.matched)
        result = self.engine.match(make_event(data={"count": 4}))
        self.assertFalse(result.matched)

    def test_lte_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.count", "operator": "lte", "value": 5}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"count": 5}))
        self.assertTrue(result.matched)
        result = self.engine.match(make_event(data={"count": 6}))
        self.assertFalse(result.matched)

    def test_in_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.npc_id", "operator": "in", "value": ["Thorne", "Elara"]}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)

    def test_in_operator_no_match(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.npc_id", "operator": "in", "value": ["Elara", "Gandalf"]}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_contains_operator_list(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.tags", "operator": "contains", "value": "combat"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"tags": ["combat", "danger"]}))
        self.assertTrue(result.matched)

    def test_contains_operator_string(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.description", "operator": "contains", "value": "bandit"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"description": "A bandit attack"}))
        self.assertTrue(result.matched)

    def test_contains_operator_dict(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.npc_archetype", "operator": "contains", "value": "merchant"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"npc_archetype": {"merchant": True, "warrior": False}}))
        self.assertTrue(result.matched)

    def test_not_contains_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.tags", "operator": "not_contains", "value": "peaceful"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"tags": ["combat", "danger"]}))
        self.assertTrue(result.matched)

    def test_exists_operator_true(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.zone_id", "operator": "exists", "value": True}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"zone_id": "eastern_road"}))
        self.assertTrue(result.matched)

    def test_exists_operator_false(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.nonexistent", "operator": "exists", "value": True}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_regex_operator(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.quest_name", "operator": "regex", "value": "^Escort"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)

    def test_regex_operator_no_match(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.quest_name", "operator": "regex", "value": "^Fetch"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_multiple_conditions_and_logic(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.quest_type", "operator": "eq", "value": "escort"},
            {"field": "event.npc_id", "operator": "eq", "value": "Thorne"},
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)
        result = self.engine.match(make_event(npc_id="Elara"))
        self.assertFalse(result.matched)

    def test_nested_field_access(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.quest_type", "operator": "eq", "value": "escort"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)

    def test_missing_field_returns_none(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.nonexistent_field", "operator": "eq", "value": "anything"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_state_field_access(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "state.tension.npc:Elara", "operator": "gt", "value": 0.5}
        ]
        self.engine.active_rules = [rule]
        state = {"tension": {"npc:Elara": 0.7}}
        result = self.engine.match(make_event(), state)
        self.assertTrue(result.matched)


class TestRuleMatching(unittest.TestCase):

    def setUp(self):
        self.engine = DmRuleEngine(rules_dir=tempfile.mkdtemp())

    def test_single_rule_match(self):
        self.engine.active_rules = [make_valid_rule()]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)
        self.assertIsNotNone(result.rule)

    def test_no_rule_match(self):
        self.engine.active_rules = [make_valid_rule()]
        result = self.engine.match(make_event(event_type="quest_completed"))
        self.assertFalse(result.matched)

    def test_priority_ordering(self):
        low = make_valid_rule(rule_id="dm_gen_001", rule_name="Low", priority=2)
        high = make_valid_rule(rule_id="dm_gen_002", rule_name="High", priority=8)
        self.engine.active_rules = [low, high]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)
        self.assertEqual(result.rule["rule_name"], "High")

    def test_inactive_rules_ignored(self):
        rule = make_valid_rule()
        rule["active"] = False
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_no_rules_returns_no_match(self):
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_event_type_mismatch(self):
        rule = make_valid_rule()
        rule["trigger"]["event_type"] = "quest_completed"
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(event_type="quest_failed"))
        self.assertFalse(result.matched)

    def test_expired_rule_ignored(self):
        rule = make_valid_rule()
        rule["expires_at"] = "2020-01-01T00:00:00Z"
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)


class TestActionExecution(unittest.TestCase):

    def setUp(self):
        self.engine = DmRuleEngine(rules_dir=tempfile.mkdtemp())

    def test_action_resolves_event_placeholders(self):
        rule = make_valid_rule()
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(npc_id="Thorne"))
        self.assertTrue(result.matched)
        self.assertEqual(result.actions[0]["parameters"]["npc"], "Thorne")

    def test_multiple_actions_resolved(self):
        rule = make_valid_rule()
        rule["actions"] = [
            {
                "type": "relationship_change",
                "parameters": {"npc": "{event.npc_id}", "delta": -25, "reason": "test"},
            },
            {
                "type": "tension_adjust",
                "parameters": {"target": "{event.npc_id}", "delta": 0.2},
            },
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(npc_id="Elara"))
        self.assertTrue(result.matched)
        self.assertEqual(len(result.actions), 2)
        self.assertEqual(result.actions[0]["parameters"]["npc"], "Elara")
        self.assertEqual(result.actions[1]["parameters"]["target"], "Elara")

    def test_non_string_params_unchanged(self):
        rule = make_valid_rule()
        rule["actions"] = [
            {"type": "tension_adjust", "parameters": {"target": "{event.npc_id}", "delta": 0.2}},
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertEqual(result.actions[0]["parameters"]["delta"], 0.2)

    def test_placeholder_in_list_param(self):
        rule = make_valid_rule()
        rule["actions"] = [
            {"type": "lore_update", "parameters": {
                "lore_id": "test",
                "title": "Test",
                "content": "Content",
                "known_by": ["{event.npc_id}", "everyone"],
            }},
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(npc_id="Thorne"))
        self.assertEqual(result.actions[0]["parameters"]["known_by"], ["Thorne", "everyone"])

    def test_unresolvable_placeholder_kept(self):
        rule = make_valid_rule()
        rule["actions"] = [
            {"type": "npc_directive", "parameters": {
                "npc": "{event.nonexistent_field}",
                "directive": "test",
            }},
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertEqual(result.actions[0]["parameters"]["npc"], "{event.nonexistent_field}")


class TestRuleLifecycle(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.engine = DmRuleEngine(rules_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_rule_auto_activates(self):
        ok, status = self.engine.add_rule(make_valid_rule(confidence=0.95))
        self.assertTrue(ok)
        self.assertEqual(status, "active")
        self.assertEqual(len(self.engine.active_rules), 1)

    def test_add_rule_pending_low_confidence(self):
        ok, status = self.engine.add_rule(make_valid_rule(confidence=0.7))
        self.assertTrue(ok)
        self.assertEqual(status, "pending")
        self.assertEqual(len(self.engine.pending_rules), 1)

    def test_add_rule_rejects_invalid(self):
        ok, msg = self.engine.add_rule(make_valid_rule(rule_id="bad"))
        self.assertFalse(ok)

    def test_add_rule_rejects_duplicate(self):
        self.engine.add_rule(make_valid_rule())
        ok, msg = self.engine.add_rule(make_valid_rule())
        self.assertFalse(ok)
        self.assertIn("Duplicate", msg)

    def test_activate_pending_rule(self):
        self.engine.add_rule(make_valid_rule(confidence=0.5))
        self.assertEqual(len(self.engine.pending_rules), 1)
        rid = self.engine.pending_rules[0]["rule_id"]
        ok = self.engine.activate_rule(rid)
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.active_rules), 1)
        self.assertEqual(len(self.engine.pending_rules), 0)

    def test_activate_nonexistent(self):
        self.assertFalse(self.engine.activate_rule("dm_gen_999"))

    def test_deactivate_rule(self):
        self.engine.add_rule(make_valid_rule(confidence=0.95))
        rid = self.engine.active_rules[0]["rule_id"]
        ok = self.engine.deactivate_rule(rid)
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.active_rules), 0)
        self.assertEqual(len(self.engine.pending_rules), 1)

    def test_deactivate_nonexistent(self):
        self.assertFalse(self.engine.deactivate_rule("dm_gen_999"))

    def test_delete_active_rule(self):
        self.engine.add_rule(make_valid_rule(confidence=0.95))
        rid = self.engine.active_rules[0]["rule_id"]
        ok = self.engine.delete_rule(rid)
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.active_rules), 0)

    def test_delete_pending_rule(self):
        self.engine.add_rule(make_valid_rule(confidence=0.5))
        rid = self.engine.pending_rules[0]["rule_id"]
        ok = self.engine.delete_rule(rid)
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.pending_rules), 0)

    def test_delete_nonexistent(self):
        self.assertFalse(self.engine.delete_rule("dm_gen_999"))

    def test_get_rule(self):
        self.engine.add_rule(make_valid_rule(confidence=0.95))
        rid = self.engine.active_rules[0]["rule_id"]
        rule = self.engine.get_rule(rid)
        self.assertIsNotNone(rule)
        self.assertEqual(rule["rule_id"], rid)

    def test_get_rule_not_found(self):
        self.assertIsNone(self.engine.get_rule("dm_gen_999"))

    def test_eviction_at_max_active(self):
        engine = DmRuleEngine(rules_dir=self.tmpdir, max_active_rules=3)
        for i in range(4):
            ok, _ = engine.add_rule(make_valid_rule(
                rule_id=f"dm_gen_{i+1:03d}",
                rule_name=f"Rule {i}",
                confidence=0.95,
                priority=i * 3,
                trigger={
                    "event_type": "quest_failed",
                    "conditions": [
                        {"field": "event.data.quest_type", "operator": "eq", "value": f"type_{i}"}
                    ],
                },
            ))
            self.assertTrue(ok)
        self.assertEqual(len(engine.active_rules), 3)
        self.assertTrue(len(engine.pending_rules) >= 1)

    def test_next_rule_id(self):
        rid = self.engine.next_rule_id()
        self.assertEqual(rid, "dm_gen_001")
        rid2 = self.engine.next_rule_id()
        self.assertEqual(rid2, "dm_gen_002")

    def test_max_pending_rules(self):
        engine = DmRuleEngine(rules_dir=self.tmpdir, max_pending_rules=2, max_active_rules=0)
        engine.min_confidence_auto_activate = 1.0
        for i in range(2):
            ok, _ = engine.add_rule(make_valid_rule(
                rule_id=f"dm_gen_{i+1:03d}",
                rule_name=f"Rule {i}",
                confidence=0.5,
                trigger={
                    "event_type": "quest_failed",
                    "conditions": [
                        {"field": "event.data.quest_type", "operator": "eq", "value": f"type_{i}"}
                    ],
                },
            ))
            self.assertTrue(ok)
        ok, msg = engine.add_rule(make_valid_rule(
            rule_id="dm_gen_003", rule_name="Overflow", confidence=0.5,
            trigger={
                "event_type": "quest_completed",
                "conditions": [
                    {"field": "event.data.quest_type", "operator": "eq", "value": "fetch"}
                ],
            },
        ))
        self.assertFalse(ok)
        self.assertIn("pending", msg.lower())


class TestPersistence(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.engine = DmRuleEngine(rules_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_active(self):
        self.engine.add_rule(make_valid_rule(confidence=0.95))
        self.engine.save_rules()

        active_dir = Path(self.tmpdir) / "active"
        files = list(active_dir.glob("*.json"))
        self.assertEqual(len(files), 1)

        engine2 = DmRuleEngine(rules_dir=self.tmpdir)
        engine2.load_rules()
        self.assertEqual(len(engine2.active_rules), 1)
        self.assertEqual(engine2.active_rules[0]["rule_id"], "dm_gen_001")

    def test_save_and_load_pending(self):
        self.engine.add_rule(make_valid_rule(confidence=0.5))
        self.engine.save_rules()

        pending_dir = Path(self.tmpdir) / "pending"
        files = list(pending_dir.glob("*.json"))
        self.assertEqual(len(files), 1)

        engine2 = DmRuleEngine(rules_dir=self.tmpdir)
        engine2.load_rules()
        self.assertEqual(len(engine2.pending_rules), 1)

    def test_save_clears_old_files(self):
        self.engine.add_rule(make_valid_rule(rule_id="dm_gen_001", confidence=0.95))
        self.engine.save_rules()

        self.engine.delete_rule("dm_gen_001")
        self.engine.add_rule(make_valid_rule(
            rule_id="dm_gen_002", rule_name="New Rule", confidence=0.95
        ))
        self.engine.save_rules()

        active_dir = Path(self.tmpdir) / "active"
        files = list(active_dir.glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].name.startswith("dm_gen_002"))

    def test_load_skips_invalid_files(self):
        active_dir = Path(self.tmpdir) / "active"
        active_dir.mkdir(parents=True, exist_ok=True)
        with open(active_dir / "dm_gen_099.json", "w") as f:
            json.dump({"invalid": True}, f)

        engine2 = DmRuleEngine(rules_dir=self.tmpdir)
        engine2.load_rules()
        self.assertEqual(len(engine2.active_rules), 0)

    def test_load_skips_malformed_json(self):
        active_dir = Path(self.tmpdir) / "active"
        active_dir.mkdir(parents=True, exist_ok=True)
        with open(active_dir / "dm_gen_098.json", "w") as f:
            f.write("not valid json {{{")

        engine2 = DmRuleEngine(rules_dir=self.tmpdir)
        engine2.load_rules()
        self.assertEqual(len(engine2.active_rules), 0)

    def test_rule_seq_restored_on_load(self):
        self.engine.add_rule(make_valid_rule(rule_id="dm_gen_005", confidence=0.95))
        self.engine.save_rules()

        engine2 = DmRuleEngine(rules_dir=self.tmpdir)
        engine2.load_rules()
        self.assertEqual(engine2.next_rule_id(), "dm_gen_006")

    def test_empty_load(self):
        engine2 = DmRuleEngine(rules_dir=self.tmpdir)
        engine2.load_rules()
        self.assertEqual(len(engine2.active_rules), 0)
        self.assertEqual(len(engine2.pending_rules), 0)


class TestGetStats(unittest.TestCase):

    def test_stats(self):
        engine = DmRuleEngine(rules_dir=tempfile.mkdtemp(), max_active_rules=50)
        stats = engine.get_stats()
        self.assertEqual(stats["active_rules"], 0)
        self.assertEqual(stats["pending_rules"], 0)
        self.assertEqual(stats["max_active"], 50)


class TestEdgeCases(unittest.TestCase):

    def setUp(self):
        self.engine = DmRuleEngine(rules_dir=tempfile.mkdtemp())

    def test_gt_with_non_numeric(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.name", "operator": "gt", "value": 5}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"name": "hello"}))
        self.assertFalse(result.matched)

    def test_in_with_non_list(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.value", "operator": "in", "value": "not_a_list"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"value": "x"}))
        self.assertFalse(result.matched)

    def test_regex_with_invalid_pattern(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.text", "operator": "regex", "value": "[invalid"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"text": "hello"}))
        self.assertFalse(result.matched)

    def test_none_field_value(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.missing", "operator": "eq", "value": None}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)

    def test_deep_nested_field(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.a.b.c", "operator": "eq", "value": "deep"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event(data={"a": {"b": {"c": "deep"}}}))
        self.assertTrue(result.matched)

    def test_not_contains_on_none(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.missing", "operator": "not_contains", "value": "x"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertTrue(result.matched)

    def test_contains_on_none(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.missing", "operator": "contains", "value": "x"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_regex_on_none(self):
        rule = make_valid_rule()
        rule["trigger"]["conditions"] = [
            {"field": "event.data.missing", "operator": "regex", "value": ".*"}
        ]
        self.engine.active_rules = [rule]
        result = self.engine.match(make_event())
        self.assertFalse(result.matched)

    def test_all_valid_action_types(self):
        from dm_rule_engine import VALID_ACTION_TYPES
        for atype in VALID_ACTION_TYPES:
            rule = make_valid_rule()
            rule["actions"] = [{"type": atype, "parameters": {"key": "val"}}]
            result = self.engine.validate(rule)
            self.assertTrue(result.valid, f"Action type '{atype}' should be valid")


if __name__ == "__main__":
    unittest.main()
