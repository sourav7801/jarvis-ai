import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omni.company_action_queue import CompanyActionQueue
from omni.opportunity_radar_scheduler import OpportunityRadarScheduler


class CompanyActionQueueTests(unittest.TestCase):
    def test_exact_payload_approval_is_tamper_evident_and_execution_free(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = CompanyActionQueue(Path(directory) / "actions.json")
            packet = queue.prepare(
                plan_id="P1", department="Marketing", action_type="PUBLISH_DRAFT",
                connector="instagram", destination="brand-account",
                payload={"copy": "Reviewed draft", "publish": False},
            )
            with self.assertRaises(ValueError):
                queue.approve(packet["id"], "wrong-hash", "owner")
            approved = queue.approve(packet["id"], packet["payload_hash"], "owner")
            self.assertEqual(approved["status"], "APPROVED_NOT_EXECUTED")
            with self.assertRaises(ValueError):
                queue.execution_envelope(packet["id"], connector_connected=False, sandbox=True)
            envelope = queue.execution_envelope(packet["id"], connector_connected=True, sandbox=True)
            self.assertTrue(envelope["sandbox_only"])
            self.assertFalse(envelope["external_action_executed"])

    def test_unconfigured_destinations_secrets_and_revoked_actions_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = CompanyActionQueue(Path(directory) / "actions.json")
            with self.assertRaises(ValueError):
                queue.prepare(
                    plan_id="P1", department="Ops", action_type="CONNECT", connector="service",
                    destination="UNCONFIGURED", payload={"access_token": "must-not-be-stored"},
                )
            packet = queue.prepare(
                plan_id="P1", department="Sales", action_type="OUTREACH", connector="email",
                destination="UNCONFIGURED", payload={"draft": "hello", "send": False},
            )
            with self.assertRaises(ValueError):
                queue.approve(packet["id"], packet["payload_hash"], "owner")
            revoked = queue.revoke(packet["id"], "Campaign cancelled")
            self.assertEqual(revoked["status"], "REVOKED")
            self.assertFalse(queue.snapshot()["external_actions_executed"])

    def test_scheduler_runs_only_when_due_and_persists_next_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "radar.json"
            scheduler = OpportunityRadarScheduler(path, interval_hours=24)
            now = datetime(2026, 8, 26, 8, tzinfo=timezone.utc)
            scheduler.enroll("P1", now=now)
            first = scheduler.run_if_due("P1", lambda: {"opportunities": []}, now=now)
            self.assertTrue(first["ran"])
            second = OpportunityRadarScheduler(path).run_if_due(
                "P1", lambda: self.fail("not due runner must not execute"), now=now + timedelta(hours=1)
            )
            self.assertFalse(second["ran"])
            self.assertEqual(second["status"], "NOT_DUE")


if __name__ == "__main__":
    unittest.main()
