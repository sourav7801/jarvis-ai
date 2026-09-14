from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "quant_terminal_v2_static"


class V16OptionDecisionRuntimeTests(unittest.TestCase):
    def test_decision_ui_consumes_canonical_scan_decisions(self):
        js = (STATIC / "v16_option_decision_runtime.js").read_text(encoding="utf-8")
        self.assertIn("AUTONOMOUS DECISION", js)
        self.assertIn("scan_decisions?.autonomous_options", js)
        self.assertIn("AUTONOMOUS CANDIDATE", js)
        self.assertIn("ACTIVE PAPER POSITION", js)
        self.assertIn("JARVIS chose not to trade", js)
        self.assertIn("VIEWING CONTRACT", js)
        self.assertIn("RISK_GEOMETRY", (ROOT / "workstation" / "v16_trading_stages.py").read_text(encoding="utf-8"))

    def test_decision_runtime_reuses_existing_state_poll_instead_of_polling(self):
        js = (STATIC / "v16_option_decision_runtime.js").read_text(encoding="utf-8")
        self.assertIn("const originalFetch = window.fetch.bind(window)", js)
        self.assertIn('requestUrl.includes("/api/v16/trading/workspace-state")', js)
        self.assertIn("response.clone().json()", js)
        self.assertNotIn("requestJson(", js)
        self.assertNotIn('fetch("/api/v16/trading/workspace-state', js)

    def test_http_serves_decision_runtime_before_workspace_router(self):
        source = (ROOT / "workstation" / "v16_terminal_http.py").read_text(encoding="utf-8")
        decision = source.index('/v16_option_decision_runtime.js')
        router = source.index('/v16_workspace_router.js')
        self.assertLess(decision, router)
        self.assertGreaterEqual(source.count('/v16_option_decision_runtime.js'), 2)

    def test_manual_viewing_and_engine_candidate_are_distinct_states(self):
        js = (STATIC / "v16_option_decision_runtime.js").read_text(encoding="utf-8")
        self.assertIn("VIEWING CONTRACT", js)
        self.assertIn("VIEWING CONTEXT · NOT EXECUTION AUTHORITY", js)
        self.assertIn("AUTONOMOUS CANDIDATE · SELECTED BY JARVIS", js)
        self.assertIn("ACTIVE PAPER POSITION", js)
        self.assertIn('#v16OptionRows tr[data-v16-contract]', js)
        self.assertNotIn("gates.SELECTED_CHAIN", js)

    def test_browser_age_is_labeled_stale_view_not_engine_degradation(self):
        js = (STATIC / "v16_option_decision_runtime.js").read_text(encoding="utf-8")
        self.assertIn('return {state: "STALE VIEW", kind: "wait", raw}', js)
        self.assertIn('pipe.textContent = "STALE VIEW"', js)
        self.assertIn("browser chain is research/context only", js)

    def test_missing_selected_underlying_decision_is_explicit_not_blank(self):
        js = (STATIC / "v16_option_decision_runtime.js").read_text(encoding="utf-8")
        self.assertIn("underlyingFromSymbol", js)
        self.assertIn("SCANNER_ROW_WITHOUT_OPTION_PROPOSAL", js)
        self.assertIn("WAIT · NO ENGINE ROW", js)
        self.assertIn("No ${esc(selectedUnderlying())} autonomous decision row exists", js)

    def test_paper_and_market_session_are_not_conflated(self):
        js = (STATIC / "v16_option_decision_runtime.js").read_text(encoding="utf-8")
        backend = (ROOT / "workstation" / "v16_trading_stages.py").read_text(encoding="utf-8")
        self.assertIn("gates.PAPER_SESSION", js)
        self.assertIn('gates["MARKET_SESSION"]', backend)
        self.assertIn("formatTime", js)

    def test_decision_surface_preserves_paper_safety_contract(self):
        backend = (ROOT / "workstation" / "v16_trading_stages.py").read_text(encoding="utf-8")
        self.assertIn('"paper_only": True', backend)
        self.assertIn('"live_execution": False', backend)
        self.assertIn('"automatic_broker_order": False', backend)


if __name__ == "__main__":
    unittest.main()
