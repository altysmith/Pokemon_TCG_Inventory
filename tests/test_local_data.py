import tempfile
import unittest
from pathlib import Path

from card_scanner.local_data import ScannerData
from card_scanner.lookup import CardInfo


class ScannerDataTests(unittest.TestCase):
    def test_card_cache_is_owned_by_this_project_and_normalizes_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = ScannerData(Path(directory) / "scanner_data.sqlite3")
            data.cache_card(
                CardInfo(
                    set_code="SSP",
                    set_name="Surging Sparks",
                    card_name="Smoochum",
                    card_number="075",
                    set_id="sv08",
                    printed_total="191",
                    source="test API",
                    image_url="https://example.test/card.png",
                )
            )

            found = data.find_card("ssp", "75")

            self.assertEqual(found.card_name, "Smoochum")
            self.assertEqual((found.set_code, found.card_number), ("SSP", "75"))
            self.assertEqual(found.status, "accepted")
            self.assertEqual(found.image_url, "https://example.test/card.png")

    def test_unknown_card_is_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = ScannerData(Path(directory) / "scanner_data.sqlite3")
            self.assertFalse(data.find_card("SSP", "999").card_name)


if __name__ == "__main__":
    unittest.main()
