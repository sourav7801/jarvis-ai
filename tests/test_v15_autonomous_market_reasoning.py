from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from omni.agent_registry import default_agent_specs
from omni.trading_intelligence.autonomous_decision_engine_v15 import AUTONOMOUS_DECISION_ENGINE_V15
from omni.trading_intelligence.causal_trade_review_v15 import CAUSAL_TRADE_REVIEW_V15
from omni.trading_intelligence.continuous_execution_policy_v14 import CONTINUOUS_EXECUTION_POLICY_V14
from omni.trading_intelligence.market_reasoning_v15 import AUTONOMOUS_MARKET_REASONING_V15
from scripts.runtime_supervisor_safety_v15 import JarvisRuntimeSupervisorV15
from workstation.market_belief_store_v15 import MarketBeliefStoreV15
from workstation.paper_execution_sizing_v13 import install_v13_execution_sizing_bridge
from workstation.paper_trading_desk import PaperTradingDesk
from workstation.position_intelligence_v15 import POSITION_INTELLIGENCE_V15
from workstation.risk_geometry_v141 import enrich_scan_row


CRYPTO_SPEC = {
    "symbol": "BTC",
    "provider_symbol": "BTCUSDT",
    "asset_class": "CRYPTO",
    "instrument_type": "SPOT",
    "native_currency": "USDT",
    "valuation_currency": "INR",
    "quantity_step": 0.00001,
    "contract_multiplier": 1.0,
    "tick_size": 0.01,
    "source": "TEST_VERIFIED_BINANCE_SPEC",
    "verified": True,
    "verification_reason": "TEST",
    "cost_model_status": "UNCONFIGURED",
}


def _evidence(tf="5m", trend="BULLISH", close=80000.0, atr=500.0, support=79000.0, resistance=82000.0):
    return {
        "available": True,
        "fresh": True,
        "timeframe": tf,
        "source": "TEST_VERIFIED_PROVIDER",
        "data_quality": "VERIFIED",
        "close": close,
        "atr14": atr,
        "support": support,
        "resistance": resistance,
        "rsi14": 58.0 if trend == "BULLISH" else 42.0,
        "volume_ratio": 1.15,
        "trend": trend,
        "complete_bars": 120,
        "last_candle_time": 1234567890,
    }


def _row(**overrides):
    payload = {
        "success": True,
        "symbol": "BTC",
        "profile": "5m_only",
        "timeframe": "5m",
        "candidate_side": "LONG",
        "side": "WAIT",
        "score": 55.0,
        "alignment": 90.0,
        "risk_reward": None,
        "regime": "TRENDING",
        "qualified": False,
        "blockers": ["SCORE_BELOW_GATE", "INVALID_RISK_LEVELS"],
        "reasons_not_to_trade": ["SCORE_BELOW_GATE", "INVALID_RISK_LEVELS"],
        "evidence": [_evidence()],
        "paper_only": True,
        "live_execution": False,
    }
    payload.update(overrides)
    return payload


def _base_decision(ev=0.25, confidence=0.20, risk=0.18, executable=True, side="LONG"):
    return {
        "policy_version": "CONTINUOUS_EXECUTION_POLICY_V14",
        "decision_authority": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
        "action": "PRIMARY" if risk >= 0.18 else "PROBE",
        "executable": executable,
        "side": side if executable else "WAIT",
        "probability_win": 0.55,
        "expected_value_r": ev,
        "confidence": confidence,
        "uncertainty": 1.0 - confidence,
        "risk_multiplier": risk if executable else 0.0,
        "utility": max(ev, 0.0) * (0.3 + 0.7 * confidence),
        "hard_blockers": [],
        "soft_evidence": [],
        "reasons": ["TEST"],
        "legacy_static_score_gate": False,
        "arbitrary_confidence_execution_gate": False,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


class MarketReasoningV15Tests(unittest.TestCase):
    def test_market_belief_and_competing_hypotheses_are_explainable(self):
        row = _row(evidence=[
            _evidence("5m", "BULLISH"),
            _evidence("15m", "BULLISH", close=80100.0),
            _evidence("1h", "MIXED", close=79900.0),
        ])
        result = AUTONOMOUS_MARKET_REASONING_V15.reason(row, base_decision=_base_decision())
        self.assertTrue(result["success"])
        self.assertGreaterEqual(len(result["hypotheses"]), 4)
        self.assertTrue(result["probabilities_are_model_estimates"])
        self.assertFalse(result["market_data_fabricated"])
        self.assertEqual(result["market_belief"]["trend_direction"], "BULLISH")
        self.assertTrue(result["data_provenance"])

    def test_low_score_low_confidence_positive_ev_remains_executable(self):
        row = _row(score=25.0)
        with patch.object(CONTINUOUS_EXECUTION_POLICY_V14, "evaluate", return_value=_base_decision(ev=0.08, confidence=0.02, risk=0.04)):
            result = AUTONOMOUS_DECISION_ENGINE_V15.evaluate(row)
        self.assertTrue(result["executable"], result)
        self.assertGreater(result["risk_multiplier"], 0.0)
        self.assertLessEqual(result["risk_multiplier"], 0.04)
        self.assertFalse(result["legacy_static_score_gate"])

    def test_high_score_negative_ev_waits(self):
        base = _base_decision(ev=-0.10, confidence=0.95, risk=0.0, executable=False)
        base["reasons"] = ["NON_POSITIVE_CONTEXTUAL_EXPECTED_VALUE"]
        with patch.object(CONTINUOUS_EXECUTION_POLICY_V14, "evaluate", return_value=base):
            result = AUTONOMOUS_DECISION_ENGINE_V15.evaluate(_row(score=99.0))
        self.assertFalse(result["executable"])
        self.assertEqual(result["risk_multiplier"], 0.0)

    def test_portfolio_allocator_prefers_utility_not_raw_score(self):
        rows = [_row(symbol="A", score=95.0), _row(symbol="B", score=40.0), _row(symbol="C", score=80.0)]
        base = [
            {**rows[0], "adaptive_decision": _base_decision(ev=0.08, confidence=0.50, risk=0.15)},
            {**rows[1], "adaptive_decision": _base_decision(ev=0.45, confidence=0.70, risk=0.22)},
            {**rows[2], "adaptive_decision": _base_decision(ev=0.16, confidence=0.50, risk=0.16)},
        ]
        with patch.object(CONTINUOUS_EXECUTION_POLICY_V14, "evaluate_many", return_value=base):
            result = AUTONOMOUS_DECISION_ENGINE_V15.evaluate_many(rows)
        decisions = {row["symbol"]: row["adaptive_decision"] for row in result}
        self.assertEqual(decisions["B"]["opportunity_rank"], 1)
        self.assertLessEqual(decisions["A"]["risk_multiplier"], 0.15)
        self.assertLessEqual(decisions["B"]["risk_multiplier"], 0.22)
        self.assertFalse(decisions["B"]["legacy_static_score_gate"])

    def test_allocator_can_skip_weak_opportunity_when_better_alternatives_exist(self):
        rows = [_row(symbol="A"), _row(symbol="B"), _row(symbol="C")]
        base = [
            {**rows[0], "adaptive_decision": _base_decision(ev=0.60, confidence=0.80, risk=0.25)},
            {**rows[1], "adaptive_decision": _base_decision(ev=0.45, confidence=0.75, risk=0.22)},
            {**rows[2], "adaptive_decision": _base_decision(ev=0.01, confidence=0.20, risk=0.04)},
        ]
        with patch.object(CONTINUOUS_EXECUTION_POLICY_V14, "evaluate_many", return_value=base):
            result = AUTONOMOUS_DECISION_ENGINE_V15.evaluate_many(rows)
        weak = result[2]["adaptive_decision"]
        self.assertFalse(weak["executable"])
        self.assertIn("BETTER_OPPORTUNITY_AVAILABLE", weak["reasons"])
        self.assertEqual(weak["risk_multiplier"], 0.0)


class V15PaperAndLearningTests(unittest.TestCase):
    def test_v141_geometry_reaches_fractional_paper_open_under_v15(self):
        row = enrich_scan_row(_row())
        decision = AUTONOMOUS_DECISION_ENGINE_V15.evaluate(row, learning_state={})
        self.assertNotIn("INVALID_RISK_LEVELS", decision.get("hard_blockers") or [])
        self.assertTrue(decision["executable"], decision)
        install_v13_execution_sizing_bridge()
        with tempfile.TemporaryDirectory() as directory:
            desk = PaperTradingDesk(
                Path(directory) / "v15-paper.sqlite3",
                starting_equity=100000.0,
                max_open_positions=8,
                max_total_risk_fraction=0.04,
                max_single_risk_fraction=0.01,
                max_gross_exposure_multiple=2.0,
            )
            result = desk.open_position(
                symbol="BTC",
                side=decision["side"],
                entry=float(row["entry"]),
                stop=float(row["stop"]),
                target=float(row["target"]),
                quantity=None,
                timeframe="5m",
                strategy="V15_TEST",
                score=float(row["score"]),
                source="V15_TEST",
                asset_type="CRYPTO",
                risk_multiplier=float(decision["risk_multiplier"]),
                valuation_multiplier=83.0,
                instrument_spec=dict(CRYPTO_SPEC),
                portfolio_bucket="INTRADAY",
                bucket_allocation_fraction=0.50,
            )
        self.assertTrue(result["success"], result)
        self.assertEqual(result["reason"], "PAPER_POSITION_OPENED")
        self.assertGreater(float(result["quantity"]), 0.0)
        self.assertLess(float(result["quantity"]), 1.0)
        self.assertFalse(result["live_execution"])

    def test_position_intelligence_never_increases_risk(self):
        position = {"id": 1, "symbol": "BTC", "side": "LONG", "entry": 100.0, "stop": 95.0, "initial_stop": 95.0}
        decision = _base_decision(ev=-0.2, confidence=0.8, risk=0.0, executable=False)
        result = POSITION_INTELLIGENCE_V15.assess(position, mark=99.0, decision=decision)
        self.assertIn(result["recommended_action"], {"REDUCE", "EXIT"})
        self.assertFalse(result["risk_may_increase"])
        self.assertFalse(result["automatic_add_from_position_manager"])

    def test_losing_good_decision_is_not_automatically_punished(self):
        row = {
            "id": 1, "symbol": "BTC", "side": "LONG", "stop": 95.0, "target": 110.0,
            "realized_pnl": -100.0, "mae_r": -1.0, "mfe_r": 0.7,
            "metadata": {
                "initial_trade_risk": 100.0,
                "legacy_numeric_gates_are_execution_authority": False,
                "risk_model": {"geometry_version": "VERIFIED_RISK_GEOMETRY_V14_1", "data_fabricated": False},
                "adaptive_decision": {"expected_value_r": 0.35, "confidence": 0.75, "hard_blockers": []},
            },
        }
        result = CAUSAL_TRADE_REVIEW_V15.review(row)
        self.assertIn(result["decision_quality"], {"GOOD_DECISION", "ACCEPTABLE_DECISION"})
        self.assertEqual(result["outcome"], "LOSS")
        self.assertEqual(result["interpretation"], "GOOD_PROCESS_ADVERSE_OUTCOME")

    def test_profitable_bad_decision_not_automatically_reinforced(self):
        row = {
            "id": 2, "symbol": "BTC", "side": "LONG", "realized_pnl": 100.0,
            "metadata": {
                "initial_trade_risk": 100.0,
                "adaptive_decision": {"expected_value_r": -0.2, "confidence": 0.2, "hard_blockers": ["STALE_MARKET_DATA"]},
            },
        }
        result = CAUSAL_TRADE_REVIEW_V15.review(row)
        self.assertEqual(result["outcome"], "PROFIT")
        self.assertIn(result["decision_quality"], {"POOR_DECISION", "MIXED_DECISION"})
        self.assertEqual(result["interpretation"], "PROFIT_DOES_NOT_VALIDATE_WEAK_PROCESS")

    def test_belief_store_tracks_previous_current_without_synthetic_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MarketBeliefStoreV15(Path(directory) / "belief.sqlite3")
            first = AUTONOMOUS_MARKET_REASONING_V15.reason(_row(), base_decision=_base_decision())
            one = store.record(first)
            second_row = _row(evidence=[_evidence(trend="BEARISH", close=79000.0, support=77000.0, resistance=80500.0)], candidate_side="SHORT")
            second = AUTONOMOUS_MARKET_REASONING_V15.reason(second_row, base_decision=_base_decision(side="SHORT"))
            two = store.record(second)
            history = store.history("BTC", "5m_only")
        self.assertTrue(one["success"] and two["success"])
        self.assertIsNotNone(two["previous_belief"])
        self.assertTrue(two["changes"])
        self.assertEqual(history["count"], 2)
        self.assertFalse(history["history_fabricated"])


class V15SupervisorAndBoundaryTests(unittest.TestCase):
    def test_snapshot_writer_uses_unique_temp_not_shared_state_tmp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            supervisor = JarvisRuntimeSupervisorV15.__new__(JarvisRuntimeSupervisorV15)
            supervisor.state_dir = root / "runtime"
            supervisor.state_path = supervisor.state_dir / "state.json"
            supervisor._persist_snapshot({"running": True, "paper_only": True})
            payload = json.loads(supervisor.state_path.read_text(encoding="utf-8"))
            leftovers = list(supervisor.state_dir.glob("state.*.tmp"))
        self.assertTrue(payload["running"])
        self.assertEqual(leftovers, [])

    def test_permanent_agent_boundary_is_29_and_critic_remains(self):
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)
        for service in ("autonomous_decision_engine_v15", "market_reasoning_v15", "position_intelligence_v15"):
            self.assertNotIn(service, names)


if __name__ == "__main__":
    unittest.main()
