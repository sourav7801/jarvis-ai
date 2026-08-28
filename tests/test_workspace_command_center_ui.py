import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "workstation" / "jarvis_os_v3_assets" / "app.js"
CSS = ROOT / "workstation" / "jarvis_os_v3_assets" / "styles.css"
SERVER = ROOT / "workstation" / "jarvis_os_v3.py"


class WorkspaceCommandCenterUITests(unittest.TestCase):
    def test_frontend_marker_and_launcher_exist(self):
        text = JS.read_text(encoding="utf-8")
        self.assertIn("JARVIS_V6_COMMAND_CENTER_UI", text)
        self.assertIn("jarvis-command-center-button", text)
        self.assertIn("/api/command-center", text)
        self.assertNotIn("body.innerHTML =", text)

    def test_css_marker_exists(self):
        self.assertIn(
            "JARVIS_V6_COMMAND_CENTER_UI_CSS",
            CSS.read_text(encoding="utf-8"),
        )

    def test_server_exposes_command_center_api(self):
        text = SERVER.read_text(encoding="utf-8")
        self.assertIn("JARVIS_V6_COMMAND_CENTER_API", text)
        self.assertIn('/api/command-center', text)


if __name__ == "__main__":
    unittest.main()
