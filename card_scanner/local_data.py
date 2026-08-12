"""Project-local card catalog cache and future inventory storage."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from .lookup import CardInfo
from .parser import normalize_card_number


class ScannerData:
    """Own all persistent card data for this scanner project."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS card_catalog (
                    set_code TEXT NOT NULL COLLATE NOCASE,
                    card_number TEXT NOT NULL,
                    set_name TEXT NOT NULL,
                    card_name TEXT NOT NULL,
                    set_id TEXT,
                    printed_total TEXT,
                    image_url TEXT,
                    source TEXT NOT NULL,
                    verified INTEGER NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (set_code, card_number)
                );

                CREATE TABLE IF NOT EXISTS inventory (
                    set_code TEXT NOT NULL COLLATE NOCASE,
                    card_number TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (set_code, card_number),
                    FOREIGN KEY (set_code, card_number)
                        REFERENCES card_catalog(set_code, card_number)
                );
                """
            )

    def find_card(self, set_code: str, card_number: str) -> CardInfo:
        code = set_code.strip().upper()
        number = normalize_card_number(card_number)
        if not code or not number:
            return CardInfo()
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT set_code, set_name, card_name, card_number, set_id,
                       source, printed_total, image_url, verified
                FROM card_catalog
                WHERE set_code = ? COLLATE NOCASE AND card_number = ?
                """,
                (code, number),
            ).fetchone()
        if row is None:
            return CardInfo()
        return CardInfo(
            set_code=row["set_code"],
            set_name=row["set_name"],
            card_name=row["card_name"],
            card_number=row["card_number"],
            set_id=row["set_id"] or "",
            source=(
                "verified local catalog"
                if row["verified"]
                else f"local cache ({row['source']})"
            ),
            printed_total=row["printed_total"] or "",
            image_url=row["image_url"] or "",
            status="accepted",
        )

    def cache_card(self, card: CardInfo, verified: bool = False) -> None:
        if not card.card_name or not card.set_code or not card.card_number:
            return
        values = asdict(card)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO card_catalog (
                    set_code, card_number, set_name, card_name, set_id,
                    printed_total, image_url, source, verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(set_code, card_number) DO UPDATE SET
                    set_name=excluded.set_name,
                    card_name=excluded.card_name,
                    set_id=excluded.set_id,
                    printed_total=excluded.printed_total,
                    image_url=excluded.image_url,
                    source=CASE WHEN card_catalog.verified = 1
                                THEN card_catalog.source ELSE excluded.source END,
                    verified=MAX(card_catalog.verified, excluded.verified),
                    last_updated=CURRENT_TIMESTAMP
                """,
                (
                    values["set_code"].upper(),
                    normalize_card_number(values["card_number"]),
                    values["set_name"],
                    values["card_name"],
                    values["set_id"],
                    values["printed_total"],
                    values["image_url"],
                    values["source"],
                    int(verified),
                ),
            )
