"""Read-only Limitless/PTCGL deck-list comparison against local inventory."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from inventory import InventoryDatabase


HEADING_RE = re.compile(
    r"^(pok[eé]mon|trainer|energy|total\s+cards?)\s*:?\s*\d*\s*$", re.IGNORECASE
)
PRINTED_LINE_RE = re.compile(
    r"^(?P<quantity>\d+)\s+(?P<name>.+?)\s+(?P<set>[A-Za-z0-9-]{2,12})\s+(?P<number>\S*\d\S*)$"
)
NAME_LINE_RE = re.compile(r"^(?P<quantity>\d+)\s+(?P<name>.+?)\s*$")
BASIC_ENERGY_TYPES = frozenset(
    {
        "grass",
        "fire",
        "water",
        "lightning",
        "psychic",
        "fighting",
        "darkness",
        "metal",
        "fairy",
    }
)
BASIC_ENERGY_SYMBOLS = {
    "grass": "G",
    "fire": "R",
    "water": "W",
    "lightning": "L",
    "psychic": "P",
    "fighting": "F",
    "darkness": "D",
    "metal": "M",
    "fairy": "Y",
}
BASIC_ENERGY_SYMBOL_RE = re.compile(r"^\{[DFGLMPRWY]\}$", re.IGNORECASE)


@dataclass
class DeckEntry:
    line: int
    quantity: int
    name: str
    set_code: str = ""
    number: str = ""
    section: str = ""


def _collector_key(value: str) -> str:
    cleaned = value.strip().upper()
    return str(int(cleaned)) if cleaned.isdigit() else cleaned.lstrip("0") or "0"


def _name_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _is_basic_energy_name(value: str) -> bool:
    """Recognize written and TCGL-symbol names for the nine Basic Energies."""
    name = _name_key(value)
    if name == "basic energy":
        return True
    explicitly_basic = name.startswith("basic ")
    if explicitly_basic:
        name = name.removeprefix("basic ").strip()
    if not name.endswith(" energy"):
        return False
    if explicitly_basic:
        return True
    energy_type = name.removesuffix(" energy").strip()
    return energy_type in BASIC_ENERGY_TYPES or bool(
        BASIC_ENERGY_SYMBOL_RE.fullmatch(energy_type)
    )


def _catalog_basic_energy_name(value: str) -> str:
    name = _name_key(value).removeprefix("basic ").removesuffix(" energy").strip()
    if BASIC_ENERGY_SYMBOL_RE.fullmatch(name):
        return f"Basic {name.upper()} Energy"
    symbol = BASIC_ENERGY_SYMBOLS.get(name)
    return f"Basic {{{symbol}}} Energy" if symbol else ""


def _catalog_symbol_energy_name(value: str) -> str:
    """Convert readable Limitless energy types to Malie's symbol notation."""
    name = " ".join(value.split())
    match = re.match(
        r"^(?P<prefix>.+?)\s+(?P<energy_type>Grass|Fire|Water|Lightning|Psychic|Fighting|Darkness|Metal|Fairy)\s+Energy$",
        name,
        re.IGNORECASE,
    )
    if not match:
        return ""
    prefix = match.group("prefix").strip()
    symbol = BASIC_ENERGY_SYMBOLS.get(match.group("energy_type").casefold())
    return f"{prefix} {{{symbol}}} Energy" if prefix and symbol else ""


def parse_deck_list(text: str) -> tuple[list[DeckEntry], list[dict]]:
    """Parse the copy-as-text format used by Limitless and PTCG Live."""
    entries: dict[tuple[str, str, str], DeckEntry] = {}
    errors: list[dict] = []
    current_section = ""
    for line_number, raw_line in enumerate(text.replace("\ufeff", "").splitlines(), 1):
        line = raw_line.strip()
        heading = HEADING_RE.match(line)
        if heading:
            heading_name = heading.group(1).casefold()
            current_section = (
                "pokemon"
                if heading_name in {"pokemon", "pokémon"}
                else "energy"
                if heading_name == "energy"
                else "trainer"
                if heading_name == "trainer"
                else current_section
            )
            continue
        if not line:
            continue
        match = PRINTED_LINE_RE.match(line)
        if match:
            quantity = int(match.group("quantity"))
            entry = DeckEntry(
                line=line_number,
                quantity=quantity,
                name=match.group("name").strip(),
                set_code=match.group("set").upper(),
                number=match.group("number").strip(),
                section=current_section,
            )
        else:
            match = NAME_LINE_RE.match(line)
            if not match:
                errors.append(
                    {"line": line_number, "text": raw_line, "message": "Could not read this line."}
                )
                continue
            quantity = int(match.group("quantity"))
            entry = DeckEntry(
                line=line_number,
                quantity=quantity,
                name=match.group("name").strip(),
                section=current_section,
            )
        if quantity < 1 or quantity > 60:
            errors.append(
                {
                    "line": line_number,
                    "text": raw_line,
                    "message": "Quantity must be between 1 and 60.",
                }
            )
            continue
        key = (_name_key(entry.name), entry.set_code, _collector_key(entry.number))
        if key in entries:
            entries[key].quantity += entry.quantity
        else:
            entries[key] = entry
    return list(entries.values()), errors


def _all_card_details(connection: sqlite3.Connection, card_ids: set[str]) -> dict[str, dict]:
    if not card_ids:
        return {}
    placeholders = ",".join("?" for _ in card_ids)
    rows = connection.execute(
        f"""
        SELECT c.id, c.name, c.card_type, COALESCE(c.card_subtype, '') AS card_subtype,
               c.number, c.hp, COALESCE(c.stage, '') AS stage,
               COALESCE(c.primary_image_url, '') AS image_url,
               s.name AS set_name, s.code AS set_code
        FROM cards c JOIN sets s ON s.id = c.set_id
        WHERE c.id IN ({placeholders})
        """,
        list(card_ids),
    ).fetchall()
    details = {str(row["id"]): dict(row) for row in rows}
    type_rows = connection.execute(
        f"SELECT card_id, position, type FROM card_types WHERE card_id IN ({placeholders}) "
        "ORDER BY card_id, position",
        list(card_ids),
    ).fetchall()
    text_rows = connection.execute(
        f"""
        SELECT card_id, position, kind, COALESCE(name, '') AS name,
               COALESCE(text, '') AS text, COALESCE(cost_json, '') AS cost_json,
               damage_amount, COALESCE(damage_suffix, '') AS damage_suffix
        FROM card_text_entries WHERE card_id IN ({placeholders})
        ORDER BY card_id, position
        """,
        list(card_ids),
    ).fetchall()
    types: dict[str, list[str]] = defaultdict(list)
    texts: dict[str, list[tuple]] = defaultdict(list)
    for row in type_rows:
        types[str(row["card_id"])].append(str(row["type"]))
    for row in text_rows:
        texts[str(row["card_id"])].append(
            (
                row["kind"], row["name"], row["text"], row["cost_json"],
                row["damage_amount"], row["damage_suffix"],
            )
        )
    for card_id, card in details.items():
        card["types"] = types[card_id]
        # Set, collector number, rarity, regulation mark, and artwork are deliberately
        # excluded: those are printing details, not gameplay identity.
        card["gameplay_key"] = json.dumps(
            (
                _name_key(card["name"]), card["hp"], card["stage"],
                tuple(types[card_id]), tuple(texts[card_id]),
            ),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return details


def _printing_candidates(
    connection: sqlite3.Connection, entry: DeckEntry
) -> list[sqlite3.Row]:
    rows = connection.execute(
        """
        SELECT DISTINCT c.id, c.name, c.card_type, COALESCE(c.card_subtype, '') AS card_subtype,
               c.number, COALESCE(c.primary_image_url, '') AS image_url,
               s.name AS set_name, s.code AS set_code
        FROM cards c
        JOIN sets s ON s.id = c.set_id
        JOIN set_codes sc ON sc.set_id = s.id
        WHERE c.language = 'en-US' AND sc.code = ? COLLATE NOCASE
              AND c.name = ? COLLATE NOCASE
        """,
        (entry.set_code, entry.name),
    ).fetchall()
    number_key = _collector_key(entry.number)
    return [row for row in rows if _collector_key(str(row["number"])) == number_key]


def _name_candidates(connection: sqlite3.Connection, entry: DeckEntry) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT c.id, c.name, c.card_type, COALESCE(c.card_subtype, '') AS card_subtype,
               c.number, COALESCE(c.primary_image_url, '') AS image_url,
               s.name AS set_name, s.code AS set_code
        FROM cards c JOIN sets s ON s.id = c.set_id
        WHERE c.language = 'en-US' AND c.name = ? COLLATE NOCASE
        ORDER BY CASE WHEN c.card_type = 'POKEMON' THEN 1 ELSE 0 END,
                 s.release_date DESC, c.number_numeric
        """,
        (entry.name,),
    ).fetchall()


def _display_category(card: dict) -> str:
    if card["card_type"] == "POKEMON":
        return "Pokémon"
    if card["card_type"] == "ENERGY":
        return f"{card['card_subtype'].title()} Energy" if card["card_subtype"] else "Energy"
    return card["card_subtype"].title() if card["card_subtype"] else "Trainer"


def check_deck_list(
    text: str, *, catalog_path: Path | str, inventory_path: Path | str
) -> dict:
    """Compare a pasted deck list to inventory without changing either database."""
    if not text.strip():
        raise ValueError("Paste a Limitless or Pokémon TCG Live deck list first.")
    catalog_path = Path(catalog_path)
    if not catalog_path.is_file():
        raise ValueError("Local card catalog is unavailable.")
    entries, errors = parse_deck_list(text)
    if not entries:
        raise ValueError("No card lines were found in that deck list.")

    holdings = {
        holding.card_id: holding.quantity
        for holding in InventoryDatabase(inventory_path).holdings()
    }
    remaining = dict(holdings)
    resolved: list[dict] = []
    with closing(sqlite3.connect(catalog_path)) as connection:
        connection.row_factory = sqlite3.Row
        requested_ids: set[str] = set()
        for entry in entries:
            exact = None
            if entry.set_code and entry.number:
                printing_candidates = _printing_candidates(connection, entry)
                printing = (
                    printing_candidates[0]
                    if len(printing_candidates) == 1
                    else None
                )
                if printing is not None and printing["card_type"] == "POKEMON":
                    # Pokémon must match the exact set and collector number.
                    exact = printing

            if exact is None:
                # Limitless includes a set and number for every line, but Trainer
                # cards and Special Energy are interchangeable by name.
                non_pokemon = [
                    row
                    for row in _name_candidates(connection, entry)
                    if row["card_type"] != "POKEMON"
                ]
                exact = non_pokemon[0] if non_pokemon else None
            if exact is None and _is_basic_energy_name(entry.name):
                catalog_name = _catalog_basic_energy_name(entry.name)
                if catalog_name:
                    alias_entry = DeckEntry(
                        line=entry.line,
                        quantity=entry.quantity,
                        name=catalog_name,
                        section=entry.section,
                    )
                    basic_energy = [
                        row
                        for row in _name_candidates(connection, alias_entry)
                        if row["card_type"] == "ENERGY"
                        and str(row["card_subtype"]).upper() == "BASIC"
                    ]
                    exact = basic_energy[0] if basic_energy else None
            if exact is None:
                catalog_name = _catalog_symbol_energy_name(entry.name)
                if catalog_name:
                    alias_entry = DeckEntry(
                        line=entry.line,
                        quantity=entry.quantity,
                        name=catalog_name,
                        section=entry.section,
                    )
                    special_energy = [
                        row
                        for row in _name_candidates(connection, alias_entry)
                        if row["card_type"] == "ENERGY"
                        and str(row["card_subtype"]).upper() == "SPECIAL"
                    ]
                    exact = special_energy[0] if special_energy else None
            requested_id = str(exact["id"]) if exact else ""
            if requested_id:
                requested_ids.add(requested_id)
            resolved.append(
                {
                    "entry": entry,
                    "requested_id": requested_id,
                    "candidate": dict(exact) if exact else None,
                    "fills": [],
                    "covered": 0,
                }
            )

        def is_basic_energy(item: dict) -> bool:
            card = item["candidate"]
            if card:
                return (
                    card["card_type"] == "ENERGY"
                    and str(card["card_subtype"]).upper() == "BASIC"
                )
            # Limitless and TCGL exports use several equivalent labels, including
            # "Fire Energy", "Basic Fire Energy", and "Basic {R} Energy".
            return _is_basic_energy_name(item["entry"].name)

        ignored_basic_energy = [item for item in resolved if is_basic_energy(item)]
        ignored_basic_energy_cards = sum(
            item["entry"].quantity for item in ignored_basic_energy
        )
        ignored_basic_energy_lines = len(ignored_basic_energy)
        resolved = [item for item in resolved if not is_basic_energy(item)]

        card_ids = set(holdings) | requested_ids
        details = _all_card_details(connection, card_ids)

        def allocate(item: dict, card_id: str, amount: int, match: str) -> int:
            take = min(amount, remaining.get(card_id, 0))
            if take <= 0:
                return 0
            remaining[card_id] -= take
            card = details[card_id]
            item["fills"].append(
                {
                    "card_id": card_id,
                    "name": card["name"],
                    "set_code": card["set_code"],
                    "set_name": card["set_name"],
                    "number": card["number"],
                    "quantity": take,
                    "image_url": card["image_url"],
                    "match": match,
                }
            )
            item["covered"] += take
            return take

        # Pokémon printings get first claim on their exact inventory copies.
        for item in resolved:
            card = item["candidate"]
            if card and card["card_type"] == "POKEMON":
                allocate(item, item["requested_id"], item["entry"].quantity, "exact printing")

        # Trainers and Energy share inventory by name, regardless of printing.
        for item in resolved:
            card = item["candidate"]
            if not card or card["card_type"] == "POKEMON":
                continue
            needed = item["entry"].quantity - item["covered"]
            target_name = card["name"]
            matching = [
                candidate for candidate in details.values()
                if candidate["card_type"] != "POKEMON"
                and _name_key(candidate["name"]) == _name_key(target_name)
            ]
            matching.sort(key=lambda value: (value["id"] != item["requested_id"], value["set_code"], value["number"]))
            for candidate in matching:
                needed -= allocate(item, candidate["id"], needed, "name match")
                if needed <= 0:
                    break

        # Only gameplay-identical Pokémon may fill a different artwork/printing.
        for item in resolved:
            card = item["candidate"]
            if not card or card["card_type"] != "POKEMON":
                continue
            needed = item["entry"].quantity - item["covered"]
            requested = details[item["requested_id"]]
            alternatives = [
                candidate for candidate in details.values()
                if candidate["card_type"] == "POKEMON"
                and candidate["id"] != item["requested_id"]
                and candidate["gameplay_key"] == requested["gameplay_key"]
            ]
            alternatives.sort(key=lambda value: (value["set_code"], value["number"]))
            for candidate in alternatives:
                needed -= allocate(item, candidate["id"], needed, "alternate artwork")
                if needed <= 0:
                    break

        # A same-name Pokémon with different card text is not an exact deck-list
        # match, but it can still be useful as an intentional/manual substitute.
        # Reserve suggestions separately so one owned copy is not advertised twice.
        suggestion_remaining = dict(remaining)
        for item in resolved:
            item["possible_substitutes"] = []
            card = item["candidate"]
            needed = item["entry"].quantity - item["covered"]
            if not card or card["card_type"] != "POKEMON" or needed <= 0:
                continue
            requested = details[item["requested_id"]]
            alternatives = [
                candidate for candidate in details.values()
                if candidate["card_type"] == "POKEMON"
                and _name_key(candidate["name"]) == _name_key(requested["name"])
                and candidate["gameplay_key"] != requested["gameplay_key"]
                and suggestion_remaining.get(candidate["id"], 0) > 0
            ]
            alternatives.sort(
                key=lambda value: (
                    -suggestion_remaining.get(value["id"], 0),
                    value["set_code"],
                    value["number"],
                )
            )
            for candidate in alternatives:
                take = min(needed, suggestion_remaining[candidate["id"]])
                if take <= 0:
                    continue
                suggestion_remaining[candidate["id"]] -= take
                needed -= take
                item["possible_substitutes"].append(
                    {
                        "card_id": candidate["id"],
                        "name": candidate["name"],
                        "set_code": candidate["set_code"],
                        "set_name": candidate["set_name"],
                        "number": candidate["number"],
                        "quantity": take,
                        "image_url": candidate["image_url"],
                        "reason": "same name, different card text",
                    }
                )
                if needed <= 0:
                    break

    items: list[dict] = []
    for item in resolved:
        entry: DeckEntry = item["entry"]
        card = item["candidate"]
        missing = entry.quantity - item["covered"]
        unresolved = card is None
        if unresolved:
            errors.append(
                {
                    "line": entry.line,
                    "text": f"{entry.quantity} {entry.name} {entry.set_code} {entry.number}".strip(),
                    "message": (
                        "Could not find that exact Pokémon printing in the local catalog."
                        if entry.set_code and entry.number
                        else "Pokémon entries require a set code and collector number."
                    ),
                }
            )
        items.append(
            {
                "name": entry.name,
                "set_code": entry.set_code,
                "number": entry.number,
                "category": _display_category(card) if card else "Unresolved",
                "deck_section": (
                    "pokemon"
                    if card and card["card_type"] == "POKEMON"
                    else "energy"
                    if card and card["card_type"] == "ENERGY"
                    else "trainer"
                    if card
                    else entry.section or "trainer"
                ),
                "requested": entry.quantity,
                "covered": item["covered"],
                "missing": missing,
                "status": "unresolved" if unresolved else ("ready" if missing == 0 else "needed"),
                "image_url": card["image_url"] if card else "",
                "fills": item["fills"],
                "possible_substitutes": item["possible_substitutes"],
            }
        )
    checked_cards = sum(item["requested"] for item in items)
    total_cards = checked_cards + ignored_basic_energy_cards
    covered_cards = sum(item["covered"] for item in items)
    substitute_cards = sum(
        substitute["quantity"]
        for item in items
        for substitute in item["possible_substitutes"]
    )
    return {
        "items": items,
        "ignored_basic_energy": [
            {
                "name": item["entry"].name,
                "set_code": item["entry"].set_code,
                "number": item["entry"].number,
                "category": "Basic Energy",
                "deck_section": "energy",
                "requested": item["entry"].quantity,
                "covered": 0,
                "missing": 0,
                "status": "ignored",
                "image_url": (
                    item["candidate"]["image_url"] if item["candidate"] else ""
                ),
            }
            for item in ignored_basic_energy
        ],
        "errors": sorted(errors, key=lambda error: error["line"]),
        "summary": {
            "deck_cards": total_cards,
            "checked_cards": checked_cards,
            "covered_cards": covered_cards,
            "missing_cards": checked_cards - covered_cards,
            "possible_substitute_cards": substitute_cards,
            "ignored_basic_energy_cards": ignored_basic_energy_cards,
            "ignored_basic_energy_lines": ignored_basic_energy_lines,
            "unique_lines": len(items) + ignored_basic_energy_lines,
            "complete": covered_cards == checked_cards and not errors,
        },
        "read_only": True,
    }
