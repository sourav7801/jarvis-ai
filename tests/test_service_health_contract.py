from __future__ import annotations

import time
import unittest
from pathlib import Path

from omni.service_health_contract import HEALTH_SCHEMA_VERSION, ServiceHealthClock


class ServiceHealthContractTests(unittest.TestCase):
    def test_uniform_envelope_contains_timing_error_dependency_and_safety_fields(self):
        health = ServiceHealthClock("TEST_SERVICE", "1.2.3")
        time.sleep(0.002)
        payload = health.payload(
            status="ready",
            healthy=True,
            dependencies={"data": "READY"},
        )
        self.assertEqual(payload["health_schema"], HEALTH_SCHEMA_VERSION)
        self.assertEqual(payload["service"], "TEST_SERVICE")
        self.assertEqual(payload["version"], "1.2.3")
        self.assertEqual(payload["status"], "READY")
        self.assertGreaterEqual(payload["uptime_seconds"], 0.0)
        self.assertIsNotNone(payload["started_at"])
        self.assertIsNotNone(payload["response_generated_at"])
        self.assertEqual(payload["dependencies"], {"data": "READY"})
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_execution"])

    def test_recorded_error_is_bounded_and_visible(self):
        health = ServiceHealthClock("TEST_SERVICE", "1")
        health.mark_error("provider failed")
        payload = health.payload(status="degraded", healthy=True)
        self.assertEqual(payload["last_error"], "provider failed")
        self.assertIsNotNone(payload["last_error_at"])
        self.assertEqual(payload["status"], "DEGRADED")

    def test_every_owned_service_health_endpoint_uses_uniform_schema(self):
        root = Path(__file__).resolve().parents[1]
        python_sources = [
            root / "workstation" / "quant_terminal_v2.py",
            root / "workstation" / "fyers_live_bridge_service.py",
            root / "workstation" / "nautilus_core_service.py",
            root / "workstation" / "jarvis_os_v3.py",
        ]
        for source in python_sources:
            text = source.read_text(encoding="utf-8")
            self.assertIn("ServiceHealthClock", text, source.name)
            self.assertIn("HEALTH.payload", text, source.name)
        voice = (root / "workstation" / "native_voice" / "JarvisVoiceService.cs").read_text(
            encoding="utf-8"
        )
        self.assertIn("JARVIS_SERVICE_HEALTH_V1", voice)
        self.assertIn("uptime_seconds", voice)
        self.assertIn("live_execution", voice)


if __name__ == "__main__":
    unittest.main()
