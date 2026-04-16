"""
Tests for inventory_validation module.
Tests item extraction from player text, inventory matching, and validation logic.
"""

import unittest
from inventory_validation import extract_mentioned_items, player_has_item, validate_inventory_for_input


class TestExtractMentionedItems(unittest.TestCase):
    """Test extraction of item names from player give/offer phrases."""

    def test_simple_give(self):
        """Standard 'I give you' extraction."""
        result = extract_mentioned_items("I give you a sword")
        self.assertIn("sword", result)

    def test_give_you_informal(self):
        """Informal 'u' instead of 'you'."""
        result = extract_mentioned_items("I give u the gold")
        self.assertIn("gold", result)

    def test_give_ya(self):
        """Informal 'ya' instead of 'you'."""
        result = extract_mentioned_items("I give ya the gem")
        self.assertIn("gem", result)

    def test_will_give_future_tense(self):
        """Future tense 'I will give you'."""
        result = extract_mentioned_items("I will give you the crown")
        self.assertIn("crown", result)

    def test_heres_trigger(self):
        """'here's' trigger phrase."""
        result = extract_mentioned_items("here's a potion")
        self.assertIn("potion", result)

    def test_here_is_trigger(self):
        """'here is' trigger phrase."""
        result = extract_mentioned_items("here is the map")
        self.assertIn("map", result)

    def test_have_got_trigger(self):
        """'I have got you' trigger."""
        result = extract_mentioned_items("I have got you the scroll")
        self.assertIn("scroll", result)

    def test_got_you_trigger(self):
        """Short 'got you' trigger."""
        result = extract_mentioned_items("got you a gem")
        self.assertIn("gem", result)

    def test_ve_got_trigger(self):
        """Contracted 'I've got you' trigger."""
        result = extract_mentioned_items("I've got you an opal")
        self.assertIn("opal", result)

    def test_take_trigger(self):
        """'take this' trigger."""
        result = extract_mentioned_items("take this amulet")
        self.assertIn("amulet", result)

    def test_offer_trigger(self):
        """'I offer' trigger."""
        result = extract_mentioned_items("I offer the shield")
        self.assertIn("shield", result)

    def test_trade_trigger(self):
        """'trade you' trigger."""
        result = extract_mentioned_items("I trade you the ring")
        self.assertIn("ring", result)

    def test_hand_trigger(self):
        """'hand you' trigger."""
        result = extract_mentioned_items("I hand you the key")
        self.assertIn("key", result)

    def test_handing_trigger(self):
        """'handing you' trigger."""
        result = extract_mentioned_items("handing you the crystal")
        self.assertIn("crystal", result)

    def test_brought_trigger(self):
        """'I brought' trigger."""
        result = extract_mentioned_items("I brought the supplies")
        self.assertIn("supplies", result)

    def test_bring_trigger(self):
        """'bring you' trigger."""
        result = extract_mentioned_items("I bring you a staff")
        self.assertIn("staff", result)

    def test_accept_trigger(self):
        """'accept this' trigger."""
        result = extract_mentioned_items("accept this offering")
        self.assertIn("offering", result)

    def test_possess_trigger(self):
        """'I possess' trigger."""
        result = extract_mentioned_items("I possess the ancient tome")
        self.assertIn("ancient tome", result)

    def test_multiple_items_in_text(self):
        """Multiple triggers in one text extract all items."""
        result = extract_mentioned_items("I give you a sword. And here's a shield")
        self.assertIn("sword", result)
        self.assertIn("shield", result)

    def test_article_the_removed(self):
        """Article 'the' is stripped from extracted item."""
        result = extract_mentioned_items("I give you the dragon scale")
        self.assertIn("dragon scale", result)
        self.assertNotIn("the dragon scale", result)

    def test_article_a_removed(self):
        """Article 'a' is stripped from extracted item."""
        result = extract_mentioned_items("here's an ancient relic")
        self.assertIn("ancient relic", result)
        self.assertNotIn("an ancient relic", result)

    def test_this_that_removed(self):
        """Demonstratives 'this/that' are stripped."""
        result = extract_mentioned_items("take this magical orb")
        self.assertIn("magical orb", result)
        self.assertNotIn("this magical orb", result)

    def test_my_removed(self):
        """Possessive 'my' is stripped."""
        result = extract_mentioned_items("I give you my trusty sword")
        self.assertIn("trusty sword", result)
        self.assertNotIn("my trusty sword", result)

    def test_trailing_to_you_removed(self):
        """Trailing 'to you' is stripped from item name."""
        result = extract_mentioned_items("I give you a map to you")
        self.assertIn("map", result)

    def test_trailing_please_removed(self):
        """Trailing 'please' is stripped from item name."""
        result = extract_mentioned_items("take the sword please")
        self.assertIn("sword", result)

    def test_sentence_terminator_split(self):
        """Period splits — only items before the period are extracted."""
        result = extract_mentioned_items("I give you a sword. Can I have some gold?")
        self.assertIn("sword", result)
        self.assertNotIn("gold", result)

    def test_comma_delimiter(self):
        """Comma splits item from trailing text."""
        result = extract_mentioned_items("I give you a sword, my friend")
        self.assertIn("sword", result)

    def test_empty_input(self):
        """Empty input returns no items."""
        self.assertEqual(extract_mentioned_items(""), [])

    def test_no_trigger_match(self):
        """Normal conversation with no give/offer returns nothing."""
        self.assertEqual(extract_mentioned_items("Hello there, how are you?"), [])

    def test_deduplication(self):
        """Same item mentioned twice is deduplicated."""
        result = extract_mentioned_items("I give you a sword and I give you a sword")
        self.assertEqual(result.count("sword"), 1)

    def test_case_insensitive(self):
        """Extraction is case-insensitive and lowercases results."""
        result = extract_mentioned_items("I GIVE YOU A SWORD")
        self.assertIn("sword", result)

    def test_multi_word_item(self):
        """Multi-word items are extracted as a unit."""
        result = extract_mentioned_items("I give you the starlight opal")
        self.assertIn("starlight opal", result)

    def test_trigger_at_end_of_string(self):
        """Trigger at end with no item after it returns nothing."""
        result = extract_mentioned_items("I will give you")
        self.assertEqual(result, [])


class TestPlayerHasItem(unittest.TestCase):
    """Test fuzzy inventory matching logic."""

    def test_exact_match(self):
        """Exact item name match."""
        self.assertTrue(player_has_item({"sword": 1}, "sword"))

    def test_case_insensitive_match(self):
        """Match is case-insensitive."""
        self.assertTrue(player_has_item({"Iron Sword": 1}, "iron sword"))

    def test_qty_zero_is_absent(self):
        """Quantity zero means the player doesn't have it."""
        self.assertFalse(player_has_item({"sword": 0}, "sword"))

    def test_qty_negative_is_absent(self):
        """Negative quantity means the player doesn't have it."""
        self.assertFalse(player_has_item({"sword": -1}, "sword"))

    def test_qty_positive_is_present(self):
        """Positive quantity means the player has it."""
        self.assertTrue(player_has_item({"sword": 3}, "sword"))

    def test_item_is_substring_of_inventory(self):
        """Short item name found as substring of inventory item."""
        self.assertTrue(player_has_item({"iron sword": 1}, "sword"))

    def test_inventory_is_substring_of_item(self):
        """Inventory item found as substring of queried item name."""
        self.assertTrue(player_has_item({"sword": 1}, "iron sword"))

    def test_short_item_no_substring(self):
        """Items shorter than 3 chars don't get substring matching."""
        self.assertFalse(player_has_item({"xabc": 1}, "ab"))

    def test_three_char_substring_enabled(self):
        """Items exactly 3 chars do get substring matching."""
        self.assertTrue(player_has_item({"xabcx": 1}, "abc"))

    def test_empty_item_name_returns_true(self):
        """Empty item name is treated as a pass (no item to verify)."""
        self.assertTrue(player_has_item({"sword": 1}, ""))

    def test_whitespace_item_name_returns_true(self):
        """Whitespace-only item name strips to empty and passes."""
        self.assertTrue(player_has_item({"sword": 1}, "  "))

    def test_empty_inventory_returns_false(self):
        """Empty inventory means item not found."""
        self.assertFalse(player_has_item({}, "sword"))

    def test_no_match_at_all(self):
        """Completely unrelated item returns False."""
        self.assertFalse(player_has_item({"shield": 1}, "sword"))

    def test_multiple_items_one_matches(self):
        """Returns True if any inventory item matches."""
        self.assertTrue(player_has_item({"shield": 1, "sword": 2}, "sword"))


class TestValidateInventoryForInput(unittest.TestCase):
    """Test the full validation pipeline: extract + check."""

    def test_valid_offer_player_has_item(self):
        """Player offers item they possess — valid."""
        valid, missing = validate_inventory_for_input(
            "I give you a sword", {"sword": 1}
        )
        self.assertTrue(valid)
        self.assertEqual(missing, [])

    def test_invalid_offer_player_lacks_item(self):
        """Player offers item they don't have — invalid."""
        valid, missing = validate_inventory_for_input(
            "I give you a dragon", {"sword": 1}
        )
        self.assertFalse(valid)
        self.assertIn("dragon", missing)

    def test_mixed_some_have_some_dont(self):
        """Player offers two items, only has one."""
        valid, missing = validate_inventory_for_input(
            "I give you a sword and I give you a dragon", {"sword": 1}
        )
        self.assertFalse(valid)
        self.assertIn("dragon", missing)
        self.assertNotIn("sword", missing)

    def test_no_offers_always_valid(self):
        """Normal conversation with no offers is always valid."""
        valid, missing = validate_inventory_for_input(
            "Hello there!", {"sword": 1}
        )
        self.assertTrue(valid)
        self.assertEqual(missing, [])

    def test_empty_inventory_any_offer_invalid(self):
        """Empty inventory means any offer is invalid."""
        valid, missing = validate_inventory_for_input(
            "I give you a sword", {}
        )
        self.assertFalse(valid)
        self.assertIn("sword", missing)

    def test_empty_input_valid(self):
        """Empty input is always valid."""
        valid, missing = validate_inventory_for_input("", {"sword": 1})
        self.assertTrue(valid)
        self.assertEqual(missing, [])

    def test_multiple_missing_items(self):
        """Multiple offered items all missing."""
        valid, missing = validate_inventory_for_input(
            "I give you a sword. And here's a dragon", {}
        )
        self.assertFalse(valid)
        self.assertIn("sword", missing)
        self.assertIn("dragon", missing)

    def test_fuzzy_match_validates(self):
        """Fuzzy substring match counts as having the item."""
        valid, missing = validate_inventory_for_input(
            "I give you an opal", {"starlight opal": 1}
        )
        self.assertTrue(valid)

    def test_qty_zero_means_missing(self):
        """Item with qty 0 is treated as missing."""
        valid, missing = validate_inventory_for_input(
            "I give you a sword", {"sword": 0}
        )
        self.assertFalse(valid)
        self.assertIn("sword", missing)


if __name__ == "__main__":
    unittest.main(verbosity=2)
