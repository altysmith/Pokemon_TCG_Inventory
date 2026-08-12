import unittest

from card_scanner.lookup import CardInfo, lookup_candidates
from card_scanner.ocr import TextObservation, build_evidence


def validated(code: str, number: str) -> CardInfo:
    supported = {
        ("ASC", "162"),
        ("PRE", "11"),
        ("PRE", "4"),
        ("MEP", "9"),
        ("MEP", "69"),
        ("PAL", "172"),
        ("DRI", "51"),
        ("POR", "76"),
        ("PRE", "86"),
    }
    if (code, number) not in supported:
        return CardInfo()
    return CardInfo(
        set_code=code,
        set_name=f"{code} set",
        card_name=f"{code} card {number}",
        card_number=number,
        set_id=code.lower(),
        source="test catalog",
    )


def evidence(raw: str):
    pieces = tuple(piece.strip() for piece in raw.split("|") if piece.strip())
    return build_evidence(
        tuple(TextObservation(piece, f"csv_regression_{index}") for index, piece in enumerate(pieces))
    )


class CsvRegressionTests(unittest.TestCase):
    def test_asc_162(self) -> None:
        codes, numbers = evidence("162/217 | ASC W162/217")
        result = lookup_candidates(codes, numbers, validator=validated)
        self.assertEqual((result.status, result.set_code, result.card_number), ("accepted", "ASC", "162"))

    def test_meg_without_number_remains_no_match(self) -> None:
        codes, numbers = evidence("MED | MGE | MIG | MEG OVUEE | MEG")
        result = lookup_candidates(codes, numbers, validator=validated)
        self.assertEqual(result.status, "no_match")

    def test_pre_11_survives_wrong_total(self) -> None:
        codes, numbers = evidence("PRE 315 | PRE11 | 4")
        result = lookup_candidates(codes, numbers, validator=validated)
        self.assertEqual((result.status, result.set_code, result.card_number), ("accepted", "PRE", "11"))

    def test_mep_promo_uses_right_side_number(self) -> None:
        codes, numbers = evidence("W9/069 | NEP")
        result = lookup_candidates(codes, numbers, validator=validated)
        self.assertEqual((result.status, result.set_code, result.card_number), ("accepted", "MEP", "69"))

    def test_other_usable_rows(self) -> None:
        cases = (
            ("172/193 | PAL 172/193", "PAL", "172"),
            ("DR 051/182 | DRI | CTD051/182", "DRI", "51"),
            ("076/088 | POR 076/088 | POR", "POR", "76"),
            ("PREOH 086/131 | PREAW 086/131 | GID086/131 | PREOW 086/131", "PRE", "86"),
            ("PRE 004/131 | 004/131 | PRE", "PRE", "4"),
        )
        for raw, expected_code, expected_number in cases:
            with self.subTest(raw=raw):
                codes, numbers = evidence(raw)
                result = lookup_candidates(codes, numbers, validator=validated)
                self.assertEqual(
                    (result.status, result.set_code, result.card_number),
                    ("accepted", expected_code, expected_number),
                )


if __name__ == "__main__":
    unittest.main()
