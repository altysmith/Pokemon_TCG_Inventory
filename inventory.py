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
    quantity_delta INTEGER NOT NULL CHECK(quantity_delta != 0),
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
    quantity_delta: int


class InventoryDatabase:
    """Own the mutable collection database and its auditable event history."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate_batch_quantities(connection)

    @staticmethod
    def _migrate_batch_quantities(connection: sqlite3.Connection) -> None:
        """Replace the Iteration 7 one-copy event constraint in place."""
        row = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'inventory_events'
            """
        ).fetchone()
        table_sql = str(row["sql"] if row else "")
        if "quantity_delta IN (-1, 1)" not in table_sql:
            return
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            DROP INDEX IF EXISTS idx_inventory_events_card;
            ALTER TABLE inventory_events RENAME TO inventory_events_legacy;
            CREATE TABLE inventory_events (
                id INTEGER PRIMARY KEY,
                card_id TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('scan_add', 'undo')),
                quantity_delta INTEGER NOT NULL CHECK(quantity_delta != 0),
                source_scan_id TEXT,
                related_event_id INTEGER UNIQUE REFERENCES inventory_events(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO inventory_events(
                id, card_id, action, quantity_delta, source_scan_id,
                related_event_id, created_at
            )
            SELECT id, card_id, action, quantity_delta, source_scan_id,
                   related_event_id, created_at
            FROM inventory_events_legacy;
            DROP TABLE inventory_events_legacy;
            CREATE INDEX idx_inventory_events_card
                ON inventory_events(card_id, id DESC);
            COMMIT;
            """
        )
        connection.execute("PRAGMA foreign_keys = ON")

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

    def add_cards(
        self,
        card_id: str,
        quantity: int,
        *,
        scan_id: str = "",
    ) -> InventoryChange:
        value = card_id.strip()
        if not value:
            raise ValueError("A canonical card ID is required for inventory.")
        if quantity < 1 or quantity > 99:
            raise ValueError("Inventory quantity must be between 1 and 99.")
        added_quantity = quantity
        self.initialize()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO inventory_holdings(card_id, quantity)
                VALUES (?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    quantity = inventory_holdings.quantity + excluded.quantity,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (value, added_quantity),
            )
            cursor = connection.execute(
                """
                INSERT INTO inventory_events(
                    card_id, action, quantity_delta, source_scan_id
                ) VALUES (?, 'scan_add', ?, ?)
                """,
                (value, added_quantity, scan_id.strip() or None),
            )
            quantity = connection.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                (value,),
            ).fetchone()["quantity"]
        return InventoryChange(
            value,
            int(quantity),
            int(cursor.lastrowid),
            added_quantity,
        )

    def add_card(self, card_id: str, *, scan_id: str = "") -> InventoryChange:
        """Compatibility helper for callers that add exactly one copy."""
        return self.add_cards(card_id, 1, scan_id=scan_id)

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
            added_quantity = int(event["quantity_delta"])
            holding = connection.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                (card_id,),
            ).fetchone()
            if holding is None or int(holding["quantity"]) < added_quantity:
                raise ValueError("The inventory quantity cannot be reduced further.")
            quantity = int(holding["quantity"]) - added_quantity
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
                ) VALUES (?, 'undo', ?, ?)
                """,
                (card_id, -added_quantity, event_id),
            )
        return InventoryChange(
            card_id,
            quantity,
            int(cursor.lastrowid),
            -added_quantity,
        )
