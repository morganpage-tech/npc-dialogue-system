"""
Dungeon Master AI — Event-driven narrative overseer for NPC Dialogue System.

Subscribes to game events, maintains narrative understanding,
and emits directives that subsystems act on. Observes its own repeated
LLM judgments and compiles them into permanent structured rules.
"""

import os
import json
import time
import hashlib
import asyncio
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum

from npc_state_manager import StateEvent, EventType, EventCallback
from dm_rule_engine import DmRuleEngine


# ============================================
# DATA MODELS
# ============================================


@dataclass
class StoryArc:
    arc_id: str
    title: str
    description: str
    status: str = "active"
    involved_npcs: List[str] = field(default_factory=list)
    involved_players: List[str] = field(default_factory=list)
    key_events: List[Dict] = field(default_factory=list)
    tension_level: float = 0.0
    started_at: float = field(default_factory=time.time)
    last_event_at: float = field(default_factory=time.time)
    resolution_conditions: List[str] = field(default_factory=list)

    def add_event(self, event_type: str, summary: str):
        self.key_events.append({
            "event_type": event_type,
            "timestamp": time.time(),
            "summary": summary,
        })
        self.last_event_at = time.time()

    def is_expired(self, ttl_hours: int = 72) -> bool:
        return (time.time() - self.last_event_at) > (ttl_hours * 3600)

    def to_dict(self) -> Dict:
        return {
            "arc_id": self.arc_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "involved_npcs": self.involved_npcs,
            "involved_players": self.involved_players,
            "key_events": self.key_events,
            "tension_level": self.tension_level,
            "started_at": self.started_at,
            "last_event_at": self.last_event_at,
            "resolution_conditions": self.resolution_conditions,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "StoryArc":
        return cls(
            arc_id=data["arc_id"],
            title=data["title"],
            description=data.get("description", ""),
            status=data.get("status", "active"),
            involved_npcs=data.get("involved_npcs", []),
            involved_players=data.get("involved_players", []),
            key_events=data.get("key_events", []),
            tension_level=data.get("tension_level", 0.0),
            started_at=data.get("started_at", time.time()),
            last_event_at=data.get("last_event_at", time.time()),
            resolution_conditions=data.get("resolution_conditions", []),
        )


@dataclass
class Observation:
    observation_id: str
    event_type: str
    event_hash: str
    event_summary: str
    context_snapshot: Dict
    llm_directive_type: str
    llm_parameters: Dict
    llm_reasoning: str
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.0

    def similarity_key(self) -> str:
        return f"{self.event_type}:{self.llm_directive_type}"

    def to_dict(self) -> Dict:
        return {
            "observation_id": self.observation_id,
            "event_type": self.event_type,
            "event_hash": self.event_hash,
            "event_summary": self.event_summary,
            "context_snapshot": self.context_snapshot,
            "llm_directive_type": self.llm_directive_type,
            "llm_parameters": self.llm_parameters,
            "llm_reasoning": self.llm_reasoning,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Observation":
        return cls(
            observation_id=data["observation_id"],
            event_type=data["event_type"],
            event_hash=data.get("event_hash", ""),
            event_summary=data.get("event_summary", ""),
            context_snapshot=data.get("context_snapshot", {}),
            llm_directive_type=data["llm_directive_type"],
            llm_parameters=data.get("llm_parameters", {}),
            llm_reasoning=data.get("llm_reasoning", ""),
            timestamp=data.get("timestamp", time.time()),
            confidence=data.get("confidence", 0.0),
        )


@dataclass
class NarrativeState:
    story_summary: str = ""
    active_arcs: Dict[str, StoryArc] = field(default_factory=dict)
    tension_map: Dict[str, float] = field(default_factory=dict)
    npc_mood_overrides: Dict[str, str] = field(default_factory=dict)
    world_conditions: set = field(default_factory=set)
    recent_observations: List[Observation] = field(default_factory=list)
    event_summaries: List[Dict] = field(default_factory=list)
    session_count: int = 0
    total_events_processed: int = 0
    total_rules_compiled: int = 0
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "story_summary": self.story_summary,
            "active_arcs": {k: v.to_dict() for k, v in self.active_arcs.items()},
            "tension_map": self.tension_map,
            "npc_mood_overrides": self.npc_mood_overrides,
            "world_conditions": list(self.world_conditions),
            "recent_observations": [o.to_dict() for o in self.recent_observations],
            "event_summaries": self.event_summaries,
            "session_count": self.session_count,
            "total_events_processed": self.total_events_processed,
            "total_rules_compiled": self.total_rules_compiled,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "NarrativeState":
        arcs = {}
        for k, v in data.get("active_arcs", {}).items():
            arcs[k] = StoryArc.from_dict(v) if isinstance(v, dict) else v
        observations = []
        for o in data.get("recent_observations", []):
            observations.append(Observation.from_dict(o) if isinstance(o, dict) else o)
        return cls(
            story_summary=data.get("story_summary", ""),
            active_arcs=arcs,
            tension_map=data.get("tension_map", {}),
            npc_mood_overrides=data.get("npc_mood_overrides", {}),
            world_conditions=set(data.get("world_conditions", [])),
            recent_observations=observations,
            event_summaries=data.get("event_summaries", []),
            session_count=data.get("session_count", 0),
            total_events_processed=data.get("total_events_processed", 0),
            total_rules_compiled=data.get("total_rules_compiled", 0),
            last_updated=data.get("last_updated", time.time()),
        )


@dataclass
class DungeonMasterConfig:
    enabled: bool = True
    model: str = "llama3.2:3b"
    backend: str = "ollama"
    api_key: Optional[str] = None
    temperature: float = 0.6
    max_tokens: int = 300
    enabled_triggers: Dict[str, bool] = field(default_factory=lambda: {
        "relationship_change": True,
        "quest_completed": True,
        "quest_failed": True,
        "world_event": True,
        "npc_state_change": True,
        "dialogue_message": False,
    })
    min_observations: int = 5
    min_confidence_auto_activate: float = 0.9
    max_active_rules: int = 50
    max_pending_rules: int = 20
    max_new_rules_per_session: int = 5
    max_observations: int = 200
    rule_ttl_hours: Optional[int] = None
    max_active_arcs: int = 5
    max_raw_events: int = 100
    max_event_summaries: int = 20
    compression_interval: int = 10
    context_token_budget: int = 750
    tension_threshold: float = 0.8
    tension_decay_rate: float = 0.05
    tension_increase_default: float = 0.15
    state_dir: str = "dm_state"
    rules_dir: str = "dm_rules"
    auto_save_interval: int = 120

    @classmethod
    def from_env(cls) -> "DungeonMasterConfig":
        cfg = cls()
        cfg.enabled = os.getenv("DM_ENABLED", "true").lower() == "true"
        cfg.model = os.getenv("DM_MODEL", cfg.model)
        cfg.backend = os.getenv("DM_BACKEND", cfg.backend)
        cfg.temperature = float(os.getenv("DM_TEMPERATURE", str(cfg.temperature)))
        cfg.max_active_rules = int(os.getenv("DM_MAX_RULES", str(cfg.max_active_rules)))
        cfg.min_observations = int(os.getenv("DM_MIN_OBSERVATIONS", str(cfg.min_observations)))
        cfg.min_confidence_auto_activate = float(
            os.getenv("DM_AUTO_ACTIVATE_THRESHOLD", str(cfg.min_confidence_auto_activate))
        )
        return cfg


# ============================================
# IGNORED EVENT TYPES
# ============================================

IGNORED_EVENT_TYPES = frozenset({
    EventType.DIALOGUE_START,
    EventType.DIALOGUE_END,
    EventType.PLAYER_JOINED,
    EventType.PLAYER_LEFT,
    EventType.QUEST_PROGRESS,
    EventType.DM_QUEST_SUGGESTION,
    EventType.DM_NPC_DIRECTIVE,
    EventType.DM_WORLD_EVENT,
    EventType.DM_CONVERSATION_TRIGGER,
    EventType.DM_LORE_UPDATE,
    EventType.DM_RELATIONSHIP_OVERRIDE,
    EventType.DM_RULE_COMPILED,
})

NEGATIVE_EVENTS = frozenset({
    "quest_failed",
    "relationship_change",
    "faction_change",
    "npc_state_change",
})

POSITIVE_EVENTS = frozenset({
    "quest_completed",
})


# ============================================
# DUNGEON MASTER
# ============================================


class DungeonMaster:
    """
    Event-driven AI overseer for the game world.

    Subscribes to game events, evaluates compiled rules first (no LLM),
    falls back to LLM judgment when no rule matches, logs observations,
    and compiles repeated patterns into permanent rules.
    """

    def __init__(
        self,
        state_manager: Any = None,
        event_callback: EventCallback = None,
        rule_engine: DmRuleEngine = None,
        config: DungeonMasterConfig = None,
        llm_provider: Any = None,
    ):
        self.config = config or DungeonMasterConfig.from_env()
        self.state_manager = state_manager
        self.event_callback = event_callback
        self.rule_engine = rule_engine or DmRuleEngine(
            rules_dir=self.config.rules_dir,
            max_active_rules=self.config.max_active_rules,
            max_pending_rules=self.config.max_pending_rules,
            min_confidence_auto_activate=self.config.min_confidence_auto_activate,
        )
        self.llm_provider = llm_provider

        self.state = NarrativeState()
        self.raw_events: List[Dict] = []
        self._events_since_compression = 0
        self._rules_compiled_this_session = 0
        self._save_task: Optional[asyncio.Task] = None
        self._running = False

        self._arc_seq = 0
        self._obs_seq = 0

    # ============================================
    # LIFECYCLE
    # ============================================

    async def start(self):
        if not self.config.enabled:
            return
        self._running = True
        self.state.session_count += 1
        if self.config.auto_save_interval > 0:
            self._save_task = asyncio.create_task(self._auto_save_loop())

    async def stop(self):
        self._running = False
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        self.save_state()
        self.rule_engine.save_rules()

    # ============================================
    # EVENT HANDLING
    # ============================================

    async def handle_event(self, event: StateEvent):
        if not self.config.enabled:
            return
        if not self._running:
            return
        if event.event_type in IGNORED_EVENT_TYPES:
            return
        if event.data.get("source") == "dungeon_master":
            return

        event_type_str = event.event_type.value
        if not self.config.enabled_triggers.get(event_type_str, False):
            return

        self.state.total_events_processed += 1
        self.state.last_updated = time.time()

        self.raw_events.append(event.to_dict())
        if len(self.raw_events) > self.config.max_raw_events:
            self.raw_events = self.raw_events[-self.config.max_raw_events:]

        self._update_tension(event)

        event_data = self._event_to_match_data(event)
        match_result = self.rule_engine.match(event_data, self.state.to_dict())

        if match_result.matched:
            await self._emit_directive_from_actions(
                match_result.actions, event, rule_matched=True
            )
        else:
            await self._llm_judge(event)

        self._check_tension_threshold()

        self._events_since_compression += 1
        if self._events_since_compression >= self.config.compression_interval:
            self._compress_narrative_sync()
            self._events_since_compression = 0

    def _event_to_match_data(self, event: StateEvent) -> Dict:
        return {
            "event_type": event.event_type.value,
            "player_id": event.player_id,
            "npc_id": event.npc_id,
            "zone_id": event.zone_id,
            "data": event.data,
        }

    # ============================================
    # HARDCODED FAST-PATH RULES
    # ============================================

    def _apply_hardcoded_rules(self, event: StateEvent) -> Optional[List[Dict]]:
        et = event.event_type
        data = event.data

        if et == EventType.RELATIONSHIP_CHANGE:
            return self._handle_relationship_change(event, data)
        if et == EventType.QUEST_COMPLETED:
            return self._handle_quest_completed(event, data)
        if et == EventType.QUEST_FAILED:
            return self._handle_quest_failed(event, data)
        if et == EventType.FACTION_CHANGE:
            return self._handle_faction_change(event, data)
        if et == EventType.WORLD_EVENT:
            return self._handle_world_event(event, data)

        return None

    def _handle_relationship_change(self, event: StateEvent, data: Dict) -> Optional[List[Dict]]:
        new_level = data.get("new_level", "")
        old_level = data.get("old_level", "")
        npc_id = event.npc_id or data.get("npc_name", "")

        directives = []

        level_transitions = {
            ("Liked", "Loved"): {
                "directive": "offer_gift",
                "prompt_modifier": f"You deeply appreciate the player. Consider offering them a personal gift or sharing a secret.",
            },
            ("Neutral", "Disliked"): {
                "directive": "cold_distant",
                "prompt_modifier": f"You have become cold towards the player. Be distant and raise your prices slightly.",
            },
            ("Disliked", "Hated"): {
                "directive": "refuse_service",
                "prompt_modifier": f"You refuse to do business with the player. Direct them elsewhere.",
            },
        }

        transition = level_transitions.get((old_level, new_level))
        if transition:
            directives.append({
                "type": "DM_NPC_DIRECTIVE",
                "data": {
                    "directive_type": "DM_NPC_DIRECTIVE",
                    "npc_name": npc_id,
                    "directive": transition["directive"],
                    "prompt_modifier": transition["prompt_modifier"],
                    "duration": "until_proven_otherwise",
                    "expires_after_events": 5,
                    "narrative_reason": f"Relationship changed from {old_level} to {new_level}",
                },
            })

        if new_level == "Adored":
            directives.append({
                "type": "DM_LORE_UPDATE",
                "data": {
                    "directive_type": "DM_LORE_UPDATE",
                    "lore_id": f"legendary_friendship_{npc_id}_{int(time.time())}",
                    "title": f"Legendary Friendship with {npc_id}",
                    "content": f"The player has achieved a legendary bond of friendship with {npc_id}.",
                    "category": "relationships",
                    "known_by": [npc_id],
                    "importance": 0.9,
                    "narrative_reason": f"Relationship reached Adored level with {npc_id}",
                },
            })

        if (old_level, new_level) == ("Disliked", "Hated") and npc_id:
            directives.append({
                "type": "DM_CONVERSATION_TRIGGER",
                "data": {
                    "directive_type": "DM_CONVERSATION_TRIGGER",
                    "npc1": npc_id,
                    "npc2": data.get("nearby_npc", ""),
                    "topic": "player_reputation",
                    "reason": f"{npc_id} hates the player and spreads negative gossip",
                    "trigger_type": "event",
                    "player_can_overhear": True,
                    "narrative_reason": f"Relationship dropped to Hated, {npc_id} gossips negatively",
                },
            })

        return directives if directives else None

    def _handle_quest_completed(self, event: StateEvent, data: Dict) -> Optional[List[Dict]]:
        npc_id = event.npc_id or data.get("npc_name", "")
        directives = [{
            "type": "DM_RELATIONSHIP_OVERRIDE",
            "data": {
                "directive_type": "DM_RELATIONSHIP_OVERRIDE",
                "changes": [
                    {"npc": npc_id, "delta": 5, "reason": "quest_reward"},
                    {"faction": data.get("faction", ""), "delta": 5, "reason": "guild_reputation"},
                ],
                "narrative_reason": f"Quest completed for {npc_id}",
            },
        }]

        for arc in self.state.active_arcs.values():
            if npc_id in arc.involved_npcs and arc.status == "active":
                arc.add_event(event.event_type.value, f"Quest completed: {data.get('quest_name', 'unknown')}")
                break

        return directives

    def _handle_quest_failed(self, event: StateEvent, data: Dict) -> Optional[List[Dict]]:
        npc_id = event.npc_id or data.get("npc_name", "")
        return [{
            "type": "DM_RELATIONSHIP_OVERRIDE",
            "data": {
                "directive_type": "DM_RELATIONSHIP_OVERRIDE",
                "changes": [
                    {"npc": npc_id, "delta": -10, "reason": "quest_failed"},
                ],
                "narrative_reason": f"Quest failed for {npc_id}",
            },
        }, {
            "type": "DM_NPC_DIRECTIVE",
            "data": {
                "directive_type": "DM_NPC_DIRECTIVE",
                "npc_name": npc_id,
                "directive": "express_disappointment",
                "prompt_modifier": f"You are deeply disappointed in the player. They failed a task you entrusted them with.",
                "duration": "until_proven_otherwise",
                "expires_after_events": 3,
                "narrative_reason": f"Quest failed for {npc_id}",
            },
        }]

    def _handle_faction_change(self, event: StateEvent, data: Dict) -> Optional[List[Dict]]:
        new_rep = data.get("new_reputation", 0)
        faction = data.get("faction", "")
        if new_rep < -50 and faction:
            return [{
                "type": "DM_WORLD_EVENT",
                "data": {
                    "directive_type": "DM_WORLD_EVENT",
                    "event_name": f"{faction} Crackdown",
                    "severity": "major",
                    "description": f"The {faction} has sent enforcers due to extremely low reputation. Merchants refuse trade.",
                    "affected_zones": data.get("affected_zones", []),
                    "affected_factions": {faction: -10},
                    "duration_hours": 48,
                    "narrative_reason": f"Faction reputation dropped below -50",
                },
            }]
        return None

    def _handle_world_event(self, event: StateEvent, data: Dict) -> Optional[List[Dict]]:
        if data.get("severity") == "major":
            directives = []
            zone = event.zone_id or data.get("location", "")
            if zone:
                directives.append({
                    "type": "DM_NPC_DIRECTIVE",
                    "data": {
                        "directive_type": "DM_NPC_DIRECTIVE",
                        "npc_name": "all_in_zone",
                        "directive": "react_to_event",
                        "prompt_modifier": f"A major event has occurred: {data.get('event_name', 'unknown')}. React naturally.",
                        "duration": "event_duration",
                        "expires_after_events": 10,
                        "narrative_reason": f"Major world event: {data.get('event_name', '')}",
                    },
                })
            return directives if directives else None
        return None

    # ============================================
    # LLM JUDGMENT
    # ============================================

    async def _llm_judge(self, event: StateEvent):
        if not self.llm_provider:
            return

        prompt = self._build_judgment_prompt(event)

        try:
            result = self.llm_provider.generate(
                messages=[{"role": "system", "content": prompt}],
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            content = result.get("content", "")
            directive = self._parse_llm_response(content)
        except Exception as e:
            print(f"DM LLM judgment failed: {e}")
            return

        if not directive or directive.get("directive") == "none":
            return

        directive_type = directive.get("directive", "")
        parameters = directive.get("parameters", {})
        reasoning = directive.get("narrative_reason", "")

        obs = self._log_observation(event, directive_type, parameters, reasoning)

        if obs:
            if self._check_for_pattern(obs):
                await self._compile_rule(obs)

        await self._emit_directive(directive_type, parameters, event, reasoning)

    def _build_judgment_prompt(self, event: StateEvent) -> str:
        arc_summaries = ""
        for arc in self.state.active_arcs.values():
            if arc.status == "active":
                arc_summaries += f"- {arc.title}: {arc.description} (tension: {arc.tension_level:.1f})\n"

        event_summaries = ""
        for es in self.state.event_summaries[-5:]:
            event_summaries += f"- {es.get('summary', '')}\n"

        return f"""You are the Dungeon Master for a fantasy RPG. You oversee the narrative and ensure the world feels alive and reactive.

## YOUR ROLE
You receive game events and decide if they should cause narrative consequences beyond what the game systems already handle. You do NOT write NPC dialogue. You emit DIRECTIVES that other systems act on.

## CURRENT WORLD STATE
{arc_summaries or "No active story arcs."}

## RECENT EVENTS
{event_summaries or "No recent events."}

## CURRENT EVENT
Type: {event.event_type.value}
Player: {event.player_id or 'unknown'}
NPC: {event.npc_id or 'unknown'}
Zone: {event.zone_id or 'unknown'}
Data: {json.dumps(event.data)}

## AVAILABLE DIRECTIVES
1. quest_suggestion — Suggest a narratively motivated quest
2. npc_directive — Give an NPC a behavioral instruction
3. world_event — Spawn a world event
4. conversation_trigger — Start an NPC-to-NPC conversation
5. lore_update — Record new lore
6. relationship_override — Cascade relationship changes
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
{{"directive": "directive_type", "parameters": {{...}}, "narrative_reason": "..."}}"""

    def _parse_llm_response(self, content: str) -> Optional[Dict]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines).strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(content[start:end + 1])
                except json.JSONDecodeError:
                    pass
        return None

    # ============================================
    # OBSERVATIONS & PATTERN DETECTION
    # ============================================

    def _log_observation(
        self,
        event: StateEvent,
        directive_type: str,
        parameters: Dict,
        reasoning: str,
    ) -> Optional[Observation]:
        self._obs_seq += 1
        obs = Observation(
            observation_id=f"obs_{self._obs_seq:03d}",
            event_type=event.event_type.value,
            event_hash=self._compute_event_hash(event),
            event_summary=f"{event.event_type.value}: {event.npc_id or ''} {event.zone_id or ''}",
            context_snapshot={
                "arcs": len(self.state.active_arcs),
                "tension": dict(self.state.tension_map),
            },
            llm_directive_type=directive_type,
            llm_parameters=parameters,
            llm_reasoning=reasoning,
            confidence=0.8,
        )

        self.state.recent_observations.append(obs)
        if len(self.state.recent_observations) > self.config.max_observations:
            self.state.recent_observations = self.state.recent_observations[-self.config.max_observations:]

        return obs

    def _compute_event_hash(self, event: StateEvent) -> str:
        key = f"{event.event_type.value}:{event.npc_id}:{event.zone_id}:{json.dumps(event.data, sort_keys=True, default=str)}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def _compute_similarity_key(self, event: StateEvent, directive_type: str) -> str:
        return "|".join([
            event.event_type.value,
            directive_type,
            str(event.npc_id or ""),
            str(event.zone_id or ""),
        ])

    def _check_for_pattern(self, new_obs: Observation) -> bool:
        similar = [
            o for o in self.state.recent_observations
            if o.similarity_key() == new_obs.similarity_key()
            and o.confidence >= 0.7
        ]
        return len(similar) >= self.config.min_observations

    # ============================================
    # RULE COMPILATION
    # ============================================

    async def _compile_rule(self, trigger_obs: Observation):
        if self._rules_compiled_this_session >= self.config.max_new_rules_per_session:
            return

        if not self.llm_provider:
            return

        similar_obs = [
            o for o in self.state.recent_observations
            if o.similarity_key() == trigger_obs.similarity_key()
        ]

        obs_data = []
        for o in similar_obs[:10]:
            obs_data.append({
                "event_type": o.event_type,
                "directive_type": o.llm_directive_type,
                "parameters": o.llm_parameters,
                "reasoning": o.llm_reasoning,
            })

        prompt = f"""You are analyzing repeated patterns in a fantasy RPG's Dungeon Master decisions.

## PATTERN OBSERVATIONS
{json.dumps(obs_data, indent=2)}

## TASK
These observations show the DM consistently making the same judgment for similar events. Create a GENERAL RULE that captures this pattern so the DM can skip the LLM call in the future.

## RULE FORMAT
Respond with ONLY a JSON object:
{{
    "rule_name": "short descriptive name",
    "description": "what this rule does and why",
    "trigger": {{
        "event_type": "event_type_value",
        "conditions": [
            {{"field": "event.data.field_name", "operator": "eq|gt|lt|in|contains", "value": "..."}}
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
- Generalize from the observations, don't overfit to specific NPC names (use {{event.npc_id}} placeholders)
- Use the narrowest conditions that cover all observations
- Use the minimum actions needed
- Set confidence based on how consistent the observations are
- Priority should reflect narrative impact (higher = more important)"""

        try:
            result = self.llm_provider.generate(
                messages=[{"role": "system", "content": prompt}],
                model=self.config.model,
                temperature=0.3,
                max_tokens=400,
            )
            content = result.get("content", "")
            rule_json = self._parse_llm_response(content)
        except Exception as e:
            print(f"DM rule compilation failed: {e}")
            return

        if not rule_json:
            return

        rule_id = self.rule_engine.next_rule_id()
        rule = {
            "rule_id": rule_id,
            "rule_name": rule_json.get("rule_name", "Auto-compiled rule"),
            "description": rule_json.get("description", ""),
            "trigger": rule_json.get("trigger", {}),
            "actions": rule_json.get("actions", []),
            "priority": rule_json.get("priority", 5),
            "confidence": rule_json.get("confidence", 0.8),
            "times_observed": len(similar_obs),
            "source_observations": [o.observation_id for o in similar_obs],
            "active": False,
        }

        ok, status = self.rule_engine.add_rule(rule, auto_activate=True)
        if ok:
            self._rules_compiled_this_session += 1
            self.state.total_rules_compiled += 1
            print(f"DM: Rule '{rule['rule_name']}' compiled ({status})")

            await self._emit_raw_directive(EventType.DM_RULE_COMPILED, {
                "directive_type": "DM_RULE_COMPILED",
                "rule_id": rule_id,
                "rule_name": rule["rule_name"],
                "status": status,
                "confidence": rule["confidence"],
                "observations_used": len(similar_obs),
                "auto_activated": status == "active",
                "narrative_reason": f"Pattern detected from {len(similar_obs)} similar observations",
            })
        else:
            print(f"DM: Rule compilation rejected: {status}")

    # ============================================
    # DIRECTIVE EMISSION
    # ============================================

    async def _emit_directive(
        self,
        directive_type: str,
        parameters: Dict,
        event: StateEvent,
        reasoning: str,
    ):
        event_type_map = {
            "quest_suggestion": EventType.DM_QUEST_SUGGESTION,
            "npc_directive": EventType.DM_NPC_DIRECTIVE,
            "world_event": EventType.DM_WORLD_EVENT,
            "conversation_trigger": EventType.DM_CONVERSATION_TRIGGER,
            "lore_update": EventType.DM_LORE_UPDATE,
            "relationship_override": EventType.DM_RELATIONSHIP_OVERRIDE,
        }
        et = event_type_map.get(directive_type)
        if not et:
            return

        data = dict(parameters)
        data["source"] = "dungeon_master"
        data["narrative_reason"] = reasoning

        await self._emit_raw_directive(et, data)

    async def _emit_directive_from_actions(
        self,
        actions: List[Dict],
        event: StateEvent,
        rule_matched: bool = False,
    ):
        for action in actions:
            atype = action.get("type", "")
            params = action.get("parameters", {})
            await self._emit_directive(atype, params, event, f"Compiled rule match")

    async def _emit_raw_directive(self, event_type: EventType, data: Dict):
        directive_event = StateEvent(
            event_type=event_type,
            timestamp=time.time(),
            data=data,
            player_id=data.get("player_id"),
            npc_id=data.get("npc") or data.get("npc_name"),
            zone_id=data.get("zone_id") or data.get("affected_zones", [None])[0] if isinstance(data.get("affected_zones"), list) else None,
        )
        if self.event_callback:
            await self.event_callback.emit(directive_event)

    # ============================================
    # TENSION
    # ============================================

    def _update_tension(self, event: StateEvent):
        now = time.time()

        for key in list(self.state.tension_map.keys()):
            last_update = self.state.last_updated
            hours_elapsed = (now - last_update) / 3600
            if hours_elapsed > 0:
                decay = self.config.tension_decay_rate * hours_elapsed
                self.state.tension_map[key] = max(
                    0.0, self.state.tension_map[key] * (1.0 - decay)
                )

        et = event.event_type.value
        delta = 0.0
        if et in NEGATIVE_EVENTS:
            data = event.data
            if et == "relationship_change":
                delta = self.config.tension_increase_default
            elif et == "quest_failed":
                delta = self.config.tension_increase_default * 1.5
            else:
                delta = self.config.tension_increase_default
        elif et in POSITIVE_EVENTS:
            delta = -self.config.tension_increase_default

        if delta != 0.0 and event.npc_id:
            npc_key = f"npc:{event.npc_id}"
            self.state.tension_map[npc_key] = max(
                0.0, min(1.0, self.state.tension_map.get(npc_key, 0.0) + delta)
            )

        overall = 0.0
        if self.state.tension_map:
            overall = sum(self.state.tension_map.values()) / len(self.state.tension_map)
        self.state.tension_map["world:overall"] = max(0.0, min(1.0, overall))

    def _check_tension_threshold(self):
        for key, value in self.state.tension_map.items():
            if value >= self.config.tension_threshold and key != "world:overall":
                print(f"DM: Tension threshold exceeded for {key}: {value:.2f}")

    # ============================================
    # NARRATIVE COMPRESSION
    # ============================================

    def _compress_narrative_sync(self):
        if len(self.raw_events) > self.config.compression_interval:
            batch = self.raw_events[-self.config.compression_interval:]
            summary_parts = []
            for e in batch:
                et = e.get("event_type", "unknown")
                npc = e.get("npc_id", "")
                summary_parts.append(f"{et}" + (f" ({npc})" if npc else ""))
            summary = f"Batch of {len(batch)} events: {', '.join(summary_parts[:5])}"
            self.state.event_summaries.append({"summary": summary, "timestamp": time.time()})
            self.raw_events = self.raw_events[-5:]

        if len(self.state.event_summaries) > self.config.max_event_summaries:
            self.state.event_summaries = self.state.event_summaries[-self.config.max_event_summaries:]

        for arc_id, arc in list(self.state.active_arcs.items()):
            if arc.status == "active" and arc.is_expired():
                arc.status = "dormant"

        if len(self.state.active_arcs) > self.config.max_active_arcs:
            active = {k: v for k, v in self.state.active_arcs.items() if v.status == "active"}
            dormant = {k: v for k, v in self.state.active_arcs.items() if v.status == "dormant"}
            resolved = {k: v for k, v in self.state.active_arcs.items() if v.status == "resolved"}

            sorted_active = dict(sorted(active.items(), key=lambda x: x[1].last_event_at, reverse=True))
            keep = dict(list(sorted_active.items())[:self.config.max_active_arcs])
            keep.update(dormant)
            keep.update(resolved)
            self.state.active_arcs = keep

    # ============================================
    # ARC MANAGEMENT
    # ============================================

    def create_arc(
        self,
        title: str,
        description: str,
        involved_npcs: List[str] = None,
        involved_players: List[str] = None,
        resolution_conditions: List[str] = None,
    ) -> StoryArc:
        self._arc_seq += 1
        arc = StoryArc(
            arc_id=f"arc_{self._arc_seq:03d}",
            title=title,
            description=description,
            involved_npcs=involved_npcs or [],
            involved_players=involved_players or [],
            resolution_conditions=resolution_conditions or [],
        )
        self.state.active_arcs[arc.arc_id] = arc
        return arc

    def advance_arc(self, arc_id: str, event_summary: str, tension_delta: float = 0.0) -> bool:
        arc = self.state.active_arcs.get(arc_id)
        if not arc:
            return False
        arc.add_event("arc_advance", event_summary)
        arc.tension_level = max(0.0, min(1.0, arc.tension_level + tension_delta))
        return True

    def resolve_arc(self, arc_id: str) -> bool:
        arc = self.state.active_arcs.get(arc_id)
        if not arc:
            return False
        arc.status = "resolved"
        arc.add_event("arc_resolved", f"Arc '{arc.title}' resolved")
        return True

    # ============================================
    # PERSISTENCE
    # ============================================

    def save_state(self):
        state_dir = Path(self.config.state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)

        with open(state_dir / "narrative_state.json", "w") as f:
            json.dump(self.state.to_dict(), f, indent=2, default=str)

        with open(state_dir / "raw_events.json", "w") as f:
            json.dump(self.raw_events[-self.config.max_raw_events:], f, indent=2, default=str)

    def load_state(self):
        state_dir = Path(self.config.state_dir)

        state_file = state_dir / "narrative_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                self.state = NarrativeState.from_dict(data)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Warning: Failed to load DM state: {e}")
                self.state = NarrativeState()

        events_file = state_dir / "raw_events.json"
        if events_file.exists():
            try:
                with open(events_file) as f:
                    self.raw_events = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Warning: Failed to load raw events: {e}")
                self.raw_events = []

        for arc in self.state.active_arcs.values():
            match_str = arc.arc_id.replace("arc_", "")
            try:
                seq = int(match_str)
                if seq > self._arc_seq:
                    self._arc_seq = seq
            except ValueError:
                pass

        for obs in self.state.recent_observations:
            match_str = obs.observation_id.replace("obs_", "")
            try:
                seq = int(match_str)
                if seq > self._obs_seq:
                    self._obs_seq = seq
            except ValueError:
                pass

    async def _auto_save_loop(self):
        while self._running:
            try:
                await asyncio.sleep(self.config.auto_save_interval)
                self.save_state()
                self.rule_engine.save_rules()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"DM auto-save error: {e}")

    # ============================================
    # STATUS
    # ============================================

    def get_status(self) -> Dict:
        high_tensions = {
            k: v for k, v in self.state.tension_map.items()
            if v >= 0.5 and k != "world:overall"
        }
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "model": self.config.model,
            "active_arcs": len([a for a in self.state.active_arcs.values() if a.status == "active"]),
            "dormant_arcs": len([a for a in self.state.active_arcs.values() if a.status == "dormant"]),
            "resolved_arcs": len([a for a in self.state.active_arcs.values() if a.status == "resolved"]),
            "active_rules": len(self.rule_engine.active_rules),
            "pending_rules": len(self.rule_engine.pending_rules),
            "total_observations": len(self.state.recent_observations),
            "total_events_processed": self.state.total_events_processed,
            "total_rules_compiled": self.state.total_rules_compiled,
            "story_summary": self.state.story_summary,
            "world_conditions": list(self.state.world_conditions),
            "tension_highlights": high_tensions,
            "session_count": self.state.session_count,
        }
