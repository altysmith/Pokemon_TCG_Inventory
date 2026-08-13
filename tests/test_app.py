import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from app import (
    add_inventory_card,
    exact_catalog_fields,
    extract_footer_fields,
    extract_footer_fields_from_readings,
    extract_literal_groups,
    save_benchmark_label,
)
from card_scanner.ocr import LiteralReading
from card_scanner.lookup import CardInfo


class AppTests(unittest.TestCase):
    @patch("app.lookup_confirmed_fields")
    def test_inventory_add_revalidates_an_exact_match(self, lookup) -> None:
        lookup.return_value = CardInfo(
            card_id="malie:sv5:123",
            card_name="Raging Bolt ex",
            status="accepted",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "inventory.sqlite3"
            with patch.object(app, "INVENTORY_PATH", path):
                info, change = add_inventory_card(
                    {
                        "set_code": "TEF",
                        "card_number": "123",
                        "set_total": "162",
                        "scan_id": "scan-1",
                        "quantity": 8,
                    }
                )

        self.assertEqual(info.card_id, "malie:sv5:123")
        self.assertEqual((change.quantity, change.quantity_delta), (8, 8))

    @patch("app.lookup_confirmed_fields")
    def test_inventory_rejects_review_or_no_match(self, lookup) -> None:
        lookup.return_value = CardInfo(status="review")

        with self.assertRaisesRegex(ValueError, "exact local catalog match"):
            add_inventory_card({"set_code": "TEF", "card_number": "123"})

    @patch("app.lookup_confirmed_fields")
    def test_inventory_rejects_invalid_batch_quantity(self, lookup) -> None:
        lookup.return_value = CardInfo(
            card_id="malie:sv5:123",
            status="accepted",
        )

        for invalid in (0, 100, 1.5, "eight"):
            with self.subTest(quantity=invalid):
                with self.assertRaisesRegex(ValueError, "quantity"):
                    add_inventory_card(
                        {
                            "set_code": "TEF",
                            "card_number": "123",
                            "quantity": invalid,
                        }
                    )

    @patch("app.find_exact_card")
    def test_fast_path_requires_an_exact_catalog_match(self, find_card) -> None:
        find_card.return_value = type(
            "Result",
            (),
            {"status": "no_match", "card": None},
        )()
        self.assertIsNone(exact_catalog_fields("PLM 113/094"))

        find_card.return_value = type(
            "Result",
            (),
            {
                "status": "exact",
                "card": type("Card", (), {"printed_total": "094"})(),
            },
        )()
        self.assertEqual(
            exact_catalog_fields("O PFLM 113/094"),
            ("", "PFL", "113", "094"),
        )
        self.assertIsNone(exact_catalog_fields("O PFLM 113/999"))

    def test_literal_groups_preserve_unknown_letters_and_leading_zeroes(self) -> None:
        self.assertEqual(
            extract_literal_groups("ZXQ EN 001/999"),
            ("ZXQ", "001 / 999"),
        )

    def test_footer_groups_keep_regulation_and_set_but_ignore_language(self) -> None:
        self.assertEqual(
            extract_literal_groups("H SSP en 075/191"),
            ("H SSP", "075 / 191"),
        )
        self.assertEqual(
            extract_footer_fields("H SSP en 075/191"),
            ("H", "SSP", "075", "191"),
        )

    def test_only_exact_english_marker_is_ignored(self) -> None:
        self.assertEqual(
            extract_literal_groups("H ENA en 075/191"),
            ("H ENA", "075 / 191"),
        )

    def test_joined_language_marker_is_removed_from_known_set_code(self) -> None:
        self.assertEqual(
            extract_footer_fields("MEGEN 086/132"),
            ("", "MEG", "086", "132"),
        )

    def test_alternate_reading_recovers_set_code_without_rewriting_literal(self) -> None:
        fields = extract_footer_fields_from_readings(
            "PELD113/094",
            (
                LiteralReading("PELD113/094", 0.922, "enlarged_color"),
                LiteralReading("O PFLa 113/094", 0.846, "enlarged_gray"),
            ),
        )

        self.assertEqual(fields, ("", "PFL", "113", "094"))

    def test_attached_regulation_mark_and_language_noise_are_separated(self) -> None:
        self.assertEqual(
            extract_footer_fields("IDRIN 135/182"),
            ("I", "DRI", "135", "182"),
        )

    def test_benchmark_save_preserves_detected_and_corrected_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "ocr_reads_it5.csv"
            record = {
                "scanned_at": "2026-07-26T12:00:00-04:00",
                "iteration": 8,
                "scan_id": "scan-1",
                "image_name": "card.png",
                "crop_path": str(Path(temp_dir) / "scan-1.png"),
                "ocr_engine": "RapidOCR",
                "literal_text": "PBE 011/13I",
                "primary_confidence": "0.875000",
                "detected_letters": "PBE I",
                "detected_numbers": "011 / 13",
                "variant_readings_json": "[]",
            }
            with patch.object(app, "CSV_PATH", csv_path):
                with app.SCAN_RECORDS_LOCK:
                    app.SCAN_RECORDS["scan-1"] = record
                saved = save_benchmark_label(
                    {
                        "iteration": 8,
                        "scan_id": "scan-1",
                        "corrected_letters": "PRE",
                        "corrected_numbers": "011 / 131",
                    }
                )

            self.assertEqual(saved["was_corrected"], "yes")
            with csv_path.open("r", newline="", encoding="utf-8-sig") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(rows[0]["detected_letters"], "PBE I")
            self.assertEqual(rows[0]["corrected_letters"], "PRE")
            self.assertEqual(rows[0]["corrected_numbers"], "011 / 131")
            self.assertNotIn("scan-1", app.SCAN_RECORDS)

    def test_iteration_mismatch_cannot_save(self) -> None:
        with self.assertRaisesRegex(ValueError, "iteration mismatch"):
            save_benchmark_label(
                {
                    "iteration": 4,
                    "scan_id": "anything",
                    "corrected_letters": "PRE",
                    "corrected_numbers": "011 / 131",
                }
            )

    def test_webcam_ui_has_capture_and_cleanup_controls(self) -> None:
        html = (app.WEB_ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (app.WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="start_camera"', html)
        self.assertIn('id="capture_frame"', html)
        self.assertIn('id="next_card"', html)
        self.assertIn('id="stop_camera"', html)
        self.assertIn('id="reuse_selection"', html)
        self.assertIn('id="lookup_card"', html)
        self.assertIn('id="scan_timing"', html)
        self.assertIn('id="inventory_add_quantity"', html)
        self.assertIn("ITERATION 8", html)
        self.assertIn("BATCH INVENTORY QUANTITIES", html)
        self.assertIn("EDITABLE CORRECTIONS", html)
        self.assertIn("fetch('/lookup'", javascript)
        self.assertIn("await lookupCurrentCard()", javascript)
        self.assertIn("const UI_ITERATION = 8", javascript)
        self.assertIn("fetch('/inventory/add'", javascript)
        self.assertIn("fetch('/inventory/undo'", javascript)
        self.assertIn("lastLookupStatus !== 'accepted'", javascript)
        self.assertIn("if (!mediaStream || scanInProgress) return", javascript)
        self.assertIn("nextCardButton.disabled = true", javascript)
        self.assertIn("Exact visual match found. No corrections are needed", javascript)
        self.assertIn("lastLookupStatus === 'no_match'", javascript)
        self.assertIn("Preparing the OCR reader", Path(app.__file__).read_text(encoding="utf-8"))
        self.assertIn("nothing was added", javascript.lower())
        self.assertIn("ONLY OCR AREA", html)
        self.assertIn("navigator.mediaDevices.getUserMedia", javascript)
        self.assertIn("function fixedIdentifierSelection", javascript)
        self.assertIn("IDENTIFIER_GUIDE = {left: 0.06, top: 0.915, width: 0.26, height: 0.055}", javascript)
        self.assertIn("lockedSelectionNormalized = fixedIdentifierSelection", javascript)
        self.assertIn(
            "mediaStream.getTracks().forEach(track => track.stop())",
            javascript,
        )
        self.assertIn(
            "window.addEventListener('pagehide', stopMediaTracks)",
            javascript,
        )
        self.assertIn(
            "window.addEventListener('beforeunload', stopMediaTracks)",
            javascript,
        )


if __name__ == "__main__":
    unittest.main()
