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
