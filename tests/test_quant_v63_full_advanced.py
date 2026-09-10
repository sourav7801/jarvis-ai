from __future__ import annotations

import unittest
from pathlib import Path

from workstation.quant_intelligence_modules import (
    SUPPORTED_MODULES,
    _analysis_timeframe,
    _safe_failure,
)


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "quant_terminal_v2_static"


class QuantV63FullAdvancedTests(unittest.TestCase):
    def test_full_advanced_module_deck_is_registered(self):
        required = {
            "adaptive-brain",
            "option-chain",
            "oi-iv",
            "fvg",
            "liquidity",
            "order-flow",
            "structure",
            "patterns",
            "heatmaps",
            "portfolio-risk",
            "trade-journal",
            "learning",
            "strategy-lab",
            "self-improvement",
        }
        self.assertTrue(required <= SUPPORTED_MODULES)

    def test_analysis_profile_mapping_is_deterministic(self):
        self.assertEqual(_analysis_timeframe("1m_only"), "1m")
        self.assertEqual(_analysis_timeframe("5m_only"), "5m")
        self.assertEqual(_analysis_timeframe("15m_only"), "15m")
        self.assertEqual(_analysis_timeframe("1h_only"), "1h")
        self.assertEqual(_analysis_timeframe("swing"), "1h")
        self.assertEqual(_analysis_timeframe("adaptive_intraday"), "15m")

    def test_safe_failures_remain_paper_only(self):
        payload = _safe_failure("strategy-lab", "BTC", "test")
        self.assertFalse(payload["success"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_execution"])

    def test_intelligence_workspace_exposes_all_advanced_modules(self):
        html = (STATIC / "intelligence.html").read_text(encoding="utf-8")
        for module in sorted(SUPPORTED_MODULES):
            self.assertIn(f'data-module="{module}"', html)
        self.assertIn('id="profileSelect"', html)
        self.assertIn("NO BROKER ORDER API", html)

    def test_terminal_exposes_full_intelligence_deck(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for module in (
            "adaptive-brain",
            "strategy-lab",
            "learning",
            "self-improvement",
            "option-chain",
            "oi-iv",
            "structure",
            "liquidity",
            "order-flow",
            "fvg",
            "patterns",
            "heatmaps",
            "portfolio-risk",
            "trade-journal",
        ):
            self.assertIn(f'data-module="{module}"', html)
        self.assertIn("/option_chart_runtime.js", html)
        self.assertIn("/paper_desk_runtime.js", html)
        self.assertIn("/advanced_terminal_runtime.js", html)
        self.assertIn("/adaptive_brain_runtime.js", html)

    def test_advanced_frontend_has_renderers_for_brain_learning_and_lab(self):
        source = (STATIC / "intelligence.js").read_text(encoding="utf-8")
        for marker in (
            "renderAdaptive",
            "renderLearning",
            "renderStrategyLab",
            "renderSelfImprovement",
            "ORDER FLOW PROXY",
            "PAPER_CHALLENGER",
        ):
            self.assertIn(marker, source)

    def test_adaptive_runtime_has_live_learning_telemetry(self):
        source = (STATIC / "adaptive_brain_runtime.js").read_text(encoding="utf-8")
        self.assertIn("/api/intelligence/decision", source)
        self.assertIn("/api/intelligence/status", source)
        self.assertIn("adaptiveBrainLiveCard", source)
        self.assertIn("STRATEGY LAB", source)
        self.assertIn("LEARNING", source)

    def test_quant_server_preserves_advanced_static_and_api_routes(self):
        source = (ROOT / "workstation" / "quant_terminal_v2.py").read_text(encoding="utf-8")
        for marker in (
            'path == "/intelligence.html"',
            'path == "/lightweight-charts.standalone.production.js"',
            'path == "/option_chart_runtime.js"',
            'path == "/paper_desk_runtime.js"',
            'path == "/advanced_terminal_runtime.js"',
            'path == "/adaptive_brain_runtime.js"',
            'path == "/api/intelligence/decision"',
            'path == "/api/intelligence/status"',
            'path == "/api/intelligence/module"',
            'path == "/api/paper/portfolio"',
        ):
            self.assertIn(marker, source)

    def test_runtime_hardening_remains_the_canonical_launcher(self):
        bat = (ROOT / "JARVIS_WORKSTATION.bat").read_text(encoding="utf-8")
        self.assertIn("scripts.jarvis_runtime_supervisor_v62", bat)
        runtime = (ROOT / "scripts" / "jarvis_runtime_supervisor_v62.py").read_text(encoding="utf-8")
        self.assertIn("REQUIRED_QUANT_PATHS", runtime)
        self.assertIn("/intelligence.html", runtime)
        self.assertIn("/adaptive_brain_runtime.js", runtime)

    def test_v63_surfaces_do_not_add_live_order_calls(self):
        paths = (
            ROOT / "workstation" / "quant_intelligence_modules.py",
            STATIC / "intelligence.js",
            STATIC / "adaptive_brain_runtime.js",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for forbidden in (
            "place_order(",
            "modify_order(",
            "cancel_order(",
            "/orders/sync",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
