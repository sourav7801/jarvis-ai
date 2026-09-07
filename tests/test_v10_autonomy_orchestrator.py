from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from omni.autonomy_orchestrator import AutonomyOrchestrator

ROOT = Path(__file__).resolve().parents[1]


class AutonomyOrchestratorV10Tests(unittest.TestCase):
    @staticmethod
    def executive(domain="GENERAL"):
        return {
            "success": True,
            "version": "8.0",
            "advanced_version": "10.0",
            "domain": domain,
            "intent": {"kind": "GENERAL", "deterministic": False},
            "steps": [{"index": 1, "phase": "PLAN", "capability": "conversation"}],
            "safety": {
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_rewrite": False,
                "external_actions": "APPROVAL_GATED",
            },
        }

    @staticmethod
    def critic():
        return {
            "success": True,
            "verdict": "VERIFIED",
            "confidence": .91,
            "verification_id": "verify-test",
            "progression_allowed": True,
            "safety": {"live_execution": False, "automatic_broker_order": False},
        }

    def test_plan_only_never_starts_or_queues_a_mission(self):
        orchestrator = AutonomyOrchestrator()
        with patch("omni.executive_control_plane.EXECUTIVE_CONTROL_PLANE.plan", return_value=self.executive()), \
             patch("omni.critic_verifier.CRITIC_VERIFIER.verify", return_value=self.critic()), \
             patch("omni.evidence_ledger.EVIDENCE_LEDGER.record", return_value={}), \
             patch("omni.mission_worker.MISSION_WORKER.enqueue") as enqueue:
            result = orchestrator.plan("Prepare a safe local architecture review.", enqueue_mission=False)
        enqueue.assert_not_called()
        self.assertIsNone(result["mission_queued"])
        self.assertFalse(result["automatic_mission_start"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["live_execution"])
        self.assertFalse(result["automatic_broker_order"])

    def test_explicit_queue_requires_verified_critic_and_does_not_start_worker(self):
        orchestrator = AutonomyOrchestrator()
        queued = {"queue_id": "queue-0123456789abcdef", "status": "QUEUED"}
        with patch("omni.executive_control_plane.EXECUTIVE_CONTROL_PLANE.plan", return_value=self.executive("MISSION")), \
             patch("omni.critic_verifier.CRITIC_VERIFIER.verify", return_value=self.critic()), \
             patch("omni.mission_worker.MISSION_WORKER.enqueue", return_value=queued) as enqueue, \
             patch("omni.mission_worker.MISSION_WORKER.start") as start, \
             patch("omni.cognitive_event_bus.COGNITIVE_EVENT_BUS.publish", return_value={}), \
             patch("omni.evidence_ledger.EVIDENCE_LEDGER.record", return_value={}):
            result = orchestrator.plan("Build a supervised local mission review packet.", enqueue_mission=True)
        enqueue.assert_called_once()
        start.assert_not_called()
        self.assertEqual(result["mission_queued"]["status"], "QUEUED")
        self.assertFalse(result["automatic_mission_start"])
        self.assertEqual(result["external_actions"], "APPROVAL_GATED")

    def test_non_verified_critic_blocks_queueing(self):
        orchestrator = AutonomyOrchestrator()
        blocked = {**self.critic(), "success": False, "verdict": "INSUFFICIENT_EVIDENCE", "progression_allowed": False}
        with patch("omni.executive_control_plane.EXECUTIVE_CONTROL_PLANE.plan", return_value=self.executive("MISSION")), \
             patch("omni.critic_verifier.CRITIC_VERIFIER.verify", return_value=blocked), \
             patch("omni.mission_worker.MISSION_WORKER.enqueue") as enqueue:
            with self.assertRaises(RuntimeError):
                orchestrator.plan("Queue a mission that must fail the critic gate.", enqueue_mission=True)
        enqueue.assert_not_called()

    def test_autonomy_is_system_plane_not_agent_30(self):
        status = AutonomyOrchestrator().status()
        self.assertTrue(status["system_plane"])
        self.assertFalse(status["permanent_agent"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["automatic_broker_order"])
        self.assertFalse(status["automatic_production_strategy_rewrite"])

    def test_v10_ui_exposes_autonomy_control_without_broker_order_api(self):
        html = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "workstation" / "completion_console_static" / "v10_advanced.js").read_text(encoding="utf-8")
        server = (ROOT / "workstation" / "completion_console_v10.py").read_text(encoding="utf-8")
        self.assertIn('id="autonomyNav"', html)
        self.assertIn("/api/autonomy", js)
        self.assertIn('path == "/api/autonomy"', server)
        self.assertIn('path == "/api/autonomy/plan"', server)
        for token in ("place_order(", "modify_order(", "cancel_order(", "submit_order("):
            self.assertNotIn(token, html)
            self.assertNotIn(token, js)
            self.assertNotIn(token, server)


if __name__ == "__main__":
    unittest.main()
