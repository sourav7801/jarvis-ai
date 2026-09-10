from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import jarvis_runtime_supervisor_v12 as runtime_v12
from workstation.adaptive_direct_trade_bridge import _adaptive_live_entry


ROOT = Path(__file__).resolve().parents[1]


class V12SupervisorContracts(unittest.TestCase):
    def test_quant_identity_rejects_old_static_controller(self) -> None:
        old_controller = {
            "success": True,
            "running": True,
            "live_execution": False,
            "mandates": {"INTRADAY": {"profile": "intraday_lanes_v11", "live_execution": False}},
        }
        with patch.object(
            runtime_v12,
            "_json_http",
            side_effect=[
                (200, {"service": "JARVIS_QUANT_TERMINAL"}),
                (200, old_controller),
            ],
        ):
            status = runtime_v12.quant_v12_surface_status()
        self.assertFalse(status["current"])

    def test_quant_identity_accepts_adaptive_controller(self) -> None:
        controller = {
            "success": True,
            "running": True,
            "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "live_execution": False,
            "active_mandates": ["INTRADAY", "SWING", "INVESTMENT"],
            "mandates": {
                "INTRADAY": {
                    "profile": "intraday_lanes_v11",
                    "advanced_profile": "intraday_lanes_v12_adaptive_ev",
                    "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
                    "live_execution": False,
                }
            },
        }
        with patch.object(
            runtime_v12,
            "_json_http",
            side_effect=[
                (200, {"service": "JARVIS_QUANT_TERMINAL"}),
                (200, controller),
            ],
        ):
            status = runtime_v12.quant_v12_surface_status()
        self.assertTrue(status["current"])
        self.assertEqual(status["decision_authority"], "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE")

    def test_v12_services_use_master_wrapper_adaptive_quant_and_v12_completion(self) -> None:
        services = {service.name: service for service in runtime_v12.v12_services(ROOT)}
        self.assertIn("start_jarvis_master_v12.py", services["master"].argv[-1])
        quant_env = dict(services["quant"].environment)
        self.assertEqual(quant_env["JARVIS_AUTO_PAPER_START"], "0")
        self.assertEqual(quant_env["JARVIS_V12_AUTO_PAPER_START"], "1")
        self.assertTrue(services["completion"].health_url.endswith("/api/v12/status"))
        self.assertEqual(services["completion"].expected_service, "JARVIS_ADAPTIVE_MARKET_INTELLIGENCE")

    def test_launcher_executes_v12_and_preserves_old_lineage_markers(self) -> None:
        source = (ROOT / "JARVIS_WORKSTATION.bat").read_text(encoding="utf-8")
        self.assertIn('-m scripts.jarvis_runtime_supervisor_v12', source)
        self.assertIn('-m scripts.jarvis_runtime_supervisor_v11', source)
        self.assertIn('-m scripts.jarvis_runtime_supervisor_v8', source)
        self.assertIn("scripts.jarvis_runtime_supervisor_v62", source)
        self.assertNotIn("place_order(", source)

    def test_completion_starter_uses_v12_surface(self) -> None:
        source = (ROOT / "start_jarvis_completion_console.py").read_text(encoding="utf-8")
        self.assertIn("completion_console_v12", source)


class V12LiveEntryContracts(unittest.TestCase):
    def _candidate(self) -> dict:
        return {
            "success": True,
            "symbol": "BTC",
            "profile": "5m_only",
            "candidate_side": "LONG",
            "side": "LONG",
            "entry": 100.0,
            "stop": 98.0,
            "target": 106.0,
            "score": 55.0,
            "alignment": 80,
            "risk_reward": 3.0,
            "regime": "TRENDING",
            "blockers": ["SCORE_BELOW_GATE"],
            "reasons_not_to_trade": ["SCORE_BELOW_GATE"],
            "adaptive_decision": {"side": "LONG", "executable": True},
        }

    def test_live_mark_outside_verified_setup_is_still_blocked(self) -> None:
        candidate = self._candidate()
        with patch("workstation.paper_trading_desk.live_mark_loader", return_value=107.0):
            entry, blocker = _adaptive_live_entry(candidate)
        self.assertIsNone(entry)
        self.assertEqual(blocker, "LIVE_MARK_OUTSIDE_SETUP")

    def test_live_mark_is_rechecked_by_adaptive_ev_not_fixed_rr(self) -> None:
        candidate = self._candidate()
        with patch("workstation.paper_trading_desk.live_mark_loader", return_value=101.0), \
             patch("workstation.adaptive_direct_trade_bridge._adaptive_decision", return_value={
                 "executable": True,
                 "side": "LONG",
                 "action": "PROBE",
                 "expected_value_r": 0.08,
                 "confidence": 0.35,
                 "risk_multiplier": 0.12,
             }) as evaluate:
            entry, blocker = _adaptive_live_entry(candidate)
        self.assertEqual(entry, 101.0)
        self.assertIsNone(blocker)
        evaluate.assert_called_once()
        self.assertGreater(candidate["live_risk_reward"], 0.0)
        self.assertEqual(candidate["adaptive_decision"]["action"], "PROBE")

    def test_live_edge_decay_blocks_trade(self) -> None:
        candidate = self._candidate()
        with patch("workstation.paper_trading_desk.live_mark_loader", return_value=104.5), \
             patch("workstation.adaptive_direct_trade_bridge._adaptive_decision", return_value={
                 "executable": False,
                 "side": "LONG",
                 "action": "WAIT",
                 "expected_value_r": -0.05,
                 "confidence": 0.40,
                 "risk_multiplier": 0.0,
             }):
            entry, blocker = _adaptive_live_entry(candidate)
        self.assertIsNone(entry)
        self.assertEqual(blocker, "LIVE_ADAPTIVE_EDGE_DECAYED")


if __name__ == "__main__":
    unittest.main()
