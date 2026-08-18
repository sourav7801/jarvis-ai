from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from omni.brain import (
    JarvisBrain,
)

from omni.meta_brain import (
    meta_brain as brain,
)

from omni.collaboration_runtime import (
    build_runtime,
)

from omni.memory_context import (
    remember_scoped,
)

from omni.memory_scope import (
    MemoryScope,
)

from omni.mission import (
    MissionPlan,
    MissionResult,
    MissionStatus,
    MissionStore,
    MissionTask,
    TaskStatus,
    new_mission_id,
)


AgentRunner = Callable[
    [
        str,
        str,
        dict[str, Any],
    ],
    Any,
]


MAX_CONTEXT_CHARS = 10000


class MissionPlanningError(
    RuntimeError
):
    pass


class AutonomousGoalEngine:

    def __init__(
        self,
        brain_instance: JarvisBrain = brain,
        *,
        max_retries: int = 2,
        store: MissionStore | None = None,
    ):

        self.brain = (
            brain_instance
        )

        self.max_retries = max(
            0,
            min(
                int(max_retries),
                5,
            ),
        )

        self.store = (
            store
            or MissionStore(
                Path("data")
                / "missions"
            )
        )


    # ========================================================
    # BRAIN COMPATIBILITY
    # ========================================================

    def agent_names(
        self,
    ) -> tuple[str, ...]:
        """
        JarvisBrain currently exposes agent_names as a method.

        This helper also supports a future property form.
        """

        value = getattr(
            self.brain,
            "agent_names",
            (),
        )

        if callable(
            value
        ):

            value = value()

        if value is None:

            return ()

        return tuple(
            value
        )


    # ========================================================
    # PLAN
    # ========================================================

    def plan(
        self,
        goal: str,
    ):

        goal = str(
            goal or ""
        ).strip()

        if not goal:

            raise MissionPlanningError(
                "Mission goal cannot be empty."
            )

        delegation = (
            self.brain.plan(
                goal
            )
        )

        mission_id = (
            new_mission_id()
        )

        supports = []

        for index, step in enumerate(
            delegation.steps,
            1,
        ):

            if (
                step.agent
                == delegation.lead_agent
            ):
                continue

            supports.append(
                MissionTask(
                    task_id=(
                        f"support-"
                        f"{index}-"
                        f"{step.agent}"
                    ),

                    agent=step.agent,

                    role="support",

                    objective=(
                        "Analyze the mission from "
                        f"the {step.agent} specialist "
                        "perspective. Produce concrete "
                        "findings, risks, assumptions, "
                        "and recommendations."
                    ),

                    capabilities=tuple(
                        step.capabilities
                    ),
                )
            )

        dependency_ids = tuple(
            task.task_id
            for task in supports
        )

        lead = MissionTask(
            task_id=(
                "lead-"
                + delegation.lead_agent
            ),

            agent=(
                delegation.lead_agent
            ),

            role="lead",

            objective=(
                "Synthesize all available specialist "
                "findings into the best solution for "
                "the mission goal. Resolve conflicts, "
                "identify uncertainty, and do not "
                "invent unsupported facts."
            ),

            dependencies=(
                dependency_ids
            ),
        )

        tasks = list(
            supports
        )

        tasks.append(
            lead
        )

        names = set(
            self.agent_names()
        )

        if (
            delegation.lead_agent
            != "quality"
            and "quality"
            in names
        ):

            tasks.append(
                MissionTask(
                    task_id=(
                        "verify-quality"
                    ),

                    agent="quality",

                    role="verifier",

                    objective=(
                        "Independently verify whether "
                        "the proposed mission result "
                        "addresses the goal. Identify "
                        "missing requirements, unsupported "
                        "claims, contradictions, or risks."
                    ),

                    dependencies=(
                        lead.task_id,
                    ),
                )
            )

        return MissionPlan(
            mission_id=mission_id,

            goal=goal,

            intent=(
                delegation.intent
            ),

            lead_agent=(
                delegation.lead_agent
            ),

            tasks=tuple(
                tasks
            ),

            confidence=(
                delegation.confidence
            ),

            requires_approval=(
                delegation.requires_approval
            ),
        )


    # ========================================================
    # CONTEXT
    # ========================================================

    @staticmethod
    def _serialize(
        value,
    ):

        try:

            text = json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )

        except Exception:

            text = str(
                value
            )

        return text[
            :MAX_CONTEXT_CHARS
        ]


    def _prompt(
        self,
        plan,
        task,
        outputs,
    ):

        dependencies = {
            dep: outputs.get(
                dep
            )
            for dep
            in task.dependencies
        }

        context = {
            "mission_id":
                plan.mission_id,

            "goal":
                plan.goal,

            "intent":
                plan.intent,

            "task_id":
                task.task_id,

            "role":
                task.role,

            "dependency_outputs":
                dependencies,
        }

        return (
            f"MISSION GOAL:\n"
            f"{plan.goal}\n\n"
            f"TASK:\n"
            f"{task.objective}\n\n"
            "[JARVIS MISSION CONTEXT]\n"
            f"{self._serialize(context)}\n"
            "[END JARVIS MISSION CONTEXT]"
        )


    # ========================================================
    # OUTPUT
    # ========================================================

    @staticmethod
    def _normalize(
        output,
    ):

        if output is None:

            return ""

        if isinstance(
            output,
            str,
        ):

            return output.strip()

        if isinstance(
            output,
            dict,
        ):

            for key in (
                "answer",
                "result",
                "output",
                "response",
                "message",
                "data",
            ):

                if key in output:

                    value = output[
                        key
                    ]

                    if isinstance(
                        value,
                        str,
                    ):

                        return (
                            value.strip()
                        )

            return json.dumps(
                output,
                ensure_ascii=False,
                default=str,
            )

        return str(
            output
        ).strip()


    # ========================================================
    # TASK EXECUTION
    # ========================================================

    def _run_task(
        self,
        plan,
        task,
        runner,
        outputs,
    ):

        prompt = self._prompt(
            plan,
            task,
            outputs,
        )

        task.status = (
            TaskStatus.RUNNING
        )

        last_error = None

        for _ in range(
            self.max_retries
            + 1
        ):

            task.attempts += 1

            try:

                output = runner(
                    task.agent,
                    prompt,
                    {
                        "mission_id":
                            plan.mission_id,

                        "task_id":
                            task.task_id,

                        "role":
                            task.role,
                    },
                )

                normalized = (
                    self._normalize(
                        output
                    )
                )

                if not normalized:

                    raise RuntimeError(
                        "Agent returned empty output."
                    )

                task.output = (
                    normalized
                )

                task.status = (
                    TaskStatus.COMPLETED
                )

                outputs[
                    task.task_id
                ] = normalized

                return True

            except Exception as exc:

                last_error = (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

        task.error = (
            last_error
        )

        task.status = (
            TaskStatus.FAILED
        )

        return False


    # ========================================================
    # EXECUTION
    # ========================================================

    def execute(
        self,
        goal: str,
        *,
        runner=None,
        project_id=None,
        approved=False,
    ):

        plan = self.plan(
            goal
        )

        if (
            plan.requires_approval
            and not approved
        ):

            return MissionResult(
                mission_id=(
                    plan.mission_id
                ),

                goal=plan.goal,

                status=(
                    MissionStatus.BLOCKED
                ),

                plan=plan,

                success=False,

                verified=False,

                errors=(
                    "Mission requires approval.",
                ),
            )

        if runner is None:

            runtime = (
                build_runtime()
            )

            runner = (
                runtime.runner
            )

        outputs = {}
        errors = []

        recovery_count = 0


        # ----------------------------------------------------
        # SUPPORT
        # ----------------------------------------------------

        for task in plan.tasks:

            if task.role != "support":
                continue

            ok = self._run_task(
                plan,
                task,
                runner,
                outputs,
            )

            if not ok:

                errors.append(
                    f"{task.agent}: "
                    f"{task.error}"
                )

                outputs[
                    task.task_id
                ] = {
                    "failed": True,
                    "error":
                        task.error,
                }


        # ----------------------------------------------------
        # LEAD
        # ----------------------------------------------------

        lead = next(
            task
            for task in plan.tasks
            if task.role == "lead"
        )

        lead_ok = self._run_task(
            plan,
            lead,
            runner,
            outputs,
        )

        final_answer = ""

        if lead_ok:

            final_answer = str(
                lead.output
            )

        else:

            errors.append(
                f"{lead.agent}: "
                f"{lead.error}"
            )

            recovery_count += 1


            # ------------------------------------------------
            # GOVERNED RECOVERY
            # ------------------------------------------------

            names = set(
                self.agent_names()
            )

            if "operator" not in names:

                return self._failure(
                    plan,
                    errors,
                    recovery_count,
                )

            recovery = MissionTask(
                task_id=(
                    "recovery-operator"
                ),

                agent="operator",

                role="recovery",

                objective=(
                    "The mission lead failed. "
                    "Review the available specialist "
                    "results and produce the safest "
                    "useful result for the original goal."
                ),

                dependencies=tuple(
                    outputs.keys()
                ),
            )

            recovery_ok = (
                self._run_task(
                    plan,
                    recovery,
                    runner,
                    outputs,
                )
            )

            if not recovery_ok:

                errors.append(
                    "operator recovery: "
                    + str(
                        recovery.error
                    )
                )

                return self._failure(
                    plan,
                    errors,
                    recovery_count,
                )

            final_answer = str(
                recovery.output
            )


        # ----------------------------------------------------
        # VERIFICATION
        # ----------------------------------------------------

        verifier = next(
            (
                task
                for task in plan.tasks
                if task.role
                == "verifier"
            ),
            None,
        )

        verified = True

        if verifier is not None:

            outputs[
                lead.task_id
            ] = final_answer

            verified = (
                self._run_task(
                    plan,
                    verifier,
                    runner,
                    outputs,
                )
            )

            if not verified:

                errors.append(
                    "quality verification: "
                    + str(
                        verifier.error
                    )
                )


        result = MissionResult(
            mission_id=(
                plan.mission_id
            ),

            goal=plan.goal,

            status=(
                MissionStatus.COMPLETED
            ),

            plan=plan,

            final_answer=(
                final_answer
            ),

            success=bool(
                final_answer
            ),

            verified=verified,

            recovery_count=(
                recovery_count
            ),

            errors=tuple(
                errors
            ),
        )

        self._save(
            result
        )

        self._remember(
            result,
            project_id,
        )

        try:
            from omni.reflection_engine import (
                record_mission_reflection,
            )

            record_mission_reflection(
                result,
                project_id=project_id,
            )

        except Exception:
            pass

        return result


    # ========================================================
    # FAILURE
    # ========================================================

    def _failure(
        self,
        plan,
        errors,
        recovery_count,
    ):

        result = MissionResult(
            mission_id=(
                plan.mission_id
            ),

            goal=plan.goal,

            status=(
                MissionStatus.FAILED
            ),

            plan=plan,

            success=False,

            verified=False,

            recovery_count=(
                recovery_count
            ),

            errors=tuple(
                errors
            ),
        )

        self._save(
            result
        )

        try:
            from omni.reflection_engine import (
                record_mission_reflection,
            )

            record_mission_reflection(
                result
            )

        except Exception:
            pass

        return result


    # ========================================================
    # DURABILITY
    # ========================================================

    def _save(
        self,
        result,
    ):

        try:

            self.store.save(
                result
            )

        except Exception:

            pass


    # ========================================================
    # EXPERIENCE MEMORY
    # ========================================================

    @staticmethod
    def _remember(
        result,
        project_id,
    ):

        if not result.success:
            return

        try:

            remember_scoped(
                (
                    "JARVIS autonomous mission\n"
                    f"Goal: {result.goal}\n"
                    f"Result: "
                    f"{result.final_answer[:6000]}"
                ),

                MemoryScope.AGENT_FINDING,

                source="jarvis",

                project_id=(
                    project_id
                ),

                tags=(
                    "autonomous-mission",
                    (
                        "mission:"
                        + result.mission_id
                    ),
                ),

                metadata={
                    "mission_id":
                        result.mission_id,

                    "verified":
                        result.verified,

                    "recovery_count":
                        result.recovery_count,
                },
            )

        except Exception:

            pass


autonomy_engine = (
    AutonomousGoalEngine()
)
