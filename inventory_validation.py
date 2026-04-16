"""
Inventory validation utilities for the NPC dialogue system.
Detects when a player claims to give/trade items they don't possess.
"""

import re
from typing import Dict, List, Tuple


GIVE_TRIGGER = re.compile(
    r"(?:i\s+(?:will\s+)?give\s+(?:you|u|ya)|"
    r"here'?s\s+(?:(?:the|a|an)\s+)?|"
    r"(?:i\s+)?(?:have\s+got|'?ve\s+got|got)\s+(?:you|u|ya)\s+(?:the\s+|a\s+|an\s+)?|"
    r"(?:i\s+)?(?:have|possess)\s+(?:(?:the|a|an)\s+)?|"
    r"(?:take|accept|here\s+is|here\s+are)\s+(?:(?:the|a|an)\s+)?|"
    r"(?:handing|hand|offer|brought|bring|trade)(?:\s+you)?\s+(?:(?:the|a|an)\s+)?)",
    re.IGNORECASE,
)


def extract_mentioned_items(text: str) -> List[str]:
    """Extract item names that the player claims to give/offer from their input text."""
    items = []
    
    for match in GIVE_TRIGGER.finditer(text):
        start = match.end()
        remainder = text[start:].strip()
        
        item = re.split(r"[.!?,;]", remainder)[0].strip()
        item = re.sub(r"^(?:the|a|an|this|that|these|those|my)\s+", "", item, flags=re.IGNORECASE).strip()
        item = re.sub(r"\s+(?:to you|for you|from me|please)$", "", item, flags=re.IGNORECASE).strip()
        item = re.sub(r"\s+(?:now|here|there|kindly|please)$", "", item, flags=re.IGNORECASE).strip()
        
        if item and 1 < len(item) <= 60:
            items.append(item.lower())
    
    return list(set(items))


def player_has_item(inventory: Dict[str, int], item_name: str) -> bool:
    """Check if the player has an item in their inventory (fuzzy match)."""
    item_lower = item_name.lower().strip()
    if not item_lower:
        return True
    
    for inv_item, qty in inventory.items():
        if qty <= 0:
            continue
        inv_lower = inv_item.lower().strip()
        if item_lower == inv_lower:
            return True
        if len(item_lower) >= 3 and (item_lower in inv_lower or inv_lower in item_lower):
            return True
    
    return False


def validate_inventory_for_input(
    player_input: str,
    player_inventory: Dict[str, int],
) -> Tuple[bool, List[str]]:
    """
    Validate that the player actually possesses any items they claim to give.
    
    Returns:
        Tuple of (is_valid, list_of_missing_items)
    """
    mentioned = extract_mentioned_items(player_input)
    missing = []
    for item in mentioned:
        if not player_has_item(player_inventory, item):
            missing.append(item)
    return (len(missing) == 0, missing)
