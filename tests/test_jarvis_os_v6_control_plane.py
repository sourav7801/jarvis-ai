from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omni.os_control_plane import JarvisOSControlPlane, os_command_kind


class JarvisOSV6ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.os = JarvisOSControlPlane(
            state_path=root / "state.json",
            event_path=root / "events.jsonl",
            failure_path=root / "failures.jsonl",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_os_command_detection(self):
        self.assertEqual(os_command_kind("jarvis os status"), "STATUS")
        self.assertEqual(os_command_kind("show all capabilities"), "CAPABILITIES")
        self.assertEqual(os_command_kind("analyze your mistakes"), "IMPROVEMENT_REVIEW")

    def test_live_trading_is_locked(self):
        decision = self.os.approval_for("live_trading")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.mode, "LOCKED")

    def test_safe_local_work_can_be_autonomous(self):
        decision = self.os.approval_for("read_only")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.mode, "AUTONOMOUS_WITH_AUDIT")

    def test_consequential_work_requires_approval(self):
        decision = self.os.approval_for("external_write")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.mode, "EXPLICIT_APPROVAL_REQUIRED")

    def test_outcome_learning_is_persistent_metadata_not_self_modification(self):
        self.os.record_outcome("unit_test", success=False, error="Timeout talking to local service")
        self.os.record_outcome("unit_test", success=False, error="Timeout talking to local service")
        review = self.os.improvement_review()
        self.assertGreaterEqual(review["failures_reviewed"], 2)
        self.assertTrue(review["recurring_failure_classes"])
        self.assertFalse(review["production_self_modification"])
        self.assertTrue(review["promotion_requires_tests"])

    def test_goal_and_event_are_persisted(self):
        goal = self.os.record_goal("Build and verify a reversible local workflow")
        self.assertEqual(goal["status"], "ACCEPTED")
        self.assertTrue(self.os.state_path.exists())
        self.assertTrue(self.os.event_path.exists())

    def test_capability_inventory_contains_os_control_plane(self):
        names = {item.name for item in self.os.capability_inventory()}
        self.assertIn("os_control_plane", names)


if __name__ == "__main__":
    unittest.main()
