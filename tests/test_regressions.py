import csv
import unittest
from pathlib import Path

from card_scanner.lookup import CardInfo, lookup_candidates
from card_scanner.ocr import TextObservation, build_evidence


ROOT = Path(__file__).resolve().parents[1]
LABELED_SNAPSHOT_PATH = ROOT / "tests" / "fixtures" / "saved_scan_regressions.csv"


def catalog_card(code: str, number: str, total: str = "") -> CardInfo:
    return CardInfo(
        set_code=code,
        set_name=f"Set {code}",
        card_name=f"Card {number}",
        card_number=number,
        printed_total=total,
        source="regression catalog",
    )


class SavedScanRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # The live card_scans.csv is user output and changes on every scan. This
        # separate labeled snapshot tests only downstream parsing/decision logic;
        # it is never input to either OCR engine.
        with LABELED_SNAPSHOT_PATH.open(encoding="utf-8-sig", newline="") as source:
            cls.rows = list(csv.DictReader(source))

    def test_all_nine_saved_rows(self) -> None:
        valid = {
            ("ASC", "162"): catalog_card("ASC", "162", "217"),
            ("MEG", "104"): catalog_card("MEG", "104", "132"),
            ("PRE", "11"): catalog_card("PRE", "11", "131"),
            ("MEP", "9"): catalog_card("MEP", "9"),
            ("MEP", "69"): catalog_card("MEP", "69"),
            ("PAL", "172"): catalog_card("PAL", "172", "193"),
            ("DR", "51"): catalog_card("DR", "51", "101"),
            ("DRI", "51"): catalog_card("DRI", "51", "182"),
            ("POR", "76"): catalog_card("POR", "76", "88"),
            ("PRE", "86"): catalog_card("PRE", "86", "131"),
            ("PRE", "4"): catalog_card("PRE", "4", "131"),
        }

        self.assertEqual(len(self.rows), 9)
        for row in self.rows:
            pieces = [
                piece.strip()
                for piece in row["raw_ocr"].replace("\n", " | ").split("|")
                if piece.strip()
            ]
            observations = tuple(
                TextObservation(piece, f"saved_pass_{index}")
                for index, piece in enumerate(pieces)
            )
            codes, numbers = build_evidence(observations)
            result = lookup_candidates(
                codes,
                numbers,
                validator=lambda code, number: valid.get((code, number), CardInfo()),
            )
            expected = (row["correct_set_name"], row["correct_card_num"])
            with self.subTest(image=row["image_name"], expected=expected):
                if expected == ("MEG", "104"):
                    self.assertEqual(result.status, "no_match")
                elif expected == ("POR", "76"):
                    # Most passes read 088, but one reads 086. Preserve the
                    # correct validated identity while surfacing that conflict.
                    self.assertEqual((result.set_code, result.card_number), expected)
                    self.assertEqual(result.status, "review")
                else:
                    self.assertEqual((result.set_code, result.card_number), expected)
                    self.assertEqual(result.status, "accepted")


if __name__ == "__main__":
    unittest.main()
