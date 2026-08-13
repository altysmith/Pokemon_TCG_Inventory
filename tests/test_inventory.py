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

    def test_add_quantity_and_undo_preserve_history(self) -> None:
        first = self.database.add_card("malie:sv5:123", scan_id="scan-1")
        second = self.database.add_card("malie:sv5:123", scan_id="scan-2")

        self.assertEqual((first.quantity, second.quantity), (1, 2))
        self.assertEqual(self.database.quantity("malie:sv5:123"), 2)

        undone = self.database.undo_add(second.event_id)

        self.assertEqual(undone.quantity, 1)
        self.assertEqual(self.database.quantity("malie:sv5:123"), 1)
        connection = sqlite3.connect(self.path)
        try:
            actions = connection.execute(
                "SELECT action, quantity_delta FROM inventory_events ORDER BY id"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(actions, [("scan_add", 1), ("scan_add", 1), ("undo", -1)])

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


if __name__ == "__main__":
    unittest.main()
