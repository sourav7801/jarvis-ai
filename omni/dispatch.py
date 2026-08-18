"""Bridge durable orchestrator steps to canonical agent/tool boundaries."""

from __future__ import annotations

from collections.abc import Callable

from .agent_registry import AgentRegistry, AgentRequest
from .contracts import Step, StepResult


ToolExecutor = Callable[[dict], str]


class StepDispatcher:
    def __init__(self, agents: AgentRegistry, tool_executor: ToolExecutor):
        self.agents = agents
        self.tool_executor = tool_executor

    def __call__(self, step: Step) -> StepResult:
        if step.action.startswith("agent:"):
            agent_name = step.action.split(":", 1)[1].strip()
            text = str(step.arguments.get("text", ""))
            capabilities = frozenset(step.arguments.get("capabilities", ()))
            response = self.agents.execute(
                AgentRequest(agent_name, text, capabilities)
            )
            return StepResult(
                response.success,
                output=response.message,
                error=None if response.success else response.error_type or response.status.value,
            )

        if step.action.startswith("tool:"):
            tool_name = step.action.split(":", 1)[1].strip()
            if not tool_name:
                return StepResult(False, error="Missing tool name.")
            decision = {
                "action": "tool",
                "tool": tool_name,
                "arguments": dict(step.arguments),
            }
            try:
                output = self.tool_executor(decision)
                if isinstance(output, dict):
                    success = bool(output.get("success", False))
                    return StepResult(
                        success,
                        output=output.get("message", output),
                        error=None if success else str(output.get("message", "Tool failed.")),
                    )
                return StepResult(True, output=output)
            except Exception as error:
                return StepResult(
                    False, error=f"{type(error).__name__}: {error}"
                )

        return StepResult(False, error="Unsupported step action namespace.")
