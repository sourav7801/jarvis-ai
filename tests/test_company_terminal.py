from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "workstation" / "jarvis_os_v3_assets"


class CompanyTerminalTests(unittest.TestCase):
    def test_company_os_is_a_real_standalone_terminal(self):
        markup = (ASSETS / "company.html").read_text(encoding="utf-8")
        script = (ASSETS / "company.js").read_text(encoding="utf-8")
        styles = (ASSETS / "company.css").read_text(encoding="utf-8")

        self.assertIn("JARVIS COMPANY OPERATING SYSTEM", markup)
        for element in (
            "ventureName", "ventureIdea", "departmentBoard", "researchTracks",
            "artifactBoard", "approvalBoard", "roadmapBoard", "companyCommand",
            "companyListen", "companyVoiceState", "activityBoard",
        ):
            self.assertIn(f'id="{element}"', markup)
        self.assertIn('/api/company-os', script)
        self.assertIn('/api/command', script)
        self.assertIn('input_mode: "typed"', script)
        self.assertIn('/api/voice/owner-status', script)
        self.assertIn('input_mode: "voice"', script)
        self.assertIn("SpeechRecognition", script)
        self.assertIn("state.external_action_queue?.actions", script)
        self.assertIn("state.autopilot_runs", script)
        self.assertIn("node.append(body,badge)", script)
        self.assertIn("EXTERNAL ACTIONS APPROVAL-GATED", markup)
        self.assertIn("company-terminal", styles)

    def test_master_server_and_navigation_expose_company_terminal(self):
        server = (ROOT / "workstation" / "jarvis_os_v3.py").read_text(encoding="utf-8")
        master = (ASSETS / "index.html").read_text(encoding="utf-8")
        app = (ASSETS / "app.js").read_text(encoding="utf-8")

        self.assertIn('parsed.path == "/company.html"', server)
        self.assertIn('parsed.path == "/company.js"', server)
        self.assertIn('parsed.path == "/company.css"', server)
        self.assertIn("/company.html", master)
        self.assertIn('action.window === "company"', app)

    def test_company_terminal_contains_no_external_execution_claim(self):
        script = (ASSETS / "company.js").read_text(encoding="utf-8")
        forbidden = ("place_order", "live_execution: true", "publish_post", "send_email")
        for value in forbidden:
            self.assertNotIn(value, script)


if __name__ == "__main__":
    unittest.main()
