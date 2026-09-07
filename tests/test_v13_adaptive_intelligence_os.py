from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.trading_intelligence.contextual_decision_engine_v13 import ContextualDecisionEngineV13
from omni.trading_intelligence.contextual_outcome_memory import ContextualOutcomeMemory
from omni.trading_intelligence.strategy_governance_pipeline_v13 import StrategyGovernancePipelineV13
from workstation.dynamic_correlation_risk_v13 import DynamicCorrelationRiskV13


def _row(*, score: float = 55.0, blockers=None, side: str = "LONG") -> dict:
    direction = "BULLISH" if side == "LONG" else "BEARISH"
    return {
        "success": True,
        "symbol": "BTC",
        "profile": "adaptive_intraday",
        "timeframe": "15m",
        "qualified": False,
        "side": "WAIT",
        "candidate_side": side,
        "score": score,
        "alignment": 84.0,
        "risk_reward": 3.0,
        "entry": 80000.0,
        "stop": 79500.0 if side == "LONG" else 80500.0,
        "target": 81500.0 if side == "LONG" else 78500.0,
        "regime": "TRENDING",
        "blockers": list(blockers or ["SCORE_BELOW_GATE"]),
        "reasons_not_to_trade": list(blockers or ["SCORE_BELOW_GATE"]),
        "pattern_confirmation": {
            "state": "CONFIRMED_BREAKOUT" if side == "LONG" else "CONFIRMED_BREAKDOWN",
            "direction": direction,
        },
        "votes": [{
            "strategy": "TEST_TREND",
            "family": "trend",
            "side": side,
            "regime_compatible": True,
        }],
        "evidence": [
            {"available": True, "fresh": True, "timeframe": "5m"},
            {"available": True, "fresh": True, "timeframe": "15m"},
        ],
        "decisions": [
            {"timeframe": "5m", "side": side},
            {"timeframe": "15m", "side": side},
        ],
        "paper_only": True,
        "live_execution": False,
    }


class ContextualOutcomeMemoryTests(unittest.TestCase):
    def test_memory_uses_only_closed_paper_outcomes_and_shrinks_small_samples(self) -> None:
        trades = [
            {
                "symbol": "BTC", "side": "LONG", "timeframe": "15m",
                "entry": 100.0, "stop": 99.0, "quantity": 1.0, "realized_pnl": 2.0,
                "metadata": {"regime": "TRENDING", "adaptive_action": "PRIMARY", "pattern_confirmation": {"state": "CONFIRMED_BREAKOUT"}},
            },
            {
                "symbol": "BTC", "side": "LONG", "timeframe": "15m",
                "entry": 100.0, "stop": 99.0, "quantity": 1.0, "realized_pnl": -1.0,
                "metadata": {"regime": "TRENDING", "adaptive_action": "PRIMARY", "pattern_confirmation": {"state": "CONFIRMED_BREAKOUT"}},
            },
        ]
        memory = ContextualOutcomeMemory()
        with patch.object(memory, "_closed_trades", return_value=trades):
            snapshot = memory.snapshot(force=True)
            lookup = memory.lookup(_row(score=60.0), action="PRIMARY")
        self.assertEqual(snapshot["closed_trade_count"], 2)
        self.assertEqual(snapshot["usable_r_count"], 2)
        self.assertTrue(lookup["evidence_available"])
        self.assertLess(abs(float(lookup["posterior_edge_r"])), 2.0)
        self.assertFalse(snapshot["synthetic_history"])
        self.assertFalse(lookup["live_execution"])


class ContextualDecisionEngineTests(unittest.TestCase):
    def test_low_legacy_score_can_execute_on_contextual_positive_ev(self) -> None:
        engine = ContextualDecisionEngineV13()
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
        with patch("omni.trading_intelligence.contextual_decision_engine_v13.CONTEXTUAL_OUTCOME_MEMORY.lookup", return_value=neutral_memory), \
             patch("workstation.dynamic_correlation_risk_v13.DYNAMIC_CORRELATION_RISK_V13.assess", return_value={"success": True, "state": "NO_OPEN_PEERS", "risk_multiplier": 1.0, "paper_only": True, "live_execution": False}):
            decision = engine.evaluate(_row(score=55.0))
        self.assertTrue(decision["executable"])
        self.assertIn(decision["action"], {"PRIMARY", "PROBE"})
        self.assertEqual(decision["decision_authority"], "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE")
        self.assertNotIn("SCORE_BELOW_GATE", decision["hard_blockers"])
        self.assertGreater(decision["expected_value_r"], 0.0)

    def test_stale_data_remains_hard_veto_even_with_good_context(self) -> None:
        engine = ContextualDecisionEngineV13()
        strong_memory = {
            "success": True,
            "posterior_edge_r": 3.0,
            "posterior_win_rate": 0.9,
            "confidence": 0.9,
            "evidence_available": True,
            "matched_cohorts": [{"sample_count": 100}],
            "paper_only": True,
            "live_execution": False,
        }
        with patch("omni.trading_intelligence.contextual_decision_engine_v13.CONTEXTUAL_OUTCOME_MEMORY.lookup", return_value=strong_memory):
            decision = engine.evaluate(_row(score=95.0, blockers=["STALE_MARKET_DATA"]))
        self.assertFalse(decision["executable"])
        self.assertEqual(decision["action"], "WAIT")
        self.assertIn("STALE_MARKET_DATA", decision["hard_blockers"])

    def test_correlation_overlay_can_only_reduce_risk(self) -> None:
        engine = ContextualDecisionEngineV13()
        neutral_memory = {
            "success": True, "posterior_edge_r": 0.0, "posterior_win_rate": 0.5,
            "confidence": 0.0, "evidence_available": False, "matched_cohorts": [],
        }
        with patch("omni.trading_intelligence.contextual_decision_engine_v13.CONTEXTUAL_OUTCOME_MEMORY.lookup", return_value=neutral_memory), \
             patch("workstation.dynamic_correlation_risk_v13.DYNAMIC_CORRELATION_RISK_V13.assess", return_value={"success": True, "state": "VERY_HIGH_SAME_DIRECTION_CORRELATION", "risk_multiplier": 0.35, "paper_only": True, "live_execution": False}):
            decision = engine.evaluate(_row(score=70.0))
        base = float(decision["base_v12_decision"]["risk_multiplier"])
        self.assertLessEqual(float(decision["risk_multiplier"]), base)
        self.assertEqual(decision["portfolio_correlation"]["state"], "VERY_HIGH_SAME_DIRECTION_CORRELATION")


class DynamicCorrelationTests(unittest.TestCase):
    def test_missing_completed_bar_data_is_unknown_not_fabricated(self) -> None:
        engine = DynamicCorrelationRiskV13()
        positions = [{"symbol": "ETH", "side": "LONG"}]
        with patch.object(engine, "_series", return_value={"success": False, "source": "TEST", "returns": {}}):
            result = engine.assess(symbol="BTC", side="LONG", profile="adaptive_intraday", positions=positions)
        self.assertEqual(result["state"], "UNKNOWN_DATA_INSUFFICIENT")
        self.assertEqual(result["risk_multiplier"], 1.0)
        self.assertFalse(result["data_fabricated"])
        self.assertIsNone(result["hard_blocker"])


class StrategyGovernanceV13Tests(unittest.TestCase):
    def test_champion_requires_explicit_operator_approval_and_remains_paper_only(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            pipeline = StrategyGovernancePipelineV13(Path(folder) / "governance.json")
            record = pipeline.register(name="test", symbol="BTC", timeframe="15m", regime="TRENDING")
            record = pipeline.mark_validated(record["record_id"], {"passed": True, "out_of_sample_passed": True})
            record = pipeline.advance(record["record_id"], "CHALLENGER")
            record = pipeline.advance(record["record_id"], "PAPER_SHADOW", evidence={"paper_trades": 40})
            record = pipeline.advance(record["record_id"], "REVIEW", evidence={"verified": True})
            with self.assertRaises(PermissionError):
                pipeline.advance(record["record_id"], "CHAMPION")
            champion = pipeline.advance(record["record_id"], "CHAMPION", operator_approved=True)
            self.assertEqual(champion["stage"], "CHAMPION")
            self.assertTrue(champion["operator_approved"])
            self.assertFalse(champion["production_strategy_changed"])
            self.assertFalse(champion["live_execution"])


if __name__ == "__main__":
    unittest.main()
