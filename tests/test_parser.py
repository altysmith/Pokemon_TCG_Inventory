import unittest

from card_scanner.catalog import known_set_codes
from card_scanner.parser import (
    ParsedCard,
    extract_code_observations,
    extract_number_observations,
    parse_card_text,
)


class ParserTests(unittest.TestCase):
    def test_slash(self) -> None:
        result = parse_card_text("ASC 162/217")
        self.assertEqual((result.set_code, result.card_number, result.set_total), ("ASC", "162", "217"))

    def test_english_marker_is_ignored(self) -> None:
        result = parse_card_text("ASC EN 162/217")
        self.assertEqual((result.set_code, result.card_number, result.set_total), ("ASC", "162", "217"))

    def test_joined_english_marker_is_ignored(self) -> None:
        result = parse_card_text("ASCEN 162/217")
        self.assertEqual((result.set_code, result.card_number, result.set_total), ("ASC", "162", "217"))

    def test_messy_spacing(self) -> None:
        result = parse_card_text("  asc   7 / 91\n")
        self.assertEqual((result.set_code, result.card_number, result.set_total), ("ASC", "7", "91"))

    def test_dash_is_not_a_separator(self) -> None:
        result = parse_card_text("ASC 7-91")
        self.assertFalse(result.is_complete)

    def test_common_ocr_bar(self) -> None:
        result = parse_card_text("ABC 001|099")
        self.assertTrue(result.is_complete)

    def test_slash_read_as_four(self) -> None:
        result = parse_card_text("MEG 1044132")
        self.assertEqual((result.set_code, result.card_number, result.set_total), ("MEG", "104", "132"))

    def test_spaces_inserted_inside_printed_total(self) -> None:
        result = parse_card_text("ASC 162 /2 17")
        self.assertEqual((result.set_code, result.card_number, result.set_total), ("ASC", "162", "217"))

    def test_duplicate_final_digit_in_printed_total(self) -> None:
        result = parse_card_text("162/2 177")
        self.assertEqual((result.card_number, result.set_total), ("162", "217"))

    def test_unrepairable_four_digit_total_is_incomplete(self) -> None:
        result = parse_card_text("ASC 162/2178")
        self.assertFalse(result.is_complete)

    def test_incomplete_text(self) -> None:
        result = parse_card_text("ASC unclear")
        self.assertEqual(result.set_code, "ASC")
        self.assertFalse(result.is_complete)

    def test_total_is_not_required_for_identity(self) -> None:
        self.assertTrue(ParsedCard("MEP", "69", "").is_complete)

    def test_known_code_at_start_of_noisy_token(self) -> None:
        values = {
            item.value
            for item in extract_code_observations("PREOH 086/131", known_set_codes())
        }
        self.assertIn("PRE", values)

    def test_unique_catalog_correction_for_promo_code(self) -> None:
        values = {
            item.value for item in extract_code_observations("NEP", known_set_codes())
        }
        self.assertIn("MEP", values)

    def test_promo_right_side_is_an_independent_number(self) -> None:
        observations = extract_number_observations("W9/069")
        self.assertTrue(
            any(item.value == "69" and item.side == "right" for item in observations)
        )

    def test_leading_zero_standalone_number_is_normalized(self) -> None:
        values = {item.value for item in extract_number_observations("PRE 004")}
        self.assertIn("4", values)


if __name__ == "__main__":
    unittest.main()
