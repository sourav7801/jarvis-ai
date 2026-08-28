import unittest
from omni.workspace_command_center import WORKSPACES, get_workspace, snapshot


class WorkspaceCommandCenterTests(unittest.TestCase):
    def test_required_workspaces_exist(self):
        keys = {item.key for item in WORKSPACES}
        self.assertTrue(
            {
                "master", "company", "quant", "paper", "research",
                "missions", "memory", "voice", "apps", "system",
                "dev", "fyers",
            } <= keys
        )

    def test_safety_is_fail_closed(self):
        payload = snapshot()
        self.assertIs(payload["safety"]["paper_only"], True)
        self.assertIs(payload["safety"]["live_execution"], False)
        self.assertIs(payload["safety"]["automatic_broker_order"], False)

    def test_codex_foundations_are_reported(self):
        payload = snapshot()
        for key in (
            "service_health_contract",
            "loopback_http",
            "official_exchange_calendar",
            "paper_scan_ledger",
        ):
            self.assertIn(key, payload["codex_foundations"])

    def test_quant_terminal_contract(self):
        quant = get_workspace("quant")
        self.assertEqual(quant["port"], 8787)
        self.assertIn("127.0.0.1:8787", quant["url"])

    def test_company_open_command(self):
        company = get_workspace("company")
        self.assertEqual(company["command"], "open company os")


if __name__ == "__main__":
    unittest.main()
