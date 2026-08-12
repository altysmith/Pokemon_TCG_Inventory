"""Catalog validation and conservative ranking for OCR card candidates."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from typing import Callable

from .catalog import set_catalog
from .parser import CodeCandidate, NumberCandidate, normalize_card_number


API_ROOT = "https://api.pokemontcg.io/v2"
TCGDEX_ROOT = "https://api.tcgdex.net/v2/en"


@dataclass(frozen=True)
class CardAlternative:
    set_code: str
    card_number: str
    set_name: str
    card_name: str
    score: int


@dataclass(frozen=True)
class CardInfo:
    set_code: str = ""
    set_name: str = ""
    card_name: str = ""
    card_number: str = ""
    set_id: str = ""
    source: str = ""
    printed_total: str = ""
    score: int = 0
    status: str = "no_match"
    alternatives: tuple[CardAlternative, ...] = ()
    review_reasons: tuple[str, ...] = ()
    image_url: str = ""


def _get_json(path: str, params: dict[str, str], api_key: str = "") -> dict:
    url = f"{API_ROOT}/{path}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "TinyCardScanner/0.2"}
    if api_key:
        headers["X-Api-Key"] = api_key
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)


def _get_url_json(url: str) -> dict | list:
    request = urllib.request.Request(url, headers={"User-Agent": "TinyCardScanner/0.2"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)


def _number_identifiers(number: str) -> tuple[str, ...]:
    values = [number]
    if number.isdigit() and len(number) < 3:
        values.append(number.zfill(3))
    return tuple(dict.fromkeys(values))


def _lookup_tcgdex_exact(code: str, number: str) -> CardInfo:
    details = set_catalog().get(code, {})
    set_id = str(details.get("tcgdex_id", ""))
    if not set_id:
        return CardInfo()

    encoded_set = urllib.parse.quote(set_id, safe="")
    last_error: Exception | None = None
    for identifier in _number_identifiers(number):
        try:
            encoded_number = urllib.parse.quote(identifier, safe="")
            card = _get_url_json(f"{TCGDEX_ROOT}/sets/{encoded_set}/{encoded_number}")
            if not isinstance(card, dict) or not card.get("name"):
                continue
            set_data = card.get("set", {})
            return CardInfo(
                set_code=code,
                set_name=str(set_data.get("name", details.get("name", ""))),
                card_name=str(card.get("name", "")),
                card_number=normalize_card_number(str(card.get("localId", number))),
                set_id=str(set_data.get("id", set_id)),
                source="TCGdex API",
                printed_total=str(details.get("printed_total", "")),
                image_url=(
                    f"{card.get('image')}/high.webp" if card.get("image") else ""
                ),
            )
        except (OSError, KeyError, TypeError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
    if last_error:
        raise last_error
    return CardInfo()


def _lookup_pokemon_exact(code: str, number: str, api_key: str = "") -> CardInfo:
    sets_payload = _get_json(
        "sets",
        {
            "q": f"ptcgoCode:{code}",
            "pageSize": "20",
            "select": "id,name,ptcgoCode,printedTotal,total",
        },
        api_key,
    )
    sets = sets_payload.get("data", [])
    exact_set = next(
        (item for item in sets if str(item.get("ptcgoCode", "")).upper() == code),
        None,
    )
    if not exact_set:
        return CardInfo()

    for identifier in _number_identifiers(number):
        cards_payload = _get_json(
            "cards",
            {
                "q": f"set.id:{exact_set['id']} number:{identifier}",
                "pageSize": "20",
                "select": "id,name,number,set",
            },
            api_key,
        )
        cards = cards_payload.get("data", [])
        exact_card = next(
            (
                item
                for item in cards
                if normalize_card_number(str(item.get("number", ""))) == number
            ),
            None,
        )
        if exact_card:
            return CardInfo(
                set_code=code,
                set_name=str(exact_set.get("name", "")),
                card_name=str(exact_card.get("name", "")),
                card_number=number,
                set_id=str(exact_set.get("id", "")),
                source="Pokémon TCG API",
                printed_total=str(exact_set.get("printedTotal", "")),
                image_url=str(exact_card.get("images", {}).get("small", "")),
            )
    return CardInfo()


def _lookup_exact(code: str, number: str, api_key: str = "") -> CardInfo:
    try:
        current = _lookup_tcgdex_exact(code, number)
        if current.card_name:
            return current
    except (OSError, KeyError, TypeError, ValueError, urllib.error.URLError):
        pass
    try:
        return _lookup_pokemon_exact(code, number, api_key)
    except (OSError, KeyError, TypeError, ValueError, urllib.error.URLError):
        return CardInfo()


Validator = Callable[[str, str], CardInfo]


def lookup_candidates(
    code_candidates: tuple[CodeCandidate, ...],
    number_candidates: tuple[NumberCandidate, ...],
    api_key: str = "",
    validator: Validator | None = None,
) -> CardInfo:
    """Validate a small candidate product and accept only a clear winner."""
    catalog = set_catalog()
    codes = [item for item in code_candidates if item.value in catalog][:3]
    numbers = list(number_candidates[:5])
    if not codes or not numbers:
        return CardInfo(
            set_code=codes[0].value if codes else "",
            card_number=numbers[0].value if numbers else "",
            status="no_match",
        )

    validate = validator or (lambda code, number: _lookup_exact(code, number, api_key))
    matches: list[tuple[int, CardInfo, bool]] = []
    cache: dict[tuple[str, str], CardInfo] = {}
    for code_candidate in codes:
        details = catalog.get(code_candidate.value, {})
        expected_total = str(details.get("printed_total", ""))
        is_promo = bool(details.get("promo"))
        for number_candidate in numbers:
            key = (code_candidate.value, number_candidate.value)
            info = cache.setdefault(key, validate(*key))
            if not info.card_name:
                continue
            score = code_candidate.score + number_candidate.score + 5
            expected = info.printed_total or expected_total
            observed_totals = set(number_candidate.totals)
            conflicting_total = False
            if expected and expected != "0" and observed_totals:
                if expected in observed_totals:
                    score += 2
                    conflicting_total = any(
                        total != expected for total in observed_totals
                    )
                else:
                    score -= 2
                    conflicting_total = True
            if is_promo and number_candidate.right_side:
                score += 3
            elif number_candidate.right_side:
                # On a regular card the right side of a separator is normally
                # the set total, not the local card number.
                score -= 3
            matches.append((score, replace(info, score=score), conflicting_total))

    if not matches:
        return CardInfo(
            set_code=codes[0].value,
            card_number=numbers[0].value,
            status="no_match",
        )

    matches.sort(
        key=lambda item: (-item[0], item[1].set_code, int(item[1].card_number or 0))
    )
    alternatives = tuple(
        CardAlternative(
            info.set_code,
            info.card_number,
            info.set_name,
            info.card_name,
            score,
        )
        for score, info, _conflicting_total in matches[:3]
    )
    winner_score, winner, winner_has_conflicting_total = matches[0]
    runner_score = matches[1][0] if len(matches) > 1 else None
    clearly_supported = winner_score >= 10
    clearly_separated = runner_score is None or winner_score - runner_score >= 2
    review_reasons: list[str] = []
    if not clearly_supported:
        review_reasons.append("weak OCR support")
    if not clearly_separated:
        review_reasons.append("multiple close catalog matches")
    if winner_has_conflicting_total:
        review_reasons.append("printed total conflicts with catalog")
    status = "review" if review_reasons else "accepted"
    return replace(
        winner,
        status=status,
        alternatives=alternatives,
        review_reasons=tuple(review_reasons),
    )


def lookup_card(
    code: str,
    number: str,
    printed_total: str = "",
    api_key: str = "",
    number_candidates: tuple[tuple[str, str], ...] = (),
) -> CardInfo:
    """Backward-compatible wrapper around evidence-based lookup."""
    codes = (CodeCandidate(code.strip().upper(), 4, ("legacy",), ("literal",)),)
    numbers = [
        NumberCandidate(
            normalize_card_number(number),
            3,
            ("legacy",),
            (normalize_card_number(printed_total),) if printed_total else (),
        )
    ]
    for candidate_number, candidate_total in number_candidates:
        item = NumberCandidate(
            normalize_card_number(candidate_number),
            1,
            ("legacy",),
            (normalize_card_number(candidate_total),) if candidate_total else (),
        )
        if item.value and all(existing.value != item.value for existing in numbers):
            numbers.append(item)
    return lookup_candidates(codes, tuple(numbers), api_key)
