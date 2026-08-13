import sqlite3
import tempfile
import unittest
from pathlib import Path

from inventory import InventoryDatabase


class InventoryDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "user_data" / "inventory.sqlite3"
        self.database = InventoryDatabase(self.path)
        self.database.initialize()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_add_batch_and_undo_preserve_history(self) -> None:
        first = self.database.add_card("malie:sv5:123", scan_id="scan-1")
        second = self.database.add_cards(
            "malie:sv5:123",
            8,
            scan_id="scan-2",
        )

        self.assertEqual((first.quantity, second.quantity), (1, 9))
        self.assertEqual(second.quantity_delta, 8)
        self.assertEqual(self.database.quantity("malie:sv5:123"), 9)

        undone = self.database.undo_add(second.event_id)

        self.assertEqual((undone.quantity, undone.quantity_delta), (1, -8))
        self.assertEqual(self.database.quantity("malie:sv5:123"), 1)
        connection = sqlite3.connect(self.path)
        try:
            actions = connection.execute(
                "SELECT action, quantity_delta FROM inventory_events ORDER BY id"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(actions, [("scan_add", 1), ("scan_add", 8), ("undo", -8)])

    def test_same_addition_cannot_be_undone_twice(self) -> None:
        added = self.database.add_card("malie:sv5:123")
        self.database.undo_add(added.event_id)

        with self.assertRaisesRegex(ValueError, "already undone"):
            self.database.undo_add(added.event_id)

    def test_database_is_independent_of_catalog_tables(self) -> None:
        connection = sqlite3.connect(self.path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            connection.close()

        self.assertIn("inventory_holdings", tables)
        self.assertIn("inventory_events", tables)
        self.assertNotIn("cards", tables)

    def test_iteration_7_database_migrates_without_losing_inventory(self) -> None:
        legacy_path = Path(self.temp.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE inventory_holdings (
                    card_id TEXT PRIMARY KEY,
                    quantity INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE inventory_events (
                    id INTEGER PRIMARY KEY,
                    card_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('scan_add', 'undo')),
                    quantity_delta INTEGER NOT NULL CHECK(quantity_delta IN (-1, 1)),
                    source_scan_id TEXT,
                    related_event_id INTEGER UNIQUE REFERENCES inventory_events(id),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO inventory_holdings(card_id, quantity)
                VALUES ('malie:sv5:123', 3);
                INSERT INTO inventory_events(card_id, action, quantity_delta)
                VALUES ('malie:sv5:123', 'scan_add', 1),
                       ('malie:sv5:123', 'scan_add', 1),
                       ('malie:sv5:123', 'scan_add', 1);
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = InventoryDatabase(legacy_path)
        migrated.initialize()
        added = migrated.add_cards("malie:sv5:123", 8)

        self.assertEqual(added.quantity, 11)
        connection = sqlite3.connect(legacy_path)
        try:
            deltas = connection.execute(
                "SELECT quantity_delta FROM inventory_events ORDER BY id"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(deltas, [(1,), (1,), (1,), (8,)])


if __name__ == "__main__":
    unittest.main()
