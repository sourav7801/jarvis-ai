from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.reliability_supervisor import ReliabilitySupervisor


class ReliabilitySupervisorV11BTests(unittest.TestCase):
    def test_native_voice_stopped_is_healthy_when_ui_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = ReliabilitySupervisor(directory)

            with (
                patch.object(supervisor, "_http_json", return_value=None),
                patch.object(supervisor, "_tcp_open", return_value=False),
            ):
                result = supervisor.probe_native_voice()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "STOPPED")
        self.assertFalse(result.repairable)
        self.assertIsNone(result.repair_id)

    def test_native_voice_offline_is_failure_when_ui_online(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "start_jarvis_native_voice.ps1").write_text(
                "# test launcher",
                encoding="utf-8",
            )
            supervisor = ReliabilitySupervisor(root)

            with (
                patch.object(supervisor, "_http_json", return_value=None),
                patch.object(supervisor, "_tcp_open", return_value=True),
            ):
                result = supervisor.probe_native_voice()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "OFFLINE")
        self.assertTrue(result.repairable)
        self.assertEqual(result.repair_id, "restart_native_voice")

    def test_native_voice_online_is_healthy(self):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = ReliabilitySupervisor(directory)

            with patch.object(
                supervisor,
                "_http_json",
                return_value={"success": True},
            ):
                result = supervisor.probe_native_voice()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "ONLINE")

    def test_fully_stopped_stack_is_healthy(self):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = ReliabilitySupervisor(directory)

            with (
                patch.object(supervisor, "_http_json", return_value=None),
                patch.object(supervisor, "_tcp_open", return_value=False),
            ):
                voice = supervisor.probe_native_voice()
                lifecycle = supervisor.probe_service_lifecycle()

        self.assertTrue(voice.ok)
        self.assertEqual(voice.status, "STOPPED")
        self.assertTrue(lifecycle.ok)
        self.assertEqual(lifecycle.status, "STOPPED")


if __name__ == "__main__":
    unittest.main()
