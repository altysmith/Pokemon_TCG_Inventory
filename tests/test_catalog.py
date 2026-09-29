import unittest

from card_scanner.catalog import known_set_codes, set_catalog


class CatalogTests(unittest.TestCase):
    def test_catalog_has_official_snapshot_and_local_promo(self) -> None:
        codes = known_set_codes()
        self.assertGreaterEqual(len(codes), 140)
        self.assertTrue(
            {"ASC", "MEG", "MEP", "PRE", "PAL", "DRI", "POR"} <= codes
        )

    def test_mep_has_offline_validation_metadata(self) -> None:
        details = set_catalog()["MEP"]
        self.assertEqual(details["tcgdex_id"], "mep")
        self.assertTrue(details["promo"])

    def test_ssp_has_verified_tcgdex_mapping(self) -> None:
        details = set_catalog()["SSP"]
        self.assertEqual(details["tcgdex_id"], "sv08")
        self.assertEqual(details["printed_total"], 191)


if __name__ == "__main__":
    unittest.main()
