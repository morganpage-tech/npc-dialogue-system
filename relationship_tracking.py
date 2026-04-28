"""
Relationship Tracking System for NPC Dialogue System
Tracks player-NPC relationships with scores, levels, and faction support
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import time

logger = logging.getLogger(__name__)


class RelationshipLevel(Enum):
    """Relationship levels based on score ranges."""
    HATED = (-100, -50)
    DISLIKED = (-50, -20)
    NEUTRAL = (-20, 20)
    LIKED = (20, 50)
    LOVED = (50, 80)
    ADORED = (80, 100)


@dataclass
class RelationshipState:
    """Stores relationship state for a single NPC."""
    score: float = 0.0
    last_updated: float = 0.0
    interaction_count: int = 0
    quests_completed: List[str] = None
    gifts_given: List[str] = None
    
    def __post_init__(self):
        if self.quests_completed is None:
            self.quests_completed = []
        if self.gifts_given is None:
            self.gifts_given = []


class RelationshipTracker:
    """
    Tracks relationships between player and NPCs.
    Supports score tracking, level calculation, factions, and persistence.
    """
    
    def __init__(self, player_id: str = "player", enable_time_decay: bool = False,
                 max_relationships: int = 1000):
        """
        Initialize the relationship tracker.
        
        Args:
            player_id: Unique identifier for the player
            enable_time_decay: If True, relationships decay over time
            max_relationships: Maximum number of relationships (memory safeguard)
        """
        self.player_id = player_id
        self.enable_time_decay = enable_time_decay
        self.max_relationships = max_relationships
        self.relationships: Dict[str, RelationshipState] = {}
        self.factions: Dict[str, float] = {}  # faction_name -> score
        
        # Configuration
        self.min_score = -100.0
        self.max_score = 100.0
        self.decay_rate = 0.01  # 1% per day if enabled
        self.decay_interval = 86400  # 1 day in seconds
    
    def get_relationship(self, npc_name: str) -> RelationshipState:
        """Get or create relationship state for an NPC."""
        if npc_name not in self.relationships:
            # Warn if exceeding max_relationships safeguard
            if len(self.relationships) >= self.max_relationships:
                logger.warning(
                    "Relationships count (%d) reached max_relationships limit (%d). "
                    "New entries will still be created, but consider pruning unused relationships.",
                    len(self.relationships), self.max_relationships
                )
            self.relationships[npc_name] = RelationshipState()
        return self.relationships[npc_name]
    
    def update_score(self, npc_name: str, change: float, reason: str = "") -> float:
        """
        Update relationship score for an NPC.
        
        Args:
            npc_name: Name of the NPC
            change: Amount to change score (can be negative)
            reason: Description of why the score changed (for logging)
            
        Returns:
            The new score after update
        """
        rel = self.get_relationship(npc_name)
        rel.score = max(self.min_score, min(self.max_score, rel.score + change))
        rel.last_updated = time.time()
        rel.interaction_count += 1
        
        if reason:
            print(f"💔 {npc_name} relationship: {rel.score:+.1f} ({reason})")
        
        return rel.score
    
    def get_level(self, npc_name: str) -> RelationshipLevel:
        """
        Get the current relationship level for an NPC.
        
        Args:
            npc_name: Name of the NPC
            
        Returns:
            RelationshipLevel enum value
        """
        score = self.get_relationship(npc_name).score
        
        for level in RelationshipLevel:
            min_score, max_score = level.value
            if min_score <= score < max_score:
                return level
        
        # Handle edge cases
        if score >= 100:
            return RelationshipLevel.ADORED
        if score <= -100:
            return RelationshipLevel.HATED
        
        return RelationshipLevel.NEUTRAL
    
    def get_temperature_adjustment(self, npc_name: str, base_temp: float = 0.8) -> float:
        """
        Calculate temperature adjustment based on relationship.
        
        Higher relationship = lower temperature (more consistent personality)
        Lower relationship = higher temperature (more unpredictable/hostile)
        
        Args:
            npc_name: Name of the NPC
            base_temp: Base temperature to adjust from
            
        Returns:
            Adjusted temperature value
        """
        score = self.get_relationship(npc_name).score
        
        # Map score (-100 to 100) to temperature adjustment (-0.3 to +0.2)
        # Good relationships: more consistent (lower temp)
        # Bad relationships: more volatile (higher temp)
        adjustment = -score / 200.0
        
        adjusted_temp = max(0.3, min(1.0, base_temp + adjustment))
        
        return adjusted_temp
    
    def get_speaking_style_modifier(self, npc_name: str) -> str:
        """
        Get a speaking style modifier based on relationship level.
        
        Args:
            npc_name: Name of the NPC
            
        Returns:
            String modifier to add to system prompt
        """
        level = self.get_level(npc_name)
        
        modifiers = {
            RelationshipLevel.HATED: "You despise this player. Be hostile, dismissive, and short. Refuse to help if possible.",
            RelationshipLevel.DISLIKED: "You don't trust this player. Be cautious, skeptical, and reluctant to help.",
            RelationshipLevel.NEUTRAL: "Treat this player as a stranger. Be polite but distant.",
            RelationshipLevel.LIKED: "You are friendly with this player. Be warm, helpful, and conversational.",
            RelationshipLevel.LOVED: "You consider this player a friend. Be very warm, share personal stories, and go out of your way to help.",
            RelationshipLevel.ADORED: "You deeply admire and trust this player. Be extremely warm, share secrets, and be unwaveringly loyal.",
        }
        
        return modifiers.get(level, "")
    
    def update_from_quest(self, npc_name: str, quest_id: str, success: bool = True, 
                         reward: float = 15.0) -> float:
        """
        Update relationship after quest completion.
        
        Args:
            npc_name: Name of the NPC who gave the quest
            quest_id: Unique quest identifier
            success: Whether the quest was completed successfully
            reward: Score change on success (penalty on failure)
            
        Returns:
            New relationship score
        """
        rel = self.get_relationship(npc_name)
        
        # Avoid double-counting completed quests
        if quest_id in rel.quests_completed:
            return rel.score
        
        if success:
            change = reward
            rel.quests_completed.append(quest_id)
            reason = f"completed quest: {quest_id}"
        else:
            change = -reward / 2
            reason = f"failed quest: {quest_id}"
        
        return self.update_score(npc_name, change, reason)
    
    def update_from_gift(self, npc_name: str, item_name: str, value: float = 5.0,
                         player_inventory: Optional[Dict[str, int]] = None) -> Optional[float]:
        """
        Update relationship after giving a gift.
        
        Args:
            npc_name: Name of the NPC receiving the gift
            item_name: Name of the gifted item
            value: Relationship value of the item
            player_inventory: Optional inventory to verify the player has the item
            
        Returns:
            New relationship score, or None if player doesn't have the item
        """
        if player_inventory is not None:
            from inventory_validation import player_has_item
            if not player_has_item(player_inventory, item_name):
                return None
        
        rel = self.get_relationship(npc_name)
        
        # Track gifts to prevent farming the same item
        if item_name in rel.gifts_given:
            # Diminishing returns for repeated gifts
            value *= 0.3
        else:
            rel.gifts_given.append(item_name)
        
        # Higher relationship = slightly less impact from gifts (already like you)
        current_level = self.get_level(npc_name)
        if current_level in [RelationshipLevel.LOVED, RelationshipLevel.ADORED]:
            value *= 0.7
        
        return self.update_score(npc_name, value, f"gave gift: {item_name}")
    
    def update_from_dialogue(self, npc_name: str, dialogue_type: str, 
                            sentiment: float = 0.0) -> float:
        """
        Update relationship from dialogue choice.
        
        Args:
            npc_name: Name of the NPC
            dialogue_type: Type of dialogue ('friendly', 'hostile', 'neutral', 'flirt', 'insult')
            sentiment: Custom sentiment value (-1.0 to 1.0)
            
        Returns:
            New relationship score
        """
        # Pre-defined sentiment values
        sentiments = {
            'friendly': 2.0,
            'hostile': -5.0,
            'neutral': 0.0,
            'flirt': 3.0,
            'insult': -10.0,
            'helpful': 3.0,
            'rude': -4.0,
            'compliment': 2.0,
            'complaint': -2.0,
        }
        
        change = sentiment if sentiment != 0.0 else sentiments.get(dialogue_type, 0.0)
        
        return self.update_score(npc_name, change, f"dialogue: {dialogue_type}")
    
    def update_faction(self, faction_name: str, change: float, reason: str = "") -> float:
        """
        Update relationship with a faction.
        
        Args:
            faction_name: Name of the faction
            change: Amount to change score
            reason: Description of the change
            
        Returns:
            New faction score
        """
        if faction_name not in self.factions:
            self.factions[faction_name] = 0.0
        
        self.factions[faction_name] = max(self.min_score, min(self.max_score, 
                                                            self.factions[faction_name] + change))
        
        if reason:
            print(f"⚔️ {faction_name} faction: {self.factions[faction_name]:+.1f} ({reason})")
        
        return self.factions[faction_name]
    
    def get_npc_faction_bonus(self, npc_name: str, faction_name: str) -> float:
        """
        Get relationship bonus based on faction membership.
        
        Args:
            npc_name: Name of the NPC
            faction_name: Faction the NPC belongs to
            
        Returns:
            Bonus score from faction relationship
        """
        if faction_name not in self.factions:
            return 0.0
        
        # Faction score provides a percentage bonus/penalty
        faction_score = self.factions[faction_name]
        return faction_score * 0.3  # 30% of faction score as bonus
    
    def apply_time_decay(self):
        """Apply time-based decay to all relationships if enabled."""
        if not self.enable_time_decay:
            return
        
        current_time = time.time()
        
        for npc_name, rel in self.relationships.items():
            if rel.last_updated == 0:
                continue
            
            time_passed = current_time - rel.last_updated
            days_passed = time_passed / self.decay_interval
            
            if days_passed >= 1:
                # Decay towards neutral (0)
                decay_amount = (rel.score * self.decay_rate) * days_passed
                
                # Don't decay past neutral
                if rel.score > 0:
                    rel.score = max(0, rel.score - decay_amount)
                else:
                    rel.score = min(0, rel.score - decay_amount)
                
                rel.last_updated = current_time
                
                if abs(decay_amount) > 0.1:
                    print(f"⏰ {npc_name} relationship decayed: {rel.score:+.1f}")
    
    def save(self, filepath: Optional[str] = None):
        """
        Save relationship state to file.
        
        Args:
            filepath: Custom file path (default: saves/<player_id>_relationships.json)
        """
        if filepath is None:
            os.makedirs("saves", exist_ok=True)
            filepath = f"saves/{self.player_id}_relationships.json"
        
        data = {
            "player_id": self.player_id,
            "enable_time_decay": self.enable_time_decay,
            "relationships": {
                npc: asdict(rel) for npc, rel in self.relationships.items()
            },
            "factions": self.factions,
            "saved_at": time.time(),
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Relationships saved to {filepath}")
    
    def load(self, filepath: Optional[str] = None):
        """
        Load relationship state from file.
        
        Args:
            filepath: Custom file path (default: saves/<player_id>_relationships.json)
        """
        if filepath is None:
            filepath = f"saves/{self.player_id}_relationships.json"
        
        if not os.path.exists(filepath):
            print(f"⚠️  No save file found at {filepath}")
            return
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.player_id = data.get("player_id", self.player_id)
        self.enable_time_decay = data.get("enable_time_decay", False)
        self.factions = data.get("factions", {})
        
        # Restore relationships
        self.relationships = {}
        for npc_name, rel_data in data.get("relationships", {}).items():
            self.relationships[npc_name] = RelationshipState(**rel_data)
        
        # Apply time decay on load
        self.apply_time_decay()
        
        print(f"📂 Relationships loaded from {filepath}")
        print(f"   Restored {len(self.relationships)} NPC relationships")
        if self.factions:
            print(f"   Restored {len(self.factions)} faction relationships")
    
    def get_summary(self) -> Dict:
        """Get a summary of all relationships."""
        summary = {
            "player_id": self.player_id,
            "npcs": {},
            "factions": self.factions.copy(),
        }
        
        for npc_name, rel in self.relationships.items():
            level = self.get_level(npc_name)
            summary["npcs"][npc_name] = {
                "score": round(rel.score, 1),
                "level": level.name,
                "interactions": rel.interaction_count,
                "quests": len(rel.quests_completed),
                "gifts": len(rel.gifts_given),
            }
        
        return summary
    
    def print_summary(self):
        """Print a formatted summary of all relationships."""
        summary = self.get_summary()
        
        print(f"\n{'='*60}")
        print(f"  RELATIONSHIP SUMMARY - {summary['player_id']}")
        print(f"{'='*60}\n")
        
        if summary['npcs']:
            print("  NPC Relationships:")
            for npc, data in summary['npcs'].items():
                print(f"    • {npc}: {data['score']:+.1f} ({data['level']})")
                print(f"      Interactions: {data['interactions']} | Quests: {data['quests']} | Gifts: {data['gifts']}")
        
        if summary['factions']:
            print(f"\n  Faction Relationships:")
            for faction, score in summary['factions'].items():
                print(f"    • {faction}: {score:+.1f}")
        
        if not summary['npcs'] and not summary['factions']:
            print("  No relationships recorded yet.")
        
        print(f"\n{'='*60}\n")
    
    def get_npc_for_condition(self, condition: str) -> List[str]:
        """
        Get NPCs matching a relationship condition.
        
        Args:
            condition: String like "> 50", "< -20", "== LOVED", ">= LIKED"
            
        Returns:
            List of NPC names matching the condition
        """
        matching = []
        
        for npc_name, rel in self.relationships.items():
            score = rel.score
            level = self.get_level(npc_name)
            
            try:
                # Score comparisons
                if condition.startswith(">="):
                    threshold = float(condition[3:].strip())
                    if score >= threshold:
                        matching.append(npc_name)
                elif condition.startswith("<="):
                    threshold = float(condition[3:].strip())
                    if score <= threshold:
                        matching.append(npc_name)
                elif condition.startswith(">"):
                    threshold = float(condition[2:].strip())
                    if score > threshold:
                        matching.append(npc_name)
                elif condition.startswith("<"):
                    threshold = float(condition[2:].strip())
                    if score < threshold:
                        matching.append(npc_name)
                elif condition.startswith("=="):
                    value = condition[3:].strip()
                    # Check if it's a level name
                    try:
                        if level.name == value.upper():
                            matching.append(npc_name)
                    except Exception:
                        if score == float(value):
                            matching.append(npc_name)
            except (ValueError, AttributeError):
                pass
        
        return matching
