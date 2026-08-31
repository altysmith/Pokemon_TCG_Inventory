"""Permanent user-owned inventory stored separately from the card catalog."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
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
    action TEXT NOT NULL CHECK(action IN ('scan_add', 'manual_set', 'undo')),
    quantity_delta INTEGER NOT NULL CHECK(quantity_delta != 0),
    source_scan_id TEXT,
    related_event_id INTEGER UNIQUE REFERENCES inventory_events(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_locations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_locations_active_name
    ON inventory_locations(lower(name)) WHERE archived_at IS NULL;

CREATE TABLE IF NOT EXISTS inventory_location_holdings (
    location_id INTEGER NOT NULL REFERENCES inventory_locations(id) ON DELETE CASCADE,
    card_id TEXT NOT NULL REFERENCES inventory_holdings(card_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(location_id, card_id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_location_holdings_card
    ON inventory_location_holdings(card_id, location_id);

CREATE INDEX IF NOT EXISTS idx_inventory_events_card
    ON inventory_events(card_id, id DESC);
"""


@dataclass(frozen=True)
class InventoryChange:
    card_id: str
    quantity: int
    event_id: int
    quantity_delta: int


@dataclass(frozen=True)
class InventoryHolding:
    card_id: str
    quantity: int
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class InventoryLocation:
    id: int
    name: str
    unique_cards: int = 0
    total_copies: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class InventoryLocationAllocation:
    location_id: int
    card_id: str
    quantity: int


@dataclass(frozen=True)
class InventoryLocationChange:
    location_id: int
    card_id: str
    quantity: int
    assigned_quantity: int
    unassigned_quantity: int


class InventoryDatabase:
    """Own the mutable collection database and its auditable event history."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate_batch_quantities(connection)
            self._migrate_manual_quantities(connection)

    def create_backup(self) -> Path | None:
        """Create a consistent, timestamped SQLite snapshot before a mutation."""
        if not self.path.is_file():
            return None
        backup_directory = self.path.parent / "backups"
        backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        destination = backup_directory / f"{self.path.stem}-backup-{timestamp}.sqlite3"
        with closing(sqlite3.connect(self.path, timeout=15)) as source:
            with closing(sqlite3.connect(destination)) as backup:
                source.backup(backup)
                backup.commit()
                integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            destination.unlink(missing_ok=True)
            raise RuntimeError("The automatic inventory backup failed its integrity check.")
        return destination

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

    @staticmethod
    def _migrate_manual_quantities(connection: sqlite3.Connection) -> None:
        """Allow audited absolute quantity changes from catalog search rows."""
        row = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'inventory_events'
            """
        ).fetchone()
        table_sql = str(row["sql"] if row else "")
        if "manual_set" in table_sql:
            return
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            DROP INDEX IF EXISTS idx_inventory_events_card;
            ALTER TABLE inventory_events RENAME TO inventory_events_before_manual;
            CREATE TABLE inventory_events (
                id INTEGER PRIMARY KEY,
                card_id TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('scan_add', 'manual_set', 'undo')),
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
            FROM inventory_events_before_manual;
            DROP TABLE inventory_events_before_manual;
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

    def holdings(self) -> tuple[InventoryHolding, ...]:
        """Return current quantities without exposing a writable SQL connection."""
        if not self.path.is_file():
            return ()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT card_id, quantity, created_at, updated_at "
                "FROM inventory_holdings "
                "WHERE quantity > 0 ORDER BY card_id"
            ).fetchall()
        return tuple(
            InventoryHolding(
                str(row["card_id"]),
                int(row["quantity"]),
                str(row["created_at"]),
                str(row["updated_at"]),
            )
            for row in rows
        )

    @staticmethod
    def _location_name(name: str) -> str:
        value = " ".join(str(name).split())
        if not value:
            raise ValueError("Give this location a name.")
        if len(value) > 60:
            raise ValueError("Location names must be 60 characters or fewer.")
        return value

    @staticmethod
    def _allocated_quantity(connection: sqlite3.Connection, card_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS quantity "
            "FROM inventory_location_holdings WHERE card_id = ?",
            (card_id,),
        ).fetchone()
        return int(row["quantity"] if row else 0)

    def locations(self) -> tuple[InventoryLocation, ...]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT l.id, l.name, l.created_at, l.updated_at,
                       COUNT(h.card_id) AS unique_cards,
                       COALESCE(SUM(h.quantity), 0) AS total_copies
                FROM inventory_locations l
                LEFT JOIN inventory_location_holdings h ON h.location_id = l.id
                WHERE l.archived_at IS NULL
                GROUP BY l.id
                ORDER BY l.name COLLATE NOCASE, l.id
                """
            ).fetchall()
        return tuple(
            InventoryLocation(
                id=int(row["id"]),
                name=str(row["name"]),
                unique_cards=int(row["unique_cards"]),
                total_copies=int(row["total_copies"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        )

    def location_allocations(self) -> tuple[InventoryLocationAllocation, ...]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT h.location_id, h.card_id, h.quantity
                FROM inventory_location_holdings h
                JOIN inventory_locations l ON l.id = h.location_id
                WHERE l.archived_at IS NULL
                ORDER BY h.card_id, h.location_id
                """
            ).fetchall()
        return tuple(
            InventoryLocationAllocation(
                location_id=int(row["location_id"]),
                card_id=str(row["card_id"]),
                quantity=int(row["quantity"]),
            )
            for row in rows
        )

    def create_location(self, name: str) -> InventoryLocation:
        value = self._location_name(name)
        self.initialize()
        self.create_backup()
        try:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    "INSERT INTO inventory_locations(name) VALUES (?)",
                    (value,),
                )
                location_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("A location already uses that name.") from exc
        return next(location for location in self.locations() if location.id == location_id)

    def rename_location(self, location_id: int, name: str) -> InventoryLocation:
        value = self._location_name(name)
        if location_id <= 0:
            raise ValueError("A valid inventory location is required.")
        self.initialize()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT name FROM inventory_locations WHERE id = ? AND archived_at IS NULL",
                (location_id,),
            ).fetchone()
        if not existing:
            raise ValueError("That inventory location no longer exists.")
        if str(existing["name"]) == value:
            return next(location for location in self.locations() if location.id == location_id)
        self.create_backup()
        try:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE inventory_locations SET name = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ? AND archived_at IS NULL",
                    (value, location_id),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("A location already uses that name.") from exc
        return next(location for location in self.locations() if location.id == location_id)

    def remove_location(self, location_id: int) -> int:
        """Archive a location and return its copies to the virtual Unassigned pool."""
        if location_id <= 0:
            raise ValueError("A valid inventory location is required.")
        self.initialize()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT l.id, COALESCE(SUM(h.quantity), 0) AS released
                FROM inventory_locations l
                LEFT JOIN inventory_location_holdings h ON h.location_id = l.id
                WHERE l.id = ? AND l.archived_at IS NULL
                GROUP BY l.id
                """,
                (location_id,),
            ).fetchone()
        if not row:
            raise ValueError("That inventory location no longer exists.")
        released = int(row["released"])
        self.create_backup()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM inventory_location_holdings WHERE location_id = ?",
                (location_id,),
            )
            connection.execute(
                "UPDATE inventory_locations "
                "SET archived_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND archived_at IS NULL",
                (location_id,),
            )
        return released

    def set_location_quantity(
        self,
        card_id: str,
        location_id: int,
        quantity: int,
    ) -> InventoryLocationChange:
        value = str(card_id).strip()
        if not value:
            raise ValueError("A canonical card ID is required for inventory.")
        if location_id <= 0:
            raise ValueError("A valid inventory location is required.")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 0 <= quantity <= 9999:
            raise ValueError("Location quantity must be between 0 and 9999.")
        self.initialize()
        with self.connect() as connection:
            holding = connection.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                (value,),
            ).fetchone()
            location = connection.execute(
                "SELECT id FROM inventory_locations WHERE id = ? AND archived_at IS NULL",
                (location_id,),
            ).fetchone()
            current = connection.execute(
                "SELECT quantity FROM inventory_location_holdings "
                "WHERE location_id = ? AND card_id = ?",
                (location_id, value),
            ).fetchone()
            other = connection.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS quantity "
                "FROM inventory_location_holdings WHERE card_id = ? AND location_id != ?",
                (value, location_id),
            ).fetchone()
        if not holding:
            raise ValueError("That card is not currently in the collection.")
        if not location:
            raise ValueError("That inventory location no longer exists.")
        total_owned = int(holding["quantity"])
        other_assigned = int(other["quantity"] if other else 0)
        if other_assigned + quantity > total_owned:
            available = max(0, total_owned - other_assigned)
            raise ValueError(
                f"Only {available} copies are available for this location."
            )
        current_quantity = int(current["quantity"]) if current else 0
        if current_quantity != quantity:
            self.create_backup()
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if quantity:
                    connection.execute(
                        """
                        INSERT INTO inventory_location_holdings(location_id, card_id, quantity)
                        VALUES (?, ?, ?)
                        ON CONFLICT(location_id, card_id) DO UPDATE SET
                            quantity = excluded.quantity,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (location_id, value, quantity),
                    )
                else:
                    connection.execute(
                        "DELETE FROM inventory_location_holdings "
                        "WHERE location_id = ? AND card_id = ?",
                        (location_id, value),
                    )
        assigned = other_assigned + quantity
        return InventoryLocationChange(
            location_id=location_id,
            card_id=value,
            quantity=quantity,
            assigned_quantity=assigned,
            unassigned_quantity=total_owned - assigned,
        )

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
        self.create_backup()
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

    def set_quantity(self, card_id: str, quantity: int) -> InventoryChange:
        """Set one canonical card quantity and retain the signed adjustment."""
        value = card_id.strip()
        if not value:
            raise ValueError("A canonical card ID is required for inventory.")
        if quantity < 0 or quantity > 9999:
            raise ValueError("Inventory quantity must be between 0 and 9999.")
        self.initialize()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                (value,),
            ).fetchone()
            allocated_quantity = self._allocated_quantity(connection, value)
        existing_quantity = int(existing["quantity"]) if existing else 0
        if quantity < allocated_quantity:
            raise ValueError(
                f"{allocated_quantity} copies are assigned to locations. "
                "Reduce those assignments before lowering the total."
            )
        if existing_quantity == quantity:
            return InventoryChange(value, quantity, 0, 0)
        self.create_backup()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                (value,),
            ).fetchone()
            prior_quantity = int(row["quantity"]) if row else 0
            quantity_delta = quantity - prior_quantity
            if quantity_delta == 0:
                return InventoryChange(value, quantity, 0, 0)
            if quantity:
                connection.execute(
                    """
                    INSERT INTO inventory_holdings(card_id, quantity)
                    VALUES (?, ?)
                    ON CONFLICT(card_id) DO UPDATE SET
                        quantity=excluded.quantity,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (value, quantity),
                )
            else:
                connection.execute(
                    "DELETE FROM inventory_holdings WHERE card_id = ?",
                    (value,),
                )
            cursor = connection.execute(
                """
                INSERT INTO inventory_events(card_id, action, quantity_delta)
                VALUES (?, 'manual_set', ?)
                """,
                (value, quantity_delta),
            )
        return InventoryChange(value, quantity, int(cursor.lastrowid), quantity_delta)

    def set_quantities(self, quantities: dict[str, int]) -> tuple[InventoryChange, ...]:
        """Apply validated absolute quantities in one transaction and one backup."""
        normalized: dict[str, int] = {}
        for card_id, quantity in quantities.items():
            value = str(card_id).strip()
            if not value:
                raise ValueError("A canonical card ID is required for inventory.")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or not 0 <= quantity <= 9999:
                raise ValueError("Inventory quantity must be between 0 and 9999.")
            normalized[value] = quantity
        if not normalized:
            return ()

        self.initialize()
        prior = {
            holding.card_id: holding.quantity
            for holding in self.holdings()
            if holding.card_id in normalized
        }
        changed = {
            card_id: quantity
            for card_id, quantity in normalized.items()
            if prior.get(card_id, 0) != quantity
        }
        if not changed:
            return ()

        with self.connect() as connection:
            allocated = {
                str(row["card_id"]): int(row["quantity"])
                for row in connection.execute(
                    "SELECT card_id, SUM(quantity) AS quantity "
                    "FROM inventory_location_holdings GROUP BY card_id"
                ).fetchall()
            }
        conflicts = [
            (card_id, allocated.get(card_id, 0))
            for card_id, quantity in changed.items()
            if quantity < allocated.get(card_id, 0)
        ]
        if conflicts:
            card_id, assigned = sorted(conflicts)[0]
            raise ValueError(
                f"{card_id} has {assigned} copies assigned to locations. "
                "Reduce those assignments before lowering the total."
            )

        self.create_backup()
        results = []
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for card_id in sorted(changed):
                quantity = changed[card_id]
                row = connection.execute(
                    "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                    (card_id,),
                ).fetchone()
                prior_quantity = int(row["quantity"]) if row else 0
                quantity_delta = quantity - prior_quantity
                if not quantity_delta:
                    continue
                if quantity:
                    connection.execute(
                        """
                        INSERT INTO inventory_holdings(card_id, quantity)
                        VALUES (?, ?)
                        ON CONFLICT(card_id) DO UPDATE SET
                            quantity=excluded.quantity,
                            updated_at=CURRENT_TIMESTAMP
                        """,
                        (card_id, quantity),
                    )
                else:
                    connection.execute(
                        "DELETE FROM inventory_holdings WHERE card_id = ?",
                        (card_id,),
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO inventory_events(card_id, action, quantity_delta)
                    VALUES (?, 'manual_set', ?)
                    """,
                    (card_id, quantity_delta),
                )
                results.append(
                    InventoryChange(card_id, quantity, int(cursor.lastrowid), quantity_delta)
                )
        return tuple(results)

    def undo_add(self, event_id: int) -> InventoryChange:
        if event_id <= 0:
            raise ValueError("A valid inventory event is required to undo an addition.")
        if not self.path.is_file():
            raise ValueError("The inventory database has not been created yet.")
        self.create_backup()
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
            allocated_quantity = self._allocated_quantity(connection, card_id)
            if quantity < allocated_quantity:
                raise ValueError(
                    f"{allocated_quantity} copies are assigned to locations. "
                    "Reduce those assignments before undoing this addition."
                )
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
