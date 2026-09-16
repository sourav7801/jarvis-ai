import unittest
from pathlib import Path

from workstation.v17_terminal_http import V17_STATUS_PATH, _v17_status


ROOT = Path(__file__).resolve().parents[1]


class _Service:
    def status(self, workspace):
        return {
            "installed": True,
            "workspace": workspace,
            "verified_auto_option_underlyings": ["BANKNIFTY", "NIFTY", "SENSEX"],
            "decision_source": "LIVE_PROVIDER_DATA_AND_COMPLETED_BARS",
        }


class _Runtime:
    v17_autonomy_service = _Service()


class V17TerminalIdentityTests(unittest.TestCase):
    def test_status_endpoint_is_v17_and_paper_only(self):
        payload = _v17_status(_Runtime(), "INTRADAY")
        self.assertEqual(V17_STATUS_PATH, "/api/v17/trading/status")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["version"], "17.0")
        self.assertEqual(payload["runtime_identity"], "V17_AUTONOMOUS_OPTIONS")
        self.assertEqual(payload["workspace"], "INTRADAY")
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_execution"])
        self.assertFalse(payload["automatic_broker_order"])
        self.assertTrue(payload["live_orders_locked"])

    def test_v17_launcher_uses_v17_http_handler(self):
        text = (ROOT / "start_jarvis_professional_terminal_v17.py").read_text(encoding="utf-8")
        self.assertIn("from workstation.v17_terminal_http import build_handler", text)
        self.assertIn("/api/v17/trading/status", text)

    def test_v17_browser_overlay_is_present(self):
        text = (ROOT / "workstation" / "quant_terminal_v2_static" / "v17_runtime.js").read_text(encoding="utf-8")
        self.assertIn("V17 · ACTIVE", text)
        self.assertIn("AUTONOMOUS OPTIONS CONVERGENCE", text)
        self.assertIn("/api/v17/trading/status", text)


if __name__ == "__main__":
    unittest.main()
