"""Export a frozen collection showcase without modifying either database."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path


SHOWCASE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SHOWCASE_ROOT.parent
INVENTORY_PATH = PROJECT_ROOT / "user_data" / "inventory.sqlite3"
CATALOG_PATH = PROJECT_ROOT / "data" / "card_catalog.sqlite3"
OUTPUT_PATH = SHOWCASE_ROOT / "inventory_snapshot.js"


def readonly_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"Required database is missing: {path}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def export_snapshot() -> dict:
    with readonly_connection(INVENTORY_PATH) as inventory:
        holdings = inventory.execute(
            """
            SELECT card_id, quantity, created_at, updated_at
            FROM inventory_holdings
            WHERE quantity > 0
            ORDER BY card_id
            """
        ).fetchall()

    if not holdings:
        return {"ok": True, "items": [], "unique_cards": 0, "total_copies": 0}

    by_id = {str(row["card_id"]): row for row in holdings}
    placeholders = ",".join("?" for _ in by_id)
    with readonly_connection(CATALOG_PATH) as catalog:
        cards = catalog.execute(
            f"""
            SELECT c.id, c.name, c.card_type,
                   COALESCE(c.card_subtype, '') AS card_subtype,
                   c.number, c.number_numeric,
                   COALESCE(c.printed_total, '') AS printed_total,
                   COALESCE(c.regulation_mark, '') AS regulation_mark,
                   COALESCE(c.primary_image_url, '') AS image_url,
                   s.name AS set_name, s.code AS set_code
            FROM cards c
            JOIN sets s ON s.id = c.set_id
            WHERE c.id IN ({placeholders})
            """,
            list(by_id),
        ).fetchall()
        type_rows = catalog.execute(
            f"""
            SELECT card_id, type
            FROM card_types
            WHERE card_id IN ({placeholders})
            ORDER BY card_id, position
            """,
            list(by_id),
        ).fetchall()

    types_by_card: dict[str, list[str]] = defaultdict(list)
    for row in type_rows:
        types_by_card[str(row["card_id"])].append(str(row["type"]))

    items = []
    for card in cards:
        item = dict(card)
        holding = by_id[str(card["id"])]
        item["quantity"] = int(holding["quantity"])
        item["date_added"] = str(holding["created_at"])
        item["date_updated"] = str(holding["updated_at"])
        item["types"] = types_by_card[str(card["id"])]
        subtype = str(item["card_subtype"])
        item["display_subtype"] = (
            f"{subtype.title()} Energy"
            if item["card_type"] == "ENERGY" and subtype
            else subtype.title()
        )
        items.append(item)

    missing = sorted(set(by_id) - {str(item["id"]) for item in items})
    if missing:
        raise RuntimeError(
            f"The catalog could not resolve {len(missing)} owned card ID(s); "
            "the snapshot was not replaced."
        )

    items.sort(key=lambda item: (str(item["name"]).casefold(), str(item["set_name"]).casefold(), str(item["number"])))
    return {
        "ok": True,
        "items": items,
        "unique_cards": len(items),
        "total_copies": sum(int(item["quantity"]) for item in items),
    }


def main() -> None:
    snapshot = export_snapshot()
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    OUTPUT_PATH.write_text(
        "// Generated read-only collection snapshot.\n"
        f"window.COLLECTION_SHOWCASE = {payload};\n",
        encoding="utf-8",
    )
    print(
        f"Exported {snapshot['unique_cards']} unique cards and "
        f"{snapshot['total_copies']} total copies to {OUTPUT_PATH}."
    )


if __name__ == "__main__":
    main()
