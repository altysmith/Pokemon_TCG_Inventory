import unittest

from card_scanner.lookup import CardInfo, lookup_candidates
from card_scanner.parser import CodeCandidate, NumberCandidate


def card(code: str, number: str, total: str = "") -> CardInfo:
    return CardInfo(
        set_code=code,
        set_name=f"{code} set",
        card_name=f"{code} card {number}",
        card_number=number,
        set_id=code.lower(),
        source="test catalog",
        printed_total=total,
    )


class LookupTests(unittest.TestCase):
    def test_total_conflict_preserves_identity_but_requires_review(self) -> None:
        codes = (CodeCandidate("PRE", 4),)
        numbers = (NumberCandidate("11", 3, totals=("4",)),)

        result = lookup_candidates(
            codes,
            numbers,
            validator=lambda code, number: card(code, number, "131"),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual((result.set_code, result.card_number), ("PRE", "11"))
        self.assertIn("printed total conflicts with catalog", result.review_reasons)

    def test_total_is_not_required_for_a_strong_identity(self) -> None:
        result = lookup_candidates(
            (CodeCandidate("ASC", 4),),
            (NumberCandidate("162", 3),),
            validator=lambda code, number: card(code, number, "217"),
        )

        self.assertEqual(result.status, "accepted")
        self.assertEqual((result.set_code, result.card_number), ("ASC", "162"))

    def test_close_valid_combinations_require_review(self) -> None:
        codes = (CodeCandidate("PRE", 4),)
        numbers = (NumberCandidate("11", 3), NumberCandidate("4", 2))

        result = lookup_candidates(
            codes,
            numbers,
            validator=lambda code, number: card(code, number, "131"),
        )

        self.assertEqual(result.status, "review")
        self.assertEqual(len(result.alternatives), 2)

    def test_weak_single_match_requires_review(self) -> None:
        result = lookup_candidates(
            (CodeCandidate("MEP", 1),),
            (NumberCandidate("69", 1),),
            validator=lambda code, number: card(code, number),
        )

        self.assertEqual(result.status, "review")

    def test_promo_right_side_can_be_clear_winner(self) -> None:
        codes = (CodeCandidate("MEP", 1),)
        numbers = (
            NumberCandidate("9", 3, totals=("69",)),
            NumberCandidate("69", 2, right_side=True),
        )

        result = lookup_candidates(
            codes,
            numbers,
            validator=lambda code, number: card(code, number),
        )

        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.card_number, "69")

    def test_missing_number_is_no_match_without_validation(self) -> None:
        called = False

        def validator(code: str, number: str) -> CardInfo:
            nonlocal called
            called = True
            return card(code, number)

        result = lookup_candidates((CodeCandidate("MEG", 4),), (), validator=validator)

        self.assertEqual(result.status, "no_match")
        self.assertFalse(called)

    def test_candidate_validation_product_is_bounded(self) -> None:
        calls: list[tuple[str, str]] = []

        def validator(code: str, number: str) -> CardInfo:
            calls.append((code, number))
            return CardInfo()

        codes = tuple(
            CodeCandidate(code, 1)
            for code in ("ASC", "MEG", "PRE", "PAL")
        )
        numbers = tuple(NumberCandidate(str(value), 1) for value in range(1, 8))

        lookup_candidates(codes, numbers, validator=validator)

        self.assertLessEqual(len(calls), 15)


if __name__ == "__main__":
    unittest.main()
