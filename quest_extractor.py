"""
Quest Extraction Layer

Detects quest offers in NPC dialogue and player acceptance/rejection
using lightweight LLM calls. Quests emerge naturally from conversation
rather than from templates.
"""

import json
import re
import time
import uuid
import logging
from typing import Optional, Dict, List, Any

from quest_generator import (
    Quest, QuestType, QuestStatus, QuestReward,
    Objective, ObjectiveType,
)
from llm_providers import create_provider, LLMProvider

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """Analyze this NPC dialogue. Determine if the NPC is offering the player a quest, task, job, or request.

NPC NAME: {npc_name}
NPC DIALOGUE: {npc_response}
{existing_quests_section}
Respond with ONLY a JSON object (no markdown, no code fences):
- If the NPC is offering a NEW quest/task/request (not already listed above):
{{"has_quest": true, "name": "short quest name", "type": "fetch|kill|explore|escort|collection|dialogue", "description": "what the NPC wants done in one sentence", "objectives": [{{"action": "collect_item|kill_target|reach_location|talk_to_npc|deliver_item|escort_npc|defeat_boss", "target": "what to interact with", "count": 1}}], "rewards": {{"gold": 0, "items": []}}, "location": "where it happens or null"}}

- If the NPC is NOT offering a quest, or is just continuing discussion of an existing quest:
{{"has_quest": false}}

Guidelines:
- A quest is a clear NEW request for the player to DO something specific (fetch, kill, explore, deliver, escort, collect, talk to someone)
- General shop talk, gossip, or vague suggestions are NOT quests
- Continuing to discuss, confirm details, or give instructions for an already-known quest is NOT a new quest
- The quest must have a concrete, actionable objective
- Use the NPC's own words to inform the quest name and description
- Infer the quest type from what the NPC is asking
- Do NOT extract a quest if the NPC is referencing or elaborating on an existing quest listed above"""

ACCEPTANCE_PROMPT = """The NPC "{npc_name}" just offered this quest to the player:
  Quest: {quest_name}
  Description: {quest_description}

The player responded with: "{player_input}"

Did the player accept, reject, or ignore the quest offer?
Respond with ONLY a JSON object (no markdown, no code fences):
{{"action": "accept"}} or {{"action": "reject"}} or {{"action": "ignore"}}

Guidelines:
- "accept" = player clearly agrees to do the quest (e.g., "sure", "I'll do it", "consider it done", "yes", "okay")
- "reject" = player clearly refuses (e.g., "no", "not interested", "too busy", "maybe later" with negative tone)
- "ignore" = player changes the subject or doesn't directly address the quest offer"""


class QuestExtractor:
    """
    Extracts quest offers from NPC dialogue and detects player acceptance.
    
    Uses lightweight LLM calls to parse natural dialogue into structured Quest objects.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        backend: Optional[str] = None,
        api_key: Optional[str] = None,
        enabled: bool = True,
    ):
        self.provider = provider or create_provider(
            backend=backend, api_key=api_key
        )
        self.model = model
        self.enabled = enabled
        self._pending_quests: Dict[str, Quest] = {}

    def _get_model(self) -> str:
        if self.model:
            return self.model
        import os
        backend = os.getenv("LLM_BACKEND", "ollama")
        if backend == "groq":
            return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return os.getenv("OLLAMA_MODEL", "llama3.2:1b")

    def _call_llm(self, prompt: str) -> Optional[str]:
        try:
            result = self.provider.generate(
                messages=[{"role": "user", "content": prompt}],
                model=self._get_model(),
                temperature=0.1,
                max_tokens=300,
            )
            return result.get("content", "").strip()
        except Exception as e:
            logger.warning(f"Quest extraction LLM call failed: {e}")
            return None

    def _parse_json(self, text: str) -> Optional[Dict]:
        if not text:
            return None

        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```\w*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```$', '', cleaned)
            cleaned = cleaned.strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        return None

    def _map_quest_type(self, type_str: str) -> QuestType:
        type_map = {
            "fetch": QuestType.FETCH,
            "kill": QuestType.KILL,
            "explore": QuestType.EXPLORE,
            "escort": QuestType.ESCORT,
            "collection": QuestType.COLLECTION,
            "collect": QuestType.COLLECTION,
            "dialogue": QuestType.DIALOGUE,
            "talk": QuestType.DIALOGUE,
        }
        return type_map.get(type_str.lower().strip(), QuestType.FETCH)

    def _map_objective_type(self, action_str: str) -> ObjectiveType:
        action_map = {
            "collect_item": ObjectiveType.COLLECT_ITEM,
            "collect": ObjectiveType.COLLECT_ITEM,
            "gather": ObjectiveType.COLLECT_ITEM,
            "pickup": ObjectiveType.COLLECT_ITEM,
            "kill_target": ObjectiveType.KILL_TARGET,
            "kill": ObjectiveType.KILL_TARGET,
            "defeat": ObjectiveType.KILL_TARGET,
            "reach_location": ObjectiveType.REACH_LOCATION,
            "reach": ObjectiveType.REACH_LOCATION,
            "travel": ObjectiveType.REACH_LOCATION,
            "go_to": ObjectiveType.REACH_LOCATION,
            "talk_to_npc": ObjectiveType.TALK_TO_NPC,
            "talk": ObjectiveType.TALK_TO_NPC,
            "speak": ObjectiveType.TALK_TO_NPC,
            "deliver_item": ObjectiveType.DELIVER_ITEM,
            "deliver": ObjectiveType.DELIVER_ITEM,
            "escort_npc": ObjectiveType.ESCORT_NPC,
            "escort": ObjectiveType.ESCORT_NPC,
            "defeat_boss": ObjectiveType.DEFEAT_BOSS,
        }
        return action_map.get(action_str.lower().strip(), ObjectiveType.COLLECT_ITEM)

    _STOP_WORDS = frozenset({
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need", "dare",
        "it", "its", "he", "she", "they", "them", "his", "her", "their",
        "this", "that", "these", "those", "i", "you", "we", "me", "my",
        "your", "our", "who", "what", "which", "where", "when", "how",
        "not", "no", "nor", "if", "then", "than", "too", "very", "just",
        "get", "got", "go", "goes", "going", "gone", "do", "did", "done",
    })

    @staticmethod
    def _is_duplicate_quest(new_quest: Quest, existing: Quest) -> bool:
        """Check if a newly extracted quest duplicates an existing one."""
        if existing.quest_giver != new_quest.quest_giver:
            return False
        if existing.quest_type != new_quest.quest_type:
            return False
        new_target_words = set()
        existing_target_words = set()
        for o in new_quest.objectives:
            new_target_words.update(o.target.lower().split())
        for o in existing.objectives:
            existing_target_words.update(o.target.lower().split())
        if new_target_words & existing_target_words:
            return True
        stop = QuestExtractor._STOP_WORDS
        new_content = {w for w in new_quest.description.lower().split() if w not in stop}
        existing_content = {w for w in existing.description.lower().split() if w not in stop}
        if len(new_content) >= 2 and len(existing_content) >= 2:
            overlap = len(new_content & existing_content) / min(len(new_content), len(existing_content))
            if overlap > 0.65:
                return True
        return False

    def _format_existing_quests_section(
        self, npc_name: str, active_quests: Optional[List[Quest]] = None
    ) -> str:
        """Build a section for the prompt listing existing quests from this NPC."""
        if not active_quests:
            return ""
        npc_quests = [
            q for q in active_quests
            if q.quest_giver == npc_name and q.status in (QuestStatus.ACTIVE, QuestStatus.AVAILABLE)
        ]
        if not npc_quests:
            return ""
        lines = ["EXISTING QUESTS from this NPC (do NOT re-extract these):"]
        for q in npc_quests:
            targets = ", ".join(o.target for o in q.objectives)
            lines.append(
                f'- "{q.name}" ({q.quest_type.value}, {q.status.value}): {q.description} [target: {targets}]'
            )
        return "\n" + "\n".join(lines) + "\n"

    def extract_quest(
        self,
        npc_name: str,
        npc_response: str,
        active_quests: Optional[List[Quest]] = None,
    ) -> Optional[Quest]:
        """
        Analyze an NPC response and extract a quest if one was offered.
        
        Skips extraction if the NPC already has a pending quest, and
        deduplicates against active/available quests from this NPC.
        
        Returns a Quest object if detected, or None.
        """
        if not self.enabled:
            return None

        if npc_name in self._pending_quests:
            logger.debug(f"Skipping extraction for {npc_name}: pending quest already exists")
            return None

        existing_section = self._format_existing_quests_section(npc_name, active_quests)

        prompt = EXTRACTION_PROMPT.format(
            npc_name=npc_name,
            npc_response=npc_response,
            existing_quests_section=existing_section,
        )

        raw = self._call_llm(prompt)
        if not raw:
            return None

        data = self._parse_json(raw)
        if not data or not data.get("has_quest"):
            if not data:
                logger.warning("Quest extraction: JSON parse failed for raw LLM response: %s", raw[:500])
            return None

        try:
            quest_type = self._map_quest_type(data.get("type", "fetch"))
            objectives = []
            for i, obj_data in enumerate(data.get("objectives", [])):
                obj_type = self._map_objective_type(
                    obj_data.get("action", "collect_item")
                )
                objectives.append(Objective(
                    id=f"obj_{i}",
                    type=obj_type,
                    description=f"{obj_type.value.replace('_', ' ').title()}: {obj_data.get('target', 'unknown')}",
                    target=obj_data.get("target", "unknown"),
                    required=obj_data.get("count", 1),
                    current=0,
                ))

            if not objectives:
                objectives.append(Objective(
                    id="obj_0",
                    type=ObjectiveType.COLLECT_ITEM,
                    description="Complete the task",
                    target="task",
                    required=1,
                    current=0,
                ))

            rewards_data = data.get("rewards", {})
            rewards = QuestReward(
                gold=rewards_data.get("gold", 0) if isinstance(rewards_data, dict) else 0,
                xp=50,
                items=rewards_data.get("items", []) if isinstance(rewards_data, dict) else [],
                relationship_bonus={npc_name: 10},
            )

            quest = Quest(
                id=f"quest_{uuid.uuid4().hex[:8]}",
                name=data.get("name", "Unknown Task"),
                description=data.get("description", ""),
                quest_giver=npc_name,
                quest_type=quest_type,
                objectives=objectives,
                rewards=rewards,
                difficulty=2,
                location=data.get("location"),
                narrative_context=npc_response[:200],
                status=QuestStatus.AVAILABLE,
            )

            if active_quests:
                for existing in active_quests:
                    if self._is_duplicate_quest(quest, existing):
                        logger.info(
                            f"Skipping duplicate quest '{quest.name}' (matches existing '{existing.name}')"
                        )
                        return None

            self._pending_quests[npc_name] = quest
            logger.info(f"Quest extracted: {quest.name} from {npc_name}")
            return quest

        except Exception as e:
            logger.warning("Failed to parse extracted quest data: %s | Raw response: %s", e, raw[:500])
            return None

    def detect_acceptance(
        self, player_input: str, npc_name: str, quest: Quest
    ) -> str:
        """
        Detect if the player accepted, rejected, or ignored a quest offer.
        
        Returns: "accept", "reject", or "ignore"
        """
        if not self.enabled:
            return "ignore"

        prompt = ACCEPTANCE_PROMPT.format(
            npc_name=npc_name,
            quest_name=quest.name,
            quest_description=quest.description,
            player_input=player_input,
        )

        raw = self._call_llm(prompt)
        if not raw:
            return "ignore"

        data = self._parse_json(raw)
        if not data:
            logger.warning("Quest acceptance: JSON parse failed for raw LLM response: %s", raw[:500])
            return "ignore"

        action = data.get("action", "ignore").lower()
        if action not in ("accept", "reject", "ignore"):
            return "ignore"

        if action in ("accept", "reject"):
            self._pending_quests.pop(npc_name, None)

        return action

    def get_pending_quest(self, npc_name: str) -> Optional[Quest]:
        """Get the pending (offered but not yet accepted/rejected) quest for an NPC."""
        return self._pending_quests.get(npc_name)

    def clear_pending(self, npc_name: str):
        """Clear the pending quest for an NPC."""
        self._pending_quests.pop(npc_name, None)


def extract_quest_sync(
    npc_name: str,
    npc_response: str,
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    active_quests: Optional[List[Quest]] = None,
) -> Optional[Quest]:
    """Convenience function for one-off quest extraction."""
    extractor = QuestExtractor(provider=provider, model=model)
    return extractor.extract_quest(npc_name, npc_response, active_quests=active_quests)
