from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.jarvis_runtime_supervisor import (
    JarvisRuntimeSupervisor,
    ManagedService,
)


class JarvisRuntimeSupervisorTests(unittest.TestCase):
    def service(self) -> ManagedService:
        return ManagedService(
            name="quant",
            argv=("python.exe", "start_jarvis_quant_terminal.py"),
            health_url="http://127.0.0.1:8787/api/health",
            expected_service="JARVIS_QUANT_TERMINAL",
            port=8787,
        )

    def test_missing_quant_service_is_started_and_durably_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = JarvisRuntimeSupervisor(
                root=Path(directory),
                services=(self.service(),),
                browser=False,
            )
            child = MagicMock()
            child.pid = 31415
            child.poll.return_value = None

            with (
                patch.object(supervisor, "_health_payload", return_value=None),
                patch.object(supervisor, "_port_open", return_value=False),
                patch("scripts.jarvis_runtime_supervisor.subprocess.Popen", return_value=child),
            ):
                result = supervisor.reconcile_once(now=100.0)

            self.assertEqual(result["services"]["quant"]["state"], "STARTING")
            self.assertEqual(result["services"]["quant"]["pid"], 31415)
            events = [
                json.loads(line)
                for line in supervisor.event_log.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(events[-1]["event"], "SERVICE_STARTED")
            self.assertEqual(events[-1]["service"], "quant")
            supervisor.stop_owned_services()

    def test_healthy_external_service_is_adopted_without_duplicate_process(self):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = JarvisRuntimeSupervisor(
                root=Path(directory),
                services=(self.service(),),
                browser=False,
            )
            with (
                patch.object(
                    supervisor,
                    "_health_payload",
                    return_value={"service": "JARVIS_QUANT_TERMINAL", "healthy": True},
                ),
                patch("scripts.jarvis_runtime_supervisor.subprocess.Popen") as popen,
            ):
                result = supervisor.reconcile_once(now=100.0)

            self.assertEqual(result["services"]["quant"]["state"], "READY_EXTERNAL")
            popen.assert_not_called()

    def test_master_html_identity_is_a_valid_health_contract(self):
        service = ManagedService(
            name="master",
            argv=("python.exe", "start_jarvis_v3.py"),
            health_url="http://127.0.0.1:8797/",
            expected_service="",
            port=8797,
            health_markers=("JARVIS", "OMNI OPERATING COMMAND CENTER"),
        )
        with tempfile.TemporaryDirectory() as directory:
            supervisor = JarvisRuntimeSupervisor(
                root=Path(directory),
                services=(service,),
                browser=False,
            )
            with (
                patch.object(supervisor, "_health_payload", return_value=None),
                patch.object(
                    supervisor,
                    "_health_page",
                    return_value="<html>JARVIS · OMNI OPERATING COMMAND CENTER</html>",
                ),
                patch("scripts.jarvis_runtime_supervisor.subprocess.Popen") as popen,
            ):
                result = supervisor.reconcile_once(now=100.0)

            self.assertEqual(result["services"]["master"]["state"], "READY_EXTERNAL")
            popen.assert_not_called()

    def test_unknown_process_on_owned_port_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = JarvisRuntimeSupervisor(
                root=Path(directory),
                services=(self.service(),),
                browser=False,
            )
            with (
                patch.object(supervisor, "_health_payload", return_value=None),
                patch.object(supervisor, "_port_open", return_value=True),
                patch("scripts.jarvis_runtime_supervisor.subprocess.Popen") as popen,
            ):
                result = supervisor.reconcile_once(now=100.0)

            self.assertEqual(result["services"]["quant"]["state"], "PORT_CONFLICT")
            popen.assert_not_called()

    def test_persistent_port_conflict_does_not_spam_the_event_log(self):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = JarvisRuntimeSupervisor(
                root=Path(directory),
                services=(self.service(),),
                browser=False,
            )
            with (
                patch.object(supervisor, "_health_payload", return_value=None),
                patch.object(supervisor, "_port_open", return_value=True),
            ):
                supervisor.reconcile_once(now=100.0)
                supervisor.reconcile_once(now=101.0)

            events = [
                json.loads(line)
                for line in supervisor.event_log.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [event["event"] for event in events],
                ["PORT_CONFLICT"],
            )

    def test_repeated_crashes_are_quarantined_instead_of_restart_looping(self):
        with tempfile.TemporaryDirectory() as directory:
            supervisor = JarvisRuntimeSupervisor(
                root=Path(directory),
                services=(self.service(),),
                browser=False,
                restart_limit=2,
                restart_window_seconds=60.0,
            )
            child = MagicMock()
            child.pid = 7
            child.poll.return_value = 1
            runtime = supervisor.runtime["quant"]
            runtime.process = child
            runtime.restart_times.extend([80.0, 90.0])

            with (
                patch.object(supervisor, "_health_payload", return_value=None),
                patch.object(supervisor, "_port_open", return_value=False),
                patch("scripts.jarvis_runtime_supervisor.subprocess.Popen") as popen,
            ):
                result = supervisor.reconcile_once(now=100.0)

            self.assertEqual(result["services"]["quant"]["state"], "QUARANTINED")
            popen.assert_not_called()
            events = [
                json.loads(line)
                for line in supervisor.event_log.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(events[-1]["event"], "SERVICE_QUARANTINED")

    def test_canonical_batch_launcher_uses_runtime_supervisor(self):
        source = Path("JARVIS.bat").read_text(encoding="utf-8")
        direct_launcher = "scripts\\jarvis_runtime_supervisor.py" in source
        hardened_launcher = "scripts.jarvis_runtime_supervisor_v62" in source
        self.assertTrue(
            direct_launcher or hardened_launcher,
            msg="JARVIS.bat must launch the canonical supervisor directly or through the hardened V6.2 wrapper.",
        )
        if hardened_launcher:
            wrapper = Path("scripts/jarvis_runtime_supervisor_v62.py").read_text(encoding="utf-8")
            self.assertIn("scripts.jarvis_runtime_supervisor", wrapper)
            self.assertIn("JarvisRuntimeSupervisor", wrapper)
        self.assertNotIn(
            'start "JARVIS Quant Trading Intelligence" /min "%JARVIS_PY%"',
            source,
        )

    def test_supervisor_source_cannot_place_live_orders(self):
        sources = [
            Path("scripts/jarvis_runtime_supervisor.py").read_text(encoding="utf-8"),
            Path("scripts/jarvis_runtime_supervisor_v62.py").read_text(encoding="utf-8"),
        ]
        for source in sources:
            self.assertNotIn("place_order", source)
            self.assertNotIn("submit_order", source)
        self.assertNotIn("fyers", sources[0].lower())


if __name__ == "__main__":
    unittest.main()
