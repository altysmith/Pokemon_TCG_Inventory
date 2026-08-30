import tempfile
import unittest
from pathlib import Path

from card_api.database import CatalogDatabase
from deck_checker import check_deck_list, parse_deck_list
from inventory import InventoryDatabase


class DeckCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.catalog_path = root / "catalog.sqlite3"
        self.inventory_path = root / "inventory.sqlite3"
        CatalogDatabase(self.catalog_path).initialize()
        with CatalogDatabase(self.catalog_path).connect() as connection:
            connection.executemany(
                "INSERT INTO sets(id, name, code, language, release_date) VALUES (?, ?, ?, 'en-US', ?)",
                [
                    ("set-tef", "Temporal Forces", "TEF", "2024-03-22"),
                    ("set-pre", "Prismatic Evolutions", "PRE", "2025-01-17"),
                    ("set-svi", "Scarlet & Violet", "SVI", "2023-03-31"),
                ],
            )
            connection.executemany(
                "INSERT INTO set_codes(set_id, code, code_type) VALUES (?, ?, 'printed')",
                [("set-tef", "TEF"), ("set-pre", "PRE"), ("set-svi", "SVI")],
            )
            cards = [
                ("bolt-regular", "set-tef", "Raging Bolt ex", "POKEMON", "", "123", 123, 240, "BASIC"),
                ("bolt-alt", "set-tef", "Raging Bolt ex", "POKEMON", "", "208", 208, 240, "BASIC"),
                ("bolt-reprint", "set-pre", "Raging Bolt ex", "POKEMON", "", "166", 166, 240, "BASIC"),
                ("bolt-different", "set-pre", "Raging Bolt ex", "POKEMON", "", "167", 167, 240, "BASIC"),
                ("research-svi", "set-svi", "Professor's Research", "TRAINER", "SUPPORTER", "189", 189, None, ""),
                ("research-pre", "set-pre", "Professor's Research", "TRAINER", "SUPPORTER", "150", 150, None, ""),
                ("basic-lightning", "set-svi", "Basic Lightning Energy", "ENERGY", "BASIC", "257", 257, None, ""),
                ("jet-energy", "set-svi", "Jet Energy", "ENERGY", "SPECIAL", "190", 190, None, ""),
                ("telepathic-energy", "set-svi", "Telepathic {P} Energy", "ENERGY", "SPECIAL", "191", 191, None, ""),
            ]
            connection.executemany(
                """
                INSERT INTO cards(
                    id, set_id, language, name, card_type, card_subtype, number,
                    number_numeric, hp, stage
                ) VALUES (?, ?, 'en-US', ?, ?, ?, ?, ?, ?, ?)
                """,
                cards,
            )
            for card_id in ("bolt-regular", "bolt-alt", "bolt-reprint"):
                connection.execute(
                    """
                    INSERT INTO card_text_entries(
                        card_id, position, kind, name, text, cost_json,
                        damage_amount, damage_suffix, raw_json
                    ) VALUES (?, 0, 'ATTACK', 'Bellowing Thunder', 'Discard Energy.',
                              '["LIGHTNING", "FIGHTING"]', 70, '×', '{}')
                    """,
                    (card_id,),
                )
            connection.execute(
                """
                INSERT INTO card_text_entries(
                    card_id, position, kind, name, text, cost_json,
                    damage_amount, damage_suffix, raw_json
                ) VALUES ('bolt-different', 0, 'ATTACK', 'Different Attack', '',
                          '["COLORLESS"]', 10, '', '{}')
                """
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_parser_accepts_limitless_headings_and_merges_duplicate_lines(self) -> None:
        entries, errors = parse_deck_list(
            "Pokémon: 2\n1 Raging Bolt ex TEF 123\n1 Raging Bolt ex TEF 123\n\nTotal Cards: 2"
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].quantity, 2)

    def test_exact_pokemon_then_alternate_art_and_name_matched_trainer(self) -> None:
        inventory = InventoryDatabase(self.inventory_path)
        inventory.set_quantity("bolt-regular", 1)
        inventory.set_quantity("bolt-alt", 1)
        inventory.set_quantity("bolt-reprint", 1)
        inventory.set_quantity("research-pre", 3)

        result = check_deck_list(
            """Pokémon: 3
3 Raging Bolt ex TEF 123

Trainer: 2
2 Professor's Research SVI 189

Total Cards: 5""",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )

        self.assertTrue(result["summary"]["complete"])
        self.assertEqual(result["summary"]["covered_cards"], 5)
        bolt = result["items"][0]
        self.assertEqual(
            [(fill["card_id"], fill["match"]) for fill in bolt["fills"]],
            [
                ("bolt-regular", "exact printing"),
                ("bolt-reprint", "alternate artwork"),
                ("bolt-alt", "alternate artwork"),
            ],
        )
        trainer = result["items"][1]
        self.assertEqual(trainer["fills"][0]["card_id"], "research-pre")
        self.assertEqual(trainer["fills"][0]["match"], "name match")

    def test_trainers_and_special_energy_ignore_requested_printing(self) -> None:
        inventory = InventoryDatabase(self.inventory_path)
        inventory.set_quantity("research-pre", 2)
        inventory.set_quantity("jet-energy", 3)

        result = check_deck_list(
            """Trainer: 2
2 Professor's Research XYZ 999

Energy: 3
3 Jet Energy ABC 999""",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )

        self.assertTrue(result["summary"]["complete"])
        self.assertEqual(result["summary"]["covered_cards"], 5)
        self.assertEqual(result["errors"], [])
        self.assertEqual(
            [fill["card_id"] for item in result["items"] for fill in item["fills"]],
            ["research-pre", "jet-energy"],
        )

    def test_readable_special_energy_type_alias_matches_catalog_symbol(self) -> None:
        InventoryDatabase(self.inventory_path).set_quantity("telepathic-energy", 3)

        result = check_deck_list(
            "3 Telepathic Psychic Energy XYZ 999",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )

        self.assertTrue(result["summary"]["complete"])
        self.assertEqual(result["items"][0]["name"], "Telepathic Psychic Energy")
        self.assertEqual(result["items"][0]["deck_section"], "energy")
        self.assertEqual(result["items"][0]["status"], "ready")
        self.assertEqual(result["items"][0]["fills"][0]["card_id"], "telepathic-energy")

    def test_pokemon_still_requires_exact_requested_printing(self) -> None:
        InventoryDatabase(self.inventory_path).set_quantity("bolt-regular", 4)

        result = check_deck_list(
            "4 Raging Bolt ex XYZ 999",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )

        self.assertEqual(result["items"][0]["status"], "unresolved")
        self.assertEqual(result["items"][0]["covered"], 0)
        self.assertEqual(result["items"][0]["missing"], 4)

    def test_same_name_but_different_pokemon_gameplay_does_not_fill(self) -> None:
        InventoryDatabase(self.inventory_path).set_quantity("bolt-different", 4)
        result = check_deck_list(
            "2 Raging Bolt ex TEF 123",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )
        self.assertEqual(result["items"][0]["covered"], 0)
        self.assertEqual(result["items"][0]["missing"], 2)
        self.assertEqual(result["summary"]["possible_substitute_cards"], 2)
        self.assertEqual(
            result["items"][0]["possible_substitutes"],
            [
                {
                    "card_id": "bolt-different",
                    "name": "Raging Bolt ex",
                    "set_code": "PRE",
                    "set_name": "Prismatic Evolutions",
                    "number": "167",
                    "quantity": 2,
                    "image_url": "",
                    "reason": "same name, different card text",
                }
            ],
        )

    def test_check_is_read_only(self) -> None:
        inventory = InventoryDatabase(self.inventory_path)
        inventory.set_quantity("research-pre", 3)
        before = inventory.holdings()
        check_deck_list(
            "2 Professor's Research SVI 189",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )
        self.assertEqual(inventory.holdings(), before)

    def test_basic_energy_is_ignored_but_special_energy_is_required(self) -> None:
        result = check_deck_list(
            """Energy: 5
3 Basic Lightning Energy SVI 257
2 Jet Energy SVI 190

Total Cards: 5""",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )

        self.assertEqual(result["summary"]["deck_cards"], 5)
        self.assertEqual(result["summary"]["checked_cards"], 2)
        self.assertEqual(result["summary"]["missing_cards"], 2)
        self.assertEqual(result["summary"]["ignored_basic_energy_cards"], 3)
        self.assertEqual(result["summary"]["ignored_basic_energy_lines"], 1)
        self.assertEqual([item["name"] for item in result["items"]], ["Jet Energy"])

    def test_name_only_basic_energy_is_ignored_even_without_catalog_match(self) -> None:
        result = check_deck_list(
            "4 Basic Mystery Energy",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )

        self.assertTrue(result["summary"]["complete"])
        self.assertEqual(result["summary"]["deck_cards"], 4)
        self.assertEqual(result["summary"]["checked_cards"], 0)
        self.assertEqual(result["summary"]["ignored_basic_energy_cards"], 4)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["items"], [])

    def test_limitless_basic_energy_names_are_ignored_but_special_energy_is_not(self) -> None:
        result = check_deck_list(
            """Energy: 14
4 Fire Energy SVE 2
3 Basic Lightning Energy SVE 4
2 Basic {W} Energy Energy 3
2 Darkness Energy
3 Jet Energy SVI 190""",
            catalog_path=self.catalog_path,
            inventory_path=self.inventory_path,
        )

        self.assertEqual(result["summary"]["ignored_basic_energy_cards"], 11)
        self.assertEqual(result["summary"]["ignored_basic_energy_lines"], 4)
        self.assertEqual(result["summary"]["deck_cards"], 14)
        self.assertEqual(result["summary"]["checked_cards"], 3)
        self.assertEqual(result["summary"]["missing_cards"], 3)
        self.assertEqual([item["name"] for item in result["items"]], ["Jet Energy"])


if __name__ == "__main__":
    unittest.main()
