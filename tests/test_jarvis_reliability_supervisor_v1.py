from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.reliability_agent import reliability
from omni.reliability_supervisor import ProbeResult, ReliabilitySupervisor


class ReliabilitySupervisorTests(unittest.TestCase):
    def test_probe_result_serializes(self):
        result = ProbeResult("voice", False, "OFFLINE", "down", True, "restart_native_voice")
        self.assertEqual(result.to_dict()["repair_id"], "restart_native_voice")

    def test_diagnose_classifies_degraded(self):
        supervisor = ReliabilitySupervisor(Path.cwd())
        fake = (
            ProbeResult("protected_core", True, "PASS"),
            ProbeResult("native_voice", False, "OFFLINE", repairable=True, repair_id="restart_native_voice"),
        )
        with patch.object(supervisor, "probes", return_value=fake), patch.object(supervisor, "_record"):
            result = supervisor.diagnose()
        self.assertEqual(result["health"], "DEGRADED")
        self.assertIn("restart_native_voice", result["repairable"])
        self.assertTrue(result["protected_core"])

    def test_repair_allowlist_blocks_unknown_repairs(self):
        supervisor = ReliabilitySupervisor(Path.cwd())
        result = supervisor.repair("rewrite_protected_core")
        self.assertFalse(result["success"])
        self.assertIn("allowlist", result["message"].lower())

    def test_agent_routes_diagnose(self):
        with patch("agents.reliability_agent.reliability_supervisor.diagnose", return_value={"message": "diagnosed"}) as call:
            result = reliability("Jarvis diagnose yourself")
        self.assertEqual(result["message"], "diagnosed")
        call.assert_called_once()

    def test_agent_routes_repair(self):
        with patch("agents.reliability_agent.reliability_supervisor.diagnose_and_repair", return_value={"message": "repaired"}) as call:
            result = reliability("Jarvis self heal")
        self.assertEqual(result["message"], "repaired")
        call.assert_called_once()

    def test_agent_routes_improvement(self):
        with patch("agents.reliability_agent.reliability_supervisor.improvement_plan", return_value={"message": "plan"}) as call:
            result = reliability("Jarvis improve yourself")
        self.assertEqual(result["message"], "plan")
        call.assert_called_once()

    def test_incident_store_is_bounded_on_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            supervisor = ReliabilitySupervisor(root)
            # No store yet -> safe empty history.
            self.assertEqual(supervisor.recent_incidents(10), [])

    def test_source_contains_no_live_order_execution(self):
        text = (Path("omni/reliability_supervisor.py").read_text(encoding="utf-8"))
        self.assertNotIn("fyers.place_order", text)
        self.assertNotIn("broker.place_order", text)


if __name__ == "__main__":
    unittest.main()
