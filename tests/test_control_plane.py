import tempfile
import unittest
from pathlib import Path

from omni.agent_registry import AgentSpec
from omni.control_plane import ControlPlane, is_control_plane_request


class FakeAudit:
    def recent_events(self, _limit):
        return [
            {
                "id": "event-1",
                "timestamp": "2026-08-17T01:00:00+00:00",
                "category": "tool",
                "name": "example",
                "status": "SUCCEEDED",
                "correlation_id": "corr-1",
                "payload": {"secret": "must-not-leak"},
                "payload_json": '{"secret":"must-not-leak"}',
            }
        ]


class ControlPlaneTests(unittest.TestCase):
    def test_control_plane_intent_is_specific(self):
        self.assertTrue(is_control_plane_request("Jarvis, show agent health"))
        self.assertTrue(is_control_plane_request("open the system core"))
        self.assertFalse(is_control_plane_request("analyze BANKNIFTY"))

    def test_agent_readiness_is_static_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "agents"
            package.mkdir()
            (package / "ready.py").write_text(
                "def run(text):\n    return text\n", encoding="utf-8"
            )
            specs = (
                AgentSpec(
                    "ready",
                    "agents.ready",
                    "run",
                    "READY AGENT",
                    frozenset({"system.read"}),
                ),
                AgentSpec(
                    "missing",
                    "agents.missing",
                    "run",
                    "MISSING AGENT",
                    frozenset({"system.read"}),
                ),
            )
            plane = ControlPlane(
                root,
                specs=specs,
                tool_provider=lambda: {},
                audit_provider=FakeAudit,
            )
            manifests = {item["name"]: item for item in plane.agent_manifests()}
            self.assertEqual(manifests["ready"]["status"], "READY")
            self.assertEqual(manifests["missing"]["status"], "UNAVAILABLE")

    def test_snapshot_omits_audit_payloads_and_locks_live_trading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "agents"
            package.mkdir()
            (package / "ready.py").write_text("def run(text):\n    return text\n")
            plane = ControlPlane(
                root,
                specs=(
                    AgentSpec(
                        "ready",
                        "agents.ready",
                        "run",
                        "READY AGENT",
                        frozenset({"system.read"}),
                    ),
                ),
                tool_provider=lambda: {},
                audit_provider=FakeAudit,
            )
            snapshot = plane.snapshot(
                live_trading_enabled=False,
                workstation_host="127.0.0.1",
            )
            self.assertEqual(snapshot["status"], "READY")
            self.assertEqual(snapshot["runtime"]["live_trading"], "LOCKED")
            self.assertTrue(snapshot["runtime"]["loopback_only"])
            self.assertNotIn("payload", snapshot["trace"][0])
            self.assertNotIn("payload_json", snapshot["trace"][0])


if __name__ == "__main__":
    unittest.main()
