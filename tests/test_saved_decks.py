import tempfile
import unittest
from pathlib import Path

from saved_decks import SavedDeckDatabase


class SavedDeckDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "decks.sqlite3"
        self.database = SavedDeckDatabase(self.path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_save_update_and_reopen_persist_the_original_deck_list(self) -> None:
        saved = self.database.save("Raging Bolt", "2 Raging Bolt ex TEF 123", 2, 1)
        updated = self.database.save(
            "Raging Bolt",
            "3 Raging Bolt ex TEF 123",
            3,
            1,
            deck_id=saved.id,
        )
        reopened = SavedDeckDatabase(self.path).decks()

        self.assertEqual(updated.id, saved.id)
        self.assertEqual(len(reopened), 1)
        self.assertEqual(reopened[0].deck_list, "3 Raging Bolt ex TEF 123")
        self.assertEqual(reopened[0].card_count, 3)

    def test_rename_rejects_duplicate_active_names(self) -> None:
        first = self.database.save("Deck One", "1 Budew PRE 004", 1, 1)
        second = self.database.save("Deck Two", "1 Raging Bolt ex TEF 123", 1, 1)

        with self.assertRaisesRegex(ValueError, "already uses"):
            self.database.rename(second.id, "deck one")

        self.assertEqual(
            {deck.id: deck.name for deck in self.database.decks()},
            {first.id: "Deck One", second.id: "Deck Two"},
        )

    def test_remove_archives_without_affecting_other_decks(self) -> None:
        removed = self.database.save("Old Deck", "1 Budew PRE 004", 1, 1)
        kept = self.database.save("Current Deck", "1 Raging Bolt ex TEF 123", 1, 1)
        self.database.replace_assignments(removed.id, {"card-1": 2})

        self.database.remove(removed.id)

        self.assertEqual([deck.id for deck in self.database.decks()], [kept.id])
        self.assertEqual(self.database.assignments(removed.id), ())
        with self.database.connect() as connection:
            archived = connection.execute(
                "SELECT archived_at FROM saved_decks WHERE id = ?", (removed.id,)
            ).fetchone()
        self.assertTrue(archived["archived_at"])

    def test_replace_and_clear_assignments_do_not_change_deck_list(self) -> None:
        deck = self.database.save("Excadrill", "2 Drilbur PBL 046", 2, 1)

        assigned = self.database.replace_assignments(
            deck.id, {"card-1": 2, "card-2": 1}
        )
        replaced = self.database.replace_assignments(deck.id, {"card-1": 1})
        cleared = self.database.clear_assignments(deck.id)

        self.assertEqual(
            {(item.card_id, item.quantity) for item in assigned},
            {("card-1", 2), ("card-2", 1)},
        )
        self.assertEqual([(item.card_id, item.quantity) for item in replaced], [("card-1", 1)])
        self.assertEqual(cleared, 1)
        self.assertEqual(self.database.assignments(deck.id), ())
        self.assertEqual(self.database.decks()[0].deck_list, "2 Drilbur PBL 046")


if __name__ == "__main__":
    unittest.main()
