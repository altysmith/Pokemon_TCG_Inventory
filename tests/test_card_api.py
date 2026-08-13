import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as scanner_app
from card_api.api import create_app
from card_api.catalog import find_exact_card
from card_api.importer import import_downloaded
from card_api.malie import download_updates, inspect_updates


SET_URL = "https://cdn.malie.io/file/malie-io/tcgl/export/v-test/sv8.en-US.json"


def sample_cards():
    return [
        {
            "name": "Smoochum",
            "card_type": "POKEMON",
            "lang": "en-US",
            "foil": {"type": "FLAT_SILVER", "mask": "REVERSE"},
            "regulation_mark": "H",
            "collector_number": {
                "full": "075/191",
                "numerator": "075",
                "denominator": "191",
                "numeric": 75,
            },
            "rarity": {"designation": "COMMON"},
            "stage": "BASIC",
            "hp": 30,
            "text": [
                {
                    "kind": "ATTACK",
                    "name": "Delightful Kiss",
                    "text": "Search your deck for up to 2 Basic Energy cards.",
                    "cost": ["COLORLESS"],
                }
            ],
            "ext": {"tcgl": {"cardID": "sv8_75_ph", "key": "sv8"}},
            "images": {
                "tcgl": {
                    "jpg": {
                        "front": "https://cdn.malie.io/card/sv8_en_075_ph.jpg"
                    }
                }
            },
        },
        {
            "name": "Smoochum",
            "card_type": "POKEMON",
            "lang": "en-US",
            "regulation_mark": "H",
            "collector_number": {
                "full": "075/191",
                "numerator": "075",
                "denominator": "191",
                "numeric": 75,
            },
            "rarity": {"designation": "COMMON"},
            "stage": "BASIC",
            "hp": 30,
            "text": [
                {
                    "kind": "ATTACK",
                    "name": "Delightful Kiss",
                    "text": "Search your deck for up to 2 Basic Energy cards.",
                    "cost": ["COLORLESS"],
                }
            ],
            "ext": {"tcgl": {"cardID": "sv8_75", "key": "sv8"}},
            "images": {
                "tcgl": {
                    "jpg": {
                        "front": "https://cdn.malie.io/card/sv8_en_075_std.jpg"
                    }
                }
            },
        },
        {
            "name": "",
            "card_type": "POKEMON",
            "collector_number": {
                "full": "076/191",
                "numerator": "076",
                "denominator": "191",
                "numeric": 76,
            },
            "hp": 0,
            "text": [],
            "images": {},
        },
    ]


def fake_source(cards):
    set_bytes = json.dumps(cards, ensure_ascii=False).encode("utf-8")
    upstream_hash = hashlib.md5(set_bytes).hexdigest()  # Malie index hash format
    index = {
        "en-US": {
            "sv8": {
                "path": "v-test/sv8.en-US.json",
                "name": "<i>Scarlet &amp; Violet—Surging Sparks</i>",
                "num": len(cards),
                "hash": upstream_hash,
                "abbr": "SSP",
            }
        }
    }
    index_bytes = json.dumps(index, ensure_ascii=False).encode("utf-8")

    def fetch(url):
        if url.endswith("index.json"):
            return index_bytes
        if url == SET_URL:
            return set_bytes
        raise AssertionError(f"Unexpected URL: {url}")

    return fetch


def fake_base_and_alt_source():
    base = sample_cards()[1]
    base["set_icon"] = "SSP_EN"
    alt = json.loads(json.dumps(base))
    alt["foil"] = {"type": "FLAT_SILVER", "mask": "REVERSE"}
    alt["ext"]["tcgl"]["cardID"] = "svalt_1"
    alt["images"]["tcgl"]["jpg"]["front"] = "https://cdn.malie.io/card/svalt_1.jpg"
    payloads = {
        "v-test/sv8.en-US.json": json.dumps([base]).encode("utf-8"),
        "v-test/svalt.en-US.json": json.dumps([alt]).encode("utf-8"),
    }
    index = {"en-US": {}}
    for source_set_id in ("svalt", "sv8"):
        path = f"v-test/{source_set_id}.en-US.json"
        index["en-US"][source_set_id] = {
            "path": path,
            "name": "" if source_set_id == "svalt" else "Surging Sparks",
            "num": 1,
            "hash": hashlib.md5(payloads[path]).hexdigest(),
            "abbr": "SVALT" if source_set_id == "svalt" else "SSP",
        }
    index_bytes = json.dumps(index).encode("utf-8")

    def fetch(url):
        if url.endswith("index.json"):
            return index_bytes
        path = url.split("/export/", 1)[1]
        return payloads[path]

    return fetch


class MalieUpdateTests(unittest.TestCase):
    def test_check_and_download_preserve_raw_json_with_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory) / "raw"
            fetch = fake_source(sample_cards())

            _raw_index, _index, statuses = inspect_updates(raw_root=raw_root, fetch=fetch)
            self.assertEqual(statuses[0].status, "new")

            download_updates(raw_root=raw_root, fetch=fetch)
            manifest = json.loads((raw_root / "manifest.json").read_text(encoding="utf-8"))
            saved_path = raw_root / manifest["sets"]["en-US:sv8"]["local_path"]
            self.assertEqual(json.loads(saved_path.read_bytes()), sample_cards())
            self.assertEqual(len(manifest["sets"]["en-US:sv8"]["sha256"]), 64)

            _raw_index, _index, statuses = inspect_updates(raw_root=raw_root, fetch=fetch)
            self.assertEqual(statuses[0].status, "current")

    def test_cross_set_alt_bucket_attaches_variant_to_printed_set(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_root = root / "raw"
            database_path = root / "catalog.sqlite3"
            download_updates(raw_root=raw_root, fetch=fake_base_and_alt_source())

            result = import_downloaded(database_path=database_path, raw_root=raw_root)

            self.assertEqual(result.sets_imported, 1)
            self.assertEqual(result.cards_imported, 1)
            self.assertEqual(result.source_records_imported, 2)
            self.assertEqual(result.cards_rejected, 0)
            client = TestClient(create_app(database_path))
            found = client.get("/cards", params={"set_code": "SSP", "number": "075"}).json()
            detail = client.get(f"/cards/{found['items'][0]['id']}").json()
            self.assertEqual(len(detail["variants"]), 2)


class ImportAndApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.raw_root = root / "raw"
        self.database_path = root / "catalog.sqlite3"
        download_updates(raw_root=self.raw_root, fetch=fake_source(sample_cards()))
        self.result = import_downloaded(
            database_path=self.database_path, raw_root=self.raw_root
        )
        self.client = TestClient(create_app(self.database_path))

    def tearDown(self):
        self.temp.cleanup()

    def test_import_rejects_invalid_card_and_records_validation(self):
        self.assertEqual(self.result.sets_imported, 1)
        self.assertEqual(self.result.cards_imported, 1)
        self.assertEqual(self.result.source_records_imported, 2)
        self.assertEqual(self.result.cards_rejected, 1)
        self.assertGreaterEqual(self.result.errors, 1)

    def test_required_endpoints_and_provenance(self):
        cards = self.client.get("/cards", params={"set_code": "ssp", "number": "75"})
        self.assertEqual(cards.status_code, 200)
        self.assertEqual(cards.json()["total"], 1)
        found = cards.json()["items"][0]
        self.assertEqual(found["name"], "Smoochum")
        self.assertEqual(found["regulation_mark"], "H")

        detail = self.client.get(f"/cards/{found['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["text_entries"][0]["kind"], "ATTACK")
        self.assertEqual(detail.json()["provenance"][0]["source_key"], "malie-tcgl")
        self.assertEqual(detail.json()["provenance"][0]["raw_record_index"], 0)
        self.assertEqual(len(detail.json()["variants"]), 2)

        search = self.client.get("/cards/search", params={"q": "smooch"})
        self.assertEqual(search.json()["total"], 1)

        sets = self.client.get("/sets")
        self.assertEqual(sets.json()["items"][0]["code"], "SSP")
        set_id = sets.json()["items"][0]["id"]
        set_cards = self.client.get(f"/sets/{set_id}/cards")
        self.assertEqual(set_cards.json()["total"], 1)

    def test_shared_exact_lookup_normalizes_leading_zeroes(self):
        result = find_exact_card("ssp", "75", database_path=self.database_path)

        self.assertEqual(result.status, "exact")
        self.assertEqual(result.card.card_name, "Smoochum")
        self.assertEqual(result.card.card_number, "075")

    def test_scanner_lookup_uses_local_catalog_and_reviews_total_conflict(self):
        with patch.object(scanner_app, "CARD_CATALOG_PATH", self.database_path):
            exact = scanner_app.lookup_confirmed_fields(
                {"set_code": "SSP", "card_number": "075", "set_total": "191"}
            )
            conflict = scanner_app.lookup_confirmed_fields(
                {"set_code": "SSP", "card_number": "075", "set_total": "999"}
            )

        self.assertEqual((exact.status, exact.card_name), ("accepted", "Smoochum"))
        self.assertEqual(exact.card_id, "malie-tcgl:en-US:sv8:075")
        self.assertEqual(exact.source, "local Malie TCGL catalog")
        self.assertEqual(conflict.status, "review")
        self.assertIn("printed total conflicts", conflict.review_reasons[0])

    def test_scanner_inventory_add_and_undo_use_canonical_card_id(self):
        inventory_path = Path(self.temp.name) / "user_data" / "inventory.sqlite3"
        with (
            patch.object(scanner_app, "CARD_CATALOG_PATH", self.database_path),
            patch.object(scanner_app, "INVENTORY_PATH", inventory_path),
        ):
            info, added = scanner_app.add_inventory_card(
                {
                    "set_code": "SSP",
                    "card_number": "075",
                    "set_total": "191",
                    "scan_id": "scan-1",
                }
            )
            undone = scanner_app.undo_inventory_add({"event_id": added.event_id})

        self.assertEqual(info.card_id, "malie-tcgl:en-US:sv8:075")
        self.assertEqual((added.quantity, undone.quantity), (1, 0))

    def test_unknown_card_is_404_not_a_guess(self):
        response = self.client.get("/cards/not-a-real-card")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
