"""Local browser interface for the tiny card text scanner."""

from __future__ import annotations

import argparse
import base64
import csv
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

from PIL import Image

from card_scanner.ocr import scan_crop, warm_up_ocr
from card_scanner.catalog import known_set_codes
from card_api.catalog import find_exact_card
from card_api.config import DATABASE_PATH as CARD_CATALOG_PATH
from card_scanner.lookup import CardInfo
from inventory import InventoryChange, InventoryDatabase


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
CSV_PATH = Path(os.environ.get("OCR_BENCHMARK_CSV", ROOT / "ocr_reads_it13.csv"))
CROP_DIR = Path(
    os.environ.get(
        "OCR_BENCHMARK_CROP_DIR",
        ROOT / "benchmark_crops" / "iteration_13",
    )
)
INVENTORY_PATH = Path(
    os.environ.get(
        "INVENTORY_DATABASE_PATH",
        ROOT / "user_data" / "inventory.sqlite3",
    )
)
MAX_REQUEST_BYTES = 30 * 1024 * 1024
ITERATION = 13
ITERATION_NAME = "Light and dark themes"
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
    "detected_letters",
    "detected_numbers",
    "corrected_letters",
    "corrected_numbers",
    "was_corrected",
    "variant_readings_json",
]
SCAN_RECORDS: dict[str, dict] = {}
SCAN_RECORDS_LOCK = threading.Lock()


def extract_footer_fields(text: str) -> tuple[str, str, str, str]:
    """Read regulation, set, card number, and total by printed position.

    This deliberately uses no known-set list. A one-letter token immediately
    before the first multi-letter token is the regulation mark; the
    multi-letter token is the literal set-code read. The exact ``en`` language
    marker is ignored.
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
    _regulation_mark, set_code, card_number, set_total = fields
    if not set_code or not card_number:
        return None
    result = find_exact_card(
        set_code,
        card_number,
        database_path=CARD_CATALOG_PATH,
    )
    if result.status != "exact" or result.card is None:
        return None
    if (
        set_total
        and result.card.printed_total
        and set_total.lstrip("0") != result.card.printed_total.lstrip("0")
    ):
        return None
    return fields


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
    holdings = inventory_database().holdings()
    if not holdings:
        return {
            "items": [],
            "unique_cards": 0,
            "total_copies": 0,
            "sort": selected_sort,
        }
    if not CARD_CATALOG_PATH.is_file():
        raise ValueError("Local card catalog is unavailable.")
    quantities = {holding.card_id: holding.quantity for holding in holdings}
    placeholders = ",".join("?" for _ in quantities)
    from card_api.database import CatalogDatabase

    with CatalogDatabase(CARD_CATALOG_PATH).connect() as connection:
        rows = connection.execute(
            f"""
            SELECT c.id, c.name, c.card_type, COALESCE(c.card_subtype, '') AS card_subtype,
                   c.number, c.number_numeric, COALESCE(c.printed_total, '') AS printed_total,
                   COALESCE(c.regulation_mark, '') AS regulation_mark,
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
        item["types"] = types_by_card[item["id"]]
        item["display_subtype"] = (
            f"{item['card_subtype'].title()} Energy"
            if item["card_type"] == "ENERGY" and item["card_subtype"]
            else item["card_subtype"].title()
        )
        item["element_group"] = _inventory_element_group(item)

    items.sort(key=lambda item: _inventory_sort_key(item, selected_sort))
    return {
        "items": items,
        "unique_cards": len(items),
        "total_copies": sum(item["quantity"] for item in items),
        "sort": selected_sort,
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
    server_version = "TinyTextReader/iteration-13"

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

    def _body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("The image request is empty or too large (30 MB maximum).")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/health":
            self._json(
                {
                    "ok": True,
                    "iteration": ITERATION,
                    "name": ITERATION_NAME,
                    "primary_ocr": "RapidOCR",
                    "primary_ocr_available": importlib.util.find_spec("rapidocr")
                    is not None,
                    "local_catalog_available": CARD_CATALOG_PATH.is_file(),
                    "inventory_available": INVENTORY_PATH.is_file(),
                }
            )
            return
        if route == "/inventory/cards":
            sort_by = parse_qs(parsed.query).get("sort", ["name"])[0]
            try:
                self._json({"ok": True, **inventory_snapshot(sort_by)})
            except (ValueError, OSError) as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        files = {
            "/": "index.html",
            "/inventory": "inventory.html",
            "/app.js": "app.js",
            "/inventory.js": "inventory.js",
            "/theme.js": "theme.js",
            "/style.css": "style.css",
        }
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
        )
        ocr_elapsed_seconds = perf_counter() - ocr_started
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
                "variant_readings": variant_readings,
                "complete": bool(result.raw_text),
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local card scanner")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    print("Preparing the OCR reader for the first card...")
    warm_up_ocr()
    inventory_database()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ScannerHandler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Card scanner is running at {url}")
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
