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
        self.assertIn(r"tools\launch_collection_app.ps1", launcher)
        app_launcher = (ROOT / "tools" / "launch_collection_app.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn(r'_ensure_dependencies.bat', app_launcher)
        self.assertIn("Start-Process -FilePath $url", app_launcher)
        self.assertIn("desktop-session/status", app_launcher)
        self.assertNotIn("Get-AppBrowser", app_launcher)
        self.assertNotIn("msedge.exe", app_launcher)

    def test_all_primary_pages_keep_the_desktop_session_alive(self) -> None:
        for filename in ("search.html", "inventory.html", "deck.html"):
            html = (ROOT / "web" / filename).read_text(encoding="utf-8")
            self.assertIn('src="/desktop-session.js"', html)
        session_javascript = (ROOT / "web" / "desktop-session.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("new EventSource", session_javascript)
        self.assertIn("sessionStorage", session_javascript)

    def test_desktop_shortcut_uses_the_current_collection_icon(self) -> None:
        shortcut_script = (
            ROOT / "tools" / "create_desktop_shortcut.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn(r"assets\pokemon-card-collection.ico", shortcut_script)
        self.assertTrue((ROOT / "assets" / "pokemon-card-collection.ico").is_file())
        self.assertTrue((ROOT / "assets" / "pokemon-card-collection.png").is_file())
        self.assertFalse((ROOT / "assets" / "pokemon-collection.ico").exists())
        self.assertFalse((ROOT / "assets" / "pokemon-collection.png").exists())

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
