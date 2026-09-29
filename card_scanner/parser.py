"""Extract structured evidence from noisy card-footer OCR text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ParsedCard:
    set_code: str = ""
    card_number: str = ""
    set_total: str = ""

    @property
    def is_complete(self) -> bool:
        # Card identity is code + local card number. The printed total is only
        # supporting evidence and is absent from many promo layouts.
        return bool(self.set_code and self.card_number)


@dataclass(frozen=True)
class CodeObservation:
    value: str
    weight: int
    kind: str
    token: str


@dataclass(frozen=True)
class NumberObservation:
    value: str
    weight: int
    kind: str
    total: str = ""
    side: str = "standalone"


@dataclass(frozen=True)
class CodeCandidate:
    value: str
    score: int
    sources: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class NumberCandidate:
    value: str
    score: int
    sources: tuple[str, ...] = ()
    totals: tuple[str, ...] = ()
    right_side: bool = False
    reasons: tuple[str, ...] = ()


_TOKEN_RE = re.compile(r"[A-Z]{2,}(?:-[A-Z]+)?")
_PAIR_RE = re.compile(
    r"(?<!\d)(\d(?:\s*\d){0,2})\s*(?P<sep>[/\\|Il4])\s*"
    r"(\d(?:\s*\d){0,3})(?!\d)"
)
_DIGIT_RE = re.compile(r"(?<!\d)\d{1,3}(?!\d)")
_LONG_DIGIT_RE = re.compile(r"(?<!\d)\d{4,9}(?!\d)")
_CODE_ADJACENT_NUMBER_RE = re.compile(r"[A-Z]{3,}\s*(0*\d{1,3})(?!\d)")


def normalize_ocr_text(text: str) -> str:
    text = text.upper().replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_card_number(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return str(int(digits)) if digits else ""


def _collector_digits(value: str, repair_trailing_duplicate: bool = False) -> str:
    digits = re.sub(r"\s+", "", value)
    if repair_trailing_duplicate and len(digits) == 4 and digits[-1] == digits[-2]:
        digits = digits[:-1]
    return normalize_card_number(digits) if len(digits) <= 3 else ""


def _distance_one(left: str, right: str) -> bool:
    return len(left) == len(right) and sum(a != b for a, b in zip(left, right)) == 1


def extract_code_observations(
    text: str, known_codes: Iterable[str]
) -> tuple[CodeObservation, ...]:
    """Return every catalog-constrained code interpretation in one OCR pass."""
    normalized = normalize_ocr_text(text)
    codes = frozenset(str(code).upper() for code in known_codes)
    observations: dict[tuple[str, str], CodeObservation] = {}

    for token in _TOKEN_RE.findall(normalized):
        if token == "EN":
            continue
        if token in codes:
            observations[(token, "exact")] = CodeObservation(token, 4, "exact", token)
        elif len(token) == 3:
            # Preserve a literal OCR observation even when it is not a known code;
            # catalog validation will prevent it from becoming a false identity.
            observations[(token, "literal")] = CodeObservation(token, 4, "literal", token)

        prefix_matches = (
            []
            if token in codes
            else [code for code in codes if len(code) >= 2 and token.startswith(code)]
        )
        if prefix_matches:
            longest = max(map(len, prefix_matches))
            for code in prefix_matches:
                if len(code) != longest:
                    continue
                suffix = token[len(code) :]
                kind = "exact_language_suffix" if suffix == "EN" else "catalog_prefix"
                weight = 4 if suffix == "EN" else 2
                observations[(code, kind)] = CodeObservation(code, weight, kind, token)

        if len(token) == 3 and token not in codes:
            fuzzy = [code for code in codes if _distance_one(token, code)]
            if len(fuzzy) == 1:
                code = fuzzy[0]
                observations[(code, "unique_correction")] = CodeObservation(
                    code, 1, "unique_correction", token
                )

    return tuple(observations.values())


def extract_number_observations(text: str) -> tuple[NumberObservation, ...]:
    """Extract card-number candidates independently from optional total evidence."""
    normalized = normalize_ocr_text(text)
    observations: dict[tuple[str, str, str], NumberObservation] = {}

    for match in _PAIR_RE.finditer(normalized):
        left = _collector_digits(match.group(1))
        right = _collector_digits(match.group(3), repair_trailing_duplicate=True)
        if not left or not right:
            continue
        exact_slash = match.group("sep") == "/"
        weight = 3 if exact_slash else 2
        kind = "slash_pair" if exact_slash else "slash_lookalike"
        observations[(left, right, "left")] = NumberObservation(
            left, weight, kind, total=right, side="left"
        )
        observations[(right, "", "right")] = NumberObservation(
            right, 2, "right_of_separator", side="right"
        )

    for match in _DIGIT_RE.finditer(normalized):
        value = normalize_card_number(match.group())
        if value:
            observations.setdefault(
                (value, "", "standalone"),
                NumberObservation(value, 1, "standalone"),
            )

    # OCR often removes the space between a set badge and collector number
    # (for example PRE11). Preserve that stronger relationship without deciding
    # which three-letter token is the real set code here.
    for match in _CODE_ADJACENT_NUMBER_RE.finditer(normalized):
        value = normalize_card_number(match.group(1))
        if value:
            observations[(value, "", "adjacent")] = NumberObservation(
                value, 3, "code_adjacent"
            )

    # When the slash disappears, retain useful windows from the resulting run.
    # Catalog validation, rather than this heuristic, decides which one is real.
    for match in _LONG_DIGIT_RE.finditer(normalized):
        run = match.group()
        for start in range(0, len(run) - 2):
            value = normalize_card_number(run[start : start + 3])
            if value:
                observations.setdefault(
                    (value, "", "run"),
                    NumberObservation(value, 1, "long_digit_run"),
                )

    return tuple(observations.values())


def parse_card_text(text: str) -> ParsedCard:
    """Compatibility parser for a single clean-ish OCR string."""
    normalized = normalize_ocr_text(text)
    code_match = re.search(r"(?<![A-Z])([A-Z]{3})(?:\s*EN)?(?![A-Z])", normalized)
    pairs = [item for item in extract_number_observations(normalized) if item.total]
    pair = max(pairs, key=lambda item: item.weight, default=None)
    return ParsedCard(
        set_code=code_match.group(1) if code_match else "",
        card_number=pair.value if pair else "",
        set_total=pair.total if pair else "",
    )
