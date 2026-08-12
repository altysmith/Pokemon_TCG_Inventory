"""SQLite schema and query helpers for canonical card data."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    homepage_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    source_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    locale TEXT,
    upstream_hash TEXT,
    sha256 TEXT NOT NULL,
    downloaded_at TEXT NOT NULL,
    imported_at TEXT,
    UNIQUE(source_id, source_url, sha256)
);

CREATE TABLE IF NOT EXISTS sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL COLLATE NOCASE,
    language TEXT NOT NULL,
    card_count INTEGER,
    release_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS set_sources (
    source_id INTEGER NOT NULL REFERENCES sources(id),
    source_set_id TEXT NOT NULL,
    language TEXT NOT NULL,
    set_id TEXT NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
    source_file_id INTEGER REFERENCES source_files(id),
    PRIMARY KEY(source_id, source_set_id, language)
);

CREATE TABLE IF NOT EXISTS set_codes (
    set_id TEXT NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
    code TEXT NOT NULL COLLATE NOCASE,
    code_type TEXT NOT NULL,
    PRIMARY KEY(set_id, code)
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    set_id TEXT NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
    language TEXT NOT NULL,
    name TEXT NOT NULL,
    card_type TEXT,
    number TEXT NOT NULL,
    number_numeric INTEGER,
    printed_total TEXT,
    hp INTEGER,
    regulation_mark TEXT,
    rarity TEXT,
    stage TEXT,
    primary_image_url TEXT,
    validation_status TEXT NOT NULL DEFAULT 'valid',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(set_id, language, number)
);

CREATE TABLE IF NOT EXISTS card_sources (
    source_id INTEGER NOT NULL REFERENCES sources(id),
    source_card_id TEXT NOT NULL,
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id),
    raw_record_index INTEGER NOT NULL,
    record_sha256 TEXT NOT NULL,
    PRIMARY KEY(source_id, source_card_id)
);

CREATE TABLE IF NOT EXISTS card_variants (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    source_file_id INTEGER NOT NULL REFERENCES source_files(id),
    source_card_id TEXT NOT NULL,
    long_form_id TEXT,
    finish_type TEXT,
    finish_mask TEXT,
    primary_image_url TEXT,
    UNIQUE(source_id, source_card_id)
);

CREATE TABLE IF NOT EXISTS card_variant_images (
    id INTEGER PRIMARY KEY,
    variant_id INTEGER NOT NULL REFERENCES card_variants(id) ON DELETE CASCADE,
    image_format TEXT NOT NULL,
    face TEXT NOT NULL,
    layer TEXT NOT NULL,
    url TEXT NOT NULL,
    UNIQUE(variant_id, image_format, face, layer)
);

CREATE TABLE IF NOT EXISTS card_text_entries (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    kind TEXT NOT NULL,
    name TEXT,
    text TEXT,
    cost_json TEXT,
    damage_amount INTEGER,
    damage_suffix TEXT,
    raw_json TEXT NOT NULL,
    UNIQUE(card_id, position)
);

CREATE TABLE IF NOT EXISTS card_images (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    image_format TEXT NOT NULL,
    face TEXT NOT NULL,
    variant TEXT NOT NULL DEFAULT 'front',
    url TEXT NOT NULL,
    UNIQUE(card_id, source_id, image_format, face, variant)
);

CREATE TABLE IF NOT EXISTS validation_issues (
    id INTEGER PRIMARY KEY,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id),
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    record_index INTEGER,
    severity TEXT NOT NULL CHECK(severity IN ('error', 'warning')),
    field TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sets_code ON sets(code);
CREATE INDEX IF NOT EXISTS idx_set_codes_code ON set_codes(code);
CREATE INDEX IF NOT EXISTS idx_cards_set_number ON cards(set_id, number_numeric, number);
CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_validation_file ON validation_issues(source_file_id);
"""


class CatalogDatabase:
    """Own connections and schema creation for the canonical catalog only."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
