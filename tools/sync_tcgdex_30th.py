"""Import the English 30th Celebration set into the local Collection catalog.

The normal catalog source does not yet publish this released set.  This tool
uses TCGdex's English set and card endpoints, retains the exact response as a
local source snapshot, and writes only reference-catalog tables.  Inventory
and account data are not touched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from card_api.config import DATABASE_PATH, PROJECT_ROOT
from card_api.database import CatalogDatabase


API_ROOT = "https://api.tcgdex.net/v2/en"
SET_CODE = "30C"
SET_SLUG = "30th"
SET_ID = "tcgdex:en-US:30th"
SOURCE_KEY = "tcgdex"
SOURCE_URL = f"{API_ROOT}/sets/{SET_SLUG}"


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Pokemon-Collection/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object from {url}")
    return value


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == payload:
            return
        path = path.with_name(f"{path.stem}-{hashlib.sha256(payload).hexdigest()[:12]}{path.suffix}")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(payload)
        temporary.flush()
        temporary_name = temporary.name
    Path(temporary_name).replace(path)


def category(value: object) -> str:
    normalized = str(value).upper()
    if normalized == "POKEMON":
        return "POKEMON"
    if normalized == "TRAINER":
        return "TRAINER"
    if normalized == "ENERGY":
        return "ENERGY"
    raise ValueError(f"Unsupported TCGdex card category: {value!r}")


def image_url(card: dict) -> str:
    """Turn TCGdex's image base URL into a browser-displayable card image."""
    base_url = str(card.get("image", "")).rstrip("/")
    if not base_url.startswith("https://assets.tcgdex.net/"):
        raise ValueError(f"TCGdex card image URL is invalid: {base_url!r}")
    return f"{base_url}/high.webp"


def sync(database_path: Path, raw_root: Path) -> tuple[int, Path]:
    set_payload = fetch_json(SOURCE_URL)
    if set_payload.get("id") != SET_SLUG or set_payload.get("name") != "30th Celebration":
        raise ValueError("TCGdex did not return the expected 30th Celebration set")
    if set_payload.get("abbreviation", {}).get("official") != SET_CODE:
        raise ValueError("TCGdex did not return the expected printed set code 30C")

    summaries = set_payload.get("cards")
    if not isinstance(summaries, list) or len(summaries) != 158:
        raise ValueError("TCGdex did not return the expected 158-card 30th Celebration list")
    cards = [fetch_json(f"{API_ROOT}/cards/{item['id']}") for item in summaries]
    if any(card.get("set", {}).get("id") != SET_SLUG for card in cards):
        raise ValueError("A downloaded card did not belong to 30th Celebration")

    snapshot = {
        "source_url": SOURCE_URL,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "set": set_payload,
        "cards": cards,
    }
    payload = (json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    snapshot_path = raw_root / SET_SLUG / f"{digest}.json"
    atomic_write(snapshot_path, payload)

    database = CatalogDatabase(database_path)
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO sources(source_key, name, homepage_url)
            VALUES (?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET name=excluded.name, homepage_url=excluded.homepage_url
            """,
            (SOURCE_KEY, "TCGdex", "https://tcgdex.dev/"),
        )
        source_id = connection.execute(
            "SELECT id FROM sources WHERE source_key = ?", (SOURCE_KEY,)
        ).fetchone()["id"]
        connection.execute(
            """
            INSERT INTO source_files(source_id, source_url, local_path, locale, sha256, downloaded_at)
            VALUES (?, ?, ?, 'en-US', ?, ?)
            ON CONFLICT(source_id, source_url, sha256) DO UPDATE SET local_path=excluded.local_path
            """,
            (source_id, SOURCE_URL, str(snapshot_path.resolve()), digest, snapshot["downloaded_at"]),
        )
        source_file_id = connection.execute(
            "SELECT id FROM source_files WHERE source_id = ? AND source_url = ? AND sha256 = ?",
            (source_id, SOURCE_URL, digest),
        ).fetchone()["id"]

        connection.execute("DELETE FROM sets WHERE id = ?", (SET_ID,))
        connection.execute(
            """
            INSERT INTO sets(id, name, code, language, card_count, release_date)
            VALUES (?, ?, ?, 'en-US', ?, ?)
            """,
            (SET_ID, set_payload["name"], SET_CODE, len(cards), set_payload.get("releaseDate")),
        )
        connection.execute(
            "INSERT INTO set_sources(source_id, source_set_id, language, set_id, source_file_id) VALUES (?, ?, 'en-US', ?, ?)",
            (source_id, SET_SLUG, SET_ID, source_file_id),
        )
        connection.execute(
            "INSERT INTO set_codes(set_id, code, code_type) VALUES (?, ?, 'printed')",
            (SET_ID, SET_CODE),
        )
        for position, card in enumerate(cards):
            card_id = str(card["id"])
            number = str(card["localId"])
            card_type = category(card.get("category"))
            subtype = card.get("trainerType") if card_type == "TRAINER" else None
            connection.execute(
                """
                INSERT INTO cards(
                    id, set_id, language, name, card_type, card_subtype, number, number_numeric,
                    printed_total, hp, rarity, stage, primary_image_url
                ) VALUES (?, ?, 'en-US', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{SET_ID}:{number}", SET_ID, card["name"], card_type, subtype, number,
                    int(number) if number.isdigit() else None,
                    str(set_payload["cardCount"]["official"]), card.get("hp"), card.get("rarity"),
                    card.get("stage"), image_url(card),
                ),
            )
            for type_position, card_type_name in enumerate(card.get("types") or []):
                connection.execute(
                    "INSERT INTO card_types(card_id, position, type) VALUES (?, ?, ?)",
                    (f"{SET_ID}:{number}", type_position, card_type_name),
                )
            record_hash = hashlib.sha256(
                json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            connection.execute(
                """
                INSERT INTO card_sources(source_id, source_card_id, card_id, source_file_id, raw_record_index, record_sha256)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source_id, card_id, f"{SET_ID}:{number}", source_file_id, position, record_hash),
            )
            connection.execute(
                "INSERT INTO card_images(card_id, source_id, image_format, face, variant, url) VALUES (?, ?, 'webp', 'front', 'front', ?)",
                (f"{SET_ID}:{number}", source_id, image_url(card)),
            )
    return len(cards), snapshot_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the TCGdex 30th Celebration set.")
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--raw-root", type=Path, default=PROJECT_ROOT / "data" / "raw" / "tcgdex")
    args = parser.parse_args()
    count, snapshot_path = sync(args.database, args.raw_root)
    print(f"Imported {count} cards from 30th Celebration; snapshot: {snapshot_path}")


if __name__ == "__main__":
    main()
