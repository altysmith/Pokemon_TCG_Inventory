"""Stable, human-readable collection export formats for future re-import."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime


EXPORT_SCHEMA = "pokemon-card-collection"
EXPORT_SCHEMA_VERSION = 1
CSV_FIELDS = (
    "schema",
    "schema_version",
    "card_id",
    "quantity",
    "name",
    "set_name",
    "set_code",
    "number",
    "printed_total",
    "card_type",
    "card_subtype",
    "types",
    "regulation_mark",
    "rarity",
    "date_added",
    "date_updated",
)
CARD_TEXT_FIELDS = (
    "name",
    "set_name",
    "set_code",
    "number",
    "printed_total",
    "card_type",
    "card_subtype",
    "regulation_mark",
    "rarity",
    "date_added",
    "date_updated",
)


def build_collection_export(snapshot: dict, exported_at: str | None = None) -> dict:
    """Return the versioned canonical export shared by JSON and CSV."""
    exported_at = exported_at or datetime.now().astimezone().isoformat(timespec="seconds")
    cards = []
    for item in snapshot.get("items", []):
        cards.append(
            {
                "card_id": item["id"],
                "quantity": int(item["quantity"]),
                "name": item.get("name", ""),
                "set_name": item.get("set_name", ""),
                "set_code": item.get("set_code", ""),
                "number": item.get("number", ""),
                "printed_total": item.get("printed_total", ""),
                "card_type": item.get("card_type", ""),
                "card_subtype": item.get("card_subtype", ""),
                "types": list(item.get("types", [])),
                "regulation_mark": item.get("regulation_mark", ""),
                "rarity": item.get("rarity", ""),
                "date_added": item.get("date_added", ""),
                "date_updated": item.get("date_updated", ""),
            }
        )
    return {
        "schema": EXPORT_SCHEMA,
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": exported_at,
        "application": "Pokemon Card Collection",
        "summary": {
            "unique_cards": len(cards),
            "total_copies": sum(card["quantity"] for card in cards),
        },
        "cards": cards,
    }


def render_collection_json(payload: dict) -> bytes:
    """Serialize an import-safe JSON export without escaping card names."""
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def render_collection_csv(payload: dict) -> bytes:
    """Serialize the same records as an Excel-friendly UTF-8 CSV export."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for card in payload.get("cards", []):
        writer.writerow(
            {
                "schema": payload["schema"],
                "schema_version": payload["schema_version"],
                **card,
                "types": "|".join(card.get("types", [])),
            }
        )
    return output.getvalue().encode("utf-8-sig")


def _validated_import_payload(
    schema: object,
    schema_version: object,
    cards: object,
    exported_at: object = "",
) -> dict:
    if schema != EXPORT_SCHEMA:
        raise ValueError("This is not a Pokemon Card Collection export.")
    try:
        version = int(schema_version)
    except (TypeError, ValueError) as exc:
        raise ValueError("The collection export has no valid schema version.") from exc
    if version != EXPORT_SCHEMA_VERSION:
        raise ValueError(f"Collection export version {version} is not supported.")
    if not isinstance(cards, list):
        raise ValueError("The collection export must contain a card list.")

    normalized_cards = []
    seen_ids = set()
    for position, card in enumerate(cards, start=1):
        if not isinstance(card, dict):
            raise ValueError(f"Collection row {position} is invalid.")
        card_id = str(card.get("card_id", "")).strip()
        if not card_id:
            raise ValueError(f"Collection row {position} has no canonical card ID.")
        if card_id in seen_ids:
            raise ValueError(f"Canonical card ID {card_id} appears more than once.")
        try:
            quantity = int(card.get("quantity", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Collection row {position} has an invalid quantity.") from exc
        if isinstance(card.get("quantity"), bool) or not 1 <= quantity <= 9999:
            raise ValueError(f"Collection row {position} quantity must be from 1 to 9999.")
        raw_types = card.get("types", [])
        if isinstance(raw_types, str):
            types = [value.strip() for value in raw_types.split("|") if value.strip()]
        elif isinstance(raw_types, list):
            types = [str(value).strip() for value in raw_types if str(value).strip()]
        else:
            raise ValueError(f"Collection row {position} has invalid card types.")
        normalized = {"card_id": card_id, "quantity": quantity}
        normalized.update({field: str(card.get(field, "")) for field in CARD_TEXT_FIELDS})
        normalized["types"] = types
        normalized_cards.append(normalized)
        seen_ids.add(card_id)

    return {
        "schema": EXPORT_SCHEMA,
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": str(exported_at or ""),
        "application": "Pokemon Card Collection",
        "summary": {
            "unique_cards": len(normalized_cards),
            "total_copies": sum(card["quantity"] for card in normalized_cards),
        },
        "cards": normalized_cards,
    }


def parse_collection_json(content: bytes | str) -> dict:
    """Parse and validate JSON without changing inventory."""
    try:
        payload = json.loads(content.decode("utf-8-sig") if isinstance(content, bytes) else content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("The JSON collection export could not be read.") from exc
    if not isinstance(payload, dict):
        raise ValueError("The JSON collection export must be an object.")
    return _validated_import_payload(
        payload.get("schema"),
        payload.get("schema_version"),
        payload.get("cards"),
        payload.get("exported_at", ""),
    )


def parse_collection_csv(content: bytes | str) -> dict:
    """Parse and validate CSV without changing inventory."""
    try:
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if not reader.fieldnames or not set(CSV_FIELDS).issubset(reader.fieldnames):
            raise ValueError("The CSV collection export is missing required columns.")
        rows = list(reader)
    except UnicodeDecodeError as exc:
        raise ValueError("The CSV collection export must use UTF-8 text.") from exc
    if not rows:
        return _validated_import_payload(EXPORT_SCHEMA, EXPORT_SCHEMA_VERSION, [])
    for position, row in enumerate(rows, start=1):
        if row.get("schema") != EXPORT_SCHEMA:
            raise ValueError(f"CSV row {position} is not a Pokemon Card Collection export.")
        if row.get("schema_version") != str(EXPORT_SCHEMA_VERSION):
            raise ValueError(f"CSV row {position} uses an unsupported schema version.")
    return _validated_import_payload(EXPORT_SCHEMA, EXPORT_SCHEMA_VERSION, rows)
