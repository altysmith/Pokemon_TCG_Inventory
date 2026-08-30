import unittest
from pathlib import Path

import app


ROOT = Path(__file__).resolve().parents[1]


class ProjectLayoutTests(unittest.TestCase):
    def test_root_has_one_normal_windows_launcher(self) -> None:
        self.assertEqual(
            [path.name for path in ROOT.glob("*.bat")],
            ["Start Pokemon Collection.bat"],
        )

    def test_maintenance_launchers_are_isolated_under_tools(self) -> None:
        tools = {path.name for path in (ROOT / "tools").glob("*.bat")}
        self.assertEqual(
            tools,
            {
                "_ensure_dependencies.bat",
                "check_card_updates.bat",
                "run_card_api.bat",
                "update_card_database.bat",
            },
        )
        launcher = (ROOT / "Start Pokemon Collection.bat").read_text(encoding="utf-8")
        self.assertIn(r"tools\_ensure_dependencies.bat", launcher)

    def test_legacy_outputs_default_outside_the_active_root(self) -> None:
        evidence = ROOT / "legacy_webcam_scanner" / "evidence"
        self.assertEqual(app.CSV_PATH.parent, evidence)
        self.assertEqual(app.SCAN_PERFORMANCE_PATH.parent, evidence)
        self.assertTrue(app.CROP_DIR.is_relative_to(evidence))

    def test_regression_fixture_is_portable(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "saved_scan_regressions.csv"
        self.assertTrue(fixture.is_file())


if __name__ == "__main__":
    unittest.main()
