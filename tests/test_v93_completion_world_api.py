from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from unittest.mock import patch

from omni.loopback_http import exclusive_server
from workstation import completion_console_v93 as console


class CompletionWorldApiTests(unittest.TestCase):
    def serve(self):
        server = exclusive_server("127.0.0.1", 0, console.CompletionHandlerV93)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_world_endpoint_preserves_safety(self) -> None:
        payload = {
            "success": True,
            "version": "9.3",
            "world": {"node_count": 2, "stale_count": 0},
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "external_actions": "APPROVAL_GATED",
        }
        with patch.object(console, "_world_payload", return_value=payload):
            server, thread = self.serve()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_address[1]}/api/world", timeout=3
                ) as response:
                    self.assertEqual(response.status, 200)
                    result = json.load(response)
                self.assertEqual(result["version"], "9.3")
                self.assertFalse(result["live_execution"])
                self.assertFalse(result["automatic_broker_order"])
                self.assertEqual(result["external_actions"], "APPROVAL_GATED")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)

    def test_overview_adds_world_and_cognitive_state(self) -> None:
        base_payload = {
            "success": True,
            "service": "JARVIS_COMPLETION_CENTER",
            "version": "9.2",
            "overall": "READY",
            "subsystems": {},
            "safety": {
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            },
        }
        world = {
            "world": {"version": "9.3", "node_count": 4},
            "bridge_status": {"installed": True},
        }
        events = {"version": "9.3", "retained": 3, "events": []}
        with patch.object(console.base, "overview_payload", return_value=base_payload), \
             patch.object(console, "_world_payload", return_value=world), \
             patch.object(console, "_cognitive_payload", return_value=events):
            result = console.overview_payload()
        self.assertEqual(result["version"], "9.3")
        self.assertEqual(result["world_model"]["node_count"], 4)
        self.assertEqual(result["cognitive_events"]["retained"], 3)
        self.assertEqual(result["overall"], "READY")
        self.assertFalse(result["safety"]["live_execution"])

    def test_world_failure_degrades_overview_without_hiding_base_state(self) -> None:
        base_payload = {
            "success": True,
            "service": "JARVIS_COMPLETION_CENTER",
            "version": "9.2",
            "overall": "READY",
            "subsystems": {"completion": {"healthy": True}},
            "completion": {"repository_complete": True},
            "safety": {"paper_only": True, "live_execution": False},
        }
        with patch.object(console.base, "overview_payload", return_value=base_payload), \
             patch.object(console, "_world_payload", side_effect=RuntimeError("world failed")), \
             patch.object(console, "_cognitive_payload", return_value={"version": "9.3", "events": []}):
            result = console.overview_payload()
        self.assertTrue(result["success"])
        self.assertEqual(result["overall"], "DEGRADED")
        self.assertIsNone(result["world_model"])
        self.assertTrue(result["completion"]["repository_complete"])
        self.assertFalse(result["subsystems"]["world_model"]["healthy"])
        self.assertFalse(result["safety"]["live_execution"])


if __name__ == "__main__":
    unittest.main()
