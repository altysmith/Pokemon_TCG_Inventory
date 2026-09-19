import unittest
from pathlib import Path
import test_deck_checker
from concurrent.futures import ThreadPoolExecutor
from deck_allocations import check_allocations, transfer_allocation
from saved_decks import SavedDeckDatabase
from inventory import InventoryDatabase


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_deck_checker.DeckCheckerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.inventory = InventoryDatabase(self.fixture.inventory_path)
        self.inventory.set_quantity('research-svi', 1)
        self.database = SavedDeckDatabase(Path(self.fixture.temp.name) / 'decks.sqlite3')
        self.source = self.database.save('Gardevoir', "1 Professor's Research SVI 189", 1, 1)
        self.target = self.database.save('Dragapult', "1 Professor's Research SVI 189", 1, 1)
        self.database.replace_assignments(self.source.id, {'research-svi': 1})

    def check(self, deck=None):
        deck = deck or self.target
        with self.database.connect() as connection:
            return check_allocations(deck.deck_list, deck.id, self.fixture.catalog_path,
                self.fixture.inventory_path, connection, {x.card_id: x.quantity for x in self.inventory.holdings()})

    def transfer(self, **changes):
        data = dict(id=self.target.id, source_deck_id=self.source.id, item_index=0,
                    quantity=1, card_id='research-svi', deck_list=self.target.deck_list)
        data.update(changes)
        return transfer_allocation(self.database, self.inventory, self.fixture.catalog_path,
                                   self.fixture.inventory_path, data)

    def test_check_is_read_only_and_identifies_source(self):
        before = self.database.assignments()
        result = self.check()
        self.assertEqual(result['summary']['missing_cards'], 0)
        self.assertEqual(result['summary']['reserved_cards'], 1)
        self.assertEqual(result['items'][0]['allocation']['sources'][0]['deck_name'], 'Gardevoir')
        self.assertEqual(self.database.assignments(), before)

    def test_transfer_preserves_inventory_and_lists_and_updates_both_decks(self):
        holdings = self.inventory.holdings()
        decks = self.database.decks()
        self.transfer()
        self.assertEqual(self.database.assignments(self.source.id), ())
        self.assertEqual(self.database.assignments(self.target.id)[0].quantity, 1)
        self.assertEqual(self.inventory.holdings(), holdings)
        self.assertEqual(self.database.decks(), decks)
        self.assertEqual(self.check()['summary']['reserved_cards'], 0)
        self.assertEqual(self.check()['items'][0]['allocation']['assigned'], 1)
        self.assertEqual(self.check(self.source)['summary']['reserved_cards'], 1)

    def test_repeated_and_excess_transfer_rejected_without_partial_writes(self):
        before = self.database.assignments()
        with self.assertRaises(ValueError):
            self.transfer(quantity=2)
        self.assertEqual(self.database.assignments(), before)
        self.transfer()
        after = self.database.assignments()
        with self.assertRaises(ValueError):
            self.transfer()
        self.assertEqual(self.database.assignments(), after)

    def test_free_alternative_printing_is_used_before_borrowing(self):
        self.inventory.set_quantity('research-pre', 1)
        allocation = self.check()['items'][0]['allocation']
        self.assertEqual(allocation['reserved'], 0)
        self.assertEqual(allocation['sources'][0]['card_id'], 'research-pre')
        self.transfer(source_deck_id=0, card_id='research-pre')
        self.assertEqual(self.database.assignments(self.source.id)[0].quantity, 1)
        self.assertEqual(self.check()['items'][0]['allocation']['assigned'], 1)

    def test_invalid_or_stale_target_does_not_mutate(self):
        before = self.database.assignments()
        for changes in [dict(id=999), dict(card_id='bolt-regular'), dict(quantity=0),
                        dict(deck_list='changed'), dict(source_deck_id=self.target.id), dict(item_index=-1)]:
            with self.assertRaises(ValueError):
                self.transfer(**changes)
            self.assertEqual(self.database.assignments(), before)

    def test_unsaved_check_has_no_mutation_controls(self):
        with self.database.connect() as connection:
            result = check_allocations(self.target.deck_list, 0, self.fixture.catalog_path,
                self.fixture.inventory_path, connection, {'research-svi': 1})
        self.assertFalse(result['items'][0]['allocation']['editable'])

    def test_true_shortage_is_separate_from_reservation(self):
        self.inventory.set_quantity('research-svi', 0)
        result = self.check()
        self.assertEqual(result['summary']['missing_cards'], 1)
        self.assertEqual(result['summary']['reserved_cards'], 0)

    def test_partial_transfer_keeps_remaining_source_copies(self):
        self.inventory.set_quantity('research-svi', 3)
        self.database.replace_assignments(self.source.id, {'research-svi': 3})
        self.transfer()
        self.assertEqual(self.database.assignments(self.source.id)[0].quantity, 2)
        self.assertEqual(self.database.assignments(self.target.id)[0].quantity, 1)

    def test_concurrent_transfers_cannot_take_the_same_copy_twice(self):
        def attempt(_):
            try:
                self.transfer()
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(attempt, range(2))), [False, True])
        self.assertEqual(self.database.assignments(self.target.id)[0].quantity, 1)

    def test_current_allocation_is_preferred_over_free_alternate(self):
        self.database.clear_assignments(self.source.id)
        self.inventory.set_quantity('research-pre', 1)
        self.database.replace_assignments(self.target.id, {'research-pre': 1})
        allocation = self.check()['items'][0]['allocation']
        self.assertEqual(allocation['assigned'], 1)
        self.assertEqual(allocation['sources'], [])

    def test_other_accounts_allocations_are_not_sources(self):
        other = SavedDeckDatabase(Path(self.fixture.temp.name) / 'other-account.sqlite3')
        other.initialize()
        with other.connect() as connection:
            result = check_allocations(self.target.deck_list, 0, self.fixture.catalog_path,
                self.fixture.inventory_path, connection, {'research-svi': 1})
        source = result['items'][0]['allocation']['sources'][0]
        self.assertEqual(source['deck_id'], 0)
        self.assertEqual(result['summary']['reserved_cards'], 0)

    def test_free_printings_are_not_double_counted_across_deck_rows(self):
        self.inventory.set_quantity('research-svi', 2)
        self.inventory.set_quantity('research-pre', 1)
        target = self.database.save('Dragapult', "1 Professor's Research SVI 189\n1 Professor's Research PRE 150",
                                    2, 2, deck_id=self.target.id)
        result = self.check(target)
        self.assertEqual(result['summary']['reserved_cards'], 0)
        self.assertEqual(sum(source['quantity'] for item in result['items']
                             for source in item['allocation']['sources']), 2)

if __name__ == '__main__':
    unittest.main()
