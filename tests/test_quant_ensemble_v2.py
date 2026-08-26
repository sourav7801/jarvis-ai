from __future__ import annotations

import unittest

from omni.trading_intelligence.quant_firm_engine import decide, strategy_votes
from omni.trading_intelligence.strategy_registry import strategy_registry
from unittest.mock import patch

from workstation.quant_terminal_v2 import scan_payload


def rising_candles(count: int = 120):
    rows = []
    price = 100.0
    for index in range(count):
        price += 0.35
        rows.append(
            {
                "time": index + 1,
                "open": price - 0.2,
                "high": price + 0.4,
                "low": price - 0.5,
                "close": price,
                "volume": 1000 + index * 15,
            }
        )
    return rows


class QuantEnsembleV2Tests(unittest.TestCase):
    def test_every_active_vote_has_a_versioned_registry_contract(self):
        votes = strategy_votes(rising_candles())
        self.assertGreaterEqual(len(votes), 3)
        for vote in votes:
            spec = strategy_registry.get(vote.strategy)
            self.assertIsNotNone(spec, vote.strategy)
            self.assertEqual(vote.strategy_version, spec.version)
            self.assertEqual(vote.required_features, spec.required_features)
            self.assertTrue(spec.metadata["research_only"])
            self.assertFalse(spec.metadata["live_execution"])

    def test_catalog_exposes_version_features_and_regime_compatibility(self):
        row = next(item for item in strategy_registry.catalog() if item["strategy_id"] == "VWAP_MOMENTUM")
        self.assertEqual(row["version"], "2.0.0")
        self.assertIn("vwap", row["required_features"])
        self.assertIn("TRENDING", row["compatible_regimes"])
        self.assertTrue(row["research_only"])

    def test_decision_contains_traceable_evidence_and_contradictions(self):
        result = decide("NIFTY", "5m", rising_candles()).to_dict()
        self.assertTrue(result["registry_versioned"])
        self.assertEqual(len(result["evidence_graph"]), len(result["votes"]))
        self.assertTrue(result["contradictions"])
        for node in result["evidence_graph"]:
            self.assertIn("strategy_version", node)
            self.assertIn("regime_weight", node)
            self.assertIn("required_features", node)
            self.assertTrue(node["paper_only"])
            self.assertFalse(node["live_execution"])

    def test_directional_decision_exposes_stop_selection_and_two_r_target(self):
        result = decide("NIFTY", "5m", rising_candles())
        self.assertEqual(result.side, "LONG")
        self.assertIsNotNone(result.risk_model)
        self.assertIn(
            result.risk_model["method"],
            {"STRUCTURE_PLUS_ATR_BUFFER", "ATR_VOLATILITY_FALLBACK"},
        )
        self.assertEqual(result.risk_model["money_management"], "POSITION_SIZE_FROM_STOP_RISK")
        self.assertTrue(result.risk_model["paper_only"])
        self.assertFalse(result.risk_model["live_execution"])
        risk = result.entry - result.stop
        self.assertAlmostEqual(result.target - result.entry, 2 * risk)

    def test_no_signal_explains_why_it_waits(self):
        result = decide("NIFTY", "5m", rising_candles(20))
        self.assertEqual(result.side, "WAIT")
        self.assertIn("NO_REGISTERED_STRATEGY_SIGNAL", result.reasons_not_to_trade)
        self.assertTrue(result.paper_only)
        self.assertFalse(result.live_execution)

    @patch("workstation.quant_terminal_v2._paper_session_open", return_value=True)
    @patch("workstation.quant_terminal_v2._timeframe_evidence")
    def test_terminal_consensus_preserves_registry_evidence(self, evidence, _session):
        decision = {**decide("NIFTY", "5m", rising_candles()).to_dict(), "success": True}
        evidence.side_effect = lambda _symbol, timeframe: {
            "timeframe": timeframe,
            "available": True,
            "trend": "BULLISH",
            "regime": decision["regime"],
            "decision": {**decision, "timeframe": timeframe},
            "patterns": {"success": True, "state": "NO_EDGE", "direction": "NEUTRAL", "score": 0},
            "fresh": True,
        }
        result = scan_payload("NIFTY", "intraday")
        self.assertEqual(result["decision_version"], "QUANT_ENSEMBLE_V2_GOVERNED_CONSENSUS_V4")
        self.assertTrue(result["registry_versioned"])
        self.assertTrue(result["evidence_graph"])
        self.assertTrue(all("timeframe" in row for row in result["evidence_graph"]))
        self.assertTrue(result["contradictions"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])


if __name__ == "__main__":
    unittest.main()
