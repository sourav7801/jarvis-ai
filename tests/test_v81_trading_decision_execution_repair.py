from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from workstation.intraday_lane_group import IntradayLaneGroup
from workstation.paper_portfolio_controller import PaperPortfolioController


ROOT = Path(__file__).resolve().parents[1]


def _engine(*, running: bool = False) -> MagicMock:
    engine = MagicMock()
    engine.configure_mandate.return_value = {"success": True}
    engine.start.return_value = {
        "success": True,
        "running": True,
        "paper_only": True,
        "live_execution": False,
    }
    engine.stop.return_value = {
        "success": True,
        "running": False,
        "paper_only": True,
        "live_execution": False,
    }
    engine.status.return_value = {
        "success": True,
        "running": running,
        "universe": [],
        "last_scan_funnel": {},
        "last_rejection_counts": {},
        "last_rows_summary": [],
        "paper_only": True,
        "live_execution": False,
    }
    engine.add_symbols.return_value = engine.status.return_value
    engine.trigger_scan.return_value = {"success": True, "scan_triggered": True}
    return engine


class PaperPortfolioIndependentControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engines = {
            "INTRADAY": _engine(),
            "SWING": _engine(),
            "INVESTMENT": _engine(),
        }
        self.controller = PaperPortfolioController(engines=self.engines)

    def test_swing_only_token_does_not_start_other_horizons(self) -> None:
        with patch.object(self.controller, "_start_candidate_router"):
            self.controller.start(intraday_profile="swing_only")

        self.engines["SWING"].start.assert_called_once_with(profile="swing", scan_now=True)
        self.engines["INTRADAY"].start.assert_not_called()
        self.engines["INVESTMENT"].start.assert_not_called()

    def test_investment_only_is_long_only(self) -> None:
        with patch.object(self.controller, "_start_candidate_router"):
            self.controller.start(intraday_profile="investment_only")

        self.engines["INVESTMENT"].configure_mandate.assert_called_once_with(
            "INVESTMENT", 0.20, ("LONG",)
        )
        self.engines["INVESTMENT"].start.assert_called_once_with(
            profile="investment", scan_now=True
        )
        self.engines["INTRADAY"].start.assert_not_called()
        self.engines["SWING"].start.assert_not_called()

    def test_stop_token_changes_only_requested_horizon(self) -> None:
        self.controller.start(intraday_profile="stop_swing")
        self.engines["SWING"].stop.assert_called_once_with()
        self.engines["INTRADAY"].stop.assert_not_called()
        self.engines["INVESTMENT"].stop.assert_not_called()

    def test_discovery_routes_equities_to_swing_and_investment(self) -> None:
        for engine in self.engines.values():
            engine.status.return_value = {
                "success": True,
                "running": True,
                "universe": [],
                "paper_only": True,
                "live_execution": False,
            }

        rows = [
            {
                "symbol": "CIPLA",
                "candidate": True,
                "auto_paper_eligible": True,
                "direction": "BULLISH",
                "state": "CONFIRMED_BREAKOUT",
                "score": 72.0,
            },
            {
                "symbol": "MARUTI",
                "candidate": True,
                "auto_paper_eligible": True,
                "direction": "BEARISH",
                "state": "CONFIRMED_BREAKDOWN",
                "score": 70.0,
            },
        ]
        result = self.controller.enroll_discovery_candidates(rows)

        self.assertIn("CIPLA", result["swing_symbols"])
        self.assertIn("MARUTI", result["swing_symbols"])
        self.assertEqual(result["investment_symbols"], ["CIPLA"])
        self.engines["SWING"].add_symbols.assert_called_once()
        self.engines["INVESTMENT"].add_symbols.assert_called_once()
        self.assertEqual(result["contract"], "DISCOVERY_SCORE_IS_NOT_EXECUTION_SCORE")
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])


class IntradayLaneGroupTests(unittest.TestCase):
    def test_discovery_symbols_go_only_to_5m_and_15m_fast_lanes(self) -> None:
        mtf = _engine()
        five = _engine()
        fifteen = _engine()
        group = IntradayLaneGroup(engines={"MTF": mtf, "5M": five, "15M": fifteen})

        group.add_symbols(["CIPLA", "MARUTI"])

        mtf.add_symbols.assert_not_called()
        five.add_symbols.assert_called_once()
        fifteen.add_symbols.assert_called_once()

    def test_start_arms_three_intraday_lanes_with_distinct_profiles(self) -> None:
        mtf = _engine()
        five = _engine()
        fifteen = _engine()
        group = IntradayLaneGroup(engines={"MTF": mtf, "5M": five, "15M": fifteen})
        group.start(profile="adaptive_intraday", scan_now=True)

        mtf.start.assert_called_once_with(profile="adaptive_intraday", scan_now=True)
        five.start.assert_called_once_with(profile="5m_only", scan_now=True)
        fifteen.start.assert_called_once_with(profile="15m_only", scan_now=True)


class PaperDeskSeparateButtonContractTests(unittest.TestCase):
    def test_ui_has_separate_intraday_swing_investment_controls(self) -> None:
        js = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "paper_desk_runtime.js"
        ).read_text(encoding="utf-8")
        for marker in (
            "INTRADAY",
            "SWING",
            "INVESTMENT",
            "intraday_only",
            "swing_only",
            "investment_only",
            "stop_intraday",
            "stop_swing",
            "stop_investment",
            "START ALL",
            "STOP ALL",
        ):
            self.assertIn(marker, js)
        self.assertNotIn("live_execution:true", js.replace(" ", "").lower())


if __name__ == "__main__":
    unittest.main()
