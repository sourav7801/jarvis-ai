from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from omni.agent_registry import default_agent_specs
from omni.governed_execution_mesh import GovernedExecutionMesh
from workstation.candidate_horizon_router import CandidateHorizonRouter
from workstation.derived_timeframe_bridge import aggregate_completed_10m
from workstation.intraday_lane_group import IntradayLaneGroup
from workstation.trading_decision_mesh import TradingDecisionMesh
from workstation.trading_timeframe_profiles import requested_trading_profile, resolve_trading_profile
from workstation import completion_console_v11


ROOT = Path(__file__).resolve().parents[1]


def _engine(*, running: bool = True) -> MagicMock:
    engine = MagicMock()
    engine.configure_mandate.return_value = {"success": True}
    engine.start.return_value = {"success": True, "running": True}
    engine.stop.return_value = {"success": True, "running": False}
    engine.add_symbols.return_value = {"success": True}
    engine.trigger_scan.return_value = {"success": True, "scan_triggered": True}
    engine.status.return_value = {
        "success": True,
        "running": running,
        "universe": [],
        "min_score": 68.0,
        "min_risk_reward": 1.8,
        "last_scan_funnel": {},
        "last_rejection_counts": {},
        "last_rows_summary": [],
        "paper_only": True,
        "live_execution": False,
    }
    return engine


class DerivedTenMinuteTests(unittest.TestCase):
    def test_only_two_contiguous_completed_5m_bars_form_one_10m_bar(self) -> None:
        candles = [
            {"time": 300, "open": 100, "high": 103, "low": 99, "close": 102, "volume": 10},
            {"time": 600, "open": 102, "high": 105, "low": 101, "close": 104, "volume": 12},
            {"time": 900, "open": 104, "high": 106, "low": 103, "close": 105, "volume": 9},
            # 1200 is deliberately missing; 900 must never be paired with 1500.
            {"time": 1500, "open": 105, "high": 107, "low": 104, "close": 106, "volume": 8},
        ]
        rows = aggregate_completed_10m(candles, phase_seconds=300)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["time"], 300)
        self.assertEqual(row["open"], 100.0)
        self.assertEqual(row["close"], 104.0)
        self.assertEqual(row["high"], 105.0)
        self.assertEqual(row["low"], 99.0)
        self.assertEqual(row["volume"], 22.0)
        self.assertEqual(row["source_bar_times"], [300, 600])
        self.assertTrue(row["derived"])
        self.assertEqual(row["derived_from"], "5m")

    def test_10m_profile_is_strict_completed_breakout_profile(self) -> None:
        profile = resolve_trading_profile("10m")
        self.assertEqual(profile.name, "10m_only")
        self.assertEqual(profile.timeframes, ("10m",))
        self.assertTrue(profile.require_confirmed_pattern)
        self.assertGreaterEqual(profile.minimum_score, 68.0)
        self.assertLessEqual(profile.risk_multiplier, 1.0)
        requested = requested_trading_profile("trade 10 minute only")
        self.assertEqual(requested.name, "10m_only")


class IntradayV11LaneTests(unittest.TestCase):
    def test_candidate_symbols_route_to_5m_10m_15m_not_mtf(self) -> None:
        engines = {"MTF": _engine(), "5M": _engine(), "10M": _engine(), "15M": _engine()}
        group = IntradayLaneGroup(engines=engines)
        group.add_symbols(["CIPLA", "MARUTI"])
        engines["MTF"].add_symbols.assert_not_called()
        for lane in ("5M", "10M", "15M"):
            engines[lane].add_symbols.assert_called_once()

    def test_start_arms_four_governed_profiles(self) -> None:
        engines = {"MTF": _engine(), "5M": _engine(), "10M": _engine(), "15M": _engine()}
        group = IntradayLaneGroup(engines=engines)
        group.start(profile="adaptive_intraday", scan_now=True)
        engines["MTF"].start.assert_called_once_with(profile="adaptive_intraday", scan_now=True)
        engines["5M"].start.assert_called_once_with(profile="5m_only", scan_now=True)
        engines["10M"].start.assert_called_once_with(profile="10m_only", scan_now=True)
        engines["15M"].start.assert_called_once_with(profile="15m_only", scan_now=True)
        status = group.status()
        self.assertEqual(status["profile"], "intraday_lanes_v11")
        self.assertEqual(status["timeframes"], ["5m", "10m", "15m"])
        self.assertTrue(status["derived_timeframes"]["10M"]["completed_bars_only"])
        self.assertFalse(status["derived_timeframes"]["10M"]["synthetic_missing_bars"])


class CandidateRouterV11Tests(unittest.TestCase):
    def test_duplicate_route_is_suppressed_when_scanner_already_routed_completion(self) -> None:
        router = CandidateHorizonRouter()
        routing = {
            "routed_at": "2026-09-08T01:00:00+00:00",
            "intraday_symbols": ["CIPLA"],
            "swing_symbols": ["CIPLA"],
            "investment_symbols": ["CIPLA"],
            "paper_only": True,
            "live_execution": False,
        }
        scanner_status = {
            "completed_at": "2026-09-08T01:00:00+00:00",
            "candidates": [{"symbol": "CIPLA"}],
            "governed_auto_routing_completed_at": "2026-09-08T01:00:00+00:00",
            "governed_auto_routing": routing,
        }
        with patch("workstation.multi_market_scanner.multi_market_scanner.status", return_value=scanner_status), \
             patch("workstation.paper_portfolio_controller.paper_portfolio_controller.enroll_discovery_candidates") as enroll:
            result = router.route_now()
        self.assertFalse(result["routed"])
        self.assertEqual(result["reason"], "SCANNER_ALREADY_ROUTED_THIS_COMPLETION")
        enroll.assert_not_called()
        self.assertEqual(router.status()["suppressed_duplicate_routes"], 1)


class TradingDecisionMeshTests(unittest.TestCase):
    def test_discovery_score_is_not_execution_authority_and_blocker_is_explained(self) -> None:
        scanner = {
            "success": True,
            "candidates": [{
                "symbol": "CIPLA",
                "candidate": True,
                "auto_paper_eligible": True,
                "state": "CONFIRMED_BREAKOUT",
                "direction": "BULLISH",
                "score": 72.0,
            }],
        }
        controller = {
            "success": True,
            "active_mandates": ["INTRADAY", "SWING"],
            "candidate_routing": {
                "intraday_symbols": ["CIPLA"],
                "swing_symbols": ["CIPLA"],
                "investment_symbols": [],
            },
            "mandates": {
                "INTRADAY": {"running": True},
                "SWING": {"running": True},
                "INVESTMENT": {"running": False},
            },
            "decision_board": [{
                "symbol": "CIPLA",
                "mandate": "SWING",
                "lane": None,
                "execution_score": 71.0,
                "candidate_side": "LONG",
                "qualified": False,
                "blockers": ["RISK_REWARD_BELOW_GATE"],
            }],
        }
        providers = {
            "scanner": lambda: scanner,
            "portfolio_controller": lambda: controller,
            "candidate_router": lambda: {"success": True},
            "derived_timeframe": lambda: {"success": True, "installed": True},
            "discovery_routing_bridge": lambda: {"success": True, "installed": True},
            "trading_governance": lambda: {"success": True},
        }
        mesh = TradingDecisionMesh()
        with patch.object(mesh, "_providers", return_value=providers), \
             patch("workstation.derived_timeframe_bridge.install_derived_timeframe_bridge", return_value={"success": True}), \
             patch("workstation.discovery_routing_bridge.install_discovery_routing_bridge", return_value={"success": True}):
            payload = mesh.snapshot()
        row = payload["rows"][0]
        self.assertEqual(row["symbol"], "CIPLA")
        self.assertEqual(row["discovery_score"], 72.0)
        self.assertEqual(row["execution_score"], 71.0)
        self.assertEqual(row["state"], "EVALUATED_BLOCKED")
        self.assertIn("RISK_REWARD_BELOW_GATE", row["why_not_trade"])
        self.assertIn("Broad completed-bar ranking", payload["score_contract"]["discovery_score"])
        self.assertFalse(payload["live_execution"])


class GovernedExecutionMeshTests(unittest.TestCase):
    def test_step_contract_locks_broker_and_gates_external_actions(self) -> None:
        rows = GovernedExecutionMesh._step_contract({
            "steps": [
                {"action": "code.analyze"},
                {"action": "publish external report"},
                {"action": "broker order"},
            ]
        })
        self.assertEqual(rows[0]["classification"], "LOCAL_GOVERNED")
        self.assertEqual(rows[1]["classification"], "APPROVAL_REQUIRED")
        self.assertEqual(rows[2]["classification"], "LIVE_BROKER_LOCKED")
        self.assertFalse(rows[2]["live_broker_allowed"])

    def test_execution_mesh_is_system_plane_not_agent(self) -> None:
        status = GovernedExecutionMesh().status()
        self.assertTrue(status["system_plane"])
        self.assertFalse(status["permanent_agent"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["automatic_broker_order"])


class CompletionV11Tests(unittest.TestCase):
    def test_overview_adds_execution_surfaces_without_weakening_safety(self) -> None:
        base = {
            "success": True,
            "version": "10.0",
            "overall": "READY",
            "subsystems": {},
            "advanced": {},
            "safety": {"paper_only": True, "live_execution": False, "automatic_broker_order": False},
        }
        advanced = {
            name: {"healthy": True, "state": "READY", "data": {"success": True}, "error": None}
            for name in (
                "governed_execution_mesh", "trading_decision_mesh",
                "derived_10m_timeframe", "discovery_routing_bridge",
            )
        }
        with patch.object(completion_console_v11.v10, "overview_payload", return_value=base), \
             patch.object(completion_console_v11.V11, "collect", return_value=advanced):
            payload = completion_console_v11.overview_payload()
        self.assertEqual(payload["version"], "11.0")
        self.assertTrue(payload["advanced"]["governed_execution_mesh"])
        self.assertTrue(payload["advanced"]["why_not_trade_diagnostics"])
        self.assertTrue(payload["safety"]["paper_only"])
        self.assertFalse(payload["safety"]["live_execution"])
        self.assertFalse(payload["safety"]["automatic_broker_order"])

    def test_ui_contains_v11_navigation_and_no_broker_order_api(self) -> None:
        html = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "workstation" / "completion_console_static" / "v11_execution_mesh.js").read_text(encoding="utf-8")
        for marker in ("executionMeshNav", "tradingDecisionNav", "derived10mNav", "V11 COGNITIVE EXECUTION"):
            self.assertIn(marker, html)
        for endpoint in (
            "/api/execution-mesh", "/api/trading-decision-mesh",
            "/api/trading-decision/explain", "/api/derived-timeframe",
            "/api/discovery-routing",
        ):
            self.assertIn(endpoint, script)
        forbidden = ("place_order(", "modify_order(", "cancel_order(", "submit_order(")
        for token in forbidden:
            self.assertNotIn(token, script)

    def test_start_script_targets_v11(self) -> None:
        text = (ROOT / "start_jarvis_completion_console.py").read_text(encoding="utf-8")
        self.assertIn("completion_console_v11", text)


class PermanentAgentContractV11Tests(unittest.TestCase):
    def test_system_planes_do_not_change_29_agent_registry(self) -> None:
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        # Legacy Critic specialist is intentionally one of the 29 agents.
        self.assertIn("critic", names)
        for system_plane in (
            "executive", "autonomy_orchestrator", "critic_verifier",
            "governed_execution_mesh", "engineering_governance",
            "trading_decision_mesh", "discovery_routing_bridge",
        ):
            self.assertNotIn(system_plane, names)


if __name__ == "__main__":
    unittest.main()
