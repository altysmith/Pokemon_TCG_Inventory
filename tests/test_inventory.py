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
        self.assertEqual(
            [(item.card_id, item.quantity) for item in self.database.holdings()],
            [("malie:sv5:123", 9)],
        )

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

    def test_manual_quantity_can_increase_decrease_and_remove_a_card(self) -> None:
        added = self.database.set_quantity("malie:sv5:123", 12)
        reduced = self.database.set_quantity("malie:sv5:123", 4)
        removed = self.database.set_quantity("malie:sv5:123", 0)

        self.assertEqual((added.quantity_delta, reduced.quantity_delta), (12, -8))
        self.assertEqual((removed.quantity, removed.quantity_delta), (0, -4))
        self.assertEqual(self.database.quantity("malie:sv5:123"), 0)
        connection = sqlite3.connect(self.path)
        try:
            actions = connection.execute(
                "SELECT action, quantity_delta FROM inventory_events ORDER BY id"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(
            actions,
            [("manual_set", 12), ("manual_set", -8), ("manual_set", -4)],
        )
        backups = sorted((self.path.parent / "backups").glob("inventory-backup-*.sqlite3"))
        self.assertEqual(len(backups), 3)
        backup = sqlite3.connect(backups[-1])
        try:
            prior = backup.execute(
                "SELECT quantity FROM inventory_holdings WHERE card_id = ?",
                ("malie:sv5:123",),
            ).fetchone()
            integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            backup.close()
        self.assertEqual(prior, (4,))
        self.assertEqual(integrity, "ok")

    def test_setting_existing_quantity_is_a_noop(self) -> None:
        self.database.set_quantity("malie:sv5:123", 3)
        backups_before = tuple((self.path.parent / "backups").glob("*.sqlite3"))
        unchanged = self.database.set_quantity("malie:sv5:123", 3)
        backups_after = tuple((self.path.parent / "backups").glob("*.sqlite3"))

        self.assertEqual((unchanged.event_id, unchanged.quantity_delta), (0, 0))
        self.assertEqual(len(backups_after), len(backups_before))

    def test_bulk_quantities_use_one_backup_and_one_transaction(self) -> None:
        self.database.set_quantities({"card-1": 2, "card-2": 4})
        backups_before = tuple((self.path.parent / "backups").glob("*.sqlite3"))

        changes = self.database.set_quantities({"card-1": 7, "card-2": 0, "card-3": 1})
        backups_after = tuple((self.path.parent / "backups").glob("*.sqlite3"))

        self.assertEqual(len(backups_after), len(backups_before) + 1)
        self.assertEqual(
            [(change.card_id, change.quantity, change.quantity_delta) for change in changes],
            [("card-1", 7, 5), ("card-2", 0, -4), ("card-3", 1, 1)],
        )
        self.assertEqual(
            [(holding.card_id, holding.quantity) for holding in self.database.holdings()],
            [("card-1", 7), ("card-3", 1)],
        )

    def test_optional_locations_allocate_owned_copies_without_changing_totals(self) -> None:
        self.database.set_quantity("card-1", 6)
        first = self.database.create_location("Deck Box 1")
        second = self.database.create_location("Trade Binder")

        first_change = self.database.set_location_quantity("card-1", first.id, 2)
        second_change = self.database.set_location_quantity("card-1", second.id, 3)
        renamed = self.database.rename_location(second.id, "Deck Box 2")

        self.assertEqual(self.database.quantity("card-1"), 6)
        self.assertEqual((first_change.assigned_quantity, first_change.unassigned_quantity), (2, 4))
        self.assertEqual((second_change.assigned_quantity, second_change.unassigned_quantity), (5, 1))
        self.assertEqual(renamed.name, "Deck Box 2")
        self.assertEqual(
            [(item.location_id, item.card_id, item.quantity) for item in self.database.location_allocations()],
            [(first.id, "card-1", 2), (second.id, "card-1", 3)],
        )

    def test_locations_prevent_double_allocation_and_invalid_total_reduction(self) -> None:
        self.database.set_quantity("card-1", 5)
        first = self.database.create_location("Deck Box 1")
        second = self.database.create_location("Deck Box 2")
        self.database.set_location_quantity("card-1", first.id, 3)

        with self.assertRaisesRegex(ValueError, "Only 2 copies"):
            self.database.set_location_quantity("card-1", second.id, 3)
        with self.assertRaisesRegex(ValueError, "assigned to locations"):
            self.database.set_quantity("card-1", 2)
        with self.assertRaisesRegex(ValueError, "assigned to locations"):
            self.database.set_quantities({"card-1": 2})

        self.assertEqual(self.database.quantity("card-1"), 5)

    def test_removing_location_returns_copies_to_unassigned_without_removing_cards(self) -> None:
        self.database.set_quantity("card-1", 4)
        location = self.database.create_location("Deck Box 1")
        self.database.set_location_quantity("card-1", location.id, 3)

        released = self.database.remove_location(location.id)

        self.assertEqual(released, 3)
        self.assertEqual(self.database.quantity("card-1"), 4)
        self.assertEqual(self.database.locations(), ())
        self.assertEqual(self.database.location_allocations(), ())

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
        self.assertIn("inventory_locations", tables)
        self.assertIn("inventory_location_holdings", tables)
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
