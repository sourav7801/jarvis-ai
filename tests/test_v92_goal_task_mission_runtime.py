from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omni.goal_task_graph import GoalTaskGraphStore
from omni.mission_queue import MissionQueue
from omni.mission_worker import MissionWorker


class FakeMissionControl:
    def __init__(self, *, verified: bool = True) -> None:
        self.verified = verified
        self.calls = []

    def create_mission(self, objective: str, title: str | None = None):
        self.calls.append((objective, title))
        verdict = "VERIFIED_LOCAL_PACKET" if self.verified else "NEEDS_HUMAN_REVIEW"
        return {
            "id": "mission-test-001",
            "title": title or "Test mission",
            "objective": objective,
            "status": "LOCAL_PACKET_READY" if self.verified else "LOCAL_PACKET_NEEDS_REVIEW",
            "selected_agents": ["strategy", "engineering", "quality", "operator"],
            "critic": {
                "verdict": verdict,
                "confidence": 91 if self.verified else 62,
                "checks": {"external_actions_locked": True},
            },
            "tasks": [{"id": "M00", "status": "SUCCEEDED"}],
            "artifacts": [{"name": "00-mission-brief.md", "path": "C:/tmp/mission/00-mission-brief.md"}],
        }


class GoalTaskGraphTests(unittest.TestCase):
    def test_persistent_dependency_dag_and_approval_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            store = GoalTaskGraphStore(Path(folder) / "graphs.json")
            graph = store.create("Build a durable supervised mission runtime for JARVIS.", queue_id="queue-0123456789abcdef")
            graph_id = graph["graph_id"]
            self.assertEqual(graph["tasks"][0]["status"], "READY")
            self.assertEqual(graph["tasks"][1]["status"], "WAITING_DEPENDENCY")

            store.update_task(graph_id, "T00", "RUNNING")
            graph = store.update_task(graph_id, "T00", "VERIFIED")
            by_id = {row["task_id"]: row for row in graph["tasks"]}
            self.assertEqual(by_id["T10"]["status"], "READY")

            store.update_task(graph_id, "T10", "RUNNING")
            store.update_task(graph_id, "T10", "VERIFIED")
            store.update_task(graph_id, "T20", "RUNNING")
            graph = store.update_task(graph_id, "T20", "VERIFIED")
            by_id = {row["task_id"]: row for row in graph["tasks"]}
            self.assertEqual(by_id["A90"]["status"], "WAITING_APPROVAL")
            self.assertEqual(graph["status"], "LOCAL_WORK_COMPLETED")
            self.assertTrue(graph["paper_only"])
            self.assertFalse(graph["live_execution"])
            with self.assertRaises(PermissionError):
                store.update_task(graph_id, "A90", "RUNNING")

            reloaded = GoalTaskGraphStore(Path(folder) / "graphs.json")
            self.assertEqual(reloaded.graph(graph_id)["status"], "LOCAL_WORK_COMPLETED")

    def test_pause_resume_graph(self):
        with tempfile.TemporaryDirectory() as folder:
            store = GoalTaskGraphStore(Path(folder) / "graphs.json")
            graph = store.create("Pause and resume a bounded local mission graph safely.")
            paused = store.pause(graph["graph_id"], "operator requested")
            self.assertEqual(paused["status"], "PAUSED")
            resumed = store.resume(graph["graph_id"])
            self.assertEqual(resumed["status"], "READY")


class MissionQueueV92Tests(unittest.TestCase):
    def test_heartbeat_checkpoint_pause_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            queue = MissionQueue(Path(folder) / "queue.json", lease_seconds=30)
            item = queue.enqueue("Create a supervised persistent mission checkpoint.", priority=88)
            leased = queue.lease_next("worker-test")
            self.assertEqual(leased["queue_id"], item["queue_id"])
            before = float(leased["lease_expires_at"])
            renewed = queue.heartbeat(item["queue_id"], worker_id="worker-test")
            self.assertGreaterEqual(float(renewed["lease_expires_at"]), before)
            checkpoint = queue.checkpoint(
                item["queue_id"], worker_id="worker-test",
                checkpoint={"phase": "TEST"}, graph_id="goal-0123456789abcdef",
            )
            self.assertEqual(checkpoint["checkpoint"]["phase"], "TEST")
            queue.fail(item["queue_id"], worker_id="worker-test", error="retry", retry=True)
            paused = queue.pause(item["queue_id"])
            self.assertEqual(paused["status"], "PAUSED")
            resumed = queue.resume(item["queue_id"])
            self.assertEqual(resumed["status"], "QUEUED")
            self.assertTrue(queue.snapshot()["pause_resume"])
            self.assertFalse(queue.snapshot()["live_execution"])


class MissionWorkerTests(unittest.TestCase):
    def make_worker(self, folder: str, *, verified: bool = True):
        queue = MissionQueue(Path(folder) / "queue.json", lease_seconds=30)
        graphs = GoalTaskGraphStore(Path(folder) / "graphs.json")
        mission_control = FakeMissionControl(verified=verified)
        worker = MissionWorker(
            queue=queue,
            graphs=graphs,
            mission_control=mission_control,
            worker_id="test-worker",
            poll_seconds=.25,
        )
        return worker, queue, graphs, mission_control

    def test_worker_consumes_queue_and_leaves_external_action_waiting(self):
        with tempfile.TemporaryDirectory() as folder:
            worker, queue, graphs, mission_control = self.make_worker(folder)
            item = worker.enqueue("Build and verify a local mission packet without external execution.", title="V9 mission")
            result = worker.run_once()
            self.assertTrue(result["success"])
            self.assertEqual(result["state"], "LOCAL_WORK_COMPLETED")
            self.assertEqual(queue.get(item["queue_id"])["status"], "SUCCEEDED")
            graph = result["graph"]
            by_id = {row["task_id"]: row for row in graph["tasks"]}
            self.assertEqual(by_id["A90"]["status"], "WAITING_APPROVAL")
            self.assertEqual(graph["status"], "LOCAL_WORK_COMPLETED")
            self.assertEqual(len(mission_control.calls), 1)
            self.assertFalse(result["live_execution"])
            self.assertFalse(result["automatic_broker_order"])
            self.assertEqual(result["external_actions"], "APPROVAL_GATED")
            self.assertEqual(graphs.graph(graph["graph_id"])["mission_id"], "mission-test-001")

    def test_unverified_packet_stops_at_quality_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            worker, queue, _graphs, _mission_control = self.make_worker(folder, verified=False)
            item = worker.enqueue("Build a mission packet that deliberately requires human review.")
            result = worker.run_once()
            self.assertFalse(result["success"])
            self.assertEqual(result["state"], "REVIEW_REQUIRED")
            self.assertEqual(queue.get(item["queue_id"])["status"], "FAILED")
            by_id = {row["task_id"]: row for row in result["graph"]["tasks"]}
            self.assertEqual(by_id["T20"]["status"], "BLOCKED")
            self.assertEqual(by_id["A90"]["status"], "WAITING_DEPENDENCY")

    def test_idle_worker_is_bounded_and_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            worker, _queue, _graphs, _mission_control = self.make_worker(folder)
            result = worker.run_once()
            self.assertEqual(result["state"], "IDLE")
            status = worker.status()
            self.assertEqual(status["bounded_concurrency"], 1)
            self.assertEqual(status["external_actions"], "APPROVAL_GATED")
            self.assertFalse(status["live_execution"])
            self.assertFalse(status["automatic_broker_order"])


if __name__ == "__main__":
    unittest.main()
