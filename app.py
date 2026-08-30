"""Local Pokémon collection, catalog search, and deck-checking application."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import importlib.util
import json
import os
import re
import threading
import uuid
import webbrowser
from dataclasses import asdict, replace
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from PIL import Image

from card_scanner.ocr import scan_crop
from card_scanner.catalog import known_set_codes
from card_api.catalog import find_exact_card, find_unique_card_by_partial_code
from card_api.config import DATABASE_PATH as CARD_CATALOG_PATH
from card_api.database import CatalogDatabase
from card_scanner.lookup import CardInfo
from collection_transfer import (
    build_collection_export,
    parse_collection_csv,
    parse_collection_json,
    render_collection_csv,
    render_collection_json,
)
from deck_checker import check_deck_list, parse_deck_list
from inventory import InventoryChange, InventoryDatabase, InventoryLocation, InventoryLocationChange
from saved_decks import SavedDeck, SavedDeckDatabase


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
LEGACY_SCANNER_WEB_ROOT = ROOT / "legacy_webcam_scanner" / "web"
CSV_PATH = Path(os.environ.get("OCR_BENCHMARK_CSV", ROOT / "ocr_reads_it18.csv"))
SCAN_PERFORMANCE_PATH = Path(
    os.environ.get(
        "SCAN_PERFORMANCE_CSV",
        ROOT / "scan_performance_it18.csv",
    )
)
CROP_DIR = Path(
    os.environ.get(
        "OCR_BENCHMARK_CROP_DIR",
        ROOT / "benchmark_crops" / "iteration_18",
    )
)
INVENTORY_PATH = Path(
    os.environ.get(
        "INVENTORY_DATABASE_PATH",
        ROOT / "user_data" / "inventory.sqlite3",
    )
)
DECK_LIBRARY_PATH = Path(
    os.environ.get(
        "DECK_LIBRARY_DATABASE_PATH",
        ROOT / "user_data" / "decks.sqlite3",
    )
)
MAX_REQUEST_BYTES = 30 * 1024 * 1024
ITERATION = 18
ITERATION_NAME = "Search-first collection intake"
SERVER_API_VERSION = 2
OCR_TIME_BUDGET_SECONDS = 10.0
LETTER_RE = re.compile(r"[A-Za-z]+")
NUMBER_RE = re.compile(r"\d+")
CURRENT_REGULATION_MARKS = frozenset("ABCDEFGHIJ")
CSV_COLUMNS = [
    "scanned_at",
    "iteration",
    "scan_id",
    "image_name",
    "crop_path",
    "ocr_engine",
    "literal_text",
    "primary_confidence",
    "client_total_seconds",
    "server_elapsed_seconds",
    "ocr_elapsed_seconds",
    "ocr_time_budget_seconds",
    "ocr_timed_out",
    "treatments_attempted_json",
    "detected_letters",
    "detected_numbers",
    "corrected_letters",
    "corrected_numbers",
    "was_corrected",
    "variant_readings_json",
]
SCAN_PERFORMANCE_COLUMNS = [
    "scanned_at",
    "iteration",
    "scan_id",
    "image_name",
    "crop_path",
    "ocr_engine",
    "literal_text",
    "primary_confidence",
    "client_total_seconds",
    "server_elapsed_seconds",
    "ocr_elapsed_seconds",
    "ocr_time_budget_seconds",
    "ocr_timed_out",
    "treatments_attempted_json",
    "variant_count",
    "regulation_mark",
    "set_code",
    "card_number",
    "set_total",
    "exact_catalog_identifier",
]
SCAN_RECORDS: dict[str, dict] = {}
SCAN_RECORDS_LOCK = threading.Lock()
SCAN_PERFORMANCE_LOCK = threading.Lock()


def extract_footer_fields(text: str) -> tuple[str, str, str, str]:
    """Read regulation, set, card number, and total by printed position.

    Exact known codes are preferred. The untouched OCR string remains separate,
    and any catalog-validated correction happens downstream. The exact ``en``
    language marker is ignored.
    """
    letter_tokens = [
        token.upper()
        for token in LETTER_RE.findall(text)
        if token.casefold() != "en"
    ]
    known_three_letter_codes = {code for code in known_set_codes() if len(code) == 3}
    set_index: int | None = None
    set_offset = 0
    set_code = ""
    for index, token in enumerate(letter_tokens):
        if (
            len(token) in (3, 4, 5)
            and token[:3] in known_three_letter_codes
        ):
            set_index = index
            set_code = token[:3]
            break
        matches = [
            (offset, token[offset : offset + 3])
            for offset in range(max(1, len(token) - 2))
            if token[offset : offset + 3] in known_three_letter_codes
            and len(token) - 3 <= 2
        ]
        if len(matches) == 1:
            set_index = index
            set_offset, set_code = matches[0]
            break
    if not set_code:
        literal_matches = [
            (index, token)
            for index, token in enumerate(letter_tokens)
            if len(token) == 3
        ]
        if len(literal_matches) == 1:
            set_index, set_code = literal_matches[0]

    regulation_mark = ""
    if set_index is not None:
        preceding = [
            token
            for token in letter_tokens[:set_index]
            if len(token) == 1 and token in CURRENT_REGULATION_MARKS
        ]
        regulation_mark = preceding[-1] if preceding else ""
        if (
            not regulation_mark
            and set_offset == 1
            and letter_tokens[set_index][0] in CURRENT_REGULATION_MARKS
        ):
            regulation_mark = letter_tokens[set_index][0]
    elif (
        letter_tokens
        and len(letter_tokens[0]) == 1
        and letter_tokens[0] in CURRENT_REGULATION_MARKS
    ):
        regulation_mark = letter_tokens[0]

    numbers = NUMBER_RE.findall(text)
    card_number = numbers[0] if numbers else ""
    set_total = numbers[1] if len(numbers) > 1 else ""
    return regulation_mark, set_code, card_number, set_total


def extract_footer_fields_from_readings(
    literal_text: str, readings: tuple,
) -> tuple[str, str, str, str]:
    """Use preserved OCR alternatives for fields without changing literal OCR."""
    candidates = [(literal_text, 1.0)]
    candidates.extend(
        (str(reading.text), float(reading.confidence))
        for reading in readings
        if str(reading.text).strip() and str(reading.text) != literal_text
    )
    parsed = [(extract_footer_fields(text), confidence) for text, confidence in candidates]

    def select(position: int) -> str:
        support: dict[str, tuple[int, float, int]] = {}
        for order, (fields, confidence) in enumerate(parsed):
            value = fields[position]
            if not value:
                continue
            count, best_confidence, first_order = support.get(
                value, (0, 0.0, order)
            )
            support[value] = (
                count + 1,
                max(best_confidence, confidence),
                min(first_order, order),
            )
        if not support:
            return ""
        return max(
            support,
            key=lambda value: (
                support[value][0],
                support[value][1],
                -support[value][2],
            ),
        )

    return tuple(select(position) for position in range(4))


def exact_catalog_fields(text: str) -> tuple[str, str, str, str] | None:
    """Return fields only when the literal reading identifies one local card."""
    fields = extract_footer_fields(text)
    regulation_mark, set_code, card_number, set_total = fields
    if not set_code or not card_number:
        if not card_number:
            return None
    else:
        result = find_exact_card(
            set_code,
            card_number,
            database_path=CARD_CATALOG_PATH,
        )
        if result.status == "exact" and result.card is not None and not (
            set_total
            and result.card.printed_total
            and set_total.lstrip("0") != result.card.printed_total.lstrip("0")
        ):
            return fields

    # Tiny white-on-dark badges commonly turn one set-code letter into another.
    # Keep the OCR literal untouched and try every one-letter interpretation,
    # accepting a repair only when code + number + printed total identify one card.
    tokens = [token.upper() for token in LETTER_RE.findall(text)]
    known_codes = {code for code in known_set_codes() if len(code) == 3}
    repaired_fields: set[tuple[str, str, str, str]] = set()
    for token in tokens:
        for offset in range(max(1, len(token) - 2)):
            window = token[offset : offset + 3]
            if len(window) != 3:
                continue
            for repaired_code in known_codes:
                if sum(a != b for a, b in zip(window, repaired_code)) != 1:
                    continue
                repaired = find_exact_card(
                    repaired_code,
                    card_number,
                    database_path=CARD_CATALOG_PATH,
                )
                if repaired.status != "exact" or repaired.card is None:
                    continue
                if (
                    set_total
                    and repaired.card.printed_total
                    and set_total.lstrip("0")
                    != repaired.card.printed_total.lstrip("0")
                ):
                    continue
                repaired_fields.add(
                    (regulation_mark, repaired_code, card_number, set_total)
                )
    if len(repaired_fields) == 1:
        return next(iter(repaired_fields))
    if repaired_fields:
        return None

    # Some inverse-color badges retain only their first letter (for example,
    # TEF -> T). This path requires both printed numbers and one unique local
    # card whose canonical set code starts with that retained token.
    if set_total:
        partial_matches: set[tuple[str, str, str, str]] = set()
        for token in tokens:
            if len(token) not in (1, 2) or token == regulation_mark:
                continue
            partial = find_unique_card_by_partial_code(
                token,
                card_number,
                set_total,
                database_path=CARD_CATALOG_PATH,
            )
            if partial.status == "exact" and partial.card is not None:
                partial_matches.add(
                    (regulation_mark, partial.card.set_code, card_number, set_total)
                )
        if len(partial_matches) == 1:
            return next(iter(partial_matches))
    return None


def exact_catalog_fields_from_readings(literal_text: str, readings: tuple) -> (
    tuple[str, str, str, str] | None
):
    """Accept one unique exact catalog identity across all retained OCR passes."""
    texts = {literal_text}
    texts.update(str(reading.text) for reading in readings if str(reading.text).strip())
    matches = {
        fields
        for text in texts
        if (fields := exact_catalog_fields(text)) is not None
    }
    return next(iter(matches)) if len(matches) == 1 else None


def extract_literal_groups(text: str) -> tuple[str, str]:
    """Separate the footer groups without catalog correction or zero removal.

    The printed ``en`` language marker is metadata, not part of the regulation
    mark or set code, so an exact standalone marker is intentionally omitted.
    The untouched OCR string remains stored separately as ``literal_text``.
    """
    regulation_mark, set_code, card_number, set_total = extract_footer_fields(text)
    return (
        " ".join(value for value in (regulation_mark, set_code) if value),
        " / ".join(value for value in (card_number, set_total) if value),
    )


def _append_csv(row: dict) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
    if not needs_header:
        with CSV_PATH.open("r", newline="", encoding="utf-8-sig") as source:
            existing_header = next(csv.reader(source), [])
        if existing_header != CSV_COLUMNS:
            raise ValueError(
                f"{CSV_PATH.name} has an incompatible header; move or rename it "
                "before saving new scan results."
            )
    with CSV_PATH.open("a", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
        if needs_header:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in CSV_COLUMNS})


def _append_scan_performance(row: dict) -> None:
    """Append one automatically recorded scan timing with a stable schema."""
    SCAN_PERFORMANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SCAN_PERFORMANCE_LOCK:
        needs_header = (
            not SCAN_PERFORMANCE_PATH.exists()
            or SCAN_PERFORMANCE_PATH.stat().st_size == 0
        )
        if not needs_header:
            with SCAN_PERFORMANCE_PATH.open(
                "r", newline="", encoding="utf-8-sig"
            ) as source:
                existing_header = next(csv.reader(source), [])
            if existing_header != SCAN_PERFORMANCE_COLUMNS:
                raise ValueError(
                    f"{SCAN_PERFORMANCE_PATH.name} has an incompatible header; "
                    "move or rename it before recording new scan timings."
                )
        with SCAN_PERFORMANCE_PATH.open(
            "a", newline="", encoding="utf-8-sig"
        ) as output:
            writer = csv.DictWriter(output, fieldnames=SCAN_PERFORMANCE_COLUMNS)
            if needs_header:
                writer.writeheader()
            writer.writerow(
                {column: row.get(column, "") for column in SCAN_PERFORMANCE_COLUMNS}
            )


def save_scan_performance(data: dict) -> dict:
    """Join browser total time to the retained server-side scan and log it once."""
    scan_id = str(data.get("scan_id", "")).strip()
    if not scan_id:
        raise ValueError("A scan ID is required to record performance.")
    try:
        client_total = float(data.get("client_total_seconds"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Client scan time must be a number.") from exc
    if client_total < 0 or client_total > 600:
        raise ValueError("Client scan time is outside the supported range.")
    with SCAN_RECORDS_LOCK:
        record = SCAN_RECORDS.get(scan_id)
        if record is None:
            raise ValueError("This scan is no longer active.")
        if record.get("performance_logged") == "yes":
            return record
        record["client_total_seconds"] = f"{client_total:.3f}"
        _append_scan_performance(record)
        record["performance_logged"] = "yes"
        return dict(record)


def save_benchmark_label(data: dict) -> dict:
    """Join user corrections to the exact server-side OCR result and save once."""
    if int(data.get("iteration", 0)) != ITERATION:
        raise ValueError(
            f"Browser/server iteration mismatch. Expected Iteration {ITERATION}; "
            "restart the scanner and refresh the page."
        )
    scan_id = str(data.get("scan_id", "")).strip()
    if not scan_id:
        raise ValueError("No scan is selected. Rescan the image area before saving.")

    with SCAN_RECORDS_LOCK:
        record = SCAN_RECORDS.get(scan_id)
        if record is None:
            raise ValueError(
                "This scan is no longer active. Rescan the image area before saving."
            )
        corrected_letters = str(data.get("corrected_letters", "")).strip()
        corrected_numbers = str(data.get("corrected_numbers", "")).strip()
        row = {
            **record,
            "corrected_letters": corrected_letters,
            "corrected_numbers": corrected_numbers,
            "was_corrected": (
                "yes"
                if (
                    corrected_letters != record["detected_letters"]
                    or corrected_numbers != record["detected_numbers"]
                )
                else "no"
            ),
        }
        _append_csv(row)
        del SCAN_RECORDS[scan_id]
    return row


def lookup_confirmed_fields(data: dict) -> CardInfo:
    """Resolve corrected fields against the canonical local catalog only."""
    code = str(data.get("set_code", "")).strip().upper()
    number = str(data.get("card_number", "")).strip()
    total = str(data.get("set_total", "")).strip()
    if not code or not number:
        raise ValueError("Set code and card number are required for lookup.")
    result = find_exact_card(code, number, database_path=CARD_CATALOG_PATH)
    if result.status == "catalog_unavailable":
        raise ValueError(
            "Local card catalog is unavailable. Run update_card_database.bat first."
        )
    if result.status == "ambiguous":
        return CardInfo(
            set_code=code,
            card_number=number,
            status="review",
            review_reasons=(
                f"set code and number matched {result.match_count} local cards",
            ),
        )
    if result.card is None:
        return CardInfo(set_code=code, card_number=number, status="no_match")
    card = result.card
    info = CardInfo(
        card_id=card.id,
        set_code=card.set_code,
        set_name=card.set_name,
        card_name=card.card_name,
        card_number=card.card_number,
        set_id=card.set_id,
        source="local Malie TCGL catalog",
        printed_total=card.printed_total,
        image_url=card.image_url,
        status="accepted",
    )
    if total and card.printed_total and total.lstrip("0") != card.printed_total.lstrip("0"):
        return replace(
            info,
            status="review",
            review_reasons=("printed total conflicts with local catalog",),
        )
    return info


def inventory_database() -> InventoryDatabase:
    database = InventoryDatabase(INVENTORY_PATH)
    database.initialize()
    return database


def saved_deck_database() -> SavedDeckDatabase:
    database = SavedDeckDatabase(DECK_LIBRARY_PATH)
    database.initialize()
    return database


def saved_decks_snapshot() -> dict:
    decks = [asdict(deck) for deck in saved_deck_database().decks()]
    return {"decks": decks, "count": len(decks), "inventory_changed": False}


def _saved_deck_name(data: dict) -> str:
    name = " ".join(str(data.get("name", "")).split())
    if not name:
        raise ValueError("Give this deck a name before saving it.")
    if len(name) > 80:
        raise ValueError("Deck names must be 80 characters or fewer.")
    return name


def _saved_deck_id(data: dict, *, required: bool = True) -> int:
    value = data.get("id", 0)
    if isinstance(value, bool):
        value = 0
    try:
        deck_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("A valid saved deck is required.") from exc
    if required and deck_id <= 0:
        raise ValueError("A valid saved deck is required.")
    return max(0, deck_id)


def save_saved_deck(data: dict) -> SavedDeck:
    name = _saved_deck_name(data)
    deck_list = str(data.get("deck_list", "")).strip()
    if not deck_list:
        raise ValueError("Paste and check a deck list before saving it.")
    if len(deck_list) > 100_000:
        raise ValueError("That deck list is too large to save.")
    entries, errors = parse_deck_list(deck_list)
    if errors:
        raise ValueError("Fix the lines needing review before saving this deck.")
    if not entries:
        raise ValueError("No cards were found in that deck list.")
    return saved_deck_database().save(
        name,
        deck_list,
        sum(entry.quantity for entry in entries),
        len(entries),
        deck_id=_saved_deck_id(data, required=False),
    )


def rename_saved_deck(data: dict) -> SavedDeck:
    return saved_deck_database().rename(
        _saved_deck_id(data),
        _saved_deck_name(data),
    )


def remove_saved_deck(data: dict) -> None:
    saved_deck_database().remove(_saved_deck_id(data))


STANDARD_REGULATION_MARKS = ("H", "I", "J")
ACE_SPEC_RARITY = "ACE_SPEC_RARE"
CATALOG_CARD_CATEGORIES = {
    "pokemon": ("POKEMON", ""),
    "supporter": ("TRAINER", "SUPPORTER"),
    "item": ("TRAINER", "ITEM"),
    "stadium": ("TRAINER", "STADIUM"),
    "tool": ("TRAINER", "TOOL"),
    "basic-energy": ("ENERGY", "BASIC"),
    "special-energy": ("ENERGY", "SPECIAL"),
}


def catalog_facets() -> dict:
    """Return search choices without selecting or exposing any card rows."""
    if not CARD_CATALOG_PATH.is_file():
        raise ValueError("Local card catalog is unavailable. Run update_card_database.bat first.")
    with CatalogDatabase(CARD_CATALOG_PATH).connect() as connection:
        sets = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, name, code FROM sets
                WHERE language = 'en-US'
                ORDER BY release_date DESC, name COLLATE NOCASE
                """
            ).fetchall()
        ]
    return {
        "sets": sets,
        "formats": [
            {"value": "standard", "label": "Standard", "marks": list(STANDARD_REGULATION_MARKS)},
            {"value": "expanded", "label": "Expanded", "marks": []},
        ],
        "language": "en-US",
    }


def catalog_search(
    query: str = "",
    *,
    set_id: str = "",
    format_name: str = "",
    card_category: str = "",
    limit: int = 48,
    offset: int = 0,
) -> dict:
    """Search the local English catalog and attach current owned quantities."""
    if not CARD_CATALOG_PATH.is_file():
        raise ValueError("Local card catalog is unavailable. Run update_card_database.bat first.")
    selected_limit = max(1, min(int(limit), 100))
    selected_offset = max(0, int(offset))
    selected_set = set_id.strip()
    selected_format = format_name.strip().lower()
    selected_category = card_category.strip().lower()
    if selected_format not in {"", "standard", "expanded"}:
        raise ValueError("Format must be Standard or Expanded.")
    if selected_category not in {"", "ace-spec", *CATALOG_CARD_CATEGORIES}:
        raise ValueError("Unknown card type filter.")
    if not any((query.strip(), selected_set, selected_format, selected_category)):
        raise ValueError("Choose at least one search option before searching.")

    filters = ["c.language = 'en-US'"]
    parameters: list[object] = []
    if selected_set:
        filters.append("c.set_id = ?")
        parameters.append(selected_set)
    if selected_format == "standard":
        placeholders = ",".join("?" for _ in STANDARD_REGULATION_MARKS)
        filters.append(f"c.regulation_mark IN ({placeholders})")
        parameters.extend(STANDARD_REGULATION_MARKS)
    if selected_category:
        if selected_category == "ace-spec":
            filters.append("c.rarity = ? COLLATE NOCASE")
            parameters.append(ACE_SPEC_RARITY)
        else:
            card_type, card_subtype = CATALOG_CARD_CATEGORIES[selected_category]
            filters.append("c.card_type = ? COLLATE NOCASE")
            parameters.append(card_type)
            if card_subtype:
                filters.append("c.card_subtype = ? COLLATE NOCASE")
                parameters.append(card_subtype)
    terms = re.findall(r"[A-Za-z0-9'-]+", query.strip())[:6]
    for term in terms:
        filters.append(
            """(
                c.name LIKE ? COLLATE NOCASE
                OR s.name LIKE ? COLLATE NOCASE
                OR EXISTS (
                    SELECT 1 FROM set_codes sc
                    WHERE sc.set_id = s.id AND sc.code = ? COLLATE NOCASE
                )
                OR ltrim(c.number, '0') = ltrim(?, '0')
            )"""
        )
        parameters.extend((f"%{term}%", f"%{term}%", term, term))
    where = " WHERE " + " AND ".join(filters)
    order_by = (
        "c.number_numeric, c.number, c.name COLLATE NOCASE"
        if selected_set
        else "c.name COLLATE NOCASE, s.name COLLATE NOCASE, c.number_numeric, c.number"
    )

    with CatalogDatabase(CARD_CATALOG_PATH).connect() as connection:
        total = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM cards c JOIN sets s ON s.id = c.set_id" + where,
                parameters,
            ).fetchone()["count"]
        )
        rows = connection.execute(
            """
            SELECT c.id, c.name, c.card_type,
                   COALESCE(c.card_subtype, '') AS card_subtype,
                   c.number, c.number_numeric,
                   COALESCE(c.printed_total, '') AS printed_total,
                   COALESCE(c.regulation_mark, '') AS regulation_mark,
                   COALESCE(c.primary_image_url, '') AS image_url,
                   s.id AS set_id, s.name AS set_name, s.code AS set_code
            FROM cards c JOIN sets s ON s.id = c.set_id
            """
            + where
            + f" ORDER BY {order_by} LIMIT ? OFFSET ?",
            [*parameters, selected_limit, selected_offset],
        ).fetchall()
    quantities = {holding.card_id: holding.quantity for holding in inventory_database().holdings()}
    items = [dict(row) for row in rows]
    for item in items:
        item["quantity"] = quantities.get(item["id"], 0)
    return {
        "items": items,
        "total": total,
        "limit": selected_limit,
        "offset": selected_offset,
        "format": selected_format,
        "card_category": selected_category,
        "language": "en-US",
    }


def set_catalog_inventory_quantity(data: dict) -> InventoryChange:
    """Set quantity only for an immutable card ID present in the local catalog."""
    card_id = str(data.get("card_id", "")).strip()
    quantity_text = str(data.get("quantity", "")).strip()
    if not card_id:
        raise ValueError("A canonical card ID is required for inventory.")
    if not quantity_text.isdigit():
        raise ValueError("Inventory quantity must be a whole number.")
    quantity = int(quantity_text)
    if quantity < 0 or quantity > 9999:
        raise ValueError("Inventory quantity must be between 0 and 9999.")
    if not CARD_CATALOG_PATH.is_file():
        raise ValueError("Local card catalog is unavailable.")
    with CatalogDatabase(CARD_CATALOG_PATH).connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM cards WHERE id = ? AND language = 'en-US'",
            (card_id,),
        ).fetchone()
    if exists is None:
        raise ValueError("That canonical card is not in the local English catalog.")
    return inventory_database().set_quantity(card_id, quantity)


def _inventory_location_id(data: dict) -> int:
    value = data.get("location_id", 0)
    if isinstance(value, bool):
        value = 0
    try:
        location_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("A valid inventory location is required.") from exc
    if location_id <= 0:
        raise ValueError("A valid inventory location is required.")
    return location_id


def create_inventory_location(data: dict) -> InventoryLocation:
    return inventory_database().create_location(str(data.get("name", "")))


def rename_inventory_location(data: dict) -> InventoryLocation:
    return inventory_database().rename_location(
        _inventory_location_id(data),
        str(data.get("name", "")),
    )


def remove_inventory_location(data: dict) -> int:
    return inventory_database().remove_location(_inventory_location_id(data))


def set_inventory_location_quantity(data: dict) -> InventoryLocationChange:
    card_id = str(data.get("card_id", "")).strip()
    quantity = data.get("quantity")
    if isinstance(quantity, bool):
        quantity = None
    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("Location quantity must be a whole number.") from exc
    return inventory_database().set_location_quantity(
        card_id,
        _inventory_location_id(data),
        quantity,
    )


def inventory_locations_snapshot() -> dict:
    database = inventory_database()
    holdings = database.holdings()
    allocations = database.location_allocations()
    total_by_card = {holding.card_id: holding.quantity for holding in holdings}
    assigned_by_card: dict[str, int] = {}
    for allocation in allocations:
        assigned_by_card[allocation.card_id] = (
            assigned_by_card.get(allocation.card_id, 0) + allocation.quantity
        )
    unassigned = {
        card_id: quantity - assigned_by_card.get(card_id, 0)
        for card_id, quantity in total_by_card.items()
    }
    return {
        "locations": [asdict(location) for location in database.locations()],
        "unassigned": {
            "unique_cards": sum(quantity > 0 for quantity in unassigned.values()),
            "total_copies": sum(max(0, quantity) for quantity in unassigned.values()),
        },
        "all": {
            "unique_cards": len(holdings),
            "total_copies": sum(total_by_card.values()),
        },
        "inventory_changed": False,
    }


INVENTORY_SORTS = {"name", "set_number", "category", "subtype", "element"}
NON_POKEMON_TYPE_ORDER = {
    "Item": 0,
    "Supporter": 1,
    "Tool": 2,
    "Stadium": 3,
    "Basic Energy": 4,
    "Special Energy": 5,
}


def _inventory_element_group(item: dict) -> str:
    if item["card_type"] == "POKEMON" and item["types"]:
        return item["types"][0].title()
    return item["display_subtype"] or item["card_type"].title()


def _inventory_sort_key(item: dict, selected_sort: str) -> tuple:
    name = item["name"].casefold()
    if selected_sort == "set_number":
        return (
            item["set_name"].casefold(),
            item["number_numeric"] if item["number_numeric"] is not None else 10**9,
            item["number"],
            name,
        )
    if selected_sort == "category":
        return (item["card_type"], item["card_subtype"], name)
    if selected_sort == "subtype":
        return (item["display_subtype"] or item["card_type"], name)
    if selected_sort == "element":
        if item["card_type"] == "POKEMON":
            return (0, item["element_group"], name)
        return (
            1,
            NON_POKEMON_TYPE_ORDER.get(item["element_group"], 99),
            item["element_group"],
            name,
        )
    return (name, item["set_name"].casefold(), item["number"])


def inventory_snapshot(sort_by: str = "name") -> dict:
    """Join user quantities to rebuildable catalog details for read-only display."""
    selected_sort = sort_by if sort_by in INVENTORY_SORTS else "name"
    database = inventory_database()
    holdings = database.holdings()
    locations = database.locations()
    allocations = database.location_allocations()
    allocations_by_card: dict[str, dict[str, int]] = {}
    for allocation in allocations:
        allocations_by_card.setdefault(allocation.card_id, {})[
            str(allocation.location_id)
        ] = allocation.quantity
    assigned_by_card = {
        card_id: sum(card_allocations.values())
        for card_id, card_allocations in allocations_by_card.items()
    }
    location_payload = [asdict(location) for location in locations]
    unassigned_payload = {
        "unique_cards": sum(
            holding.quantity - assigned_by_card.get(holding.card_id, 0) > 0
            for holding in holdings
        ),
        "total_copies": sum(
            max(0, holding.quantity - assigned_by_card.get(holding.card_id, 0))
            for holding in holdings
        ),
    }
    if not holdings:
        return {
            "items": [],
            "unique_cards": 0,
            "total_copies": 0,
            "sort": selected_sort,
            "locations": location_payload,
            "unassigned": unassigned_payload,
        }
    if not CARD_CATALOG_PATH.is_file():
        raise ValueError("Local card catalog is unavailable.")
    quantities = {holding.card_id: holding.quantity for holding in holdings}
    holding_dates = {
        holding.card_id: {
            "date_added": holding.created_at,
            "date_updated": holding.updated_at,
        }
        for holding in holdings
    }
    placeholders = ",".join("?" for _ in quantities)
    from card_api.database import CatalogDatabase

    with CatalogDatabase(CARD_CATALOG_PATH).connect() as connection:
        rows = connection.execute(
            f"""
            SELECT c.id, c.name, c.card_type, COALESCE(c.card_subtype, '') AS card_subtype,
                   c.number, c.number_numeric, COALESCE(c.printed_total, '') AS printed_total,
                   COALESCE(c.regulation_mark, '') AS regulation_mark,
                   COALESCE(c.rarity, '') AS rarity,
                   COALESCE(c.primary_image_url, '') AS image_url,
                   s.name AS set_name, s.code AS set_code
            FROM cards c JOIN sets s ON s.id = c.set_id
            WHERE c.id IN ({placeholders})
            """,
            list(quantities),
        ).fetchall()
        items = [dict(row) for row in rows]
        type_rows = connection.execute(
            f"SELECT card_id, type FROM card_types WHERE card_id IN ({placeholders}) "
            "ORDER BY card_id, position",
            list(quantities),
        ).fetchall()
    types_by_card = {card_id: [] for card_id in quantities}
    for row in type_rows:
        types_by_card[row["card_id"]].append(row["type"])
    for item in items:
        item["quantity"] = quantities[item["id"]]
        item["locations"] = allocations_by_card.get(item["id"], {})
        item["assigned_quantity"] = assigned_by_card.get(item["id"], 0)
        item["unassigned_quantity"] = item["quantity"] - item["assigned_quantity"]
        item.update(holding_dates[item["id"]])
        item["types"] = types_by_card[item["id"]]
        item["display_subtype"] = (
            f"{item['card_subtype'].title()} Energy"
            if item["card_type"] == "ENERGY" and item["card_subtype"]
            else item["card_subtype"].title()
        )
        item["is_ace_spec"] = item["rarity"].upper() == ACE_SPEC_RARITY
        item["element_group"] = _inventory_element_group(item)

    items.sort(key=lambda item: _inventory_sort_key(item, selected_sort))
    return {
        "items": items,
        "unique_cards": len(items),
        "total_copies": sum(item["quantity"] for item in items),
        "sort": selected_sort,
        "locations": location_payload,
        "unassigned": unassigned_payload,
    }


def _parse_inventory_import(data: dict) -> tuple[dict, str]:
    filename = Path(str(data.get("filename", "")).strip()).name
    content = data.get("content", "")
    if not filename or not isinstance(content, str) or not content.strip():
        raise ValueError("Choose a non-empty CSV or JSON collection export.")
    suffix = Path(filename).suffix.casefold()
    if suffix == ".json":
        payload = parse_collection_json(content)
    elif suffix == ".csv":
        payload = parse_collection_csv(content)
    else:
        raise ValueError("Collection imports must use a .json or .csv file.")
    return payload, filename


def _catalog_cards_for_import(card_ids: set[str]) -> dict[str, dict]:
    if not card_ids:
        return {}
    if not CARD_CATALOG_PATH.is_file():
        raise ValueError("Local card catalog is unavailable.")
    found: dict[str, dict] = {}
    with CatalogDatabase(CARD_CATALOG_PATH).connect() as connection:
        ordered_ids = sorted(card_ids)
        for start in range(0, len(ordered_ids), 400):
            batch = ordered_ids[start : start + 400]
            placeholders = ",".join("?" for _ in batch)
            rows = connection.execute(
                f"""
                SELECT c.id, c.name, c.number, COALESCE(c.printed_total, '') AS printed_total,
                       COALESCE(c.primary_image_url, '') AS image_url,
                       s.name AS set_name, s.code AS set_code
                FROM cards c JOIN sets s ON s.id = c.set_id
                WHERE c.language = 'en-US' AND c.id IN ({placeholders})
                """,
                batch,
            ).fetchall()
            found.update({str(row["id"]): dict(row) for row in rows})
    return found


def _inventory_import_fingerprint(
    mode: str,
    imported: dict[str, int],
    current: dict[str, int],
) -> str:
    encoded = json.dumps(
        {
            "mode": mode,
            "imported": sorted(imported.items()),
            "current": sorted(current.items()),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def inventory_import_preview(data: dict) -> dict:
    """Validate an export and summarize exact changes without mutating inventory."""
    mode = str(data.get("mode", "update")).strip().casefold()
    if mode not in {"update", "replace"}:
        raise ValueError("Choose Update listed cards or Restore/replace.")
    payload, filename = _parse_inventory_import(data)
    imported_cards = {card["card_id"]: card for card in payload["cards"]}
    imported = {card_id: card["quantity"] for card_id, card in imported_cards.items()}
    current = {
        holding.card_id: holding.quantity
        for holding in inventory_database().holdings()
    }
    catalog = _catalog_cards_for_import(set(imported) | (set(current) if mode == "replace" else set()))
    unknown_ids = sorted(set(imported) - set(catalog))
    errors = [
        f"{imported_cards[card_id].get('name') or card_id}: canonical card ID is not in the local English catalog."
        for card_id in unknown_ids
    ]

    considered = set(imported) | (set(current) if mode == "replace" else set())
    counts = {"additions": 0, "quantity_changes": 0, "removals": 0, "unchanged": 0}
    changes = []
    for card_id in considered:
        old_quantity = current.get(card_id, 0)
        new_quantity = imported.get(card_id, 0 if mode == "replace" else old_quantity)
        if old_quantity == new_quantity:
            counts["unchanged"] += 1
            continue
        if old_quantity == 0:
            change_type = "addition"
            counts["additions"] += 1
        elif new_quantity == 0:
            change_type = "removal"
            counts["removals"] += 1
        else:
            change_type = "quantity_change"
            counts["quantity_changes"] += 1
        details = catalog.get(card_id) or imported_cards.get(card_id, {})
        changes.append(
            {
                "card_id": card_id,
                "name": details.get("name", card_id),
                "set_name": details.get("set_name", ""),
                "set_code": details.get("set_code", ""),
                "number": details.get("number", ""),
                "printed_total": details.get("printed_total", ""),
                "image_url": details.get("image_url", ""),
                "old_quantity": old_quantity,
                "new_quantity": new_quantity,
                "change": change_type,
            }
        )
    changes.sort(key=lambda item: (item["change"], str(item["name"]).casefold(), item["card_id"]))
    total_before = sum(current.values())
    total_after = (
        sum(imported.values())
        if mode == "replace"
        else total_before + sum(item["new_quantity"] - item["old_quantity"] for item in changes)
    )
    return {
        "filename": filename,
        "mode": mode,
        "preview_id": _inventory_import_fingerprint(mode, imported, current),
        "can_apply": not errors,
        "errors": errors,
        "summary": {
            **counts,
            "affected_cards": len(changes),
            "imported_cards": len(imported),
            "total_before": total_before,
            "total_after": total_after,
        },
        "changes": changes,
    }


def apply_inventory_import(data: dict) -> dict:
    """Revalidate a preview, then apply it as one backed-up bulk mutation."""
    preview = inventory_import_preview(data)
    if not preview["can_apply"]:
        raise ValueError("Fix the import errors before applying this collection file.")
    if str(data.get("preview_id", "")) != preview["preview_id"]:
        raise ValueError("The collection changed after this preview. Preview the file again.")
    quantities = {
        item["card_id"]: int(item["new_quantity"])
        for item in preview["changes"]
    }
    changes = inventory_database().set_quantities(quantities)
    return {
        "mode": preview["mode"],
        "filename": preview["filename"],
        "applied_cards": len(changes),
        "summary": preview["summary"],
    }


def add_inventory_card(data: dict) -> tuple[CardInfo, InventoryChange]:
    """Add only a freshly revalidated, unique canonical card match."""
    info = lookup_confirmed_fields(data)
    if info.status != "accepted" or not info.card_id:
        raise ValueError(
            "Inventory additions require one exact local catalog match with no conflicts."
        )
    quantity_text = str(data.get("quantity", 1)).strip()
    if not quantity_text.isdigit():
        raise ValueError("Inventory quantity must be a whole number.")
    quantity = int(quantity_text)
    if quantity < 1 or quantity > 99:
        raise ValueError("Inventory quantity must be between 1 and 99.")
    change = inventory_database().add_cards(
        info.card_id,
        quantity,
        scan_id=str(data.get("scan_id", "")),
    )
    return info, change


def undo_inventory_add(data: dict) -> InventoryChange:
    try:
        event_id = int(data.get("event_id", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("A valid inventory event is required for undo.") from exc
    return inventory_database().undo_add(event_id)


class ScannerHandler(BaseHTTPRequestHandler):
    server_version = "TinyTextReader/iteration-18"

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _download(self, content: bytes, content_type: str, filename: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("The image request is empty or too large (30 MB maximum).")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/scan":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if route == "/health":
            self._json(
                {
                    "ok": True,
                    "server_api_version": SERVER_API_VERSION,
                    "iteration": ITERATION,
                    "name": ITERATION_NAME,
                    "primary_ocr": "RapidOCR",
                    "primary_ocr_available": importlib.util.find_spec("rapidocr")
                    is not None,
                    "local_catalog_available": CARD_CATALOG_PATH.is_file(),
                    "inventory_available": INVENTORY_PATH.is_file(),
                    "deck_library_available": DECK_LIBRARY_PATH.is_file(),
                }
            )
            return
        if route == "/decks":
            try:
                self._json({"ok": True, **saved_decks_snapshot()})
            except (ValueError, OSError) as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "/inventory/cards":
            sort_by = parse_qs(parsed.query).get("sort", ["name"])[0]
            try:
                self._json({"ok": True, **inventory_snapshot(sort_by)})
            except (ValueError, OSError) as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "/inventory/locations":
            try:
                self._json({"ok": True, **inventory_locations_snapshot()})
            except (ValueError, OSError) as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route in {"/inventory/export.json", "/inventory/export.csv"}:
            try:
                payload = build_collection_export(inventory_snapshot("name"))
                timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
                if route.endswith(".json"):
                    self._download(
                        render_collection_json(payload),
                        "application/json; charset=utf-8",
                        f"pokemon-collection-{timestamp}.json",
                    )
                else:
                    self._download(
                        render_collection_csv(payload),
                        "text/csv; charset=utf-8",
                        f"pokemon-collection-{timestamp}.csv",
                    )
            except (ValueError, OSError) as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "/catalog/search":
            query = parse_qs(parsed.query)
            try:
                self._json(
                    {
                        "ok": True,
                        **catalog_search(
                            query.get("q", [""])[0],
                            set_id=query.get("set", [""])[0],
                            format_name=query.get("format", [""])[0],
                            card_category=query.get("type", [""])[0],
                            limit=int(query.get("limit", [48])[0]),
                            offset=int(query.get("offset", [0])[0]),
                        ),
                    }
                )
            except (TypeError, ValueError, OSError) as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "/catalog/facets":
            try:
                self._json({"ok": True, **catalog_facets()})
            except (ValueError, OSError) as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        files = {
            "/": "search.html",
            "/inventory": "inventory.html",
            "/deck": "deck.html",
            "/search.js": "search.js",
            "/inventory.js": "inventory.js",
            "/deck.js": "deck.js",
            "/card-inspector.js": "card-inspector.js",
            "/theme.js": "theme.js",
            "/style.css": "style.css",
        }
        if route == "/legacy-webcam-scanner":
            path = LEGACY_SCANNER_WEB_ROOT / "index.html"
        elif route == "/legacy-webcam-scanner/app.js":
            path = LEGACY_SCANNER_WEB_ROOT / "app.js"
        else:
            filename = files.get(route)
            if not filename:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path = WEB_ROOT / filename
        content = path.read_bytes()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
        }[path.suffix]
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            data = self._body_json()
            if self.path == "/scan":
                self._scan(data)
            elif self.path == "/lookup":
                info = lookup_confirmed_fields(data)
                quantity = (
                    inventory_database().quantity(info.card_id)
                    if info.status == "accepted" and info.card_id
                    else 0
                )
                self._json(
                    {
                        "ok": True,
                        "card": asdict(info),
                        "inventory_quantity": quantity,
                    }
                )
            elif self.path == "/inventory/add":
                info, change = add_inventory_card(data)
                self._json(
                    {
                        "ok": True,
                        "card": asdict(info),
                        "inventory": asdict(change),
                    }
                )
            elif self.path == "/inventory/undo":
                change = undo_inventory_add(data)
                self._json({"ok": True, "inventory": asdict(change)})
            elif self.path == "/inventory/set-quantity":
                change = set_catalog_inventory_quantity(data)
                self._json({"ok": True, "inventory": asdict(change)})
            elif self.path == "/inventory/locations/create":
                location = create_inventory_location(data)
                self._json(
                    {
                        "ok": True,
                        "location": asdict(location),
                        "inventory_changed": False,
                    }
                )
            elif self.path == "/inventory/locations/rename":
                location = rename_inventory_location(data)
                self._json(
                    {
                        "ok": True,
                        "location": asdict(location),
                        "inventory_changed": False,
                    }
                )
            elif self.path == "/inventory/locations/remove":
                released = remove_inventory_location(data)
                self._json(
                    {
                        "ok": True,
                        "removed": True,
                        "released_copies": released,
                        "inventory_changed": False,
                    }
                )
            elif self.path == "/inventory/locations/set-quantity":
                change = set_inventory_location_quantity(data)
                self._json(
                    {
                        "ok": True,
                        "allocation": asdict(change),
                        "inventory_changed": False,
                    }
                )
            elif self.path == "/inventory/import/preview":
                self._json({"ok": True, **inventory_import_preview(data)})
            elif self.path == "/inventory/import/apply":
                self._json({"ok": True, **apply_inventory_import(data)})
            elif self.path == "/deck/check":
                result = check_deck_list(
                    str(data.get("deck_list", "")),
                    catalog_path=CARD_CATALOG_PATH,
                    inventory_path=INVENTORY_PATH,
                )
                self._json({"ok": True, **result})
            elif self.path == "/decks/save":
                deck = save_saved_deck(data)
                self._json({"ok": True, "deck": asdict(deck), "inventory_changed": False})
            elif self.path == "/decks/rename":
                deck = rename_saved_deck(data)
                self._json({"ok": True, "deck": asdict(deck), "inventory_changed": False})
            elif self.path == "/decks/remove":
                remove_saved_deck(data)
                self._json({"ok": True, "removed": True, "inventory_changed": False})
            elif self.path == "/scan/timing":
                row = save_scan_performance(data)
                self._json(
                    {
                        "ok": True,
                        "path": str(SCAN_PERFORMANCE_PATH),
                        "scan_id": row["scan_id"],
                    }
                )
            elif self.path == "/save":
                row = save_benchmark_label(data)
                self._json(
                    {
                        "ok": True,
                        "path": str(CSV_PATH),
                        "scan_id": row["scan_id"],
                    }
                )
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError, json.JSONDecodeError, OSError) as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _scan(self, data: dict) -> None:
        server_started = perf_counter()
        if int(data.get("iteration", 0)) != ITERATION:
            raise ValueError(
                f"Browser/server iteration mismatch. Expected Iteration {ITERATION}; "
                "restart the scanner and refresh the page."
            )
        encoded = str(data["image"])
        if "," in encoded:
            encoded = encoded.split(",", 1)[1]
        raw = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(raw)) as opened:
            crop = opened.convert("RGB")
        accepted_fields: tuple[str, str, str, str] | None = None

        def accept_exact_identifier(text: str) -> bool:
            nonlocal accepted_fields
            accepted_fields = exact_catalog_fields(text)
            return accepted_fields is not None

        ocr_started = perf_counter()
        result = scan_crop(
            crop,
            derive_card_candidates=False,
            early_stop_validator=accept_exact_identifier,
            time_budget_seconds=OCR_TIME_BUDGET_SECONDS,
        )
        ocr_elapsed_seconds = perf_counter() - ocr_started
        accepted_fields = accepted_fields or exact_catalog_fields_from_readings(
            result.raw_text,
            result.literal_readings,
        )
        regulation_mark, set_code, card_number, set_total = (
            accepted_fields
            or extract_footer_fields_from_readings(
                result.raw_text,
                result.literal_readings,
            )
        )
        letters = " ".join(
            value for value in (regulation_mark, set_code) if value
        )
        numbers = " / ".join(value for value in (card_number, set_total) if value)
        scan_id = uuid.uuid4().hex
        CROP_DIR.mkdir(parents=True, exist_ok=True)
        crop_path = CROP_DIR / f"{scan_id}.png"
        crop.save(crop_path, format="PNG")
        server_elapsed_seconds = perf_counter() - server_started
        variant_readings = [
            {
                "variant": reading.variant,
                "text": reading.text,
                "confidence": round(reading.confidence, 6),
            }
            for reading in result.literal_readings
        ]
        record = {
            "scanned_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "iteration": ITERATION,
            "scan_id": scan_id,
            "image_name": Path(str(data.get("image_name", ""))).name,
            "crop_path": str(crop_path.resolve()),
            "ocr_engine": result.ocr_engine,
            "literal_text": result.raw_text,
            "primary_confidence": f"{result.primary_confidence:.6f}",
            "client_total_seconds": "",
            "server_elapsed_seconds": f"{server_elapsed_seconds:.3f}",
            "ocr_elapsed_seconds": f"{ocr_elapsed_seconds:.3f}",
            "ocr_time_budget_seconds": f"{OCR_TIME_BUDGET_SECONDS:.1f}",
            "ocr_timed_out": "yes" if result.timed_out else "no",
            "treatments_attempted_json": json.dumps(
                result.treatments_attempted,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "variant_count": len(result.literal_readings),
            "regulation_mark": regulation_mark,
            "set_code": set_code,
            "card_number": card_number,
            "set_total": set_total,
            "exact_catalog_identifier": "yes" if accepted_fields else "no",
            "detected_letters": letters,
            "detected_numbers": numbers,
            "variant_readings_json": json.dumps(
                variant_readings, ensure_ascii=False, separators=(",", ":")
            ),
        }
        with SCAN_RECORDS_LOCK:
            SCAN_RECORDS[scan_id] = record
        self._json(
            {
                "ok": True,
                "iteration": ITERATION,
                "iteration_name": ITERATION_NAME,
                "scan_id": scan_id,
                "raw_ocr": result.raw_text,
                "letters_read": letters,
                "numbers_read": numbers,
                "regulation_mark": regulation_mark,
                "set_code": set_code,
                "card_number": card_number,
                "set_total": set_total,
                "ocr_engine": result.ocr_engine,
                "ocr_evidence": result.evidence_text,
                "primary_confidence": result.primary_confidence,
                "ocr_elapsed_seconds": round(ocr_elapsed_seconds, 3),
                "server_elapsed_seconds": round(server_elapsed_seconds, 3),
                "ocr_time_budget_seconds": OCR_TIME_BUDGET_SECONDS,
                "ocr_timed_out": result.timed_out,
                "treatments_attempted": result.treatments_attempted,
                "variant_readings": variant_readings,
                "complete": bool(result.raw_text),
            }
        )


def _running_collection_server(port: int) -> dict | None:
    try:
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=0.6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload.get("ok") else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Pokémon collection app")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--start-path",
        choices=("/", "/legacy-webcam-scanner"),
        default="/",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    existing = _running_collection_server(args.port)
    if existing is not None:
        url = f"http://127.0.0.1:{args.port}{args.start_path}"
        if existing.get("server_api_version") == SERVER_API_VERSION:
            print(f"The current Pokemon Collection app is already running at {url}")
            if not args.no_browser:
                webbrowser.open(url)
            return
        raise SystemExit(
            f"An older Pokemon Collection server is still using port {args.port}. "
            "Close every older Pokemon Collection command window, then start the app again."
        )
    inventory_database()
    saved_deck_database()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ScannerHandler)
    url = f"http://127.0.0.1:{server.server_port}{args.start_path}"
    print(f"Pokémon collection is running at {url}")
    print("Press Ctrl+C to stop it.")
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
