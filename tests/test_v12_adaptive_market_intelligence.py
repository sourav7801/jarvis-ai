from __future__ import annotations

from pathlib import Path
import unittest

from omni.agent_registry import default_agent_specs
from omni.trading_intelligence.adaptive_opportunity_policy import (
    ADAPTIVE_OPPORTUNITY_POLICY,
    HARD_BLOCKERS,
)
from workstation.adaptive_paper_autonomy_engine import AdaptivePaperAutonomyEngine
from workstation import completion_console_v12


ROOT = Path(__file__).resolve().parents[1]


def _row(
    *,
    score: float = 66.0,
    alignment: float = 75.0,
    rr: float = 2.0,
    blockers: list[str] | None = None,
    side: str = "LONG",
    regime: str = "TRENDING",
) -> dict:
    direction = "BULLISH" if side == "LONG" else "BEARISH"
    return {
        "success": True,
        "symbol": "BTC",
        "profile": "adaptive_intraday",
        "qualified": False,
        "side": "WAIT",
        "candidate_side": side,
        "score": score,
        "alignment": alignment,
        "risk_reward": rr,
        "entry": 79000.0,
        "stop": 78750.0 if side == "LONG" else 79250.0,
        "target": 79500.0 if side == "LONG" else 78500.0,
        "regime": regime,
        "blockers": blockers or ["SCORE_BELOW_GATE"],
        "reasons_not_to_trade": blockers or ["SCORE_BELOW_GATE"],
        "pattern_confirmation": {
            "state": "CONFIRMED_BREAKOUT" if side == "LONG" else "CONFIRMED_BREAKDOWN",
            "direction": direction,
        },
        "votes": [
            {
                "strategy": "TEST_TREND",
                "family": "trend",
                "side": side,
                "regime_compatible": True,
            }
        ],
        "evidence": [
            {"available": True, "fresh": True, "timeframe": "5m"},
            {"available": True, "fresh": True, "timeframe": "15m"},
        ],
        "decisions": [
            {"timeframe": "5m", "side": side},
            {"timeframe": "15m", "side": side},
        ],
        "profile_rules": {
            "minimum_score": 67.0,
            "minimum_alignment": 100,
            "minimum_risk_reward": 1.8,
        },
        "paper_only": True,
        "live_execution": False,
    }


class AdaptiveOpportunityPolicyTests(unittest.TestCase):
    def test_score_below_67_is_not_binary_blocker(self) -> None:
        decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
            _row(score=66.0, blockers=["SCORE_BELOW_GATE"]),
            learning_state={},
        )
        self.assertTrue(decision["executable"])
        self.assertIn(decision["action"], {"PRIMARY", "PROBE"})
        self.assertNotIn("SCORE_BELOW_GATE", decision["hard_blockers"])
        self.assertIn("SCORE_BELOW_GATE", decision["soft_evidence"])
        self.assertFalse(decision["legacy_static_score_gate"])
        self.assertGreater(decision["expected_value_r"], 0.0)

    def test_even_much_lower_score_can_trade_when_ev_is_strong(self) -> None:
        decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
            _row(score=55.0, alignment=82.0, rr=3.2, blockers=["SCORE_BELOW_GATE"]),
            learning_state={},
        )
        self.assertTrue(decision["executable"])
        self.assertGreater(decision["expected_value_r"], 0.0)
        self.assertGreater(decision["risk_multiplier"], 0.0)

    def test_stale_data_remains_a_hard_veto(self) -> None:
        decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
            _row(score=90.0, alignment=100.0, rr=4.0, blockers=["STALE_MARKET_DATA"]),
            learning_state={},
        )
        self.assertFalse(decision["executable"])
        self.assertEqual(decision["action"], "WAIT")
        self.assertIn("STALE_MARKET_DATA", decision["hard_blockers"])

    def test_invalid_levels_remain_a_hard_veto(self) -> None:
        row = _row(score=80.0, blockers=[])
        row["stop"] = None
        decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(row, learning_state={})
        self.assertFalse(decision["executable"])
        self.assertIn("INVALID_RISK_LEVELS", decision["hard_blockers"])

    def test_policy_status_has_no_static_numeric_authority(self) -> None:
        status = ADAPTIVE_OPPORTUNITY_POLICY.status()
        self.assertFalse(status["legacy_score_threshold_is_execution_authority"])
        self.assertFalse(status["legacy_alignment_threshold_is_execution_authority"])
        self.assertFalse(status["legacy_risk_reward_threshold_is_execution_authority"])
        self.assertIn("STALE_MARKET_DATA", HARD_BLOCKERS)
        self.assertTrue(status["supports_low_risk_probe"])
        self.assertFalse(status["live_execution"])


class AdaptivePaperEngineContractTests(unittest.TestCase):
    def test_engine_exposes_adaptive_authority_without_live_execution(self) -> None:
        engine = AdaptivePaperAutonomyEngine(
            universe=("BTC",),
            profile="5m_only",
            manage_marks=False,
        )
        status = engine.status()
        self.assertEqual(status["decision_authority"], "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE")
        self.assertFalse(status["adaptive_intelligence"]["legacy_score_threshold_is_execution_authority"])
        self.assertFalse(status["live_execution"])

    def test_source_does_not_reintroduce_static_candidate_score_gate(self) -> None:
        source = (ROOT / "workstation" / "adaptive_paper_autonomy_engine.py").read_text(encoding="utf-8")
        self.assertNotIn('float(row.get("score") or 0.0) >= self.min_score', source)
        self.assertNotIn('float(row.get("risk_reward") or 0.0) >= self.min_risk_reward', source)
        self.assertIn("adaptive_decision", source)
        self.assertIn("risk_multiplier=final_risk_multiplier", source)


class V12RuntimeContractTests(unittest.TestCase):
    def test_quant_launcher_disables_legacy_singleton_and_starts_adaptive_controller(self) -> None:
        source = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        self.assertIn('os.environ["JARVIS_AUTO_PAPER_START"] = "0"', source)
        self.assertIn("start_v12_adaptive_paper", source)
        self.assertIn("paper_portfolio_controller.start", source)
        self.assertIn("install_adaptive_direct_trade_bridge", source)

    def test_completion_v12_preserves_safety_and_29_agent_boundary(self) -> None:
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)
        for system_plane in (
            "adaptive_opportunity_policy",
            "adaptive_market_sampler",
            "adaptive_paper_autonomy",
        ):
            self.assertNotIn(system_plane, names)
        status_source = (ROOT / "workstation" / "completion_console_v12.py").read_text(encoding="utf-8")
        self.assertIn('"version": "12.0"', status_source)
        self.assertIn('"live_execution": False', status_source)
        self.assertIn('"automatic_broker_order": False', status_source)

    def test_v12_ui_has_live_btc_sampling_surface(self) -> None:
        html = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "workstation" / "completion_console_static" / "v12_adaptive_market.js").read_text(encoding="utf-8")
        self.assertIn("adaptiveMarketNav", html)
        self.assertIn("v12_adaptive_market.js", html)
        self.assertIn("/api/adaptive-market/sample", js)
        self.assertIn("legacy score", js)
        self.assertNotIn("place_order(", js)
        self.assertNotIn("submit_order(", js)


if __name__ == "__main__":
    unittest.main()
