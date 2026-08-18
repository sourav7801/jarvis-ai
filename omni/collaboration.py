from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from omni.brain import DelegationPlan, JarvisBrain, brain


AgentRunner = Callable[
    [str, str, dict[str, Any]],
    Any
]


@dataclass(frozen=True)
class AgentContribution:
    agent: str
    role: str
    success: bool
    output: Any = None
    error: str | None = None


@dataclass(frozen=True)
class CollaborationResult:
    request: str
    intent: str
    lead_agent: str
    contributions: tuple[AgentContribution, ...]
    final_answer: str
    success: bool

    @property
    def participating_agents(self) -> tuple[str, ...]:
        return tuple(
            item.agent
            for item in self.contributions
        )


class CollaborationEngine:
    """
    Bounded multi-agent collaboration.

    Important:
    - Does not bypass governance.
    - Does not execute tools directly.
    - Agent execution is supplied through a governed runner.
    - Supporting agents receive bounded prior context.
    - Lead agent receives specialist findings for synthesis.
    """

    def __init__(
        self,
        brain_instance: JarvisBrain | None = None,
        max_context_items: int = 8,
    ):
        self.brain = brain_instance or brain
        self.max_context_items = max(
            1,
            int(max_context_items),
        )

    def collaborate(
        self,
        request: str,
        runner: AgentRunner,
    ) -> CollaborationResult:

        plan = self.brain.plan(request)

        contributions: list[AgentContribution] = []
        shared_context: list[dict[str, Any]] = []

        # -------------------------------------------------
        # Supporting specialists first
        # -------------------------------------------------

        support_steps = [
            step
            for step in plan.steps
            if step.role == "support"
        ]

        for step in support_steps:

            context = {
                "original_request": request,
                "intent": plan.intent,
                "lead_agent": plan.lead_agent,
                "role": "support",
                "prior_findings": tuple(
                    shared_context[-self.max_context_items:]
                ),
            }

            try:
                output = runner(
                    step.agent,
                    request,
                    context,
                )

                contribution = AgentContribution(
                    agent=step.agent,
                    role="support",
                    success=True,
                    output=output,
                )

                shared_context.append({
                    "agent": step.agent,
                    "output": output,
                })

            except Exception as exc:

                contribution = AgentContribution(
                    agent=step.agent,
                    role="support",
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                )

            contributions.append(contribution)

        # -------------------------------------------------
        # Lead synthesizes specialist findings
        # -------------------------------------------------

        lead_context = {
            "original_request": request,
            "intent": plan.intent,
            "role": "lead",
            "specialist_findings": tuple(
                shared_context[-self.max_context_items:]
            ),
            "instruction": (
                "Synthesize the specialist findings into one "
                "coherent answer. Do not invent findings that "
                "were not supplied."
            ),
        }

        try:
            lead_output = runner(
                plan.lead_agent,
                request,
                lead_context,
            )

            contributions.append(
                AgentContribution(
                    agent=plan.lead_agent,
                    role="lead",
                    success=True,
                    output=lead_output,
                )
            )

            final_answer = self._normalize_answer(
                lead_output
            )

            success = True

        except Exception as exc:

            contributions.append(
                AgentContribution(
                    agent=plan.lead_agent,
                    role="lead",
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

            final_answer = (
                "The lead agent could not synthesize "
                "the collaboration result."
            )

            success = False

        return CollaborationResult(
            request=request,
            intent=plan.intent,
            lead_agent=plan.lead_agent,
            contributions=tuple(contributions),
            final_answer=final_answer,
            success=success,
        )

    @staticmethod
    def _normalize_answer(output: Any) -> str:

        if isinstance(output, str):
            return output

        if isinstance(output, dict):

            for key in (
                "answer",
                "response",
                "result",
                "message",
                "output",
            ):
                value = output.get(key)

                if isinstance(value, str):
                    return value

            return str(output)

        return str(output)


collaboration_engine = CollaborationEngine()
