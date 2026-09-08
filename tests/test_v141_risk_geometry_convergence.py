from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from omni.trading_intelligence.continuous_execution_policy_v14 import (
    CONTINUOUS_EXECUTION_POLICY_V14,
)
from workstation.paper_execution_sizing_v13 import install_v13_execution_sizing_bridge
from workstation.paper_trading_desk import PaperTradingDesk
from workstation.risk_geometry_v141 import enrich_scan_row, status


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


def _btc_evidence(
    *,
    timeframe: str = "5m",
    side: str = "LONG",
    close: float = 80000.0,
    atr: float = 500.0,
    support: float = 79000.0,
    resistance: float = 82000.0,
) -> dict:
    return {
        "available": True,
        "fresh": True,
        "timeframe": timeframe,
        "source": "TEST_VERIFIED_PROVIDER",
        "data_quality": "VERIFIED",
        "close": close,
        "atr14": atr,
        "support": support,
        "resistance": resistance,
        "complete_bars": 120,
        "last_candle_time": 1234567890,
        "trend": "BULLISH" if side == "LONG" else "BEARISH",
        "decision": {"side": side},
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
        "evidence": [_btc_evidence()],
        "paper_only": True,
        "live_execution": False,
    }
    payload.update(overrides)
    return payload


class RiskGeometryV141Tests(unittest.TestCase):
    def test_low_legacy_score_no_longer_suppresses_valid_geometry(self) -> None:
        row = enrich_scan_row(_row())
        self.assertFalse(row["qualified"])
        self.assertIn("SCORE_BELOW_GATE", row["blockers"])
        self.assertNotIn("INVALID_RISK_LEVELS", row["blockers"])
        self.assertEqual(row["entry"], 80000.0)
        self.assertLess(row["stop"], row["entry"])
        self.assertGreater(row["target"], row["entry"])
        self.assertGreater(row["risk_reward"], 0.0)
        self.assertTrue(row["risk_geometry_repaired"])
        geometry = row["risk_geometry_v141"]
        self.assertTrue(geometry["derived_from_verified_completed_bar_evidence"])
        self.assertTrue(geometry["anchor_direction_matches_candidate"])
        self.assertFalse(geometry["synthetic_market_data"])
        self.assertFalse(geometry["data_fabricated"])
        self.assertFalse(geometry["live_execution"])

    def test_short_geometry_has_correct_directional_order(self) -> None:
        row = enrich_scan_row(_row(
            candidate_side="SHORT",
            pattern_confirmation={"state": "CONFIRMED_BREAKDOWN", "direction": "BEARISH"},
            votes=[{"strategy": "TEST_TREND", "family": "trend", "side": "SHORT", "regime_compatible": True}],
            evidence=[_btc_evidence(side="SHORT")],
        ))
        self.assertGreater(row["stop"], row["entry"])
        self.assertLess(row["target"], row["entry"])
        self.assertNotIn("INVALID_RISK_LEVELS", row["blockers"])
        self.assertTrue(row["risk_geometry_v141"]["anchor_direction_matches_candidate"])

    def test_candidate_aligned_evidence_is_preferred_over_opposing_anchor(self) -> None:
        row = enrich_scan_row(_row(
            profile="adaptive_intraday",
            evidence=[
                _btc_evidence(timeframe="15m", side="LONG", close=80100.0, support=79200.0, resistance=82100.0),
                _btc_evidence(timeframe="5m", side="SHORT", close=79900.0, support=78800.0, resistance=81100.0),
            ],
        ))
        self.assertEqual(row["entry"], 80100.0)
        self.assertEqual(row["risk_geometry_v141"]["anchor_timeframe"], "15m")
        self.assertTrue(row["risk_geometry_v141"]["anchor_direction_matches_candidate"])

    def test_no_direction_does_not_manufacture_geometry(self) -> None:
        row = enrich_scan_row(_row(candidate_side="WAIT"))
        self.assertIsNone(row.get("entry"))
        self.assertIn("INVALID_RISK_LEVELS", row["blockers"])
        self.assertEqual(row["risk_geometry_v141"]["state"], "NOT_ATTEMPTED_NO_DIRECTION")

    def test_stale_evidence_does_not_clear_invalid_risk_hard_blocker(self) -> None:
        source = _row()
        source["evidence"][0]["fresh"] = False
        row = enrich_scan_row(source)
        self.assertIsNone(row.get("entry"))
        self.assertIn("INVALID_RISK_LEVELS", row["blockers"])
        self.assertEqual(row["risk_geometry_v141"]["state"], "BLOCKED_VERIFIED_GEOMETRY_INPUT_UNAVAILABLE")

    def test_v14_policy_receives_repaired_geometry_without_static_score_authority(self) -> None:
        row = enrich_scan_row(_row())
        decision = CONTINUOUS_EXECUTION_POLICY_V14.evaluate(row, learning_state={})
        self.assertNotIn("INVALID_RISK_LEVELS", decision["hard_blockers"])
        self.assertFalse(decision["legacy_static_score_gate"])
        self.assertFalse(decision["arbitrary_confidence_execution_gate"])
        self.assertFalse(decision["live_execution"])
        self.assertFalse(decision["automatic_broker_order"])

    def test_repaired_geometry_reaches_fractional_btc_paper_open(self) -> None:
        row = enrich_scan_row(_row())
        decision = CONTINUOUS_EXECUTION_POLICY_V14.evaluate(row, learning_state={})
        self.assertTrue(decision["executable"], decision)
        install_v13_execution_sizing_bridge()
        with tempfile.TemporaryDirectory() as directory:
            desk = PaperTradingDesk(
                Path(directory) / "v141-paper.sqlite3",
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
                strategy="V14_1_RISK_GEOMETRY_TEST",
                score=float(row["score"]),
                source="V14_1_TEST",
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
        self.assertTrue(result["fractional_auto_sizing"])
        self.assertTrue(result["constraint_aware_auto_sizing"])
        self.assertFalse(result["live_execution"])

    def test_existing_valid_geometry_is_preserved_and_stale_invalid_token_removed(self) -> None:
        source = _row(
            entry=80000.0,
            stop=79000.0,
            target=82000.0,
            risk_reward=2.0,
            blockers=["SCORE_BELOW_GATE", "INVALID_RISK_LEVELS"],
            reasons_not_to_trade=["SCORE_BELOW_GATE", "INVALID_RISK_LEVELS"],
        )
        row = enrich_scan_row(source)
        self.assertEqual(row["entry"], 80000.0)
        self.assertEqual(row["stop"], 79000.0)
        self.assertEqual(row["target"], 82000.0)
        self.assertEqual(row["risk_geometry_v141"]["state"], "EXISTING_VALID_GEOMETRY")
        self.assertTrue(row["risk_geometry_v141"]["stale_invalid_risk_token_cleared"])
        self.assertNotIn("INVALID_RISK_LEVELS", row["blockers"])
        self.assertNotIn("INVALID_RISK_LEVELS", row["reasons_not_to_trade"])

    def test_status_preserves_hard_invalid_risk_boundary_and_paper_only(self) -> None:
        payload = status()
        self.assertTrue(payload["invalid_risk_levels_remains_hard_blocker_when_geometry_unavailable"])
        self.assertTrue(payload["verified_completed_bar_evidence_only"])
        self.assertTrue(payload["prefers_candidate_aligned_evidence"])
        self.assertFalse(payload["data_fabricated"])
        self.assertFalse(payload["live_execution"])
        self.assertFalse(payload["automatic_broker_order"])


if __name__ == "__main__":
    unittest.main()
