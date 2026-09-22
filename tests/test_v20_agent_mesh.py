from __future__ import annotations

from omni.agent_registry import AgentRegistry, AgentResponse, AgentStatus
from workstation.v20_agent_mesh import ROLE_TO_AGENT, V20AgentMesh


class FakeRegistry(AgentRegistry):
    def __init__(self):
        pass

    def execute(self, request):
        return AgentResponse(
            status=AgentStatus.SUCCEEDED,
            agent=request.agent,
            message=f"completed:{request.text}",
            correlation_id=request.correlation_id,
            data={"request": request.text},
        )


def test_mesh_exposes_parallel_lanes():
    mesh = V20AgentMesh(max_workers=4, registry=FakeRegistry())
    try:
        status = mesh.status()
        assert status["service"] == "JARVIS_V20_MULTI_AGENT_MESH"
        assert status["max_workers"] == 4
        assert status["paper_only"] is True
        assert {"intraday", "swing", "investment", "options", "risk"} <= set(status["lanes"])
        assert ROLE_TO_AGENT["options"] == "trading"
    finally:
        mesh.shutdown()


def test_mesh_dispatches_without_blocking_submission():
    mesh = V20AgentMesh(max_workers=3, registry=FakeRegistry())
    try:
        task = mesh.submit("research", "find market news", {"workspace": "OPTIONS"})
        assert task["status"] == "RUNNING"
        task_id = task["task_id"]
        for _ in range(100):
            result = mesh.task_status(task_id)
            if result.get("status") == "SUCCEEDED":
                break
        assert result["status"] == "SUCCEEDED"
        assert result["result"]["agent"] == "research"
        assert result["paper_only"] is True
    finally:
        mesh.shutdown()
