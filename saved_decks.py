"""Local saved-deck library kept separate from physical card inventory."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS saved_decks (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    deck_list TEXT NOT NULL,
    card_count INTEGER NOT NULL CHECK(card_count > 0),
    unique_entries INTEGER NOT NULL CHECK(unique_entries > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_decks_active_name
    ON saved_decks(lower(name)) WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_saved_decks_updated
    ON saved_decks(archived_at, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS saved_deck_assignments (
    deck_id INTEGER NOT NULL,
    card_id TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(deck_id, card_id),
    FOREIGN KEY(deck_id) REFERENCES saved_decks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_saved_deck_assignments_card
    ON saved_deck_assignments(card_id, deck_id);
"""


@dataclass(frozen=True)
class SavedDeck:
    id: int
    name: str
    deck_list: str
    card_count: int
    unique_entries: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SavedDeckAssignment:
    deck_id: int
    card_id: str
    quantity: int
    created_at: str
    updated_at: str


class SavedDeckDatabase:
    """Persist deck lists without reserving or changing inventory cards."""

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
        connection.execute("PRAGMA busy_timeout = 15000")
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _deck(row: sqlite3.Row) -> SavedDeck:
        return SavedDeck(
            id=int(row["id"]),
            name=str(row["name"]),
            deck_list=str(row["deck_list"]),
            card_count=int(row["card_count"]),
            unique_entries=int(row["unique_entries"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def decks(self) -> tuple[SavedDeck, ...]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, deck_list, card_count, unique_entries,
                       created_at, updated_at
                FROM saved_decks
                WHERE archived_at IS NULL
                ORDER BY updated_at DESC, name COLLATE NOCASE, id DESC
                """
            ).fetchall()
        return tuple(self._deck(row) for row in rows)

    def assignments(self, deck_id: int = 0) -> tuple[SavedDeckAssignment, ...]:
        self.initialize()
        query = """
            SELECT a.deck_id, a.card_id, a.quantity, a.created_at, a.updated_at
            FROM saved_deck_assignments a
            JOIN saved_decks d ON d.id = a.deck_id
            WHERE d.archived_at IS NULL
        """
        parameters: tuple[int, ...] = ()
        if deck_id:
            query += " AND a.deck_id = ?"
            parameters = (deck_id,)
        query += " ORDER BY a.deck_id, a.card_id"
        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(
            SavedDeckAssignment(
                deck_id=int(row["deck_id"]),
                card_id=str(row["card_id"]),
                quantity=int(row["quantity"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        )

    def replace_assignments(
        self, deck_id: int, quantities: dict[str, int]
    ) -> tuple[SavedDeckAssignment, ...]:
        """Replace one deck's owned-card assignments without touching inventory."""
        if deck_id <= 0:
            raise ValueError("A valid saved deck is required.")
        normalized: dict[str, int] = {}
        for card_id, quantity in quantities.items():
            card = str(card_id).strip()
            amount = int(quantity)
            if not card or amount <= 0:
                continue
            normalized[card] = amount
        self.initialize()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM saved_decks WHERE id = ? AND archived_at IS NULL",
                (deck_id,),
            ).fetchone()
            if not exists:
                raise ValueError("That saved deck no longer exists.")
            connection.execute(
                "DELETE FROM saved_deck_assignments WHERE deck_id = ?", (deck_id,)
            )
            connection.executemany(
                """
                INSERT INTO saved_deck_assignments(deck_id, card_id, quantity)
                VALUES (?, ?, ?)
                """,
                [(deck_id, card_id, quantity) for card_id, quantity in normalized.items()],
            )
        return self.assignments(deck_id)

    def clear_assignments(self, deck_id: int) -> int:
        self.initialize()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM saved_decks WHERE id = ? AND archived_at IS NULL",
                (deck_id,),
            ).fetchone()
            if not exists:
                raise ValueError("That saved deck no longer exists.")
            cursor = connection.execute(
                "DELETE FROM saved_deck_assignments WHERE deck_id = ?", (deck_id,)
            )
        return int(cursor.rowcount)

    def save(
        self,
        name: str,
        deck_list: str,
        card_count: int,
        unique_entries: int,
        *,
        deck_id: int = 0,
    ) -> SavedDeck:
        self.initialize()
        try:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if deck_id:
                    existing = connection.execute(
                        "SELECT id FROM saved_decks WHERE id = ? AND archived_at IS NULL",
                        (deck_id,),
                    ).fetchone()
                    if not existing:
                        raise ValueError("That saved deck no longer exists.")
                    connection.execute(
                        """
                        UPDATE saved_decks
                        SET name = ?, deck_list = ?, card_count = ?, unique_entries = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND archived_at IS NULL
                        """,
                        (name, deck_list, card_count, unique_entries, deck_id),
                    )
                else:
                    cursor = connection.execute(
                        """
                        INSERT INTO saved_decks(name, deck_list, card_count, unique_entries)
                        VALUES (?, ?, ?, ?)
                        """,
                        (name, deck_list, card_count, unique_entries),
                    )
                    deck_id = int(cursor.lastrowid)
                row = connection.execute(
                    """
                    SELECT id, name, deck_list, card_count, unique_entries,
                           created_at, updated_at
                    FROM saved_decks WHERE id = ? AND archived_at IS NULL
                    """,
                    (deck_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError("A saved deck already uses that name.") from exc
        if row is None:
            raise ValueError("The deck could not be saved.")
        return self._deck(row)

    def rename(self, deck_id: int, name: str) -> SavedDeck:
        self.initialize()
        try:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE saved_decks SET name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND archived_at IS NULL
                    """,
                    (name, deck_id),
                )
                if not cursor.rowcount:
                    raise ValueError("That saved deck no longer exists.")
                row = connection.execute(
                    """
                    SELECT id, name, deck_list, card_count, unique_entries,
                           created_at, updated_at
                    FROM saved_decks WHERE id = ?
                    """,
                    (deck_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError("A saved deck already uses that name.") from exc
        return self._deck(row)

    def remove(self, deck_id: int) -> None:
        """Archive a deck so removal does not destroy its stored list."""
        self.initialize()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE saved_decks
                SET archived_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND archived_at IS NULL
                """,
                (deck_id,),
            )
            if not cursor.rowcount:
                raise ValueError("That saved deck no longer exists.")
            connection.execute(
                "DELETE FROM saved_deck_assignments WHERE deck_id = ?", (deck_id,)
            )
