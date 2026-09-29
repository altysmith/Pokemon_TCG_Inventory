import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from app import extract_footer_fields, extract_literal_groups, save_benchmark_label


class AppTests(unittest.TestCase):
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
                "iteration": 5,
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
                        "iteration": 5,
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
        self.assertIn("fetch('/lookup'", javascript)
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
