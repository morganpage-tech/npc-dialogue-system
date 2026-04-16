"""
Quest Generation System for NPC Dialogue System
Procedural quest generation with NPC integration, difficulty scaling, and persistence
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Set, Any, TYPE_CHECKING
from dataclasses import dataclass, asdict, field
from enum import Enum
import random

# Optional imports for integration
try:
    from relationship_tracking import RelationshipTracker, RelationshipLevel
    HAS_RELATIONSHIP_SYSTEM = True
except ImportError:
    HAS_RELATIONSHIP_SYSTEM = False
    RelationshipTracker = None
    RelationshipLevel = None

try:
    from lore_system import LoreSystem
    HAS_LORE_SYSTEM = True
except ImportError:
    HAS_LORE_SYSTEM = False
    LoreSystem = None


class QuestType(Enum):
    """Types of quests that can be generated."""
    KILL = "kill"              # Defeat enemies
    FETCH = "fetch"            # Deliver items
    EXPLORE = "explore"        # Discover locations
    ESCORT = "escort"          # Protect/guide NPCs
    COLLECTION = "collection"  # Gather resources
    DIALOGUE = "dialogue"      # Talk to NPCs


class QuestStatus(Enum):
    """Possible states for a quest."""
    AVAILABLE = "available"    # Can be accepted
    ACTIVE = "active"          # Currently in progress
    COMPLETED = "completed"    # Successfully finished
    FAILED = "failed"          # Failed (time expired, etc.)
    ABANDONED = "abandoned"    # Player gave up


class ObjectiveType(Enum):
    """Types of objectives within a quest."""
    KILL_TARGET = "kill_target"
    COLLECT_ITEM = "collect_item"
    REACH_LOCATION = "reach_location"
    TALK_TO_NPC = "talk_to_npc"
    ESCORT_NPC = "escort_npc"
    DELIVER_ITEM = "deliver_item"
    DISCOVER_SECRET = "discover_secret"
    DEFEAT_BOSS = "defeat_boss"


@dataclass
class Objective:
    """A single objective within a quest."""
    id: str
    type: ObjectiveType
    description: str
    target: str              # What to interact with (enemy type, item name, NPC, location)
    required: int = 1        # How many needed
    current: int = 0         # Current progress
    optional: bool = False   # If True, not required for completion
    
    def is_complete(self) -> bool:
        """Check if objective is complete."""
        return self.current >= self.required
    
    def progress_percent(self) -> float:
        """Get completion percentage."""
        if self.required == 0:
            return 100.0
        return min(100.0, (self.current / self.required) * 100)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "target": self.target,
            "required": self.required,
            "current": self.current,
            "optional": self.optional,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Objective':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=ObjectiveType(data["type"]),
            description=data["description"],
            target=data["target"],
            required=data.get("required", 1),
            current=data.get("current", 0),
            optional=data.get("optional", False),
        )


@dataclass
class QuestReward:
    """Rewards for completing a quest."""
    gold: int = 0
    xp: int = 0
    items: List[str] = field(default_factory=list)
    relationship_bonus: Dict[str, int] = field(default_factory=dict)  # npc_name -> bonus
    faction_bonus: Dict[str, int] = field(default_factory=dict)       # faction_name -> bonus
    unlocks: List[str] = field(default_factory=list)  # Quest IDs that become available
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "gold": self.gold,
            "xp": self.xp,
            "items": self.items,
            "relationship_bonus": self.relationship_bonus,
            "faction_bonus": self.faction_bonus,
            "unlocks": self.unlocks,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'QuestReward':
        """Create from dictionary."""
        return cls(
            gold=data.get("gold", 0),
            xp=data.get("xp", 0),
            items=data.get("items", []),
            relationship_bonus=data.get("relationship_bonus", {}),
            faction_bonus=data.get("faction_bonus", {}),
            unlocks=data.get("unlocks", []),
        )


@dataclass
class Quest:
    """
    A complete quest with objectives, rewards, and metadata.
    """
    id: str
    name: str
    description: str
    quest_giver: str           # NPC who gives the quest
    quest_type: QuestType
    
    # Objectives
    objectives: List[Objective]
    
    # Rewards
    rewards: QuestReward
    
    # Constraints
    time_limit: Optional[int] = None    # Seconds until failure, None = no limit
    prerequisites: List[str] = field(default_factory=list)  # Required quest IDs
    min_relationship: Optional[str] = None  # Required relationship level with quest giver
    required_items: List[str] = field(default_factory=list)  # Items needed to start
    
    # State
    status: QuestStatus = QuestStatus.AVAILABLE
    accepted_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Metadata
    difficulty: int = 1        # 1-5 scale
    generated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None  # When quest becomes unavailable
    location: Optional[str] = None  # Where the quest takes place
    narrative_context: str = ""  # Why this quest exists (lore-friendly reason)
    
    def is_expired(self) -> bool:
        """Check if quest has expired (no longer available)."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def is_timed_out(self) -> bool:
        """Check if active quest has exceeded time limit."""
        if self.status != QuestStatus.ACTIVE:
            return False
        if self.time_limit is None or self.accepted_at is None:
            return False
        return time.time() > (self.accepted_at + self.time_limit)
    
    def is_complete(self) -> bool:
        """Check if all required objectives are complete."""
        for obj in self.objectives:
            if not obj.optional and not obj.is_complete():
                return False
        return True
    
    def progress_percent(self) -> float:
        """Get overall quest completion percentage."""
        required = [o for o in self.objectives if not o.optional]
        if not required:
            return 100.0
        return sum(o.progress_percent() for o in required) / len(required)
    
    def get_time_remaining(self) -> Optional[int]:
        """Get seconds remaining for timed quests."""
        if self.time_limit is None or self.accepted_at is None:
            return None
        remaining = (self.accepted_at + self.time_limit) - time.time()
        return max(0, int(remaining))
    
    def accept(self, player_inventory: Optional[Dict[str, int]] = None) -> bool:
        """Accept the quest."""
        if self.status != QuestStatus.AVAILABLE:
            return False
        if self.is_expired():
            return False
        if self.required_items and player_inventory is not None:
            for item in self.required_items:
                item_lower = item.lower()
                has_item = any(
                    item_lower in inv_item.lower() and qty > 0
                    for inv_item, qty in player_inventory.items()
                )
                if not has_item:
                    return False
        self.status = QuestStatus.ACTIVE
        self.accepted_at = time.time()
        return True
    
    def abandon(self) -> bool:
        """Abandon the quest."""
        if self.status != QuestStatus.ACTIVE:
            return False
        self.status = QuestStatus.ABANDONED
        return True
    
    def complete(self) -> bool:
        """Complete the quest."""
        if self.status != QuestStatus.ACTIVE:
            return False
        if not self.is_complete():
            return False
        self.status = QuestStatus.COMPLETED
        self.completed_at = time.time()
        return True
    
    def fail(self, reason: str = "") -> bool:
        """Fail the quest."""
        if self.status != QuestStatus.ACTIVE:
            return False
        self.status = QuestStatus.FAILED
        self.completed_at = time.time()
        return True
    
    def update_objective(self, objective_type: ObjectiveType, target: str, amount: int = 1) -> bool:
        """
        Update progress on an objective.
        
        Args:
            objective_type: Type of objective to update
            target: Target of the objective (enemy name, item name, etc.)
            amount: Amount to add to progress
            
        Returns:
            True if objective was updated, False if not found
        """
        for obj in self.objectives:
            if obj.type == objective_type and obj.target.lower() == target.lower():
                obj.current = min(obj.required, obj.current + amount)
                return True
        return False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "quest_giver": self.quest_giver,
            "quest_type": self.quest_type.value,
            "objectives": [o.to_dict() for o in self.objectives],
            "rewards": self.rewards.to_dict(),
            "time_limit": self.time_limit,
            "prerequisites": self.prerequisites,
            "min_relationship": self.min_relationship,
            "required_items": self.required_items,
            "status": self.status.value,
            "accepted_at": self.accepted_at,
            "completed_at": self.completed_at,
            "difficulty": self.difficulty,
            "generated_at": self.generated_at,
            "expires_at": self.expires_at,
            "location": self.location,
            "narrative_context": self.narrative_context,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Quest':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            quest_giver=data["quest_giver"],
            quest_type=QuestType(data["quest_type"]),
            objectives=[Objective.from_dict(o) for o in data.get("objectives", [])],
            rewards=QuestReward.from_dict(data.get("rewards", {})),
            time_limit=data.get("time_limit"),
            prerequisites=data.get("prerequisites", []),
            min_relationship=data.get("min_relationship"),
            required_items=data.get("required_items", []),
            status=QuestStatus(data.get("status", "available")),
            accepted_at=data.get("accepted_at"),
            completed_at=data.get("completed_at"),
            difficulty=data.get("difficulty", 1),
            generated_at=data.get("generated_at", time.time()),
            expires_at=data.get("expires_at"),
            location=data.get("location"),
            narrative_context=data.get("narrative_context", ""),
        )


class QuestGenerator:
    """
    Generates procedural quests based on NPC, player state, and world context.
    """
    
    def __init__(
        self,
        templates_dir: str = "quest_templates",
        relationship_tracker: Optional[RelationshipTracker] = None,
        lore_system: Optional[LoreSystem] = None,
    ):
        """
        Initialize the quest generator.
        
        Args:
            templates_dir: Directory containing quest template JSON files
            relationship_tracker: Optional relationship tracker for context
            lore_system: Optional lore system for world context
        """
        self.templates_dir = templates_dir
        self.relationship_tracker = relationship_tracker
        self.lore_system = lore_system
        self.templates: Dict[QuestType, List[Dict]] = {}
        
        self._load_templates()
    
    def _load_templates(self):
        """Load quest templates from JSON files."""
        template_files = {
            QuestType.KILL: "kill.json",
            QuestType.FETCH: "fetch.json",
            QuestType.EXPLORE: "explore.json",
            QuestType.ESCORT: "escort.json",
            QuestType.COLLECTION: "collection.json",
            QuestType.DIALOGUE: "dialogue.json",
        }
        
        for quest_type, filename in template_files.items():
            filepath = os.path.join(self.templates_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.templates[quest_type] = data.get("templates", [])
            else:
                # Use default templates if file doesn't exist
                self.templates[quest_type] = self._get_default_templates(quest_type)
    
    def _get_default_templates(self, quest_type: QuestType) -> List[Dict]:
        """Get default templates for a quest type."""
        defaults = {
            QuestType.KILL: [
                {
                    "name": "{target_name} Problem",
                    "description": "Defeat {count} {target_name} in {location}.",
                    "objectives": [{"type": "kill_target", "target": "{target_name}", "count": "{count}"}],
                    "narrative_templates": [
                        "The {target_name} in {location} have been causing trouble.",
                        "We need someone to deal with the {target_name} infestation.",
                        "Hunters have reported increased {target_name} activity near {location}.",
                    ]
                }
            ],
            QuestType.FETCH: [
                {
                    "name": "Delivery to {recipient}",
                    "description": "Deliver {item} to {recipient} at {location}.",
                    "objectives": [{"type": "deliver_item", "target": "{item}"}],
                    "narrative_templates": [
                        "I need this {item} delivered to {recipient}.",
                        "Can you take this {item} to {recipient}? They're waiting for it.",
                    ]
                }
            ],
            QuestType.EXPLORE: [
                {
                    "name": "Explore {location}",
                    "description": "Investigate {location} and discover its secrets.",
                    "objectives": [{"type": "reach_location", "target": "{location}"}],
                    "narrative_templates": [
                        "I've heard rumors about {location}. Can you investigate?",
                        "Something strange is happening at {location}. I need someone to check it out.",
                    ]
                }
            ],
            QuestType.ESCORT: [
                {
                    "name": "Escort {escort_target}",
                    "description": "Guide {escort_target} safely to {destination}.",
                    "objectives": [{"type": "escort_npc", "target": "{escort_target}"}],
                    "narrative_templates": [
                        "{escort_target} needs an escort to {destination}. Can you help?",
                        "The roads are dangerous. {escort_target} needs protection on the journey.",
                    ]
                }
            ],
            QuestType.COLLECTION: [
                {
                    "name": "Gather {item}",
                    "description": "Collect {count} {item} from {location}.",
                    "objectives": [{"type": "collect_item", "target": "{item}", "count": "{count}"}],
                    "narrative_templates": [
                        "I need {count} {item} for my work. Can you gather them?",
                        "The {item} found in {location} are of the highest quality.",
                    ]
                }
            ],
            QuestType.DIALOGUE: [
                {
                    "name": "Speak with {target_npc}",
                    "description": "Talk to {target_npc} and learn about {topic}.",
                    "objectives": [{"type": "talk_to_npc", "target": "{target_npc}"}],
                    "narrative_templates": [
                        "{target_npc} has information I need. Can you speak with them?",
                        "I need someone trustworthy to negotiate with {target_npc}.",
                    ]
                }
            ],
        }
        return defaults.get(quest_type, [])
    
    def generate_quest(
        self,
        npc_name: str,
        npc_data: Optional[Dict] = None,
        player_state: Optional[Dict] = None,
        quest_type: Optional[QuestType] = None,
        difficulty: Optional[int] = None,
    ) -> Optional[Quest]:
        """
        Generate a quest for an NPC to offer.
        
        Args:
            npc_name: Name of the NPC giving the quest
            npc_data: NPC character data (archetype, location, etc.)
            player_state: Player state (level, completed quests, etc.)
            quest_type: Force a specific quest type (random if None)
            difficulty: Force a specific difficulty (calculated if None)
            
        Returns:
            Generated Quest or None if generation failed
        """
        npc_data = npc_data or {}
        player_state = player_state or {}
        
        # Determine quest type
        if quest_type is None:
            quest_type = self._determine_quest_type(npc_name, npc_data)
        
        # Get template
        templates = self.templates.get(quest_type, [])
        if not templates:
            return None
        
        template = random.choice(templates)
        
        # Calculate difficulty
        if difficulty is None:
            difficulty = self._calculate_difficulty(player_state)
        
        # Generate quest content
        quest_id = f"quest_{uuid.uuid4().hex[:8]}"
        
        # Fill in template variables
        quest_data = self._fill_template(
            template, 
            npc_name, 
            npc_data, 
            player_state,
            difficulty
        )
        
        # Create objectives
        objectives = self._create_objectives(template, quest_data, difficulty)
        
        # Create rewards
        rewards = self._create_rewards(quest_type, difficulty, npc_name)
        
        # Create the quest
        quest = Quest(
            id=quest_id,
            name=quest_data.get("name", "Unknown Quest"),
            description=quest_data.get("description", "Complete this task."),
            quest_giver=npc_name,
            quest_type=quest_type,
            objectives=objectives,
            rewards=rewards,
            difficulty=difficulty,
            location=quest_data.get("location"),
            narrative_context=quest_data.get("narrative", ""),
        )
        
        # Add time limit for certain quest types
        if quest_type in [QuestType.FETCH, QuestType.ESCORT]:
            quest.time_limit = 300 + (difficulty * 60)  # 5-10 minutes
        
        # Add prerequisites based on relationship
        if self.relationship_tracker and HAS_RELATIONSHIP_SYSTEM:
            rel_level = self.relationship_tracker.get_level(npc_name)
            if rel_level in [RelationshipLevel.LOVED, RelationshipLevel.ADORED]:
                # High relationship quests may unlock special rewards
                quest.rewards.relationship_bonus[npc_name] = 10
            elif rel_level in [RelationshipLevel.HATED, RelationshipLevel.DISLIKED]:
                # Low relationship may require minimum level
                quest.min_relationship = "NEUTRAL"
        
        return quest
    
    def _determine_quest_type(self, npc_name: str, npc_data: Dict) -> QuestType:
        """Determine appropriate quest type based on NPC archetype."""
        archetype = npc_data.get("archetype", "").lower()
        faction = npc_data.get("faction", "").lower()
        
        # Archetype-based quest preferences
        archetype_quests = {
            "merchant": [QuestType.FETCH, QuestType.COLLECTION, QuestType.DIALOGUE],
            "guard": [QuestType.KILL, QuestType.ESCORT, QuestType.EXPLORE],
            "warrior": [QuestType.KILL, QuestType.ESCORT],
            "scholar": [QuestType.EXPLORE, QuestType.DIALOGUE, QuestType.COLLECTION],
            "mage": [QuestType.COLLECTION, QuestType.EXPLORE, QuestType.DIALOGUE],
            "hunter": [QuestType.KILL, QuestType.COLLECTION, QuestType.EXPLORE],
            "farmer": [QuestType.COLLECTION, QuestType.FETCH, QuestType.KILL],
            "noble": [QuestType.FETCH, QuestType.DIALOGUE, QuestType.ESCORT],
            "blacksmith": [QuestType.COLLECTION, QuestType.FETCH],
            "healer": [QuestType.COLLECTION, QuestType.FETCH, QuestType.DIALOGUE],
        }
        
        # Faction-based quest preferences
        faction_quests = {
            "merchants_guild": [QuestType.FETCH, QuestType.COLLECTION],
            "warriors_guild": [QuestType.KILL, QuestType.ESCORT],
            "scholars_guild": [QuestType.EXPLORE, QuestType.DIALOGUE],
            "thieves_guild": [QuestType.FETCH, QuestType.EXPLORE],
            "mages_guild": [QuestType.COLLECTION, QuestType.EXPLORE],
        }
        
        # Check archetype first
        if archetype in archetype_quests:
            return random.choice(archetype_quests[archetype])
        
        # Check faction
        if faction in faction_quests:
            return random.choice(faction_quests[faction])
        
        # Default to random
        return random.choice(list(QuestType))
    
    def _calculate_difficulty(self, player_state: Dict) -> int:
        """Calculate appropriate difficulty based on player state."""
        player_level = player_state.get("level", 1)
        completed_quests = len(player_state.get("completed_quests", []))
        
        # Base difficulty on player level
        base_diff = min(5, max(1, player_level // 3 + 1))
        
        # Adjust for experienced players
        if completed_quests > 10:
            base_diff = min(5, base_diff + 1)
        
        return base_diff
    
    def _fill_template(
        self,
        template: Dict,
        npc_name: str,
        npc_data: Dict,
        player_state: Dict,
        difficulty: int
    ) -> Dict:
        """Fill template with generated content."""
        # Get lore context if available
        location = self._get_location(npc_data, player_state)
        target_name = self._get_target_name(template, npc_data, difficulty)
        item = self._get_item_name(template, npc_data)
        count = self._get_count(difficulty)
        
        # Build quest data
        data = {
            "name": template.get("name", "Quest").format(
                target_name=target_name,
                location=location,
                item=item,
                count=count,
                recipient=self._get_npc_name(),
                escort_target=self._get_npc_name(),
                target_npc=self._get_npc_name(),
                topic="recent events",
            ),
            "description": template.get("description", "Complete this task.").format(
                target_name=target_name,
                location=location,
                item=item,
                count=count,
                recipient=self._get_npc_name(),
                escort_target=self._get_npc_name(),
                target_npc=self._get_npc_name(),
            ),
            "location": location,
            "narrative": "",
        }
        
        # Add narrative context
        narratives = template.get("narrative_templates", [])
        if narratives:
            data["narrative"] = random.choice(narratives).format(
                target_name=target_name,
                location=location,
                item=item,
                escort_target=self._get_npc_name(),
                target_npc=self._get_npc_name(),
            )
        
        return data
    
    def _create_objectives(
        self,
        template: Dict,
        quest_data: Dict,
        difficulty: int
    ) -> List[Objective]:
        """Create objectives from template."""
        objectives = []
        
        for i, obj_template in enumerate(template.get("objectives", [])):
            obj_type = ObjectiveType(obj_template.get("type", "kill_target"))
            target = obj_template.get("target", "enemy")
            
            # Format target
            if "{target_name}" in target:
                target = target.replace("{target_name}", quest_data.get("target_name", "enemy"))
            if "{item}" in target:
                target = target.replace("{item}", quest_data.get("item", "item"))
            if "{location}" in target:
                target = target.replace("{location}", quest_data.get("location", "location"))
            
            # Calculate required count
            count_str = obj_template.get("count", "1")
            try:
                required = int(count_str)
            except ValueError:
                # It's a template variable
                required = self._get_count(difficulty)
            
            objective = Objective(
                id=f"obj_{i}",
                type=obj_type,
                description=f"{obj_type.value.replace('_', ' ').title()}: {target}",
                target=target,
                required=required,
                current=0,
            )
            objectives.append(objective)
        
        return objectives
    
    def _create_rewards(
        self,
        quest_type: QuestType,
        difficulty: int,
        npc_name: str
    ) -> QuestReward:
        """Create rewards based on quest type and difficulty."""
        # Base rewards scale with difficulty
        base_gold = difficulty * 25
        base_xp = difficulty * 50
        
        # Quest type modifiers
        type_modifiers = {
            QuestType.KILL: 1.2,
            QuestType.ESCORT: 1.3,
            QuestType.EXPLORE: 1.0,
            QuestType.FETCH: 0.8,
            QuestType.COLLECTION: 0.9,
            QuestType.DIALOGUE: 0.7,
        }
        
        modifier = type_modifiers.get(quest_type, 1.0)
        
        return QuestReward(
            gold=int(base_gold * modifier),
            xp=int(base_xp * modifier),
            items=self._get_reward_items(quest_type, difficulty),
            relationship_bonus={npc_name: 5 + difficulty * 2},
        )
    
    def _get_reward_items(self, quest_type: QuestType, difficulty: int) -> List[str]:
        """Get reward items based on quest type and difficulty."""
        item_pools = {
            QuestType.KILL: ["monster_hide", "sharp_fang", "rare_bone", "gold_ring"],
            QuestType.FETCH: ["travel_rations", "silver_coin", "merchant_letter"],
            QuestType.EXPLORE: ["ancient_map", "mysterious_artifact", "rare_gem"],
            QuestType.ESCORT: ["guard_badge", "traveler_pendant", "silver_chest"],
            QuestType.COLLECTION: ["gatherer_pouch", "rare_herb", "quality_reagent"],
            QuestType.DIALOGUE: ["information_scroll", "secret_key", "contact_letter"],
        }
        
        pool = item_pools.get(quest_type, ["mystery_box"])
        
        # Higher difficulty = more/better items
        if difficulty >= 4:
            return [random.choice(pool)]
        elif difficulty >= 3:
            return [random.choice(pool)] if random.random() > 0.5 else []
        return []
    
    def _get_location(self, npc_data: Dict, player_state: Dict) -> str:
        """Get appropriate location for quest."""
        # Check NPC location
        npc_location = npc_data.get("location")
        if npc_location:
            return npc_location
        
        # Use lore system if available
        if self.lore_system:
            locations = self.lore_system.query("locations")
            if locations:
                # Extract location names from lore
                return "a nearby area"
        
        # Default locations
        default_locations = [
            "Whisperwood", "Bandit's Pass", "Crystal Caverns",
            "Old Ruins", "Mountain Peak", "Forest Grove",
            "Abandoned Mine", "River Crossing", "Sacred Grove",
        ]
        return random.choice(default_locations)
    
    def _get_target_name(self, template: Dict, npc_data: Dict, difficulty: int) -> str:
        """Get enemy/target name for kill quests."""
        enemies_by_difficulty = {
            1: ["wolf", "rat", "spider", "bat"],
            2: ["bandit", "goblin", "skeleton", "zombie"],
            3: ["orc", "troll", "harpy", "ogre"],
            4: ["demon", "wraith", "golem", "chimera"],
            5: ["dragon", "lich", "ancient_beast", "demon_lord"],
        }
        
        pool = enemies_by_difficulty.get(difficulty, enemies_by_difficulty[1])
        return random.choice(pool)
    
    def _get_item_name(self, template: Dict, npc_data: Dict) -> str:
        """Get item name for fetch/collection quests."""
        items = [
            "healing_herb", "rare_mushroom", "moonpetal", "iron_ore",
            "enchanted_crystal", "ancient_scroll", "rare_gem", "quality_potion",
            "silver_key", "mysterious_letter", "family_heirloom", "magic_ring",
        ]
        return random.choice(items)
    
    def _get_npc_name(self) -> str:
        """Get a random NPC name."""
        names = [
            "Elder Theron", "Merchant Lydia", "Guard Captain Marcus",
            "Scholar Elena", "Healer Jonas", "Blacksmith Greta",
            "Hunter Finn", "Farmer Mara", "Noble Aldric",
        ]
        return random.choice(names)
    
    def _get_count(self, difficulty: int) -> int:
        """Get count based on difficulty."""
        return 2 + difficulty


class QuestManager:
    """
    Manages quest state, persistence, and progress tracking.
    """
    
    def __init__(
        self,
        quest_generator: Optional[QuestGenerator] = None,
        relationship_tracker: Optional[RelationshipTracker] = None,
        save_dir: str = "saves",
    ):
        """
        Initialize the quest manager.
        
        Args:
            quest_generator: Quest generator instance
            relationship_tracker: Relationship tracker for reward processing
            save_dir: Directory for save files
        """
        self.quest_generator = quest_generator or QuestGenerator()
        self.relationship_tracker = relationship_tracker
        self.save_dir = save_dir
        
        # Quest storage
        self.active_quests: Dict[str, Quest] = {}
        self.available_quests: Dict[str, List[Quest]] = {}  # npc_name -> quests
        self.completed_quests: Set[str] = set()
        self.failed_quests: Set[str] = set()
        
        # Ensure save directory exists
        os.makedirs(save_dir, exist_ok=True)
    
    def get_available_quests(
        self,
        npc_name: str,
        player_state: Optional[Dict] = None
    ) -> List[Quest]:
        """
        Get quests available from an NPC.
        
        Args:
            npc_name: Name of the NPC
            player_state: Current player state for filtering
            
        Returns:
            List of available quests
        """
        player_state = player_state or {}
        
        # Check if we have cached quests
        if npc_name in self.available_quests:
            # Filter out expired quests
            quests = [q for q in self.available_quests[npc_name] 
                     if not q.is_expired() and q.status == QuestStatus.AVAILABLE]
            
            # Filter by prerequisites
            quests = [q for q in quests 
                     if all(p in self.completed_quests for p in q.prerequisites)]
            
            # Filter by relationship requirement
            if self.relationship_tracker and HAS_RELATIONSHIP_SYSTEM:
                filtered = []
                for q in quests:
                    if q.min_relationship:
                        level = self.relationship_tracker.get_level(npc_name)
                        required = RelationshipLevel[q.min_relationship]
                        # Check if current level >= required
                        level_order = list(RelationshipLevel)
                        if level_order.index(level) >= level_order.index(required):
                            filtered.append(q)
                    else:
                        filtered.append(q)
                quests = filtered
            
            return quests
        
        return []
    
    def generate_quests_for_npc(
        self,
        npc_name: str,
        npc_data: Optional[Dict] = None,
        player_state: Optional[Dict] = None,
        count: int = 2
    ) -> List[Quest]:
        """
        Generate new quests for an NPC to offer.
        
        Args:
            npc_name: Name of the NPC
            npc_data: NPC character data
            player_state: Current player state
            count: Number of quests to generate
            
        Returns:
            List of generated quests
        """
        npc_data = npc_data or {}
        player_state = player_state or {}
        
        quests = []
        for _ in range(count):
            quest = self.quest_generator.generate_quest(
                npc_name=npc_name,
                npc_data=npc_data,
                player_state=player_state,
            )
            if quest:
                quests.append(quest)
        
        # Store available quests
        if npc_name not in self.available_quests:
            self.available_quests[npc_name] = []
        self.available_quests[npc_name].extend(quests)
        
        return quests
    
    def register_quest(self, quest: Quest):
        """
        Register an extracted or generated quest as available.
        
        Idempotent - registering the same quest twice is a no-op.
        """
        npc_name = quest.quest_giver
        self.available_quests.setdefault(npc_name, [])
        existing_ids = {q.id for q in self.available_quests[npc_name]}
        if quest.id not in existing_ids:
            self.available_quests[npc_name].append(quest)
    
    def accept_quest(self, quest_id: str, player_inventory: Optional[Dict[str, int]] = None) -> Optional[Quest]:
        """
        Accept a quest.
        
        Args:
            quest_id: ID of the quest to accept
            player_inventory: Optional inventory dict for required_items check
            
        Returns:
            The accepted quest, or None if not found
        """
        for npc_name, quests in self.available_quests.items():
            for quest in quests:
                if quest.id == quest_id:
                    if quest.accept(player_inventory=player_inventory):
                        self.active_quests[quest_id] = quest
                        quests.remove(quest)
                        return quest
        return None
    
    def abandon_quest(self, quest_id: str) -> bool:
        """
        Abandon an active quest.
        
        Args:
            quest_id: ID of the quest to abandon
            
        Returns:
            True if quest was abandoned
        """
        if quest_id in self.active_quests:
            quest = self.active_quests[quest_id]
            if quest.abandon():
                del self.active_quests[quest_id]
                return True
        return False
    
    def complete_quest(self, quest_id: str) -> Optional[Dict]:
        """
        Complete a quest and process rewards.
        
        Args:
            quest_id: ID of the quest to complete
            
        Returns:
            Reward data, or None if quest couldn't be completed
        """
        if quest_id not in self.active_quests:
            return None
        
        quest = self.active_quests[quest_id]
        
        if not quest.is_complete():
            return None
        
        if quest.complete():
            self.completed_quests.add(quest_id)
            del self.active_quests[quest_id]
            
            # Process relationship rewards
            if self.relationship_tracker:
                for npc_name, bonus in quest.rewards.relationship_bonus.items():
                    self.relationship_tracker.update_score(
                        npc_name, bonus, f"completed quest: {quest.name}"
                    )
                
                for faction, bonus in quest.rewards.faction_bonus.items():
                    self.relationship_tracker.update_faction(
                        faction, bonus, f"completed quest: {quest.name}"
                    )
            
            return quest.rewards.to_dict()
        
        return None
    
    def fail_quest(self, quest_id: str, reason: str = "") -> bool:
        """
        Fail a quest.
        
        Args:
            quest_id: ID of the quest to fail
            reason: Reason for failure
            
        Returns:
            True if quest was failed
        """
        if quest_id in self.active_quests:
            quest = self.active_quests[quest_id]
            if quest.fail(reason):
                self.failed_quests.add(quest_id)
                del self.active_quests[quest_id]
                
                # Apply relationship penalty
                if self.relationship_tracker:
                    self.relationship_tracker.update_score(
                        quest.quest_giver, -10, f"failed quest: {quest.name}"
                    )
                
                return True
        return False
    
    def update_progress(
        self,
        objective_type: ObjectiveType,
        target: str,
        amount: int = 1
    ) -> Dict[str, int]:
        """
        Update progress on all active quests matching an action.
        
        Args:
            objective_type: Type of objective to update
            target: Target of the action
            amount: Amount to add
            
        Returns:
            Dict of quest_id -> new_progress for updated quests
        """
        updates = {}
        
        for quest_id, quest in self.active_quests.items():
            if quest.update_objective(objective_type, target, amount):
                updates[quest_id] = quest.progress_percent()
        
        return updates
    
    def check_timeouts(self) -> List[str]:
        """
        Check for timed-out quests and fail them.
        
        Returns:
            List of failed quest IDs
        """
        failed = []
        
        for quest_id, quest in list(self.active_quests.items()):
            if quest.is_timed_out():
                self.fail_quest(quest_id, "Time limit exceeded")
                failed.append(quest_id)
        
        return failed
    
    def get_active_quests(self) -> List[Quest]:
        """Get all active quests."""
        return list(self.active_quests.values())
    
    def get_quest(self, quest_id: str) -> Optional[Quest]:
        """Get a specific quest by ID."""
        return self.active_quests.get(quest_id)
    
    def save(self, player_id: str = "player"):
        """
        Save quest state to file.
        
        Args:
            player_id: Player identifier for save file
        """
        filepath = os.path.join(self.save_dir, f"{player_id}_quests.json")
        
        data = {
            "player_id": player_id,
            "active_quests": [q.to_dict() for q in self.active_quests.values()],
            "available_quests": {
                npc: [q.to_dict() for q in quests]
                for npc, quests in self.available_quests.items()
            },
            "completed_quests": list(self.completed_quests),
            "failed_quests": list(self.failed_quests),
            "saved_at": time.time(),
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved quest data to {filepath}")
    
    def load(self, player_id: str = "player"):
        """
        Load quest state from file.
        
        Args:
            player_id: Player identifier for save file
        """
        filepath = os.path.join(self.save_dir, f"{player_id}_quests.json")
        
        if not os.path.exists(filepath):
            print(f"No quest save file found at {filepath}")
            return
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.active_quests = {
            q["id"]: Quest.from_dict(q)
            for q in data.get("active_quests", [])
        }
        
        self.available_quests = {
            npc: [Quest.from_dict(q) for q in quests]
            for npc, quests in data.get("available_quests", {}).items()
        }
        
        self.completed_quests = set(data.get("completed_quests", []))
        self.failed_quests = set(data.get("failed_quests", []))
        
        print(f"Loaded quest data from {filepath}")
        print(f"  Active: {len(self.active_quests)} | Completed: {len(self.completed_quests)}")
    
    def get_summary(self) -> Dict:
        """Get summary of quest state."""
        return {
            "active": len(self.active_quests),
            "completed": len(self.completed_quests),
            "failed": len(self.failed_quests),
            "available_npcs": list(self.available_quests.keys()),
        }
    
    def print_summary(self):
        """Print formatted summary of quest state."""
        print(f"\n{'='*60}")
        print("  QUEST SUMMARY")
        print(f"{'='*60}\n")
        
        print(f"  Active Quests: {len(self.active_quests)}")
        for quest in self.active_quests.values():
            time_str = ""
            if quest.get_time_remaining():
                remaining = quest.get_time_remaining()
                mins, secs = divmod(remaining, 60)
                time_str = f" [{mins}:{secs:02d} remaining]"
            print(f"    - {quest.name} ({quest.progress_percent():.0f}%){time_str}")
        
        print(f"\n  Completed: {len(self.completed_quests)}")
        print(f"  Failed: {len(self.failed_quests)}")
        
        print(f"\n{'='*60}\n")


# Convenience function for quick quest generation
def generate_quest_for_npc(
    npc_name: str,
    npc_archetype: str = None,
    player_level: int = 1,
    quest_type: str = None
) -> Optional[Quest]:
    """
    Quick helper to generate a quest for an NPC.
    
    Args:
        npc_name: Name of the NPC
        npc_archetype: NPC archetype (merchant, guard, etc.)
        player_level: Player's current level
        quest_type: Force a specific quest type
        
    Returns:
        Generated quest or None
    """
    generator = QuestGenerator()
    
    npc_data = {}
    if npc_archetype:
        npc_data["archetype"] = npc_archetype
    
    player_state = {"level": player_level}
    
    qtype = QuestType(quest_type) if quest_type else None
    
    return generator.generate_quest(
        npc_name=npc_name,
        npc_data=npc_data,
        player_state=player_state,
        quest_type=qtype,
    )
