import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from app import (
    add_inventory_card,
    catalog_facets,
    catalog_search,
    exact_catalog_fields,
    extract_footer_fields,
    extract_footer_fields_from_readings,
    extract_literal_groups,
    save_benchmark_label,
    save_scan_performance,
    set_catalog_inventory_quantity,
)
from card_scanner.ocr import LiteralReading
from card_scanner.lookup import CardInfo
from card_api.database import CatalogDatabase
from collection_transfer import (
    EXPORT_SCHEMA,
    EXPORT_SCHEMA_VERSION,
    build_collection_export,
    parse_collection_csv,
    parse_collection_json,
    render_collection_csv,
    render_collection_json,
)
from inventory import InventoryDatabase


class AppTests(unittest.TestCase):
    def test_collection_exports_share_a_versioned_import_safe_schema(self) -> None:
        snapshot = {
            "items": [
                {
                    "id": "card-pre-011",
                    "quantity": 7,
                    "name": "Budew",
                    "set_name": "Prismatic Evolutions",
                    "set_code": "PRE",
                    "number": "011",
                    "printed_total": "131",
                    "card_type": "POKEMON",
                    "card_subtype": "BASIC",
                    "types": ["GRASS"],
                    "regulation_mark": "H",
                    "rarity": "COMMON",
                    "date_added": "2026-08-30 10:00:00",
                    "date_updated": "2026-08-30 10:05:00",
                }
            ]
        }
        payload = build_collection_export(snapshot, "2026-08-30T10:10:00-04:00")
        json_export = json.loads(render_collection_json(payload).decode("utf-8"))
        csv_export = list(
            csv.DictReader(io.StringIO(render_collection_csv(payload).decode("utf-8-sig")))
        )

        self.assertEqual(json_export["schema"], EXPORT_SCHEMA)
        self.assertEqual(json_export["schema_version"], EXPORT_SCHEMA_VERSION)
        self.assertEqual(json_export["summary"], {"unique_cards": 1, "total_copies": 7})
        self.assertEqual(json_export["cards"][0]["card_id"], "card-pre-011")
        self.assertEqual(json_export["cards"][0]["types"], ["GRASS"])
        self.assertEqual(csv_export[0]["schema"], EXPORT_SCHEMA)
        self.assertEqual(csv_export[0]["schema_version"], str(EXPORT_SCHEMA_VERSION))
        self.assertEqual(csv_export[0]["card_id"], "card-pre-011")
        self.assertEqual(csv_export[0]["quantity"], "7")
        self.assertEqual(csv_export[0]["types"], "GRASS")
        self.assertEqual(parse_collection_json(render_collection_json(payload))["cards"], payload["cards"])
        self.assertEqual(parse_collection_csv(render_collection_csv(payload))["cards"], payload["cards"])

    def test_collection_import_parsers_reject_unknown_or_damaged_exports(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a Pokemon Card Collection"):
            parse_collection_json('{"schema": "something-else", "schema_version": 1, "cards": []}')
        with self.assertRaisesRegex(ValueError, "required columns"):
            parse_collection_csv("name,quantity\nBudew,4\n")
        with self.assertRaisesRegex(ValueError, "appears more than once"):
            parse_collection_json(
                json.dumps(
                    {
                        "schema": EXPORT_SCHEMA,
                        "schema_version": EXPORT_SCHEMA_VERSION,
                        "cards": [
                            {"card_id": "card-1", "quantity": 1},
                            {"card_id": "card-1", "quantity": 2},
                        ],
                    }
                )
            )

    def test_catalog_search_combines_set_code_number_and_inventory_quantity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalog_path = root / "catalog.sqlite3"
            inventory_path = root / "inventory.sqlite3"
            catalog = CatalogDatabase(catalog_path)
            catalog.initialize()
            with catalog.connect() as connection:
                connection.execute(
                    "INSERT INTO sets(id, name, code, language) VALUES (?, ?, ?, ?)",
                    ("set-pre", "Prismatic Evolutions", "PRE", "en-US"),
                )
                connection.execute(
                    "INSERT INTO set_codes(set_id, code, code_type) VALUES (?, ?, ?)",
                    ("set-pre", "PRE", "printed"),
                )
                connection.execute(
                    """
                    INSERT INTO cards(
                        id, set_id, language, name, card_type, number, number_numeric,
                        printed_total, regulation_mark, primary_image_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("card-pre-011", "set-pre", "en-US", "Budew", "POKEMON", "011", 11, "131", "H", "https://example.test/card.jpg"),
                )
            InventoryDatabase(inventory_path).set_quantity("card-pre-011", 7)

            with (
                patch.object(app, "CARD_CATALOG_PATH", catalog_path),
                patch.object(app, "INVENTORY_PATH", inventory_path),
            ):
                result = catalog_search(
                    "PRE 11", format_name="standard", card_category="pokemon"
                )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["id"], "card-pre-011")
        self.assertEqual(result["items"][0]["quantity"], 7)
        self.assertEqual(result["language"], "en-US")

    def test_catalog_search_requires_submission_criteria_and_filters_format_and_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalog_path = root / "catalog.sqlite3"
            inventory_path = root / "inventory.sqlite3"
            catalog = CatalogDatabase(catalog_path)
            catalog.initialize()
            with catalog.connect() as connection:
                connection.execute(
                    "INSERT INTO sets(id, name, code, language) VALUES ('set-1', 'Test Set', 'TST', 'en-US')"
                )
                rows = [
                    ("g-pokemon", "G Pokémon", "POKEMON", "", "001", 1, "G", "COMMON"),
                    ("h-pokemon", "H Pokémon", "POKEMON", "", "002", 2, "H", "COMMON"),
                    ("i-supporter", "I Supporter", "TRAINER", "SUPPORTER", "003", 3, "I", "UNCOMMON"),
                    ("j-item", "J ACE SPEC Item", "TRAINER", "ITEM", "004", 4, "J", "ACE_SPEC_RARE"),
                ]
                connection.executemany(
                    """
                    INSERT INTO cards(
                        id, set_id, language, name, card_type, card_subtype,
                        number, number_numeric, regulation_mark, rarity
                    ) VALUES (?, 'set-1', 'en-US', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            with (
                patch.object(app, "CARD_CATALOG_PATH", catalog_path),
                patch.object(app, "INVENTORY_PATH", inventory_path),
            ):
                with self.assertRaisesRegex(ValueError, "Choose at least one"):
                    catalog_search()
                standard = catalog_search(format_name="standard")
                expanded = catalog_search(format_name="expanded")
                supporters = catalog_search(
                    format_name="standard", card_category="supporter"
                )
                items = catalog_search(format_name="standard", card_category="item")
                ace_specs = catalog_search(format_name="standard", card_category="ace-spec")
                facets = catalog_facets()

        self.assertEqual({item["regulation_mark"] for item in standard["items"]}, {"H", "I", "J"})
        self.assertEqual(expanded["total"], 4)
        self.assertEqual([item["id"] for item in supporters["items"]], ["i-supporter"])
        self.assertEqual([item["id"] for item in items["items"]], ["j-item"])
        self.assertEqual([item["id"] for item in ace_specs["items"]], ["j-item"])
        self.assertEqual(facets["formats"][0]["marks"], ["H", "I", "J"])

    def test_catalog_quantity_revalidates_canonical_card_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalog_path = root / "catalog.sqlite3"
            inventory_path = root / "inventory.sqlite3"
            catalog = CatalogDatabase(catalog_path)
            catalog.initialize()
            with catalog.connect() as connection:
                connection.execute(
                    "INSERT INTO sets(id, name, code, language) VALUES ('set-1', 'Test', 'TST', 'en-US')"
                )
                connection.execute(
                    "INSERT INTO cards(id, set_id, language, name, number) VALUES ('card-1', 'set-1', 'en-US', 'Budew', '004')"
                )
            with (
                patch.object(app, "CARD_CATALOG_PATH", catalog_path),
                patch.object(app, "INVENTORY_PATH", inventory_path),
            ):
                change = set_catalog_inventory_quantity({"card_id": "card-1", "quantity": 9})
                with self.assertRaisesRegex(ValueError, "not in the local English catalog"):
                    set_catalog_inventory_quantity({"card_id": "invented", "quantity": 9})

        self.assertEqual((change.card_id, change.quantity), ("card-1", 9))

    def test_automatic_scan_performance_is_logged_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scan_performance_it18.csv"
            record = {
                "scanned_at": "2026-08-13T15:00:00-04:00",
                "iteration": 18,
                "scan_id": "scan-timing-1",
                "ocr_engine": "RapidOCR",
                "ocr_elapsed_seconds": "4.250",
                "server_elapsed_seconds": "4.300",
                "ocr_time_budget_seconds": "10.0",
                "ocr_timed_out": "no",
                "treatments_attempted_json": '["rapidocr:original"]',
                "variant_count": 1,
            }
            with (
                patch.object(app, "SCAN_PERFORMANCE_PATH", path),
                app.SCAN_RECORDS_LOCK,
            ):
                app.SCAN_RECORDS["scan-timing-1"] = record
            try:
                with patch.object(app, "SCAN_PERFORMANCE_PATH", path):
                    first = save_scan_performance(
                        {"scan_id": "scan-timing-1", "client_total_seconds": 4.5}
                    )
                    save_scan_performance(
                        {"scan_id": "scan-timing-1", "client_total_seconds": 4.6}
                    )
            finally:
                with app.SCAN_RECORDS_LOCK:
                    app.SCAN_RECORDS.pop("scan-timing-1", None)

            with path.open("r", newline="", encoding="utf-8-sig") as source:
                rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 1)
        self.assertEqual(first["client_total_seconds"], "4.500")
        self.assertEqual(rows[0]["ocr_time_budget_seconds"], "10.0")
        self.assertEqual(rows[0]["treatments_attempted_json"], '["rapidocr:original"]')

    def test_inventory_snapshot_attaches_catalog_regulation_mark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalog_path = root / "catalog.sqlite3"
            inventory_path = root / "inventory.sqlite3"
            catalog = CatalogDatabase(catalog_path)
            catalog.initialize()
            with catalog.connect() as connection:
                connection.execute(
                    "INSERT INTO sets(id, name, code, language) VALUES (?, ?, ?, ?)",
                    ("set-1", "Test Set", "TST", "en-US"),
                )
                connection.execute(
                    """
                    INSERT INTO cards(
                        id, set_id, language, name, card_type, number,
                        number_numeric, regulation_mark, rarity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("card-1", "set-1", "en-US", "Budew", "POKEMON", "004", 4, "H", "ACE_SPEC_RARE"),
                )
                connection.execute(
                    "INSERT INTO card_types(card_id, position, type) VALUES (?, ?, ?)",
                    ("card-1", 0, "GRASS"),
                )
            InventoryDatabase(inventory_path).add_card("card-1")

            with (
                patch.object(app, "CARD_CATALOG_PATH", catalog_path),
                patch.object(app, "INVENTORY_PATH", inventory_path),
            ):
                snapshot = app.inventory_snapshot()

        self.assertEqual(snapshot["items"][0]["regulation_mark"], "H")
        self.assertEqual(snapshot["items"][0]["rarity"], "ACE_SPEC_RARE")
        self.assertTrue(snapshot["items"][0]["is_ace_spec"])
        self.assertTrue(snapshot["items"][0]["date_added"])
        self.assertTrue(snapshot["items"][0]["date_updated"])

    def test_element_view_keeps_other_card_categories_after_pokemon(self) -> None:
        items = [
            {
                "name": "Professor's Research",
                "card_type": "TRAINER",
                "card_subtype": "SUPPORTER",
                "display_subtype": "Supporter",
                "types": [],
            },
            {
                "name": "Budew",
                "card_type": "POKEMON",
                "card_subtype": "",
                "display_subtype": "",
                "types": ["GRASS"],
            },
            {
                "name": "Nest Ball",
                "card_type": "TRAINER",
                "card_subtype": "ITEM",
                "display_subtype": "Item",
                "types": [],
            },
        ]
        for item in items:
            item["element_group"] = app._inventory_element_group(item)
        items.sort(key=lambda item: app._inventory_sort_key(item, "element"))

        self.assertEqual(
            [(item["name"], item["element_group"]) for item in items],
            [("Budew", "Grass"), ("Nest Ball", "Item"), ("Professor's Research", "Supporter")],
        )

    @patch("app.lookup_confirmed_fields")
    def test_inventory_add_revalidates_an_exact_match(self, lookup) -> None:
        lookup.return_value = CardInfo(
            card_id="malie:sv5:123",
            card_name="Raging Bolt ex",
            status="accepted",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "inventory.sqlite3"
            with patch.object(app, "INVENTORY_PATH", path):
                info, change = add_inventory_card(
                    {
                        "set_code": "TEF",
                        "card_number": "123",
                        "set_total": "162",
                        "scan_id": "scan-1",
                        "quantity": 8,
                    }
                )

        self.assertEqual(info.card_id, "malie:sv5:123")
        self.assertEqual((change.quantity, change.quantity_delta), (8, 8))

    @patch("app.lookup_confirmed_fields")
    def test_inventory_rejects_review_or_no_match(self, lookup) -> None:
        lookup.return_value = CardInfo(status="review")

        with self.assertRaisesRegex(ValueError, "exact local catalog match"):
            add_inventory_card({"set_code": "TEF", "card_number": "123"})

    @patch("app.lookup_confirmed_fields")
    def test_inventory_rejects_invalid_batch_quantity(self, lookup) -> None:
        lookup.return_value = CardInfo(
            card_id="malie:sv5:123",
            status="accepted",
        )

        for invalid in (0, 100, 1.5, "eight"):
            with self.subTest(quantity=invalid):
                with self.assertRaisesRegex(ValueError, "quantity"):
                    add_inventory_card(
                        {
                            "set_code": "TEF",
                            "card_number": "123",
                            "quantity": invalid,
                        }
                    )

    @patch("app.find_exact_card")
    def test_fast_path_requires_an_exact_catalog_match(self, find_card) -> None:
        find_card.return_value = type(
            "Result",
            (),
            {"status": "no_match", "card": None},
        )()
        self.assertIsNone(exact_catalog_fields("PLM 113/094"))

        find_card.return_value = type(
            "Result",
            (),
            {
                "status": "exact",
                "card": type("Card", (), {"printed_total": "094"})(),
            },
        )()
        self.assertEqual(
            exact_catalog_fields("O PFLM 113/094"),
            ("", "PFL", "113", "094"),
        )
        self.assertIsNone(exact_catalog_fields("O PFLM 113/999"))

    def test_literal_groups_preserve_unknown_letters_and_leading_zeroes(self) -> None:
        self.assertEqual(
            extract_literal_groups("ZXQ EN 001/999"),
            ("ZXQ", "001 / 999"),
        )

    def test_footer_groups_keep_regulation_and_set_but_ignore_language(self) -> None:
        self.assertEqual(
            extract_literal_groups("H SSP en 075/191"),
            ("H SSP", "075 / 191"),
        )
        self.assertEqual(
            extract_footer_fields("H SSP en 075/191"),
            ("H", "SSP", "075", "191"),
        )

    def test_only_exact_english_marker_is_ignored(self) -> None:
        self.assertEqual(
            extract_literal_groups("H ENA en 075/191"),
            ("H ENA", "075 / 191"),
        )

    def test_joined_language_marker_is_removed_from_known_set_code(self) -> None:
        self.assertEqual(
            extract_footer_fields("MEGEN 086/132"),
            ("", "MEG", "086", "132"),
        )

    def test_literal_dark_badge_read_is_not_rewritten_by_field_parser(self) -> None:
        self.assertEqual(
            extract_footer_fields("☐ BUKm 031/086"),
            ("", "", "031", "086"),
        )

    def test_catalog_validated_repair_handles_dark_badges(self) -> None:
        self.assertEqual(
            app.exact_catalog_fields("☐ BUKm 031/086"),
            ("", "BLK", "031", "086"),
        )
        self.assertEqual(
            app.exact_catalog_fields("WIT 034/086"),
            ("", "WHT", "034", "086"),
        )

    def test_low_confidence_alternate_can_supply_unique_exact_dark_badge(self) -> None:
        self.assertEqual(
            app.exact_catalog_fields_from_readings(
                "BU031/086",
                (
                    LiteralReading("BU031/086", 0.949, "original"),
                    LiteralReading("☐ BUKm 031/086", 0.772, "enlarged_gray"),
                ),
            ),
            ("", "BLK", "031", "086"),
        )

    def test_missing_set_code_is_not_guessed_from_shared_number_and_total(self) -> None:
        self.assertEqual(
            extract_footer_fields("034/086"),
            ("", "", "034", "086"),
        )

    def test_partial_tef_badge_requires_retained_prefix_and_both_numbers(self) -> None:
        self.assertEqual(
            app.exact_catalog_fields_from_readings(
                "085/162",
                (
                    LiteralReading("T 085/162", 0.911, "original"),
                    LiteralReading("T085/162", 0.967, "enlarged_color"),
                    LiteralReading("085/162", 1.0, "enlarged_gray_sharp"),
                ),
            ),
            ("", "TEF", "085", "162"),
        )
        self.assertIsNone(app.exact_catalog_fields("085/162"))
        self.assertIsNone(app.exact_catalog_fields("T 085"))

    def test_alternate_reading_recovers_set_code_without_rewriting_literal(self) -> None:
        fields = extract_footer_fields_from_readings(
            "PELD113/094",
            (
                LiteralReading("PELD113/094", 0.922, "enlarged_color"),
                LiteralReading("O PFLa 113/094", 0.846, "enlarged_gray"),
            ),
        )

        self.assertEqual(fields, ("", "PFL", "113", "094"))

    def test_attached_regulation_mark_and_language_noise_are_separated(self) -> None:
        self.assertEqual(
            extract_footer_fields("IDRIN 135/182"),
            ("I", "DRI", "135", "182"),
        )

    def test_benchmark_save_preserves_detected_and_corrected_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "ocr_reads_it5.csv"
            record = {
                "scanned_at": "2026-07-26T12:00:00-04:00",
                "iteration": 18,
                "scan_id": "scan-1",
                "image_name": "card.png",
                "crop_path": str(Path(temp_dir) / "scan-1.png"),
                "ocr_engine": "RapidOCR",
                "literal_text": "PBE 011/13I",
                "primary_confidence": "0.875000",
                "detected_letters": "PBE I",
                "detected_numbers": "011 / 13",
                "variant_readings_json": "[]",
            }
            with patch.object(app, "CSV_PATH", csv_path):
                with app.SCAN_RECORDS_LOCK:
                    app.SCAN_RECORDS["scan-1"] = record
                saved = save_benchmark_label(
                    {
                        "iteration": 18,
                        "scan_id": "scan-1",
                        "corrected_letters": "PRE",
                        "corrected_numbers": "011 / 131",
                    }
                )

            self.assertEqual(saved["was_corrected"], "yes")
            with csv_path.open("r", newline="", encoding="utf-8-sig") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(rows[0]["detected_letters"], "PBE I")
            self.assertEqual(rows[0]["corrected_letters"], "PRE")
            self.assertEqual(rows[0]["corrected_numbers"], "011 / 131")
            self.assertNotIn("scan-1", app.SCAN_RECORDS)

    def test_iteration_mismatch_cannot_save(self) -> None:
        with self.assertRaisesRegex(ValueError, "iteration mismatch"):
            save_benchmark_label(
                {
                    "iteration": 4,
                    "scan_id": "anything",
                    "corrected_letters": "PRE",
                    "corrected_numbers": "011 / 131",
                }
            )

    def test_webcam_ui_has_capture_and_cleanup_controls(self) -> None:
        html = (app.LEGACY_SCANNER_WEB_ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (app.LEGACY_SCANNER_WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="start_camera"', html)
        self.assertIn('id="capture_frame"', html)
        self.assertIn('id="next_card"', html)
        self.assertIn('id="stop_camera"', html)
        self.assertIn('id="reuse_selection"', html)
        self.assertIn('id="lookup_card"', html)
        self.assertIn('id="scan_timing"', html)
        self.assertIn('id="inventory_add_quantity"', html)
        self.assertLess(
            html.index('id="add_inventory"'),
            html.index('id="regulation_mark"'),
        )
        self.assertIn("ITERATION 18", html)
        self.assertIn("SEARCH-FIRST INTAKE", html)
        self.assertIn("EDITABLE CORRECTIONS", html)
        self.assertIn("fetch('/lookup'", javascript)
        self.assertIn("await lookupCurrentCard()", javascript)
        self.assertIn("const UI_ITERATION = 18", javascript)
        self.assertIn("fetch('/scan/timing'", javascript)
        self.assertIn("10s LIMIT REACHED", javascript)
        self.assertIn('id="theme_toggle"', html)
        self.assertIn('src="/theme.js"', html)
        theme_javascript = (app.WEB_ROOT / "theme.js").read_text(encoding="utf-8")
        inventory_html = (app.WEB_ROOT / "inventory.html").read_text(encoding="utf-8")
        inventory_javascript = (app.WEB_ROOT / "inventory.js").read_text(encoding="utf-8")
        card_inspector_javascript = (app.WEB_ROOT / "card-inspector.js").read_text(encoding="utf-8")
        stylesheet = (app.WEB_ROOT / "style.css").read_text(encoding="utf-8")
        self.assertIn('id="theme_toggle"', inventory_html)
        self.assertIn('src="/theme.js"', inventory_html)
        self.assertIn('id="card_drawer"', inventory_html)
        self.assertIn('data-mode="typing"', inventory_html)
        self.assertIn('id="inventory_search"', inventory_html)
        self.assertIn('class="binder-top-navigation"', inventory_html)
        self.assertIn('href="/deck">Check a Deck</a>', inventory_html)
        self.assertLess(
            inventory_html.index('class="binder-top-navigation"'),
            inventory_html.index('id="inventory_groups"'),
        )
        self.assertIn("function categoryKey", inventory_javascript)
        self.assertIn("function isAceSpec", inventory_javascript)
        self.assertIn("'ace-spec', 'ACE SPEC'", inventory_javascript)
        self.assertIn("function openDrawer", inventory_javascript)
        self.assertIn('src="/card-inspector.js"', inventory_html)
        self.assertIn('id="drawer_image_button"', inventory_html)
        self.assertIn("window.CardInspector.open(card", inventory_javascript)
        self.assertIn("window.CardInspector = {open, close}", card_inspector_javascript)
        self.assertIn('id="drawer_quantity_input"', inventory_html)
        self.assertIn('id="drawer_quantity_save"', inventory_html)
        self.assertIn("async function saveDrawerQuantity", inventory_javascript)
        self.assertIn("Remove ${card.name} from your collection?", inventory_javascript)
        self.assertIn("fetch('/inventory/set-quantity'", inventory_javascript)
        self.assertIn("CARD_IMAGE_MAX_CONCURRENT = 6", inventory_javascript)
        self.assertIn("CARD_IMAGE_MAX_RETRIES = 2", inventory_javascript)
        self.assertIn("CARD_IMAGE_TIMEOUT_MS = 7000", inventory_javascript)
        self.assertIn("function observeCardImage", inventory_javascript)
        self.assertIn("collection_retry", inventory_javascript)
        self.assertIn(".binder-card-art.image-loading::before", stylesheet)
        self.assertIn('href="/inventory/export.csv"', inventory_html)
        self.assertIn('href="/inventory/export.json"', inventory_html)
        self.assertIn(".binder-export-actions", stylesheet)
        self.assertIn("No cards in your inventory match these filters", inventory_javascript)
        self.assertIn("prefers-color-scheme: dark", theme_javascript)
        self.assertIn("localStorage.setItem", theme_javascript)
        self.assertIn(':root[data-theme="dark"]', stylesheet)
        self.assertIn('href="/inventory"', html)
        search_html = (app.WEB_ROOT / "search.html").read_text(encoding="utf-8")
        search_javascript = (app.WEB_ROOT / "search.js").read_text(encoding="utf-8")
        self.assertIn("ITERATION 18", search_html)
        self.assertIn('src="/card-inspector.js"', search_html)
        self.assertNotIn('href="/scan"', search_html)
        self.assertNotIn('href="/scan"', inventory_html)
        self.assertIn('id="catalog_query"', search_html)
        self.assertIn('id="catalog_set"', search_html)
        self.assertIn('id="catalog_format"', search_html)
        self.assertIn('value="standard" selected', search_html)
        self.assertIn('id="catalog_card_type"', search_html)
        self.assertIn('id="catalog_active_filters"', search_html)
        self.assertIn('id="catalog_reset_filters"', search_html)
        self.assertIn('value="ace-spec"', search_html)
        self.assertNotIn('id="catalog_regulation"', search_html)
        self.assertIn("Standard · Marks H, I, J", search_html)
        self.assertIn("Search cards</button>", search_html)
        self.assertIn('id="catalog_pagination_bottom"', search_html)
        self.assertIn('id="catalog_next_bottom"', search_html)
        self.assertIn('id="catalog_back_to_top"', search_html)
        self.assertIn("window.scrollTo({top: 0, behavior: 'smooth'})", search_javascript)
        self.assertIn("fetch('/catalog/facets'", search_javascript)
        self.assertIn("window.CardInspector.open(card", search_javascript)
        self.assertIn("Choose at least one search option", search_javascript)
        self.assertIn("function renderActiveFilters", search_javascript)
        self.assertIn("Format: ${label}", search_javascript)
        self.assertIn("fetch('/inventory/set-quantity'", search_javascript)
        self.assertIn("CURRENT OWNED", search_javascript)
        self.assertIn("catalog-save-feedback", search_javascript)
        self.assertIn("Saved: ${card.quantity} owned", search_javascript)
        deck_html = (app.WEB_ROOT / "deck.html").read_text(encoding="utf-8")
        deck_javascript = (app.WEB_ROOT / "deck.js").read_text(encoding="utf-8")
        self.assertNotIn('href="/scan"', deck_html)
        self.assertIn('id="deck_list"', deck_html)
        self.assertIn("deck-missing-gallery", deck_javascript)
        self.assertIn("deck-owned-gallery", deck_javascript)
        self.assertIn("Full deck list", deck_javascript)
        self.assertLess(
            deck_javascript.index("Missing cards"),
            deck_javascript.index("Cards you already have"),
        )
        self.assertLess(
            deck_javascript.index("Cards you already have"),
            deck_javascript.index("Full deck list"),
        )
        self.assertIn("Missing cards", deck_javascript)
        self.assertIn("Cards you already have", deck_javascript)
        self.assertIn("Same-name substitute available", deck_javascript)
        self.assertIn("possible_substitute_cards", deck_javascript)
        self.assertIn("Basic Energy ignored", deck_javascript)
        self.assertIn("ignored_basic_energy_cards", deck_javascript)
        self.assertIn("Basic Energy is ignored", deck_html)
        self.assertIn("Iteration 18 readability pass", stylesheet)
        self.assertIn("fetch('/inventory/add'", javascript)
        self.assertIn("fetch('/inventory/undo'", javascript)
        self.assertIn("lastLookupStatus !== 'accepted'", javascript)
        self.assertIn("lookupButton.hidden = true", javascript)
        self.assertIn("if (!mediaStream || scanInProgress) return", javascript)
        self.assertIn("nextCardButton.disabled = true", javascript)
        self.assertIn("Exact visual match found. No corrections are needed", javascript)
        self.assertIn("lastLookupStatus === 'no_match'", javascript)
        self.assertNotIn("warm_up_ocr()", Path(app.__file__).read_text(encoding="utf-8"))
        self.assertIn('src="/legacy-webcam-scanner/app.js"', html)
        self.assertIn("nothing was added", javascript.lower())
        self.assertIn("ONLY OCR AREA", html)
        self.assertIn("navigator.mediaDevices.getUserMedia", javascript)
        self.assertIn("function fixedIdentifierSelection", javascript)
        self.assertIn("IDENTIFIER_GUIDE = {left: 0.06, top: 0.915, width: 0.26, height: 0.055}", javascript)
        self.assertIn("lockedSelectionNormalized = fixedIdentifierSelection", javascript)
        self.assertIn(
            "mediaStream.getTracks().forEach(track => track.stop())",
            javascript,
        )
        self.assertIn(
            "window.addEventListener('pagehide', stopMediaTracks)",
            javascript,
        )
        self.assertIn(
            "window.addEventListener('beforeunload', stopMediaTracks)",
            javascript,
        )


if __name__ == "__main__":
    unittest.main()
