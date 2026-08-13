import unittest
from unittest.mock import patch

from PIL import Image

from card_scanner.ocr import LiteralReading, TextObservation, build_evidence, scan_crop


class OcrTests(unittest.TestCase):
    @patch("card_scanner.ocr._run_rapidocr")
    def test_zero_time_budget_stops_before_any_treatment(self, run_rapidocr) -> None:
        result = scan_crop(
            Image.new("RGB", (100, 20), "white"),
            derive_card_candidates=False,
            time_budget_seconds=0,
        )

        self.assertTrue(result.timed_out)
        self.assertEqual(result.treatments_attempted, ())
        run_rapidocr.assert_not_called()

    def test_correlated_passes_do_not_inflate_repetition_score(self) -> None:
        same_source, _ = build_evidence(
            (
                TextObservation("PREOH", "gray"),
                TextObservation("PREAW", "gray"),
            )
        )
        independent, _ = build_evidence(
            (
                TextObservation("PREOH", "gray"),
                TextObservation("PREAW", "green"),
            )
        )
        same_score = next(item.score for item in same_source if item.value == "PRE")
        independent_score = next(item.score for item in independent if item.value == "PRE")
        self.assertEqual((same_score, independent_score), (2, 4))

    @patch("card_scanner.ocr._run_rapidocr", return_value=())
    @patch("card_scanner.ocr.find_tesseract", return_value="tesseract")
    @patch(
        "card_scanner.ocr._run_tesseract",
        side_effect=["ASC unclear", "ASC unclear", "162/217", "162/217"],
    )
    @patch("card_scanner.ocr._variants")
    def test_combines_code_and_number_from_different_passes(
        self, variants, _run_tesseract, _find_tesseract, _run_rapidocr
    ) -> None:
        source = Image.new("RGB", (20, 10), "white")
        variants.return_value = [source.copy(), source.copy()]

        result = scan_crop(source)

        self.assertEqual(result.parsed.set_code, "ASC")
        self.assertIn(
            ("162", ("217",)),
            [(item.value, item.totals) for item in result.number_candidates],
        )
        self.assertEqual(result.raw_text, "ASC unclear | 162/217")

    @patch("card_scanner.ocr._run_rapidocr", return_value=())
    @patch("card_scanner.ocr.find_tesseract", return_value="tesseract")
    @patch(
        "card_scanner.ocr._run_tesseract",
        side_effect=["MEG 7104132", "MEG 7104132"],
    )
    @patch("card_scanner.ocr._variants")
    def test_retains_run_on_number_recovery_candidate(
        self, variants, _run_tesseract, _find_tesseract, _run_rapidocr
    ) -> None:
        source = Image.new("RGB", (20, 10), "white")
        variants.return_value = [source.copy()]

        result = scan_crop(source)

        self.assertIn("104", [item.value for item in result.number_candidates])
        self.assertIn("132", [item.value for item in result.number_candidates])

    @patch("card_scanner.ocr._variants", return_value=[])
    @patch("card_scanner.ocr.find_tesseract", return_value="tesseract")
    @patch(
        "card_scanner.ocr._run_rapidocr",
        side_effect=[
            (LiteralReading("ZXQ 987/654", 0.91),),
            (LiteralReading("ZXQ 987/654", 0.95),),
            (LiteralReading("ZXQ 987/654", 0.82),),
            (LiteralReading("ZXQ 987/654", 0.84),),
        ],
    )
    def test_primary_reader_returns_literal_unknown_text(
        self, _run_rapidocr, _find_tesseract, _variants
    ) -> None:
        source = Image.new("RGB", (100, 20), "white")

        result = scan_crop(source)

        self.assertEqual(result.raw_text, "ZXQ 987/654")
        self.assertEqual(result.ocr_engine, "RapidOCR")
        self.assertEqual(result.primary_confidence, 0.95)
        self.assertEqual(
            [reading.variant for reading in result.literal_readings],
            [
                "original",
                "enlarged_color",
                "enlarged_gray",
                "enlarged_gray_sharp",
            ],
        )
        self.assertEqual(
            [reading.confidence for reading in result.literal_readings],
            [0.91, 0.95, 0.82, 0.84],
        )

    @patch("card_scanner.ocr.build_evidence")
    @patch("card_scanner.ocr._variants")
    @patch(
        "card_scanner.ocr._run_rapidocr",
        return_value=(LiteralReading("ABC 001/999", 0.96),),
    )
    def test_ocr_only_mode_does_not_build_card_candidates(
        self, _run_rapidocr, variants, build_evidence
    ) -> None:
        source = Image.new("RGB", (100, 20), "white")

        result = scan_crop(source, derive_card_candidates=False)

        self.assertEqual(result.raw_text, "ABC 001/999")
        self.assertEqual(result.code_candidates, ())
        self.assertEqual(result.number_candidates, ())
        build_evidence.assert_not_called()
        variants.assert_not_called()

    @patch(
        "card_scanner.ocr._run_rapidocr",
        side_effect=[
            (LiteralReading("O PFL 113/094", 0.91),),
            (LiteralReading("unused", 0.99),),
        ],
    )
    def test_fast_mode_stops_after_complete_high_confidence_identifier(
        self, run_rapidocr
    ) -> None:
        result = scan_crop(
            Image.new("RGB", (100, 20), "white"),
            derive_card_candidates=False,
            early_stop_validator=lambda text: text == "O PFL 113/094",
        )

        self.assertEqual(result.raw_text, "O PFL 113/094")
        self.assertEqual(run_rapidocr.call_count, 1)
        self.assertEqual(len(result.literal_readings), 1)
        self.assertEqual(result.treatments_attempted, ("rapidocr:original",))

    @patch(
        "card_scanner.ocr._run_rapidocr",
        side_effect=[
            (LiteralReading("PELD113/094", 0.92),),
            (LiteralReading("PELE 113/094", 0.88),),
            (LiteralReading("O PFLa 113/094", 0.84),),
            (LiteralReading("O PFLa 113/094", 0.83),),
        ],
    )
    def test_fast_mode_keeps_fallbacks_when_set_code_is_missing(
        self, run_rapidocr
    ) -> None:
        result = scan_crop(
            Image.new("RGB", (100, 20), "white"),
            derive_card_candidates=False,
            early_stop_validator=lambda _text: False,
        )

        self.assertEqual(run_rapidocr.call_count, 4)
        self.assertEqual(len(result.literal_readings), 4)


if __name__ == "__main__":
    unittest.main()
