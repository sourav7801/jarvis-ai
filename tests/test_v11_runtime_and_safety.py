from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from omni.governed_execution_mesh import GovernedExecutionMesh
from scripts import jarvis_runtime_supervisor_v11 as runtime_v11


ROOT = Path(__file__).resolve().parents[1]


class V11CompletionRuntimeTests(unittest.TestCase):
    def test_completion_identity_requires_exact_v11_contract(self) -> None:
        payload = b'{"success":true,"version":"11.0","service":"JARVIS_COGNITIVE_EXECUTION_CONVERGENCE","permanent_agents":29,"live_execution":false,"automatic_broker_order":false}'
        with patch.object(runtime_v11, "_http", return_value=(200, payload)):
            status = runtime_v11.completion_v11_surface_status()
        self.assertTrue(status["current"])
        self.assertEqual(status["version"], "11.0")

    def test_completion_identity_rejects_v10_or_unknown_surface(self) -> None:
        with patch.object(runtime_v11, "_http", return_value=(200, b'{"success":true,"version":"10.0","service":"JARVIS_ADVANCED_AUTONOMY_CONVERGENCE"}')):
            status = runtime_v11.completion_v11_surface_status()
        self.assertFalse(status["current"])

    def test_unknown_completion_process_is_never_trusted(self) -> None:
        self.assertFalse(runtime_v11._trusted_completion_process({
            "ExecutablePath": "C:\\Windows\\System32\\python.exe",
            "CommandLine": "python unrelated_server.py",
        }))
        self.assertTrue(runtime_v11._trusted_completion_process({
            "ExecutablePath": "C:\\Jarvis\\.venv\\Scripts\\python.exe",
            "CommandLine": "C:\\Jarvis\\.venv\\Scripts\\python.exe C:\\Jarvis\\start_jarvis_completion_console.py",
        }))

    def test_supervised_completion_uses_v11_identity_endpoint(self) -> None:
        services = {service.name: service for service in runtime_v11.v11_services(ROOT)}
        completion = services["completion"]
        self.assertTrue(completion.health_url.endswith("/api/v11/status"))
        self.assertEqual(completion.expected_service, "JARVIS_COGNITIVE_EXECUTION_CONVERGENCE")

    def test_launcher_preserves_old_safety_lineage_but_runs_v11(self) -> None:
        launcher = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        self.assertIn("scripts.jarvis_runtime_supervisor_v62", launcher)
        self.assertIn("scripts.jarvis_runtime_supervisor_v8", launcher)
        self.assertIn("-m scripts.jarvis_runtime_supervisor_v11", launcher)
        self.assertNotIn("place_order(", launcher)
        self.assertNotIn("submit_order(", launcher)


class V11MissionQueueSafetyTests(unittest.TestCase):
    def test_live_broker_step_is_blocked_before_local_mission_queue(self) -> None:
        mesh = GovernedExecutionMesh()
        autonomy = {
            "domain": "MARKETS",
            "executive": {"steps": [{"capability": "broker.order"}]},
            "critic": {"verification_id": "v10-critic"},
        }
        with patch("omni.autonomy_orchestrator.AUTONOMY_ORCHESTRATOR.plan", return_value=autonomy) as v10_plan, \
             patch.object(mesh, "_domain_surface", return_value={"healthy": True, "name": "test", "data": {}, "error": None}), \
             patch("omni.critic_verifier.CRITIC_VERIFIER.verify", return_value={"progression_allowed": False, "confidence": 0.2}), \
             patch("omni.mission_worker.MISSION_WORKER.enqueue") as enqueue:
            with self.assertRaises(PermissionError):
                mesh.plan("place a live broker order for testing", enqueue_mission=True)
        v10_plan.assert_called_once_with("place a live broker order for testing", enqueue_mission=False)
        enqueue.assert_not_called()

    def test_verified_local_packet_can_queue_but_never_auto_starts(self) -> None:
        mesh = GovernedExecutionMesh()
        autonomy = {
            "domain": "SYSTEM",
            "executive": {"steps": [{"capability": "system.health"}]},
            "critic": {"verification_id": "v10-critic"},
        }
        queued = {"queue_id": "q-1", "status": "QUEUED"}
        with patch("omni.autonomy_orchestrator.AUTONOMY_ORCHESTRATOR.plan", return_value=autonomy), \
             patch.object(mesh, "_domain_surface", return_value={"healthy": True, "name": "test", "data": {}, "error": None}), \
             patch("omni.critic_verifier.CRITIC_VERIFIER.verify", return_value={"progression_allowed": True, "confidence": 0.9, "verification_id": "v11-critic"}), \
             patch("omni.mission_worker.MISSION_WORKER.enqueue", return_value=queued) as enqueue, \
             patch("omni.evidence_ledger.EVIDENCE_LEDGER.record", return_value={}), \
             patch("omni.cognitive_event_bus.COGNITIVE_EVENT_BUS.publish", return_value={}):
            result = mesh.plan("inspect system health and prepare a local report", enqueue_mission=True)
        enqueue.assert_called_once()
        self.assertEqual(result["mission_queued"], queued)
        self.assertFalse(result["automatic_mission_start"])
        self.assertFalse(result["live_execution"])
        self.assertFalse(result["automatic_broker_order"])


if __name__ == "__main__":
    unittest.main()
