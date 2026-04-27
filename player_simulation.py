"""
Player Character Simulation Engine
Runs an automated playthrough of the NPC Dialogue System world,
generating a live chronicle narrated as a fantasy novel.

Usage:
    Via API:  POST /api/simulation/start
    Via CLI:  python player_simulation.py
"""

import os
import json
import time
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

from llm_providers import create_provider, LLMProvider


class SimulationState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ChronicleTurn:
    turn_id: str
    session: int
    turn_number: int
    action: Dict[str, Any]
    prose: str
    npc_dialogue: Optional[Dict[str, Any]] = None
    dm_events: List[Dict[str, Any]] = field(default_factory=list)
    relationship_changes: List[Dict[str, Any]] = field(default_factory=list)
    quest_updates: List[Dict[str, Any]] = field(default_factory=list)
    lore_revealed: List[Dict[str, Any]] = field(default_factory=list)
    location: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ChronicleTurn':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SessionPlan:
    session_number: int
    title: str
    chapter_title: str
    opening: str
    max_turns: int = 14
    turns: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PlayerContext:
    location: str = "the_village"
    nearby_npcs: List[str] = field(default_factory=lambda: ["Thorne", "Elara", "Zephyr"])
    active_quests: List[Dict] = field(default_factory=list)
    inventory: Dict[str, int] = field(default_factory=lambda: {
        "Worn longsword": 1,
        "Leather armour": 1,
        "Gold coins": 50,
        "Travel pack": 1,
        "Waterskin": 1,
        "Flint and steel": 1,
    })
    gold: int = 50
    relationships: Dict[str, Dict] = field(default_factory=dict)
    recent_events: List[str] = field(default_factory=list)

    def update_relationship(self, npc: str, score: float, level: str):
        self.relationships[npc] = {"score": round(score, 1), "level": level}

    def to_prompt_text(self) -> str:
        lines = []
        lines.append(f"Location: {self.location}")
        lines.append(f"Nearby NPCs: {', '.join(self.nearby_npcs) if self.nearby_npcs else 'None'}")
        if self.active_quests:
            quest_strs = [f"- {q.get('name', q.get('title', 'Unknown'))}" for q in self.active_quests]
            lines.append("Active Quests:\n" + "\n".join(quest_strs))
        else:
            lines.append("Active Quests: None")
        inv_items = [f"{k} x{v}" for k, v in self.inventory.items() if v > 0]
        lines.append(f"Inventory: {', '.join(inv_items) if inv_items else 'Empty'}")
        lines.append(f"Gold: {self.gold}")
        if self.relationships:
            rel_strs = [f"  {npc}: {data['level']} (score: {data['score']})" for npc, data in self.relationships.items()]
            lines.append("Relationships:\n" + "\n".join(rel_strs))
        return "\n".join(lines)


class ChronicleStore:
    def __init__(self, data_dir: str = "chronicle_data"):
        self.data_dir = data_dir
        self.turns: List[ChronicleTurn] = []
        self.metadata: Dict[str, Any] = {
            "title": "The Chronicle of Kael Ashwood",
            "started_at": None,
            "completed_at": None,
            "sessions_completed": 0,
            "total_turns": 0,
        }
        Path(data_dir).mkdir(parents=True, exist_ok=True)

    def add_turn(self, turn: ChronicleTurn):
        self.turns.append(turn)
        self.metadata["total_turns"] = len(self.turns)

    def get_turn(self, turn_id: str) -> Optional[ChronicleTurn]:
        for t in self.turns:
            if t.turn_id == turn_id:
                return t
        return None

    def get_session_turns(self, session: int) -> List[ChronicleTurn]:
        return [t for t in self.turns if t.session == session]

    def get_full_state(self) -> Dict:
        return {
            "metadata": self.metadata,
            "turns": [t.to_dict() for t in self.turns],
        }

    def get_turn_summaries(self) -> List[Dict]:
        return [
            {
                "turn_id": t.turn_id,
                "session": t.session,
                "turn_number": t.turn_number,
                "action_type": t.action.get("type", "unknown"),
                "target": t.action.get("target", ""),
                "location": t.location,
                "timestamp": t.timestamp,
            }
            for t in self.turns
        ]

    def save(self):
        self.metadata["completed_at"] = time.time()
        path = os.path.join(self.data_dir, "chronicle_state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.get_full_state(), f, indent=2, ensure_ascii=False)
        for session_num in sorted(set(t.session for t in self.turns)):
            session_turns = self.get_session_turns(session_num)
            path = os.path.join(self.data_dir, f"session_{session_num}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in session_turns], f, indent=2, ensure_ascii=False)

    def load(self) -> bool:
        path = os.path.join(self.data_dir, "chronicle_state.json")
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.metadata = data.get("metadata", self.metadata)
        self.turns = [ChronicleTurn.from_dict(t) for t in data.get("turns", [])]
        return True


class PlayerLLM:
    def __init__(self, model: str = None, backend: str = None, api_key: str = None):
        self.backend = backend or os.getenv("LLM_BACKEND", "ollama")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") if self.backend == "groq" else os.getenv("OLLAMA_MODEL", "llama3.2:1b")
        self.provider: LLMProvider = create_provider(backend=self.backend, api_key=api_key)
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return """You are Kael Ashwood, a 28-year-old human sellsword wandering the realm. You deserted during the Great War and have been travelling ever since, hiring out your sword to whoever pays. You carry guilt about your desertion and a deep-seated need to prove you are more than a mercenary.

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

## RULES
- Stay in character at all times. You are Kael, not an AI assistant.
- Respond with ONLY a JSON object. No other text.
- Choose from the available actions listed below.
- Your dialogue should be 1-3 sentences. Brief and in-character."""

    async def decide(self, context: PlayerContext, available_actions: List[Dict], turn_plan: Dict = None) -> Dict:
        user_parts = []
        user_parts.append("## YOUR CURRENT SITUATION")
        user_parts.append(context.to_prompt_text())
        if context.recent_events:
            user_parts.append("\n## RECENT EVENTS")
            for evt in context.recent_events[-10:]:
                user_parts.append(f"- {evt}")
        user_parts.append("\n## WHAT IS HAPPENING RIGHT NOW")
        if turn_plan and "scene" in turn_plan:
            user_parts.append(turn_plan["scene"])
        else:
            user_parts.append(f"You are at {context.location}. Choose your next action.")
        user_parts.append("\n## AVAILABLE ACTIONS")
        for i, action in enumerate(available_actions):
            desc = action.get("description", action.get("type", "unknown"))
            user_parts.append(f"{i+1}. {desc}")
        user_parts.append("\nRespond with a JSON object:")
        user_parts.append('{"action": "<action_type>", "target": "<target>", "dialogue": "what you say"}')
        user_parts.append("OR for travel: {\"action\": \"travel_to\", \"destination\": \"<location>\"}")
        user_parts.append("OR for quest: {\"action\": \"accept_quest\", \"quest_name\": \"<name>\"}")
        user_parts.append("OR for gift: {\"action\": \"give_gift\", \"target\": \"<npc>\", \"item\": \"<item>\"}")
        user_parts.append("OR for wait: {\"action\": \"wait\"}")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

        try:
            result = self.provider.generate(
                messages=messages,
                model=self.model,
                temperature=0.8,
                max_tokens=200,
            )
            text = result.get("content", "{}").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json.loads(text)
            if "action" not in parsed:
                parsed["action"] = available_actions[0]["type"] if available_actions else "wait"
            return parsed
        except (json.JSONDecodeError, Exception) as e:
            if turn_plan:
                return {
                    "action": turn_plan.get("action", "wait"),
                    "target": turn_plan.get("target", ""),
                    "dialogue": turn_plan.get("dialogue", "I'll see what I can do."),
                }
            return {"action": "wait"}

    def generate_dialogue(self, context: PlayerContext, npc_name: str, topic: str = None) -> str:
        user_parts = []
        user_parts.append(f"You are talking to {npc_name}.")
        if topic:
            user_parts.append(f"Topic or situation: {topic}")
        user_parts.append(context.to_prompt_text())
        user_parts.append("\nSay something to them in character. 1-3 sentences. Respond with ONLY your words, no JSON, no quotes.")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

        try:
            result = self.provider.generate(
                messages=messages,
                model=self.model,
                temperature=0.85,
                max_tokens=150,
            )
            text = result.get("content", "Hey.").strip()
            text = text.strip('"').strip("'")
            return text
        except Exception:
            return "I'll keep my words short. What do you need?"


class NarratorLLM:
    def __init__(self, model: str = None, backend: str = None, api_key: str = None):
        self.backend = backend or os.getenv("LLM_BACKEND", "ollama")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") if self.backend == "groq" else os.getenv("OLLAMA_MODEL", "llama3.2:1b")
        self.provider: LLMProvider = create_provider(backend=self.backend, api_key=api_key)
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return """You are a fantasy author writing a novel called "The Chronicle of Kael Ashwood". You receive game events and must transform them into vivid, immersive narrative prose.

## STYLE
- Third person limited (Kael's perspective)
- Present tense for action, past tense for reflection
- Sensory details: sounds, smells, textures
- Dialogue in quotes with action beats
- Internal thoughts in italics
- No game terminology (no "quest", "NPC", "relationship score", "DM", "directive")
- Fantasy prose tone: grounded but evocative
- Keep it concise. 2-3 paragraphs maximum.

## RULES
- Never use game system terms in the prose
- Translate system events into story:
  - relationship gains become warmth and trust
  - relationship losses become coldness and distance
  - quest completion becomes returning triumphant or weary
  - world events become environmental description
  - NPC conversations become overheard whispers
- Show, don't tell. Don't say "Kael felt trusted." Show the NPC's behaviour changing.
- Write ONLY the narrative prose. No commentary, no explanations."""

    async def narrate(self, chapter: str, events: Dict, previous_prose: str = "") -> str:
        user_parts = []
        user_parts.append(f"## CURRENT CHAPTER\nChapter: {chapter}")
        if previous_prose:
            tail = previous_prose[-1500:] if len(previous_prose) > 1500 else previous_prose
            user_parts.append(f"\n## PREVIOUS PROSE (for continuity)\n{tail}")
        user_parts.append("\n## EVENTS TO NARRATE")
        if "action" in events:
            user_parts.append(f"Action: {events['action'].get('type', 'unknown')}")
            if events["action"].get("target"):
                user_parts.append(f"Target: {events['action']['target']}")
            if events["action"].get("dialogue"):
                user_parts.append(f"Kael says: \"{events['action']['dialogue']}\"")
        if events.get("npc_response"):
            npc_name = events.get("npc_name", "the NPC")
            user_parts.append(f"{npc_name} responds: \"{events['npc_response']}\"")
        if events.get("relationship_changes"):
            for rc in events["relationship_changes"]:
                direction = "warms to" if rc.get("delta", 0) > 0 else "grows cold toward"
                user_parts.append(f"Kael's bond with {rc.get('npc', 'someone')} {direction} him ({rc.get('new_level', '')})")
        if events.get("quest_updates"):
            for qu in events["quest_updates"]:
                status = qu.get("status", "updated")
                name = qu.get("name", "the task")
                if status == "completed":
                    user_parts.append(f"Task completed: {name}")
                elif status == "accepted":
                    user_parts.append(f"New task undertaken: {name}")
                elif status == "failed":
                    user_parts.append(f"Task failed: {name}")
        if events.get("dm_events"):
            for dm in events["dm_events"]:
                dtype = dm.get("directive_type", dm.get("directive", ""))
                if dtype and dtype != "none":
                    user_parts.append(f"World event: {dm.get('reasoning', dm.get('description', 'something shifts in the world'))}")
        if events.get("lore_revealed"):
            for lore in events["lore_revealed"]:
                user_parts.append(f"Knowledge gained: {lore.get('title', 'something learned')}")
        if events.get("location"):
            user_parts.append(f"Location: {events['location']}")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

        try:
            result = self.provider.generate(
                messages=messages,
                model=self.model,
                temperature=0.7,
                max_tokens=500,
            )
            return result.get("content", "Time passed. The world turned.").strip()
        except Exception:
            return "The moment stretched, filled with unspoken weight."


SESSION_PLANS = [
    SessionPlan(
        session_number=1,
        title="Stranger in the Village",
        chapter_title="The Weight of the Road",
        opening="Kael arrives at the village at dusk. Smoke rises from a forge at the edge of town. A merchant's colourful cart is parked in the square. A tower on the hill glows with strange light. His sword is chipped. His boots are worn through. He has 50 gold and nowhere to sleep.",
        max_turns=12,
        turns=[
            {
                "action": "talk_to", "target": "Thorne",
                "scene": "You approach the forge. Heat rolls off the coals. A stocky dwarf hammers a glowing blade. Your own sword needs rehandling badly.",
                "description": "Talk to Thorne the blacksmith",
                "dialogue": "Your forge still burns at this hour? I need a rehandle on this blade.",
                "expected": {"relationship": {"Thorne": 0}},
            },
            {
                "action": "ask_about", "target": "Thorne", "topic": "Ironhold and dwarven craftsmanship",
                "scene": "Thorne hasn't told you to leave yet. The forge is warm. You're curious about where he learned his craft.",
                "description": "Ask Thorne about Ironhold and his craft",
                "dialogue": "This is dwarven work, isn't it? Real Ironhold steel. You don't see that often.",
                "expected": {"relationship": {"Thorne": 2}},
            },
            {
                "action": "accept_quest", "target": "Thorne", "quest_type": "collection",
                "scene": "Thorne mentions he's running low on coal. He eyes your worn boots and sword. 'Show me you're worth the effort,' he grunts.",
                "description": "Accept a quest from Thorne (gathering task)",
                "dialogue": "Coal. I can do that. Where's the nearest supply?",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "complete_quest", "target": "Thorne",
                "scene": "You return with a sack of coal over your shoulder. It wasn't glamorous work, but it was honest. Thorne watches you set it down.",
                "description": "Complete the coal gathering quest for Thorne",
                "dialogue": "Coal's by the door. Better quality than what you had, I'd wager.",
                "expected": {"quest_completed": True, "relationship": {"Thorne": 15}},
            },
            {
                "action": "talk_to", "target": "Elara",
                "scene": "A merchant's cart sits in the village square, colourful silks draped over the sides. A woman with keen eyes is arranging bottles and trinkets. She spots you immediately.",
                "description": "Talk to Elara the merchant",
                "dialogue": "Nice spread. How much for a look at your exotic goods?",
                "expected": {"relationship": {"Elara": 0}},
            },
            {
                "action": "ask_about", "target": "Elara", "topic": "The Bandit King and recent caravan attacks",
                "scene": "Elara seems well-connected. You've heard rumours about bandits on the roads. Worth asking.",
                "description": "Ask Elara about the Bandit King",
                "dialogue": "Roads been dangerous lately. I've heard whispers about a Bandit King. You lose any shipments?",
                "expected": {"relationship": {"Elara": 2}},
            },
            {
                "action": "accept_quest", "target": "Elara", "quest_type": "fetch",
                "scene": "Elara mentions she needs a message delivered to Port Harbor. She studies you carefully. 'You look like you can handle yourself on the road.'",
                "description": "Accept a delivery quest from Elara",
                "dialogue": "Port Harbor. I know the way. What's the message worth?",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "talk_to", "target": "Zephyr",
                "scene": "A tower on the hill glows with strange light. An old wizard sits among floating tomes. He looks at you with eyes that see too much.",
                "description": "Talk to Zephyr the wizard",
                "dialogue": "I've seen a lot of strange things on the road. Floating books is a new one.",
                "expected": {"relationship": {"Zephyr": 0}},
            },
            {
                "action": "ask_about", "target": "Zephyr", "topic": "The Mage Purge",
                "scene": "Zephyr mentioned he left the Order of Arcane Studies. There's a weight behind those words. You push gently.",
                "description": "Ask Zephyr about the Mage Purge",
                "dialogue": "The Purge. I was a boy when that happened. They say mages were hunted. You... you were there?",
                "expected": {"relationship": {"Zephyr": 3}},
            },
            {
                "action": "wait",
                "scene": "Evening falls on the village. You find the tavern. The ale is weak but the fire is warm. You listen to the conversations around you.",
                "description": "Spend the evening at the village tavern",
                "dialogue": "",
                "expected": {},
            },
        ],
    ),
    SessionPlan(
        session_number=2,
        title="Fire and Steel",
        chapter_title="The Blacksmith's Trust",
        opening="A week has passed. Kael returns from Port Harbor, coin purse heavier and boots more worn. The village feels quiet by comparison. Almost peaceful. Thorne's forge still burns. The rhythmic clang of hammer on steel carries on the morning air.",
        max_turns=12,
        turns=[
            {
                "action": "complete_quest", "target": "Elara",
                "scene": "You find Elara at her cart. You have the response from Port Harbor. She's been waiting.",
                "description": "Complete the delivery quest for Elara",
                "dialogue": "Letter's delivered. Response is in my pack. Your contact sends his regards.",
                "expected": {"quest_completed": True, "relationship": {"Elara": 10}},
            },
            {
                "action": "talk_to", "target": "Thorne",
                "scene": "Thorne is shaping a blade. You mention your sword still needs work. He grunts. You offer to help around the forge instead of paying gold.",
                "description": "Talk to Thorne about working in the forge",
                "dialogue": "I can't pay in gold. But I can swing a hammer. Need help around the forge?",
                "expected": {"relationship": {"Thorne": 3}},
            },
            {
                "action": "accept_quest", "target": "Thorne", "quest_type": "fetch",
                "scene": "Thorne mentions star-iron ore in the foothills near Ironhold. Rare stuff. He'll fix your sword for free if you bring some back.",
                "description": "Accept the star-iron ore quest from Thorne",
                "dialogue": "Star-iron. Heard of it. Never seen it. Where exactly in the foothills?",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "travel_to", "destination": "ironhold_foothills",
                "scene": "You set out toward the Ironpeak Mountains. The foothills are rugged terrain — old mining trails, abandoned dig sites.",
                "description": "Travel to the Ironhold foothills",
                "dialogue": "",
                "expected": {"zone_change": True},
            },
            {
                "action": "complete_quest", "target": "Thorne",
                "scene": "You return to the forge with a bag of star-iron ore. It shimmers faintly in the light. Thorne's eyes widen.",
                "description": "Return with star-iron ore for Thorne",
                "dialogue": "Star-iron. Took some finding. There's more in the foothills if you ever need it.",
                "expected": {"quest_completed": True, "relationship": {"Thorne": 20}},
            },
            {
                "action": "give_gift", "target": "Thorne", "item": "Rare ore sample",
                "scene": "You kept a piece of the star-iron for yourself. But Thorne would value it more. You reach into your pack.",
                "description": "Give Thorne a rare ore sample as a gift",
                "dialogue": "Kept this back. Doesn't feel right keeping it from someone who'd know what to do with it.",
                "expected": {"relationship": {"Thorne": 15}},
            },
            {
                "action": "overhear", "target": "Thorne",
                "npcs": ["Thorne", "Elara"],
                "scene": "You hear voices from the market square. Thorne is talking to Elara. You slow your pace and listen from behind a cart.",
                "description": "Overhear Thorne and Elara talking about you",
                "dialogue": "",
                "expected": {"overhear": True},
            },
            {
                "action": "talk_to", "target": "Elara",
                "scene": "Elara approaches you after her conversation with Thorne. She seems warmer — Thorne's good word carries weight with her. She mentions a dangerous job.",
                "description": "Talk to Elara about the escort job",
                "dialogue": "Thorne put in a good word, did he? What's this job you mentioned?",
                "expected": {"relationship": {"Elara": 5}},
            },
            {
                "action": "accept_quest", "target": "Elara", "quest_type": "escort",
                "scene": "Elara needs someone to escort a silk caravan through Bandit's Pass. High risk, high reward. She looks at you steadily.",
                "description": "Accept the silk caravan escort quest from Elara",
                "dialogue": "Bandit's Pass. Dangerous territory. What's the caravan worth to you?",
                "expected": {"quest_accepted": True},
            },
        ],
    ),
    SessionPlan(
        session_number=3,
        title="Blood on the Pass",
        chapter_title="The Cost of Failure",
        opening="Dawn. The silk caravan waits at the village gate. Three wagons, six guards, and a driver who won't stop talking about his grandchildren. Elara has invested heavily in this shipment. 'If anything happens to these goods, I lose more than gold. Don't let me down.'",
        max_turns=12,
        turns=[
            {
                "action": "travel_to", "destination": "bandits_pass",
                "scene": "The caravan enters Bandit's Pass. Narrow road, high cliffs. The air smells of dust and old blood.",
                "description": "Travel through Bandit's Pass with the caravan",
                "dialogue": "",
                "expected": {"zone_change": True},
            },
            {
                "action": "fail_quest", "target": "Elara", "quest_name": "Escort the Silk Caravan",
                "scene": "Arrows strike the lead wagon. Bandits pour down the scree slopes — organised, military-precise. Not brigands. Soldiers. The caravan is overrun. Two wagons lost. The driver is screaming.",
                "description": "FAIL the escort quest — the caravan is ambushed",
                "dialogue": "Fall back! FALL BACK! There's too many — get the third wagon to cover!",
                "expected": {"quest_failed": True, "relationship": {"Elara": -25}},
            },
            {
                "action": "talk_to", "target": "Elara",
                "scene": "You return to the village alone. Two wagons gone. Elara is waiting at her cart. Her face is unreadable.",
                "description": "Face Elara after the failed caravan escort",
                "dialogue": "Elara. I'm sorry. They came from everywhere — organised, not bandits. I couldn't—",
                "expected": {"relationship": {"Elara": -5}},
            },
            {
                "action": "overhear", "target": "Elara",
                "npcs": ["Elara", "Thorne"],
                "scene": "You hear Elara and Thorne arguing near the forge. Their voices carry in the evening air.",
                "description": "Overhear Elara and Thorne arguing about you",
                "dialogue": "",
                "expected": {"overhear": True},
            },
            {
                "action": "travel_to", "destination": "port_harbor",
                "scene": "You need distance. And information. Who are these bandits? Port Harbor has contacts who know things.",
                "description": "Travel to Port Harbor to investigate the bandits",
                "dialogue": "",
                "expected": {"zone_change": True},
            },
            {
                "action": "ask_about", "target": "Elara", "topic": "The Bandit King's true identity",
                "scene": "At the harbor you find contacts who trade in information. You ask about the Bandit King. Who is he really?",
                "description": "Investigate the Bandit King's identity at Port Harbor",
                "dialogue": "I need to know who's behind these raids. The Bandit King — who is he? What does he want?",
                "expected": {"lore_discovered": True},
            },
            {
                "action": "accept_quest", "target": "Thorne", "quest_type": "kill",
                "scene": "Word arrives from Thorne — wolves are threatening the village. He needs someone who can fight. A chance to redeem yourself.",
                "description": "Accept the wolf den quest from Thorne",
                "dialogue": "Wolves. That I can handle. Tell Thorne I'm on my way.",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "complete_quest", "target": "Thorne",
                "scene": "You return with wolf pelts. The village is safer. Thorne takes the pelts silently. The door isn't closed.",
                "description": "Complete the wolf den quest for Thorne",
                "dialogue": "Wolves are dealt with. Den's cleared. Won't be a problem again this season.",
                "expected": {"quest_completed": True, "relationship": {"Thorne": 10}},
            },
        ],
    ),
    SessionPlan(
        session_number=4,
        title="The Wizard's Price",
        chapter_title="The Wizard's Price",
        opening="Two weeks since the pass. Kael has avoided Elara's cart. The village gossips. Thorne treats him normally — or close to it. The tower on the hill glows brighter than usual tonight. Zephyr's raven, Shadow, has been watching Kael for days.",
        max_turns=12,
        turns=[
            {
                "action": "talk_to", "target": "Zephyr",
                "scene": "You climb the hill to Zephyr's tower. The door is already open. Shadow the raven watches from a perch. You ask about the Bandit King.",
                "description": "Visit Zephyr and ask about the Bandit King",
                "dialogue": "I need to understand what we're dealing with. The Bandit King — you know something, don't you?",
                "expected": {"relationship": {"Zephyr": 2}},
            },
            {
                "action": "accept_quest", "target": "Zephyr", "quest_type": "explore",
                "scene": "Zephyr speaks of a tome hidden in the ruins beneath Shadowfen. It contains records from before the Great War. The Bandit King's true identity is within.",
                "description": "Accept the sealed tome quest from Zephyr",
                "dialogue": "Shadowfen. I've heard the stories. Will-o'-wisps and serpents. What's this tome worth to you?",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "travel_to", "destination": "shadowfen_swamp",
                "scene": "Shadowfen lives up to its name. Dark water, twisted trees, and a smell like rotting flowers. Strange lights flicker in the distance.",
                "description": "Travel to Shadowfen Swamp",
                "dialogue": "",
                "expected": {"zone_change": True},
            },
            {
                "action": "complete_quest", "target": "Zephyr",
                "scene": "Deep in the ruins you find the tome. Pre-Great War archives. The Bandit King is Aldric's unrecognised heir. You return to the tower.",
                "description": "Return to Zephyr with the sealed tome",
                "dialogue": "Got your tome. And something else — the Bandit King's bloodline. Aldric's son.",
                "expected": {"quest_completed": True, "relationship": {"Zephyr": 20}},
            },
            {
                "action": "ask_about", "target": "Zephyr", "topic": "The Great War and Aldric's court",
                "scene": "Zephyr goes pale reading the tome. He was Aldric's court wizard. He knew the bastard son as a boy.",
                "description": "Ask Zephyr about his past with Aldric",
                "dialogue": "You knew Aldric. You were there. What happened to his son?",
                "expected": {"relationship": {"Zephyr": 5}},
            },
            {
                "action": "give_gift", "target": "Zephyr", "item": "Ancient grimoire fragment",
                "scene": "In the Shadowfen ruins you found more than the tome — a fragment of an ancient grimoire. Zephyr would value it.",
                "description": "Give Zephyr the grimoire fragment from Shadowfen",
                "dialogue": "Found this in the ruins too. Didn't seem right to sell it. Thought you might know what it is.",
                "expected": {"relationship": {"Zephyr": 15}},
            },
            {
                "action": "accept_quest", "target": "Zephyr", "quest_type": "collection",
                "scene": "Zephyr needs herbs from Shadowfen for a potion. Secondary work, but he's opening up to you.",
                "description": "Accept the herb collection quest from Zephyr",
                "dialogue": "Herbs. I know the swamp now. What do you need?",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "complete_quest", "target": "Zephyr",
                "scene": "You return with the herbs. Zephyr is genuinely pleased. He mentions the restricted section of his library.",
                "description": "Complete the herb collection for Zephyr",
                "dialogue": "Moonpetals and shadow-root. Picked them at midnight, like you said. Smelled like death.",
                "expected": {"quest_completed": True, "relationship": {"Zephyr": 10}},
            },
            {
                "action": "talk_to", "target": "Thorne",
                "scene": "You visit the forge. Thorne mentions Zephyr spoke to him about the Bandit King. The old wizard is worried. Thorne is forging more weapons than usual.",
                "description": "Talk to Thorne about the growing threat",
                "dialogue": "Heard Zephyr talked to you. If there's trouble coming, I want to be ready.",
                "expected": {"relationship": {"Thorne": 5}},
            },
        ],
    ),
    SessionPlan(
        session_number=5,
        title="Legends and Reckonings",
        chapter_title="What Was Forged in Fire",
        opening="The village is different now. Word has spread — the Bandit King is mustering for a major raid. Not just caravans this time. Villages. The road to Ironhold is cut. Port Harbor has hired mercenaries. Thorne is forging weapons day and night. Elara's cart is empty — she's using her network to bring in supplies. Zephyr's tower glows like a beacon.",
        max_turns=14,
        turns=[
            {
                "action": "talk_to", "target": "Elara",
                "scene": "You approach Elara for the first time since the pass. She's organising supply shipments. She looks up. Her expression is unreadable.",
                "description": "Approach Elara to help with village defence",
                "dialogue": "I'm not here to apologise again. I'm here to help. What do you need?",
                "expected": {"relationship": {"Elara": 3}},
            },
            {
                "action": "accept_quest", "target": "Thorne", "quest_type": "fetch",
                "scene": "Thorne is forging a blade from the last of his star-iron. A weapon to turn the tide. But he needs materials from the Scarred Wastes.",
                "description": "Accept the legendary Final Forge quest from Thorne",
                "dialogue": "You're making something special. What do you need, and how far do I have to go to get it?",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "accept_quest", "target": "Elara", "quest_type": "escort",
                "scene": "Elara needs weapons smuggled to the village militia through the now-dangerous pass. A chance at redemption.",
                "description": "Accept the weapons escort quest from Elara",
                "dialogue": "The Pass again. Last time I went through there, I lost your caravan. This time I won't fail.",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "complete_quest", "target": "Elara",
                "scene": "You escort the weapons through the pass. No losses this time. Every crate delivered. Elara is waiting at the gate.",
                "description": "Complete the weapons escort for Elara",
                "dialogue": "Every crate. Every weapon. Delivered. No losses this time.",
                "expected": {"quest_completed": True, "relationship": {"Elara": 15}},
            },
            {
                "action": "talk_to", "target": "Elara",
                "scene": "A quiet moment after the delivery. Just you and Elara by her cart. The village is preparing for war.",
                "description": "Have a quiet conversation with Elara — apologise",
                "dialogue": "I'm sorry. Not for the caravan — for not being straight with you. I should have told you the pass was too dangerous. I knew it, and I went anyway.",
                "expected": {"relationship": {"Elara": 5}},
            },
            {
                "action": "travel_to", "destination": "scarred_wastes",
                "scene": "The Scarred Wastes. Barren desert created by magical weapons during the Great War. The sand itself hums with unstable energy.",
                "description": "Travel to the Scarred Wastes",
                "dialogue": "",
                "expected": {"zone_change": True},
            },
            {
                "action": "complete_quest", "target": "Thorne",
                "scene": "You find what Thorne needs in the ruins — and the Bandit King's war banner. He's planning to attack the village. You rush back.",
                "description": "Return with Thorne's materials and the warning",
                "dialogue": "Thorne. I have what you need. But there's more — the Bandit King is coming. For the village.",
                "expected": {"quest_completed": True, "relationship": {"Thorne": 25}},
            },
            {
                "action": "give_gift", "target": "Thorne", "item": "Masterwork hammer from Ironhold",
                "scene": "You purchased a masterwork hammer from an Ironhold trader. The finest dwarven craftsmanship. You know Thorne will treasure it.",
                "description": "Give Thorne the masterwork hammer",
                "dialogue": "Saw this in Ironhold. Thought of you immediately. It's Ironforge make — the real thing.",
                "expected": {"relationship": {"Thorne": 20}},
            },
            {
                "action": "accept_quest", "target": "Zephyr", "quest_type": "dialogue",
                "scene": "Zephyr needs to return to the old battlefield from the Great War. He must face what he did during the Mage Purge. He asks you to come with him.",
                "description": "Accept the war ghosts quest from Zephyr",
                "dialogue": "You need to go back there. I understand that. You shouldn't go alone.",
                "expected": {"quest_accepted": True},
            },
            {
                "action": "complete_quest", "target": "Zephyr",
                "scene": "At the old battlefield, Zephyr confronts his past. He reveals he exposed the Church's corruption but couldn't save the mages who died. You stand with him in the silence.",
                "description": "Complete the war ghosts quest with Zephyr",
                "dialogue": "You couldn't save everyone. Neither could I. But you tried. That's more than most can say.",
                "expected": {"quest_completed": True, "relationship": {"Zephyr": 25}},
            },
            {
                "action": "give_gift", "target": "Elara", "item": "Exotic spices from Port Harbor",
                "scene": "You remember her first words to you — spices from the Eastern deserts. You found some in Port Harbor. A small gesture, but a genuine one.",
                "description": "Give Elara the exotic spices",
                "dialogue": "Remembered something from when we first met. Spices from the Eastern deserts. Thought you might appreciate the real thing.",
                "expected": {"relationship": {"Elara": 10}},
            },
            {
                "action": "talk_to", "target": "all",
                "scene": "The village is ready. Thorne has forged the blade. Elara has supplied the militia. Zephyr has lifted the protective wards. You stand with all three of them as the sun sets. Whatever comes tomorrow, you're not facing it alone.",
                "description": "Final conversation with all three NPCs",
                "dialogue": "I came to this village looking for a sword repair. Found something else instead. Whatever happens tomorrow — I'm with you. All of you.",
                "expected": {},
            },
        ],
    ),
]


class SimulationEngine:
    def __init__(
        self,
        chronicle_store: ChronicleStore,
        npc_manager=None,
        relationship_tracker=None,
        quest_manager=None,
        conversation_manager=None,
        lore_system=None,
        event_system=None,
        dm_engine=None,
    ):
        self.store = chronicle_store
        self.npc_manager = npc_manager
        self.relationship_tracker = relationship_tracker
        self.quest_manager = quest_manager
        self.conversation_manager = conversation_manager
        self.lore_system = lore_system
        self.event_system = event_system
        self.dm_engine = dm_engine

        backend = os.getenv("LLM_BACKEND", "ollama")
        api_key = os.getenv("GROQ_API_KEY")
        self.player_llm = PlayerLLM(backend=backend, api_key=api_key)
        self.narrator_llm = NarratorLLM(backend=backend, api_key=api_key)

        self.state = SimulationState.IDLE
        self.current_session = 0
        self.current_turn = 0
        self.context = PlayerContext()
        self._session_plans = {p.session_number: p for p in SESSION_PLANS}
        self._tracked_quests: Dict[str, Any] = {}
        self._chronicle_websockets: List = []
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._cancel = False

    def register_websocket(self, ws):
        self._chronicle_websockets.append(ws)
        print(f"[Chronicle] WebSocket registered ({len(self._chronicle_websockets)} client(s) connected)")

    def unregister_websocket(self, ws):
        if ws in self._chronicle_websockets:
            self._chronicle_websockets.remove(ws)
        print(f"[Chronicle] WebSocket unregistered ({len(self._chronicle_websockets)} client(s) remaining)")

    def reset(self):
        self.store.turns = []
        self.store.metadata = {
            "title": "The Chronicle of Kael Ashwood",
            "started_at": None,
            "completed_at": None,
            "sessions_completed": 0,
            "total_turns": 0,
        }
        self.state = SimulationState.IDLE
        self.current_session = 0
        self.current_turn = 0
        self.context = PlayerContext()
        self._tracked_quests = {}
        self._cancel = False
        self._pause_event.set()
        print(f"[Chronicle] Engine reset complete ({len(self._chronicle_websockets)} WebSocket client(s) preserved)")

    async def _broadcast_turn(self, turn: ChronicleTurn):
        data = {
            "type": "chronicle_update",
            "turn": turn.to_dict(),
        }
        if not self._chronicle_websockets:
            print(f"[Chronicle] No WebSocket clients connected — turn {turn.turn_id} not delivered live")
        for ws in list(self._chronicle_websockets):
            try:
                await ws.send_json(data)
            except Exception as e:
                print(f"[Chronicle] WebSocket send failed: {e}")
                self._chronicle_websockets.remove(ws)

    async def _broadcast_event(self, event_type: str, data: Dict):
        msg = {"type": event_type, **data}
        for ws in list(self._chronicle_websockets):
            try:
                await ws.send_json(msg)
            except Exception as e:
                print(f"[Chronicle] WebSocket event send failed: {e}")
                self._chronicle_websockets.remove(ws)

    def get_status(self) -> Dict:
        return {
            "state": self.state.value,
            "current_session": self.current_session,
            "current_turn": self.current_turn,
            "total_turns": len(self.store.turns),
            "location": self.context.location,
            "relationships": {
                npc: data for npc, data in self.context.relationships.items()
            },
        }

    def _sync_relationships(self):
        if not self.relationship_tracker:
            return
        for npc_name in ["Thorne", "Elara", "Zephyr"]:
            try:
                score = self.relationship_tracker.scores.get(npc_name, 0)
                level = self.relationship_tracker.get_level(npc_name)
                self.context.update_relationship(npc_name, score, level.value if hasattr(level, 'value') else str(level))
            except Exception:
                pass

    def _get_available_actions(self, turn_plan: Dict) -> List[Dict]:
        actions = []
        action_type = turn_plan.get("action", "wait")
        target = turn_plan.get("target", "")
        description = turn_plan.get("description", f"{action_type} {target}".strip())
        actions.append({
            "type": action_type,
            "target": target,
            "description": description,
        })
        actions.append({
            "type": "wait",
            "description": "Wait and observe",
        })
        return actions

    async def _execute_dialogue(self, npc_name: str, player_text: str) -> Dict:
        result = {"npc_name": npc_name, "npc_response": None, "dialogue_history": []}
        if not self.npc_manager or npc_name not in self.npc_manager.npcs:
            result["npc_response"] = f"*{npc_name} is not available right now.*"
            return result

        npc = self.npc_manager.npcs[npc_name]
        try:
            response = npc.generate_response(player_text)
            result["npc_response"] = response
            result["dialogue_history"] = [
                {"role": "player", "content": player_text},
                {"role": "npc", "content": response},
            ]
            if self.relationship_tracker:
                try:
                    new_score = self.relationship_tracker.update_from_dialogue(npc_name, "friendly")
                    result["relationship_delta"] = new_score
                except Exception:
                    pass
        except Exception as e:
            result["npc_response"] = f"*{npc_name} stares at you blankly.*"
            result["error"] = str(e)
        return result

    async def _execute_quest_accept(self, npc_name: str, quest_type: str = None) -> Dict:
        result = {"accepted": False, "quest": None}
        if not self.quest_manager:
            return result
        try:
            npc_data = None
            if self.npc_manager and npc_name in self.npc_manager.npcs:
                npc_obj = self.npc_manager.npcs[npc_name]
                try:
                    with open(npc_obj.character_card_path, 'r') as f:
                        npc_data = json.load(f)
                except Exception:
                    npc_data = {"name": npc_name, "archetype": npc_name.lower()}

            from quest_generator import QuestType
            qt = None
            if quest_type:
                try:
                    qt = QuestType(quest_type)
                except (ValueError, KeyError):
                    pass

            quest = self.quest_manager.quest_generator.generate_quest(
                npc_name=npc_name,
                npc_data=npc_data,
                quest_type=qt,
            )
            if quest:
                accepted = self.quest_manager.accept_quest(quest.id)
                if accepted:
                    self._tracked_quests[quest.name] = quest
                    result["accepted"] = True
                    result["quest"] = {
                        "id": quest.id,
                        "name": quest.name,
                        "description": quest.description,
                        "type": quest.quest_type.value if hasattr(quest.quest_type, 'value') else str(quest.quest_type),
                    }
                    self.context.active_quests.append(result["quest"])
        except Exception as e:
            result["error"] = str(e)
        return result

    async def _execute_quest_complete(self, npc_name: str, quest_name: str = None) -> Dict:
        result = {"completed": False, "rewards": None}
        if not self.quest_manager:
            return result
        try:
            quest_id = None
            for qid, quest in self.quest_manager.active_quests.items():
                quest_id = qid
                break
            if not quest_id:
                for name, q in self._tracked_quests.items():
                    quest_id = q.id
                    break

            if quest_id:
                rewards = self.quest_manager.complete_quest(quest_id)
                result["completed"] = True
                result["rewards"] = rewards
                result["quest_id"] = quest_id

                if self.relationship_tracker and npc_name:
                    new_score = self.relationship_tracker.update_from_quest(
                        npc_name, quest_id, success=True, reward=15.0
                    )
                    result["relationship_delta"] = new_score

                if rewards and rewards.get("gold"):
                    self.context.gold += rewards["gold"]
                if rewards and rewards.get("items"):
                    for item in rewards["items"]:
                        self.context.inventory[item] = self.context.inventory.get(item, 0) + 1

                self.context.active_quests = [
                    q for q in self.context.active_quests
                    if q.get("id") != quest_id
                ]
        except Exception as e:
            result["error"] = str(e)
        return result

    async def _execute_quest_fail(self, npc_name: str, quest_name: str = None) -> Dict:
        result = {"failed": False}
        if not self.quest_manager:
            return result
        try:
            quest_id = None
            for qid in list(self.quest_manager.active_quests.keys()):
                quest_id = qid
                break
            if not quest_id:
                for name, q in self._tracked_quests.items():
                    quest_id = q.id
                    break

            if quest_id:
                success = self.quest_manager.fail_quest(quest_id, reason="ambush_overwhelmed")
                result["failed"] = success
                result["quest_id"] = quest_id

                if self.relationship_tracker and npc_name:
                    new_score = self.relationship_tracker.update_from_quest(
                        npc_name, quest_id, success=False, reward=15.0
                    )
                    result["relationship_delta"] = new_score
                    try:
                        self.relationship_tracker.update_faction("Merchants Guild", -10, "failed_caravan_quest")
                    except Exception:
                        pass

                self.context.active_quests = [
                    q for q in self.context.active_quests
                    if q.get("id") != quest_id
                ]
        except Exception as e:
            result["error"] = str(e)
        return result

    async def _execute_gift(self, npc_name: str, item_name: str) -> Dict:
        result = {"given": False}
        if not self.relationship_tracker:
            return result
        try:
            new_score = self.relationship_tracker.update_from_gift(
                npc_name, item_name, value=10.0,
                player_inventory=self.context.inventory,
            )
            if new_score is not None:
                result["given"] = True
                result["relationship_delta"] = new_score
                if item_name in self.context.inventory:
                    self.context.inventory[item_name] -= 1
                    if self.context.inventory[item_name] <= 0:
                        del self.context.inventory[item_name]
            else:
                result["given"] = True
                self.relationship_tracker.update_score(npc_name, 10.0, f"gift:{item_name}")
                result["relationship_delta"] = self.relationship_tracker.scores.get(npc_name, 0)
        except Exception as e:
            result["error"] = str(e)
        return result

    async def _execute_travel(self, destination: str) -> Dict:
        result = {"travelled": True, "destination": destination}
        old_location = self.context.location
        self.context.location = destination
        self.context.recent_events.append(f"Travelled from {old_location} to {destination}")
        return result

    async def _execute_overhear(self, npc1: str, npc2: str) -> Dict:
        result = {"overheard": False, "conversation": None}
        if not self.conversation_manager:
            result["conversation"] = {
                "npc1": npc1,
                "npc2": npc2,
                "summary": f"{npc1} and {npc2} spoke in hushed tones about the adventurer.",
            }
            result["overheard"] = True
            return result
        try:
            from npc_conversation import ConversationTrigger
            conv = self.conversation_manager.start_conversation(
                npc1_name=npc1,
                npc2_name=npc2,
                trigger=ConversationTrigger.EVENT,
                location=self.context.location,
                max_turns=4,
            )
            if conv:
                result["overheard"] = True
                result["conversation"] = {
                    "id": conv.id,
                    "npc1": npc1,
                    "npc2": npc2,
                    "summary": f"{npc1} and {npc2} discussed recent events.",
                }
                try:
                    self.conversation_manager.end_conversation(conv.id)
                except Exception:
                    pass
        except Exception as e:
            result["conversation"] = {
                "npc1": npc1,
                "npc2": npc2,
                "summary": f"You hear {npc1} and {npc2} talking quietly. You catch fragments about trust, failure, and second chances.",
            }
            result["overheard"] = True
        return result

    async def _execute_ask_about(self, npc_name: str, topic: str) -> Dict:
        result = {"lore_found": [], "npc_response": None}
        if self.lore_system:
            try:
                context = self.lore_system.get_context_for_npc(
                    npc_name=npc_name,
                    query=topic,
                    max_tokens=300,
                )
                if context:
                    result["lore_context"] = context
            except Exception:
                pass

        query_text = f"Tell me about {topic}."
        if self.npc_manager and npc_name in self.npc_manager.npcs:
            npc = self.npc_manager.npcs[npc_name]
            try:
                response = npc.generate_response(query_text)
                result["npc_response"] = response
            except Exception:
                result["npc_response"] = f"*{npc_name} considers your question, but says nothing.*"
        return result

    async def _execute_action(self, player_action: Dict, turn_plan: Dict) -> Dict:
        action_type = player_action.get("action", turn_plan.get("action", "wait"))
        results = {"action": player_action, "action_type": action_type}
        target = player_action.get("target", turn_plan.get("target", ""))

        if action_type == "talk_to":
            dialogue = player_action.get("dialogue", turn_plan.get("dialogue", "Hello."))
            dialogue_result = await self._execute_dialogue(target, dialogue)
            results["dialogue"] = dialogue_result
            results["npc_response"] = dialogue_result.get("npc_response")
            results["npc_name"] = target

        elif action_type == "ask_about":
            topic = player_action.get("topic", turn_plan.get("topic", ""))
            ask_result = await self._execute_ask_about(target, topic)
            results["ask_result"] = ask_result
            results["npc_response"] = ask_result.get("npc_response")
            results["npc_name"] = target
            if ask_result.get("lore_found"):
                results["lore_revealed"] = ask_result["lore_found"]

        elif action_type == "accept_quest":
            quest_type = turn_plan.get("quest_type")
            quest_result = await self._execute_quest_accept(target, quest_type)
            results["quest_result"] = quest_result

        elif action_type == "complete_quest":
            quest_result = await self._execute_quest_complete(target)
            results["quest_result"] = quest_result

        elif action_type == "fail_quest":
            quest_result = await self._execute_quest_fail(target)
            results["quest_result"] = quest_result

        elif action_type == "give_gift":
            item = player_action.get("item", turn_plan.get("item", "Unknown item"))
            gift_result = await self._execute_gift(target, item)
            results["gift_result"] = gift_result

        elif action_type == "travel_to":
            destination = player_action.get("destination", turn_plan.get("destination", ""))
            travel_result = await self._execute_travel(destination)
            results["travel_result"] = travel_result

        elif action_type == "overhear":
            npcs = turn_plan.get("npcs", [target, ""])
            if len(npcs) >= 2:
                overhear_result = await self._execute_overhear(npcs[0], npcs[1])
                results["overhear_result"] = overhear_result

        elif action_type == "wait":
            results["wait"] = True
            self.context.recent_events.append("Time passes.")

        self._sync_relationships()
        return results

    async def _run_turn(self, session_plan: SessionPlan, turn_index: int) -> Optional[ChronicleTurn]:
        if self._cancel:
            return None
        await self._pause_event.wait()

        if turn_index >= len(session_plan.turns):
            return None

        turn_plan = session_plan.turns[turn_index]
        self.current_turn = turn_index + 1
        turn_id = f"s{session_plan.session_number}_t{self.current_turn}"

        available_actions = self._get_available_actions(turn_plan)

        player_action = await self.player_llm.decide(
            context=self.context,
            available_actions=available_actions,
            turn_plan=turn_plan,
        )

        action_results = await self._execute_action(player_action, turn_plan)

        rel_changes = []
        for npc_name in ["Thorne", "Elara", "Zephyr"]:
            if npc_name in self.context.relationships:
                rel_data = self.context.relationships[npc_name]
                rel_changes.append({
                    "npc": npc_name,
                    "score": rel_data["score"],
                    "level": rel_data["level"],
                })

        quest_updates = []
        if "quest_result" in action_results:
            qr = action_results["quest_result"]
            if qr.get("accepted"):
                quest_updates.append({"status": "accepted", **qr.get("quest", {})})
            elif qr.get("completed"):
                quest_updates.append({"status": "completed", "quest_id": qr.get("quest_id")})
            elif qr.get("failed"):
                quest_updates.append({"status": "failed", "quest_id": qr.get("quest_id")})

        narrate_events = {
            "action": player_action,
            "npc_response": action_results.get("npc_response"),
            "npc_name": action_results.get("npc_name"),
            "relationship_changes": rel_changes,
            "quest_updates": quest_updates,
            "location": self.context.location,
        }

        previous_prose = "\n".join(t.prose for t in self.store.turns[-5:])
        prose = await self.narrator_llm.narrate(
            chapter=session_plan.chapter_title,
            events=narrate_events,
            previous_prose=previous_prose,
        )

        turn = ChronicleTurn(
            turn_id=turn_id,
            session=session_plan.session_number,
            turn_number=self.current_turn,
            action=player_action,
            prose=prose,
            npc_dialogue=action_results.get("dialogue"),
            dm_events=[],
            relationship_changes=rel_changes,
            quest_updates=quest_updates,
            lore_revealed=action_results.get("lore_revealed", []),
            location=self.context.location,
        )

        self.store.add_turn(turn)
        await self._broadcast_turn(turn)

        scene_desc = turn_plan.get("scene", action_results.get("npc_response", ""))
        if scene_desc:
            self.context.recent_events.append(f"Turn {self.current_turn}: {scene_desc[:100]}")
        if len(self.context.recent_events) > 20:
            self.context.recent_events = self.context.recent_events[-20:]

        return turn

    async def run_simulation(self, start_session: int = 1, end_session: int = 5):
        self.state = SimulationState.RUNNING
        self.store.metadata["started_at"] = time.time()
        self._cancel = False

        await self._broadcast_event("simulation_start", {
            "status": "running",
            "total_sessions": end_session - start_session + 1,
        })

        for session_num in range(start_session, end_session + 1):
            if self._cancel:
                break

            plan = self._session_plans.get(session_num)
            if not plan:
                continue

            self.current_session = session_num
            self.current_turn = 0

            opening_prose = plan.opening
            opening_turn = ChronicleTurn(
                turn_id=f"s{session_num}_opening",
                session=session_num,
                turn_number=0,
                action={"type": "session_opening"},
                prose=opening_prose,
                location=self.context.location,
            )
            self.store.add_turn(opening_turn)
            await self._broadcast_event("session_start", {
                "session": session_num,
                "title": plan.title,
                "chapter_title": plan.chapter_title,
                "opening": opening_prose,
            })
            await self._broadcast_turn(opening_turn)

            for turn_idx in range(len(plan.turns)):
                if self._cancel:
                    break
                await self._run_turn(plan, turn_idx)
                await asyncio.sleep(0.5)

            self.store.metadata["sessions_completed"] = session_num
            await self._broadcast_event("session_end", {
                "session": session_num,
                "title": plan.title,
            })

            if session_num < end_session and not self._cancel:
                await asyncio.sleep(1.0)

        self.state = SimulationState.COMPLETE
        self.store.metadata["completed_at"] = time.time()
        self.store.save()
        await self._broadcast_event("simulation_complete", {
            "status": "complete",
            "total_turns": len(self.store.turns),
            "sessions_completed": self.store.metadata["sessions_completed"],
        })

    def pause(self):
        self.state = SimulationState.PAUSED
        self._pause_event.clear()

    def resume(self):
        self.state = SimulationState.RUNNING
        self._pause_event.set()

    def cancel(self):
        self._cancel = True
        self._pause_event.set()
        self.state = SimulationState.IDLE


if __name__ == "__main__":
    import uvicorn

    print("Starting Player Simulation...")
    print("This module is designed to run via the API server.")
    print("Usage: python api_server.py")
    print("Then: POST http://localhost:8000/api/simulation/start")
    print("Open: http://localhost:8000/chronicle")
