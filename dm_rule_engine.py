"""
DM Rule Engine — Compiled Rule DSL Interpreter for Dungeon Master AI.

Evaluates structured JSON rules against game events without LLM calls.
Handles validation, matching, action execution, and persistence.
"""

import json
import re
import time
import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


CIRCULAR_TRIGGERS: Dict[str, set] = {
    "relationship_change": {"relationship_change", "faction_change"},
    "faction_change": {"faction_change", "relationship_change"},
    "npc_directive": {"npc_state_change"},
    "world_event": {"world_event"},
    "conversation_trigger": set(),
    "lore_update": set(),
    "quest_suggestion": {"quest_completed", "quest_accepted"},
    "tension_adjust": set(),
    "arc_advance": set(),
}

VALID_OPERATORS = frozenset({
    "eq", "neq", "gt", "lt", "gte", "lte",
    "in", "contains", "not_contains", "exists", "regex",
})

VALID_ACTION_TYPES = frozenset({
    "relationship_change", "faction_change",
    "npc_directive", "world_event",
    "conversation_trigger", "lore_update",
    "quest_suggestion", "tension_adjust",
    "arc_advance",
})

RULE_REQUIRED_FIELDS = frozenset({
    "rule_id", "rule_name", "description", "trigger", "actions",
    "priority", "confidence",
})

TRIGGER_REQUIRED_FIELDS = frozenset({"event_type", "conditions"})

CONDITION_REQUIRED_FIELDS = frozenset({"field", "operator", "value"})

ACTION_REQUIRED_FIELDS = frozenset({"type", "parameters"})

PLACEHOLDER_RE = re.compile(r"\{event\.([a-zA-Z0-9_.]+)\}")


@dataclass
class RuleValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)


@dataclass
class RuleMatchResult:
    matched: bool
    rule: Optional[Dict] = None
    actions: Optional[List[Dict]] = None


class DmRuleEngine:
    """
    Rule engine for the Dungeon Master system.

    Loads, validates, matches, and persists compiled rules.
    Rules are JSON objects conforming to the DM Rule DSL.
    """

    def __init__(
        self,
        rules_dir: str = "dm_rules",
        max_active_rules: int = 50,
        max_pending_rules: int = 20,
        min_confidence_auto_activate: float = 0.9,
    ):
        self.rules_dir = Path(rules_dir)
        self.max_active_rules = max_active_rules
        self.max_pending_rules = max_pending_rules
        self.min_confidence_auto_activate = min_confidence_auto_activate

        self.active_rules: List[Dict] = []
        self.pending_rules: List[Dict] = []

        self._rule_seq = 0

    # ============================================
    # RULE VALIDATION
    # ============================================

    def validate(self, rule: Dict) -> RuleValidationResult:
        errors: List[str] = []

        if not isinstance(rule, dict):
            return RuleValidationResult(valid=False, errors=["Rule must be a dict"])

        missing = RULE_REQUIRED_FIELDS - set(rule.keys())
        if missing:
            errors.append(f"Missing required fields: {sorted(missing)}")

        if "rule_id" in rule:
            if not isinstance(rule["rule_id"], str) or not re.match(
                r"^dm_gen_\d{3}$", rule["rule_id"]
            ):
                errors.append(
                    "rule_id must match pattern 'dm_gen_NNN'"
                )

        if "rule_name" in rule:
            if not isinstance(rule["rule_name"], str) or not rule["rule_name"].strip():
                errors.append("rule_name must be a non-empty string")

        if "priority" in rule:
            p = rule["priority"]
            if not isinstance(p, int) or not (0 <= p <= 10):
                errors.append("priority must be an integer 0-10")

        if "confidence" in rule:
            c = rule["confidence"]
            if not isinstance(c, (int, float)) or not (0.0 <= c <= 1.0):
                errors.append("confidence must be a float 0.0-1.0")

        if "trigger" in rule and isinstance(rule["trigger"], dict):
            self._validate_trigger(rule["trigger"], errors)

        if "actions" in rule and isinstance(rule["actions"], list):
            self._validate_actions(rule["actions"], errors)

        if errors:
            return RuleValidationResult(valid=False, errors=errors)

        if "trigger" in rule and "actions" in rule:
            if self._check_circular(rule):
                errors.append(
                    "Circular trigger detected: rule actions would re-trigger this rule"
                )
                return RuleValidationResult(valid=False, errors=errors)

        return RuleValidationResult(valid=True, errors=[])

    def _validate_trigger(self, trigger: Dict, errors: List[str]):
        missing = TRIGGER_REQUIRED_FIELDS - set(trigger.keys())
        if missing:
            errors.append(f"Trigger missing required fields: {sorted(missing)}")
            return

        if not isinstance(trigger["event_type"], str) or not trigger["event_type"]:
            errors.append("trigger.event_type must be a non-empty string")

        conditions = trigger.get("conditions")
        if not isinstance(conditions, list):
            errors.append("trigger.conditions must be a list")
            return

        for i, cond in enumerate(conditions):
            if not isinstance(cond, dict):
                errors.append(f"Condition {i} must be a dict")
                continue
            cmissing = CONDITION_REQUIRED_FIELDS - set(cond.keys())
            if cmissing:
                errors.append(f"Condition {i} missing fields: {sorted(cmissing)}")
                continue
            op = cond["operator"]
            if op not in VALID_OPERATORS:
                errors.append(
                    f"Condition {i}: unknown operator '{op}'"
                )

    def _validate_actions(self, actions: List[Dict], errors: List[str]):
        if not actions:
            errors.append("actions list must not be empty")
            return

        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                errors.append(f"Action {i} must be a dict")
                continue
            amissing = ACTION_REQUIRED_FIELDS - set(action.keys())
            if amissing:
                errors.append(f"Action {i} missing fields: {sorted(amissing)}")
                continue
            atype = action["type"]
            if atype not in VALID_ACTION_TYPES:
                errors.append(f"Action {i}: unknown type '{atype}'")
            if not isinstance(action["parameters"], dict):
                errors.append(f"Action {i}: parameters must be a dict")

    def _check_circular(self, rule: Dict) -> bool:
        trigger_event = rule.get("trigger", {}).get("event_type", "")
        for action in rule.get("actions", []):
            produced = CIRCULAR_TRIGGERS.get(action.get("type", ""), set())
            if trigger_event in produced:
                return True
        return False

    def _check_duplicate(self, rule: Dict) -> bool:
        new_sig = self._rule_signature(rule)
        for existing in self.active_rules + self.pending_rules:
            if self._rule_signature(existing) == new_sig:
                return True
        return False

    def _rule_signature(self, rule: Dict) -> str:
        trigger = rule.get("trigger", {})
        conditions = trigger.get("conditions", [])
        sig_parts = [trigger.get("event_type", "")]
        for c in sorted(conditions, key=lambda x: x.get("field", "")):
            sig_parts.append(f"{c.get('field')}:{c.get('operator')}:{c.get('value')}")
        sig_parts.append(str(len(rule.get("actions", []))))
        for a in sorted(rule.get("actions", []), key=lambda x: x.get("type", "")):
            sig_parts.append(a.get("type", ""))
        return hashlib.md5("|".join(sig_parts).encode()).hexdigest()

    # ============================================
    # RULE MATCHING
    # ============================================

    def match(
        self,
        event_data: Dict,
        narrative_state: Optional[Dict] = None,
    ) -> RuleMatchResult:
        narrative_state = narrative_state or {}

        sorted_rules = sorted(
            [r for r in self.active_rules if r.get("active", True)],
            key=lambda r: r.get("priority", 0),
            reverse=True,
        )

        for rule in sorted_rules:
            if self._rule_matches(rule, event_data, narrative_state):
                resolved_actions = self._resolve_actions(
                    rule.get("actions", []), event_data
                )
                return RuleMatchResult(
                    matched=True,
                    rule=rule,
                    actions=resolved_actions,
                )

        return RuleMatchResult(matched=False)

    def _rule_matches(
        self,
        rule: Dict,
        event_data: Dict,
        narrative_state: Dict,
    ) -> bool:
        trigger = rule.get("trigger", {})
        trigger_type = trigger.get("event_type", "")

        event_type = event_data.get("event_type", "")
        if trigger_type != event_type:
            return False

        for condition in trigger.get("conditions", []):
            if not self._evaluate_condition(condition, event_data, narrative_state):
                return False

        if rule.get("expires_at"):
            try:
                expires = datetime.fromisoformat(
                    rule["expires_at"].replace("Z", "+00:00")
                )
                if datetime.now(timezone.utc) > expires:
                    return False
            except (ValueError, TypeError):
                pass

        return True

    def _evaluate_condition(
        self,
        condition: Dict,
        event_data: Dict,
        narrative_state: Dict,
    ) -> bool:
        field_path = condition.get("field", "")
        operator = condition.get("operator", "")
        expected = condition.get("value")

        actual = self._resolve_field(field_path, event_data, narrative_state)

        if operator == "eq":
            return actual == expected
        elif operator == "neq":
            return actual != expected
        elif operator == "gt":
            return self._safe_compare(actual, expected, lambda a, b: a > b)
        elif operator == "lt":
            return self._safe_compare(actual, expected, lambda a, b: a < b)
        elif operator == "gte":
            return self._safe_compare(actual, expected, lambda a, b: a >= b)
        elif operator == "lte":
            return self._safe_compare(actual, expected, lambda a, b: a <= b)
        elif operator == "in":
            if isinstance(expected, (list, tuple, set)):
                return actual in expected
            return False
        elif operator == "contains":
            if isinstance(actual, (list, tuple, set, str)):
                return expected in actual
            if isinstance(actual, dict):
                return expected in actual
            return False
        elif operator == "not_contains":
            if isinstance(actual, (list, tuple, set, str, dict)):
                return expected not in actual
            return True
        elif operator == "exists":
            return (actual is not None) == bool(expected)
        elif operator == "regex":
            if actual is None:
                return False
            try:
                return bool(re.search(str(expected), str(actual)))
            except re.error:
                return False

        return False

    @staticmethod
    def _safe_compare(actual, expected, comparator):
        try:
            return comparator(float(actual), float(expected))
        except (TypeError, ValueError):
            return False

    def _resolve_field(
        self,
        path: str,
        event_data: Dict,
        narrative_state: Dict,
    ) -> Any:
        if path.startswith("event."):
            return self._traverse(event_data, path[6:])
        elif path.startswith("state."):
            return self._traverse(narrative_state, path[6:])
        return None

    @staticmethod
    def _traverse(data: Any, path: str) -> Any:
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            if current is None:
                return None
        return current

    def _resolve_actions(
        self, actions: List[Dict], event_data: Dict
    ) -> List[Dict]:
        resolved = []
        for action in actions:
            new_action = {
                "type": action["type"],
                "parameters": self._resolve_placeholders(
                    action.get("parameters", {}), event_data
                ),
            }
            resolved.append(new_action)
        return resolved

    def _resolve_placeholders(
        self, params: Dict, event_data: Dict
    ) -> Dict:
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_string(value, event_data)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_placeholders(value, event_data)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_string(v, event_data) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                resolved[key] = value
        return resolved

    def _resolve_string(self, s: str, event_data: Dict) -> str:
        def replacer(match):
            field_path = match.group(1)
            val = self._traverse(event_data, field_path)
            return str(val) if val is not None else match.group(0)

        return PLACEHOLDER_RE.sub(replacer, s)

    # ============================================
    # RULE LIFECYCLE
    # ============================================

    def add_rule(
        self,
        rule: Dict,
        auto_activate: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        validation = self.validate(rule)
        if not validation.valid:
            return False, f"Validation failed: {'; '.join(validation.errors)}"

        if self._check_duplicate(rule):
            return False, "Duplicate rule: a rule with identical trigger conditions already exists"

        if auto_activate and rule.get("confidence", 0) >= self.min_confidence_auto_activate:
            if len(self.active_rules) >= self.max_active_rules:
                self._evict_lowest_priority()
            rule["active"] = True
            self.active_rules.append(rule)
            status = "active"
        else:
            if len(self.pending_rules) >= self.max_pending_rules:
                return False, "Maximum pending rules reached"
            rule["active"] = False
            self.pending_rules.append(rule)
            status = "pending"

        if not rule.get("created_at"):
            rule["created_at"] = datetime.now(timezone.utc).isoformat()

        self._update_rule_seq(rule.get("rule_id", ""))
        return True, status

    def activate_rule(self, rule_id: str) -> bool:
        for i, rule in enumerate(self.pending_rules):
            if rule.get("rule_id") == rule_id:
                if len(self.active_rules) >= self.max_active_rules:
                    self._evict_lowest_priority()
                rule["active"] = True
                self.pending_rules.pop(i)
                self.active_rules.append(rule)
                return True
        return False

    def deactivate_rule(self, rule_id: str) -> bool:
        for rule in self.active_rules:
            if rule.get("rule_id") == rule_id:
                rule["active"] = False
                self.active_rules.remove(rule)
                self.pending_rules.append(rule)
                return True
        return False

    def delete_rule(self, rule_id: str) -> bool:
        for i, rule in enumerate(self.active_rules):
            if rule.get("rule_id") == rule_id:
                self.active_rules.pop(i)
                return True
        for i, rule in enumerate(self.pending_rules):
            if rule.get("rule_id") == rule_id:
                self.pending_rules.pop(i)
                return True
        return False

    def get_rule(self, rule_id: str) -> Optional[Dict]:
        for rule in self.active_rules:
            if rule.get("rule_id") == rule_id:
                return rule
        for rule in self.pending_rules:
            if rule.get("rule_id") == rule_id:
                return rule
        return None

    def _evict_lowest_priority(self):
        if not self.active_rules:
            return
        lowest = min(self.active_rules, key=lambda r: (r.get("priority", 0), r.get("created_at", "")))
        lowest["active"] = False
        self.active_rules.remove(lowest)
        if len(self.pending_rules) < self.max_pending_rules:
            self.pending_rules.append(lowest)

    def _update_rule_seq(self, rule_id: str):
        match = re.match(r"dm_gen_(\d+)", rule_id)
        if match:
            seq = int(match.group(1))
            if seq > self._rule_seq:
                self._rule_seq = seq

    def next_rule_id(self) -> str:
        self._rule_seq += 1
        return f"dm_gen_{self._rule_seq:03d}"

    # ============================================
    # PERSISTENCE
    # ============================================

    def save_rules(self):
        active_dir = self.rules_dir / "active"
        pending_dir = self.rules_dir / "pending"
        active_dir.mkdir(parents=True, exist_ok=True)
        pending_dir.mkdir(parents=True, exist_ok=True)

        for f in active_dir.glob("*.json"):
            f.unlink()
        for f in pending_dir.glob("*.json"):
            f.unlink()

        for rule in self.active_rules:
            rid = rule.get("rule_id", "unknown")
            path = active_dir / f"{rid}.json"
            with open(path, "w") as f:
                json.dump(rule, f, indent=2)

        for rule in self.pending_rules:
            rid = rule.get("rule_id", "unknown")
            path = pending_dir / f"{rid}.json"
            with open(path, "w") as f:
                json.dump(rule, f, indent=2)

    def load_rules(self):
        self.active_rules = []
        self.pending_rules = []

        active_dir = self.rules_dir / "active"
        pending_dir = self.rules_dir / "pending"

        if active_dir.exists():
            for f in sorted(active_dir.glob("*.json")):
                try:
                    with open(f) as fh:
                        rule = json.load(fh)
                    result = self.validate(rule)
                    if result.valid:
                        rule["active"] = True
                        self.active_rules.append(rule)
                        self._update_rule_seq(rule.get("rule_id", ""))
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Warning: Failed to load rule {f.name}: {e}")

        if pending_dir.exists():
            for f in sorted(pending_dir.glob("*.json")):
                try:
                    with open(f) as fh:
                        rule = json.load(fh)
                    result = self.validate(rule)
                    if result.valid:
                        rule["active"] = False
                        self.pending_rules.append(rule)
                        self._update_rule_seq(rule.get("rule_id", ""))
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Warning: Failed to load rule {f.name}: {e}")

    # ============================================
    # UTILITY
    # ============================================

    def get_stats(self) -> Dict:
        return {
            "active_rules": len(self.active_rules),
            "pending_rules": len(self.pending_rules),
            "max_active": self.max_active_rules,
            "max_pending": self.max_pending_rules,
            "next_rule_id": self.next_rule_id_preview(),
        }

    def next_rule_id_preview(self) -> str:
        return f"dm_gen_{self._rule_seq + 1:03d}"
