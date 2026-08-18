import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.agent_registry import AgentResponse, AgentStatus
from omni.mission_control import MissionControl, is_mission_request
from workstation import app


class FakeRegistry:
    def __init__(self, fail_agent=None):
        self.fail_agent = fail_agent
        self.thread_names = set()

    def get(self, name):
        return object()

    def execute(self, request):
        self.thread_names.add(threading.current_thread().name)
        time.sleep(0.01)
        if request.agent == self.fail_agent:
            return AgentResponse(
                AgentStatus.FAILED,
                request.agent,
                "Specialist failed safely.",
                request.correlation_id,
                error_type="SyntheticFailure",
            )
        return AgentResponse(
            AgentStatus.SUCCEEDED,
            request.agent,
            f"{request.agent} contribution prepared.",
            request.correlation_id,
            data={
                "message": f"{request.agent} contribution prepared.",
                "deliverable": {
                    "current_assessment": "Evidence is still required.",
                    "recommended_sequence": ["Define", "Test", "Review"],
                    "approval_gate": "External actions require approval.",
                },
            },
        )


class MissionControlTests(unittest.TestCase):
    def test_explicit_mission_detection_preserves_fast_normal_routing(self):
        self.assertTrue(is_mission_request("Mission: build a secure customer portal"))
        self.assertTrue(is_mission_request("Coordinate agents to launch this product"))
        self.assertTrue(is_mission_request("Build a secure customer portal", "mission"))
        self.assertFalse(is_mission_request("what time is it"))

    def test_mission_is_parallel_durable_verified_and_approval_gated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = FakeRegistry()
            control = MissionControl(
                registry,
                state_path=root / "mission.json",
                workspaces_root=root / "workspaces",
                max_workers=4,
            )
            with patch("omni.mission_control.audit_event"):
                mission = control.create_mission(
                    "Build a secure analytics dashboard with an API and accessible UI.",
                    title="Analytics Mission",
                )

            self.assertEqual(mission["status"], "LOCAL_PACKET_READY")
            self.assertEqual(mission["critic"]["verdict"], "VERIFIED_LOCAL_PACKET")
            self.assertGreaterEqual(len(registry.thread_names), 2)
            self.assertEqual(len(mission["selected_agents"]), 7)
            self.assertEqual(len(mission["artifacts"]), 6)
            self.assertTrue(all(Path(item["path"]).is_file() for item in mission["artifacts"]))
            self.assertEqual(mission["tasks"][-1]["status"], "AWAITING_APPROVAL")
            self.assertTrue(mission["tasks"][-1]["approval_required"])
            self.assertFalse(mission["trace"]["external_actions_executed"])

            reloaded = MissionControl(
                registry,
                state_path=root / "mission.json",
                workspaces_root=root / "workspaces",
            )
            self.assertEqual(reloaded.snapshot()["latest_mission"]["id"], mission["id"])

    def test_critic_degrades_safely_when_specialist_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = MissionControl(
                FakeRegistry(fail_agent="quality"),
                state_path=root / "mission.json",
                workspaces_root=root / "workspaces",
            )
            with patch("omni.mission_control.audit_event"):
                mission = control.create_mission(
                    "Build a secure software platform for local business operations."
                )
            self.assertEqual(mission["status"], "LOCAL_PACKET_NEEDS_REVIEW")
            self.assertEqual(mission["critic"]["verdict"], "NEEDS_HUMAN_REVIEW")
            self.assertIn("FAILED_SAFE", {task["status"] for task in mission["tasks"]})

    def test_master_command_routes_explicit_mission_to_mission_control(self):
        mission = {
            "selected_agents": ["strategy", "quality"],
            "artifacts": [{"name": "packet"}],
            "critic": {"verdict": "VERIFIED_LOCAL_PACKET"},
        }
        snapshot = {"latest_mission": mission}
        with (
            patch.object(app, "is_mission_request", return_value=True),
            patch.object(app.MISSION_CONTROL, "create_mission", return_value=mission) as create,
            patch.object(app.MISSION_CONTROL, "snapshot", return_value=snapshot),
            patch.object(app, "audit_event"),
        ):
            result = app.execute_command("Coordinate agents to build a secure app", "master")
        self.assertEqual(result["action"], "open_mission")
        self.assertEqual(result["source"], "mission_control")
        self.assertEqual(result["mission_control"], snapshot)
        self.assertEqual(result["routed_context"], "mission")
        self.assertGreaterEqual(len(result["routed_messages"]), 2)
        create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
