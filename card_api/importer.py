"""Normalize preserved Malie exports into the canonical SQLite catalog."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    DATABASE_PATH,
    MALIE_SOURCE_KEY,
    MALIE_SOURCE_NAME,
    RAW_ROOT,
)
from .database import CatalogDatabase
from .malie import read_manifest
from .validation import ValidationIssue, validate_card, validate_set


@dataclass(frozen=True)
class ImportResult:
    sets_imported: int
    cards_imported: int
    source_records_imported: int
    cards_rejected: int
    errors: int
    warnings: int


def import_downloaded(
    *,
    database_path: Path = DATABASE_PATH,
    raw_root: Path = RAW_ROOT,
    only_sets: set[str] | None = None,
) -> ImportResult:
    manifest = read_manifest(raw_root)
    database = CatalogDatabase(database_path)
    database.initialize()
    totals = {
        "sets": 0,
        "cards": 0,
        "source_records": 0,
        "rejected": 0,
        "errors": 0,
        "warnings": 0,
    }

    with database.connect() as connection:
        source_id = _ensure_source(connection)
        entries = sorted(
            manifest.get("sets", {}).items(),
            key=lambda item: (
                str(item[1].get("source_set_id", "")).casefold().endswith("alt"),
                item[0],
            ),
        )
        for key, entry in entries:
            source_set_id = str(entry.get("source_set_id", ""))
            if only_sets and source_set_id not in only_sets:
                continue
            _import_set(
                connection,
                source_id=source_id,
                raw_root=raw_root,
                source_set_id=source_set_id,
                entry=entry,
                totals=totals,
            )

    return ImportResult(
        sets_imported=totals["sets"],
        cards_imported=totals["cards"],
        source_records_imported=totals["source_records"],
        cards_rejected=totals["rejected"],
        errors=totals["errors"],
        warnings=totals["warnings"],
    )


def _ensure_source(connection) -> int:
    connection.execute(
        """
        INSERT INTO sources(source_key, name, homepage_url)
        VALUES (?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
            name=excluded.name,
            homepage_url=excluded.homepage_url
        """,
        (MALIE_SOURCE_KEY, MALIE_SOURCE_NAME, "https://malie.io/static/index.html"),
    )
    return int(
        connection.execute(
            "SELECT id FROM sources WHERE source_key = ?", (MALIE_SOURCE_KEY,)
        ).fetchone()["id"]
    )


def _import_set(
    connection,
    *,
    source_id: int,
    raw_root: Path,
    source_set_id: str,
    entry: dict,
    totals: dict[str, int],
) -> None:
    locale = str(entry.get("locale", ""))
    local_relative = str(entry.get("local_path", ""))
    local_path = raw_root / local_relative
    if not local_path.is_file():
        raise FileNotFoundError(f"Raw set export is missing: {local_path}")
    payload = local_path.read_bytes()
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if actual_sha256 != entry.get("sha256"):
        raise ValueError(f"Raw file hash mismatch: {local_path}")

    source_file_id = _ensure_source_file(
        connection,
        source_id=source_id,
        entry=entry,
        local_path=local_path,
        sha256=actual_sha256,
    )
    connection.execute(
        "DELETE FROM validation_issues WHERE source_file_id = ?", (source_file_id,)
    )

    set_issues = validate_set(
        {
            "name": entry.get("name"),
            "abbr": entry.get("abbr"),
            "path": entry.get("index_path"),
            "hash": entry.get("upstream_hash"),
            "num": entry.get("card_count"),
        },
        source_set_id,
    )
    _record_issues(
        connection,
        source_file_id=source_file_id,
        entity_type="set",
        entity_id=source_set_id,
        record_index=None,
        issues=set_issues,
        totals=totals,
    )
    if any(issue.severity == "error" for issue in set_issues):
        return

    cards = json.loads(payload)
    if not isinstance(cards, list):
        issue = ValidationIssue("error", "cards", "Set export root is not a list.")
        _record_issues(
            connection,
            source_file_id=source_file_id,
            entity_type="set",
            entity_id=source_set_id,
            record_index=None,
            issues=[issue],
            totals=totals,
        )
        return

    if source_set_id.casefold().endswith("alt"):
        old_set_id = f"{MALIE_SOURCE_KEY}:{locale}:{source_set_id}"
        connection.execute("DELETE FROM sets WHERE id = ?", (old_set_id,))
        _import_variant_bucket(
            connection,
            source_id=source_id,
            source_file_id=source_file_id,
            locale=locale,
            cards=cards,
            totals=totals,
        )
        connection.execute(
            "UPDATE source_files SET imported_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), source_file_id),
        )
        return

    set_id = f"{MALIE_SOURCE_KEY}:{locale}:{source_set_id}"
    set_code = str(entry["abbr"]).strip().upper()
    set_name = _plain_text(str(entry["name"])) or set_code or source_set_id
    release_date = _release_date(cards)
    connection.execute(
        """
        INSERT INTO sets(id, name, code, language, card_count, release_date, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            code=excluded.code,
            language=excluded.language,
            card_count=excluded.card_count,
            release_date=excluded.release_date,
            updated_at=CURRENT_TIMESTAMP
        """,
        (set_id, set_name, set_code, locale, entry.get("card_count"), release_date),
    )
    connection.execute(
        """
        INSERT INTO set_sources(source_id, source_set_id, language, set_id, source_file_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_set_id, language) DO UPDATE SET
            set_id=excluded.set_id,
            source_file_id=excluded.source_file_id
        """,
        (source_id, source_set_id, locale, set_id, source_file_id),
    )
    connection.execute("DELETE FROM set_codes WHERE set_id = ?", (set_id,))
    connection.execute(
        "INSERT INTO set_codes(set_id, code, code_type) VALUES (?, ?, 'source-abbreviation')",
        (set_id, set_code),
    )
    for printed_code in sorted({_printed_set_code(card) for card in cards} - {""}):
        connection.execute(
            """
            INSERT INTO set_codes(set_id, code, code_type)
            VALUES (?, ?, 'printed')
            ON CONFLICT(set_id, code) DO NOTHING
            """,
            (set_id, printed_code),
        )
    connection.execute("DELETE FROM cards WHERE set_id = ?", (set_id,))

    seen_numbers: set[str] = set()
    for record_index, card in enumerate(cards):
        issues = validate_card(card)
        collector = card.get("collector_number", {}) if isinstance(card, dict) else {}
        number = str(collector.get("numerator", "")).strip()
        source_card_id = _source_card_id(card) if isinstance(card, dict) else ""
        if not source_card_id:
            issues.append(ValidationIssue("error", "ext.tcgl.cardID", "Source card ID is missing."))
        entity_id = source_card_id or f"record:{record_index}"
        _record_issues(
            connection,
            source_file_id=source_file_id,
            entity_type="card",
            entity_id=entity_id,
            record_index=record_index,
            issues=issues,
            totals=totals,
        )
        if any(issue.severity == "error" for issue in issues):
            totals["rejected"] += 1
            continue
        if number in seen_numbers:
            card_id = f"{set_id}:{number}"
            if not _same_canonical_card(connection, card_id, card):
                conflict = ValidationIssue(
                    "error",
                    "collector_number.numerator",
                    "Duplicate card number has conflicting canonical card data.",
                )
                _record_issues(
                    connection,
                    source_file_id=source_file_id,
                    entity_type="card",
                    entity_id=entity_id,
                    record_index=record_index,
                    issues=[conflict],
                    totals=totals,
                )
                totals["rejected"] += 1
                continue
            _insert_source_variant(
                connection,
                source_id=source_id,
                source_file_id=source_file_id,
                card_id=card_id,
                record_index=record_index,
                card=card,
                source_card_id=source_card_id,
            )
            totals["source_records"] += 1
            continue
        seen_numbers.add(number)
        _insert_card(
            connection,
            source_id=source_id,
            source_file_id=source_file_id,
            set_id=set_id,
            locale=locale,
            record_index=record_index,
            card=card,
            source_card_id=source_card_id,
            has_warnings=any(issue.severity == "warning" for issue in issues),
        )
        totals["cards"] += 1
        totals["source_records"] += 1

    connection.execute(
        "UPDATE source_files SET imported_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), source_file_id),
    )
    totals["sets"] += 1


def _ensure_source_file(connection, *, source_id: int, entry: dict, local_path: Path, sha256: str) -> int:
    connection.execute(
        """
        INSERT INTO source_files(
            source_id, source_url, local_path, locale, upstream_hash, sha256, downloaded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_url, sha256) DO UPDATE SET
            local_path=excluded.local_path,
            upstream_hash=excluded.upstream_hash
        """,
        (
            source_id,
            entry.get("source_url"),
            str(local_path.resolve()),
            entry.get("locale"),
            entry.get("upstream_hash"),
            sha256,
            entry.get("downloaded_at"),
        ),
    )
    return int(
        connection.execute(
            """
            SELECT id FROM source_files
            WHERE source_id = ? AND source_url = ? AND sha256 = ?
            """,
            (source_id, entry.get("source_url"), sha256),
        ).fetchone()["id"]
    )


def _insert_card(
    connection,
    *,
    source_id: int,
    source_file_id: int,
    set_id: str,
    locale: str,
    record_index: int,
    card: dict,
    source_card_id: str,
    has_warnings: bool,
) -> None:
    collector = card["collector_number"]
    number = str(collector["numerator"]).strip()
    card_id = f"{set_id}:{number}"
    images = list(_images(card))
    primary_image = next(
        (item[3] for item in images if item[0] == "jpg" and item[1] == "front"),
        images[0][3] if images else None,
    )
    rarity = card.get("rarity")
    rarity_name = rarity.get("designation") if isinstance(rarity, dict) else None
    connection.execute(
        """
        INSERT INTO cards(
            id, set_id, language, name, card_type, number, number_numeric,
            printed_total, hp, regulation_mark, rarity, stage,
            primary_image_url, validation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            card_id,
            set_id,
            locale,
            card["name"].strip(),
            card.get("card_type"),
            number,
            collector.get("numeric"),
            collector.get("denominator"),
            card.get("hp"),
            card.get("regulation_mark"),
            rarity_name,
            card.get("stage"),
            primary_image,
            "warning" if has_warnings else "valid",
        ),
    )
    _insert_source_variant(
        connection,
        source_id=source_id,
        source_file_id=source_file_id,
        card_id=card_id,
        record_index=record_index,
        card=card,
        source_card_id=source_card_id,
    )
    for position, text_entry in enumerate(card.get("text") or []):
        damage = text_entry.get("damage")
        connection.execute(
            """
            INSERT INTO card_text_entries(
                card_id, position, kind, name, text, cost_json,
                damage_amount, damage_suffix, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                position,
                text_entry["kind"],
                text_entry.get("name"),
                text_entry.get("text"),
                json.dumps(text_entry.get("cost"), ensure_ascii=False)
                if "cost" in text_entry
                else None,
                damage.get("amount") if isinstance(damage, dict) else None,
                damage.get("suffix") if isinstance(damage, dict) else None,
                json.dumps(text_entry, ensure_ascii=False, sort_keys=True),
            ),
        )
    for image_format, face, variant, url in images:
        connection.execute(
            """
            INSERT INTO card_images(
                card_id, source_id, image_format, face, variant, url
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (card_id, source_id, image_format, face, variant, url),
        )


def _insert_source_variant(
    connection,
    *,
    source_id: int,
    source_file_id: int,
    card_id: str,
    record_index: int,
    card: dict,
    source_card_id: str,
) -> None:
    canonical = json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    connection.execute(
        """
        INSERT INTO card_sources(
            source_id, source_card_id, card_id, source_file_id,
            raw_record_index, record_sha256
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            source_card_id,
            card_id,
            source_file_id,
            record_index,
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        ),
    )
    tcgl = card.get("ext", {}).get("tcgl", {})
    foil = card.get("foil") if isinstance(card.get("foil"), dict) else {}
    images = list(_images(card))
    primary_image = next(
        (item[3] for item in images if item[0] == "jpg" and item[1] == "front"),
        images[0][3] if images else None,
    )
    connection.execute(
        """
        INSERT INTO card_variants(
            card_id, source_id, source_file_id, source_card_id, long_form_id,
            finish_type, finish_mask, primary_image_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            card_id,
            source_id,
            source_file_id,
            source_card_id,
            tcgl.get("longFormID"),
            foil.get("type"),
            foil.get("mask"),
            primary_image,
        ),
    )
    variant_id = connection.execute(
        "SELECT id FROM card_variants WHERE source_id = ? AND source_card_id = ?",
        (source_id, source_card_id),
    ).fetchone()["id"]
    for image_format, face, layer, url in images:
        connection.execute(
            """
            INSERT INTO card_variant_images(
                variant_id, image_format, face, layer, url
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (variant_id, image_format, face, layer, url),
        )


def _import_variant_bucket(
    connection,
    *,
    source_id: int,
    source_file_id: int,
    locale: str,
    cards: list,
    totals: dict[str, int],
) -> None:
    """Attach Malie's cross-set alternate-art records to their printed sets."""
    for record_index, card in enumerate(cards):
        issues = validate_card(card)
        source_card_id = _source_card_id(card) if isinstance(card, dict) else ""
        if not source_card_id:
            issues.append(ValidationIssue("error", "ext.tcgl.cardID", "Source card ID is missing."))
        set_code = _printed_set_code(card) if isinstance(card, dict) else ""
        if not set_code:
            issues.append(ValidationIssue("error", "set_icon", "Printed set code is missing."))
        collector = card.get("collector_number", {}) if isinstance(card, dict) else {}
        number = str(collector.get("numerator", "")).strip()
        matches = connection.execute(
            """
            SELECT DISTINCT s.id
            FROM sets s JOIN set_codes sc ON sc.set_id = s.id
            WHERE sc.code = ? COLLATE NOCASE AND s.language = ?
            """,
            (set_code, locale),
        ).fetchall()
        if len(matches) != 1:
            issues.append(
                ValidationIssue(
                    "error",
                    "set_icon",
                    f"Printed set code resolves to {len(matches)} canonical sets.",
                )
            )
        card_id = f"{matches[0]['id']}:{number}" if len(matches) == 1 else ""
        if card_id and not _same_canonical_card(connection, card_id, card):
            issues.append(
                ValidationIssue(
                    "error",
                    "collector_number.numerator",
                    "Alternate record does not match the canonical set-and-number card.",
                )
            )
        entity_id = source_card_id or f"record:{record_index}"
        _record_issues(
            connection,
            source_file_id=source_file_id,
            entity_type="card_variant",
            entity_id=entity_id,
            record_index=record_index,
            issues=issues,
            totals=totals,
        )
        if any(issue.severity == "error" for issue in issues):
            totals["rejected"] += 1
            continue
        _insert_source_variant(
            connection,
            source_id=source_id,
            source_file_id=source_file_id,
            card_id=card_id,
            record_index=record_index,
            card=card,
            source_card_id=source_card_id,
        )
        totals["source_records"] += 1


def _same_canonical_card(connection, card_id: str, card: dict) -> bool:
    row = connection.execute(
        "SELECT name, card_type, hp, printed_total FROM cards WHERE id = ?", (card_id,)
    ).fetchone()
    collector = card.get("collector_number", {})
    return row is not None and (
        row["name"],
        row["card_type"],
        row["hp"],
        row["printed_total"],
    ) == (
        card.get("name"),
        card.get("card_type"),
        card.get("hp"),
        collector.get("denominator"),
    )


def _record_issues(
    connection,
    *,
    source_file_id: int,
    entity_type: str,
    entity_id: str,
    record_index: int | None,
    issues: list[ValidationIssue],
    totals: dict[str, int],
) -> None:
    for issue in issues:
        connection.execute(
            """
            INSERT INTO validation_issues(
                source_file_id, entity_type, entity_id, record_index,
                severity, field, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_file_id,
                entity_type,
                entity_id,
                record_index,
                issue.severity,
                issue.field,
                issue.message,
            ),
        )
        totals["errors" if issue.severity == "error" else "warnings"] += 1


def _source_card_id(card: dict) -> str:
    ext = card.get("ext")
    tcgl = ext.get("tcgl") if isinstance(ext, dict) else None
    return str(tcgl.get("cardID", "")).strip() if isinstance(tcgl, dict) else ""


def _printed_set_code(card: dict) -> str:
    icon = card.get("set_icon")
    if not isinstance(icon, str):
        return ""
    return re.sub(r"_[A-Z]{2,5}$", "", icon.strip().upper())


def _release_date(cards: list) -> str | None:
    dates: list[str] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        tcgl = card.get("ext", {}).get("tcgl", {})
        value = tcgl.get("reldate") if isinstance(tcgl, dict) else None
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", value):
            dates.append(value[:10])
    return min(dates) if dates else None


def _images(card: dict):
    images = card.get("images")
    if not isinstance(images, dict):
        return
    for _source_name, formats in images.items():
        if not isinstance(formats, dict):
            continue
        for image_format, faces in formats.items():
            if not isinstance(faces, dict):
                continue
            for face_or_variant, url in faces.items():
                if not isinstance(url, str):
                    continue
                if face_or_variant in {"front", "back"}:
                    face, variant = face_or_variant, "front"
                else:
                    face, variant = "front", face_or_variant
                yield str(image_format), face, variant, url


def _plain_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()
