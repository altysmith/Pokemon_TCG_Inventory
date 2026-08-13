"""Permanent user-owned inventory stored separately from the card catalog."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS inventory_holdings (
    card_id TEXT PRIMARY KEY,
    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_events (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('scan_add', 'undo')),
    quantity_delta INTEGER NOT NULL CHECK(quantity_delta IN (-1, 1)),
    source_scan_id TEXT,
    related_event_id INTEGER UNIQUE REFERENCES inventory_events(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inventory_events_card
    ON inventory_events(card_id, id DESC);
"""


@dataclass(frozen=True)
class InventoryChange:
    card_id: str
    quantity: int
    event_id: int


class InventoryDatabase:
    """Own the mutable collection database and its auditable event history."""

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

    def quantity(self, card_id: str) -> int:
        value = card_id.strip()
        if not value or not self.path.is_file():
            return 0
        with self.connect() as connection:
            row = connection.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                (value,),
            ).fetchone()
        return int(row["quantity"]) if row else 0

    def add_card(self, card_id: str, *, scan_id: str = "") -> InventoryChange:
        value = card_id.strip()
        if not value:
            raise ValueError("A canonical card ID is required for inventory.")
        self.initialize()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO inventory_holdings(card_id, quantity)
                VALUES (?, 1)
                ON CONFLICT(card_id) DO UPDATE SET
                    quantity = quantity + 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (value,),
            )
            cursor = connection.execute(
                """
                INSERT INTO inventory_events(
                    card_id, action, quantity_delta, source_scan_id
                ) VALUES (?, 'scan_add', 1, ?)
                """,
                (value, scan_id.strip() or None),
            )
            quantity = connection.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                (value,),
            ).fetchone()["quantity"]
        return InventoryChange(value, int(quantity), int(cursor.lastrowid))

    def undo_add(self, event_id: int) -> InventoryChange:
        if event_id <= 0:
            raise ValueError("A valid inventory event is required to undo an addition.")
        if not self.path.is_file():
            raise ValueError("The inventory database has not been created yet.")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = connection.execute(
                """
                SELECT id, card_id, action, quantity_delta
                FROM inventory_events WHERE id = ?
                """,
                (event_id,),
            ).fetchone()
            if event is None or event["action"] != "scan_add":
                raise ValueError("That inventory addition cannot be undone.")
            already_undone = connection.execute(
                "SELECT 1 FROM inventory_events WHERE related_event_id = ?",
                (event_id,),
            ).fetchone()
            if already_undone:
                raise ValueError("That inventory addition was already undone.")
            card_id = str(event["card_id"])
            holding = connection.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                (card_id,),
            ).fetchone()
            if holding is None or int(holding["quantity"]) < 1:
                raise ValueError("The inventory quantity cannot be reduced further.")
            quantity = int(holding["quantity"]) - 1
            if quantity:
                connection.execute(
                    """
                    UPDATE inventory_holdings
                    SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE card_id = ?
                    """,
                    (quantity, card_id),
                )
            else:
                connection.execute(
                    "DELETE FROM inventory_holdings WHERE card_id = ?",
                    (card_id,),
                )
            cursor = connection.execute(
                """
                INSERT INTO inventory_events(
                    card_id, action, quantity_delta, related_event_id
                ) VALUES (?, 'undo', -1, ?)
                """,
                (card_id, event_id),
            )
        return InventoryChange(card_id, quantity, int(cursor.lastrowid))
