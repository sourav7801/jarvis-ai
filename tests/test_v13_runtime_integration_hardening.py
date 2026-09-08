from __future__ import annotations

import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

from omni.trading_intelligence.contextual_decision_engine_v13 import ContextualDecisionEngineV13
from workstation import quant_terminal_v2 as quant_terminal
from workstation.quant_terminal_v13_bridge import (
    QuantTerminalV13Handler,
    install_quant_terminal_v13_bridge,
)


ROOT = Path(__file__).resolve().parents[1]


def _row() -> dict:
    return {
        "success": True,
        "symbol": "BTC",
        "profile": "adaptive_intraday",
        "timeframe": "15m",
        "candidate_side": "LONG",
        "side": "WAIT",
        "score": 60.0,
        "alignment": 85.0,
        "risk_reward": 3.0,
        "entry": 100.0,
        "stop": 98.0,
        "target": 106.0,
        "regime": "TRENDING",
        "blockers": ["SCORE_BELOW_GATE"],
        "reasons_not_to_trade": ["SCORE_BELOW_GATE"],
        "pattern_confirmation": {
            "state": "CONFIRMED_BREAKOUT",
            "direction": "BULLISH",
        },
        "votes": [{
            "strategy": "TEST_TREND",
            "family": "trend",
            "side": "LONG",
            "regime_compatible": True,
        }],
        "evidence": [
            {"available": True, "fresh": True, "timeframe": "5m"},
            {"available": True, "fresh": True, "timeframe": "15m"},
        ],
        "paper_only": True,
        "live_execution": False,
    }


class V13QuantRuntimeAssetBridgeTests(unittest.TestCase):
    def test_quant_bridge_serves_every_generation_asset_referenced_by_html(self) -> None:
        html = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "index.html"
        ).read_text(encoding="utf-8")
        source = inspect.getsource(QuantTerminalV13Handler.do_GET)
        for asset in ("v12_paper_intelligence.js", "v13_contextual_paper_runtime.js"):
            self.assertIn(f'src="/{asset}"', html)
            self.assertIn(f'/{asset}', source)
            self.assertTrue((quant_terminal.STATIC / asset).is_file())
        self.assertIn("/api/v13/runtime-assets", source)
        for token in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(token, source)

    def test_install_rebinds_only_quant_handler_and_keeps_live_execution_locked(self) -> None:
        original = quant_terminal.Handler
        try:
            result = install_quant_terminal_v13_bridge()
            self.assertIs(quant_terminal.Handler, QuantTerminalV13Handler)
            self.assertTrue(result["installed"])
            self.assertTrue(result["v12_paper_intelligence_asset"])
            self.assertTrue(result["v13_contextual_paper_asset"])
            self.assertFalse(result["live_execution"])
            self.assertFalse(result["automatic_broker_order"])
        finally:
            quant_terminal.Handler = original

    def test_quant_launcher_installs_http_overlay_before_base_server(self) -> None:
        source = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        install_index = source.index("v13_http = install_v13_quant_http_bridge()")
        serve_index = source.index("trading_app.main()")
        self.assertLess(install_index, serve_index)
        self.assertIn("CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE", source)
        self.assertNotIn("place_order(", source)


class V13DirectCallerCompatibilityTests(unittest.TestCase):
    def test_contextual_engine_accepts_v12_explicit_learning_state_contract(self) -> None:
        neutral_memory = {
            "success": True,
            "posterior_edge_r": 0.0,
            "posterior_win_rate": 0.5,
            "confidence": 0.0,
            "evidence_available": False,
            "matched_cohorts": [],
            "paper_only": True,
            "live_execution": False,
        }
        engine = ContextualDecisionEngineV13()
        with patch(
            "omni.trading_intelligence.contextual_decision_engine_v13.CONTEXTUAL_OUTCOME_MEMORY.lookup",
            return_value=neutral_memory,
        ), patch(
            "workstation.dynamic_correlation_risk_v13.DYNAMIC_CORRELATION_RISK_V13.assess",
            return_value={
                "success": True,
                "state": "NO_OPEN_PEERS",
                "risk_multiplier": 1.0,
                "paper_only": True,
                "live_execution": False,
            },
        ):
            decision = engine.evaluate(_row(), learning_state={})
        self.assertEqual(decision["decision_authority"], "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE")
        self.assertFalse(decision["live_execution"])
        self.assertFalse(decision["automatic_broker_order"])

    def test_direct_bridge_call_shape_matches_contextual_engine_signature(self) -> None:
        signature = inspect.signature(ContextualDecisionEngineV13.evaluate)
        self.assertIn("learning_state", signature.parameters)
        direct_source = (
            ROOT / "workstation" / "adaptive_direct_trade_bridge.py"
        ).read_text(encoding="utf-8")
        self.assertIn("learning_state=_learning_state()", direct_source)


if __name__ == "__main__":
    unittest.main()
