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
        self.assertEqual(payload["version"], "17.4.1")
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

    def test_v17_root_removes_legacy_browser_overlay_stack(self):
        text = (ROOT / "workstation" / "v17_terminal_http.py").read_text(encoding="utf-8")
        for asset in (
            "v12_paper_intelligence.js",
            "v13_contextual_paper_runtime.js",
            "v14_execution_runtime.js",
            "v141_risk_geometry_runtime.js",
            "v15_market_reasoning_runtime.js",
            "v16_workspace.js",
            "v16_option_execution.js",
            "v16_option_readiness_runtime.js",
            "adaptive_brain_runtime.js",
            "advanced_terminal_runtime.js",
        ):
            self.assertIn(asset, text)
        self.assertIn("V17 owns the professional Options surface", text)

    def test_chart_layout_supports_all_1_to_8_values(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        js = (root / "workstation" / "quant_terminal_v2_static" / "app.js").read_text(encoding="utf-8")
        css = (root / "workstation" / "quant_terminal_v2_static" / "style.css").read_text(encoding="utf-8")
        for value in range(1, 9):
            if value not in (1, 2, 4, 6, 8):
                self.assertIn(f"layout-{value}", css)
        self.assertIn("for(let index=0;index<layout;index++)", js)
        self.assertIn("for(let offset=1;offset<order.length;offset+=2)", js)

    def test_v17_options_transition_is_lightweight(self):
        text = (ROOT / "workstation" / "quant_terminal_v2_static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('if(activeWorkspace==="OPTIONS") return;', text)
        self.assertIn('if(activeWorkspace!=="OPTIONS"){', text)

    def test_v17_nautilus_uses_isolated_python_when_available(self):
        text = (ROOT / "scripts" / "jarvis_runtime_supervisor_v17.py").read_text(encoding="utf-8")
        self.assertIn(".venv-nautilus-new", text)
        self.assertIn("JARVIS_NAUTILUS_PY", text)

    def test_v17_browser_overlay_is_present(self):
        text = (ROOT / "workstation" / "quant_terminal_v2_static" / "v17_runtime.js").read_text(encoding="utf-8")
        self.assertIn("V17 · ACTIVE", text)
        self.assertIn("ONE-TOUCH AUTONOMOUS PAPER TRADING", text)
        self.assertIn("CHART-FIRST", text)
        self.assertIn("/api/v17/trading/status", text)


if __name__ == "__main__":
    unittest.main()
