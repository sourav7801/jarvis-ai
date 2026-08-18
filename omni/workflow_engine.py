from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from enum import Enum

from pathlib import Path

import json
import time
import uuid


from omni.action_engine import (
    action_engine,
)


class WorkflowState(
    str,
    Enum,
):

    RUNNING = "running"

    COMPLETED = "completed"

    FAILED = "failed"

    BLOCKED = "blocked"


@dataclass(frozen=True)
class WorkflowStep:

    step_id: str

    tool: str

    arguments: dict

    approved: bool = False

    retries: int = 0

    continue_on_failure: bool = False


@dataclass(frozen=True)
class WorkflowResult:

    workflow_id: str

    state: WorkflowState

    completed_steps: int

    total_steps: int

    results: tuple[dict, ...]

    error: str | None = None


class WorkflowEngine:

    def __init__(
        self,
        *,
        engine=None,
        audit_path=None,
    ):

        self.engine = (
            engine
            or action_engine
        )

        self.audit_path = Path(
            audit_path
            or (
                Path("data")
                / "audit"
                / "workflows.jsonl"
            )
        )


    def _audit(
        self,
        result,
    ):

        self.audit_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        record = {
            **asdict(
                result
            ),

            "state":
                result.state.value,

            "timestamp":
                time.time(),
        }

        with self.audit_path.open(
            "a",
            encoding="utf-8",
        ) as handle:

            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )


    def run(
        self,
        steps,
    ):

        steps = tuple(
            steps
        )

        workflow_id = (
            "workflow-"
            + uuid.uuid4()
            .hex[:16]
        )


        results = []

        completed = 0


        for raw_step in steps:

            if isinstance(
                raw_step,
                WorkflowStep,
            ):

                step = raw_step

            elif isinstance(
                raw_step,
                dict,
            ):

                step = WorkflowStep(
                    step_id=str(
                        raw_step.get(
                            "step_id",
                            (
                                "step-"
                                + str(
                                    len(
                                        results
                                    )
                                    + 1
                                )
                            ),
                        )
                    ),

                    tool=str(
                        raw_step[
                            "tool"
                        ]
                    ),

                    arguments=dict(
                        raw_step.get(
                            "arguments",
                            {},
                        )
                    ),

                    approved=bool(
                        raw_step.get(
                            "approved",
                            False,
                        )
                    ),

                    retries=max(
                        0,

                        min(
                            int(
                                raw_step.get(
                                    "retries",
                                    0,
                                )
                            ),
                            3,
                        ),
                    ),

                    continue_on_failure=
                        bool(
                            raw_step.get(
                                "continue_on_failure",
                                False,
                            )
                        ),
                )

            else:

                raise TypeError(
                    "Workflow steps must be "
                    "WorkflowStep or dict."
                )


            attempts = 0

            action = None


            while (
                attempts
                <= step.retries
            ):

                attempts += 1


                action = (
                    self.engine
                    .execute(
                        step.tool,

                        step.arguments,

                        approved=
                            step.approved,
                    )
                )


                if action.success:
                    break


            result_data = {
                "step_id":
                    step.step_id,

                "tool":
                    step.tool,

                "success":
                    action.success,

                "attempts":
                    attempts,

                "risk":
                    action.risk.value,

                "output":
                    action.output,

                "error":
                    action.error,
            }


            results.append(
                result_data
            )


            if action.success:

                completed += 1

                continue


            if (
                action.error
                == "Explicit approval required."
            ):

                workflow = (
                    WorkflowResult(
                        workflow_id=
                            workflow_id,

                        state=
                            WorkflowState.BLOCKED,

                        completed_steps=
                            completed,

                        total_steps=
                            len(
                                steps
                            ),

                        results=
                            tuple(
                                results
                            ),

                        error=(
                            "Workflow blocked "
                            "awaiting approval."
                        ),
                    )
                )

                self._audit(
                    workflow
                )

                return workflow


            if not (
                step
                .continue_on_failure
            ):

                workflow = (
                    WorkflowResult(
                        workflow_id=
                            workflow_id,

                        state=
                            WorkflowState.FAILED,

                        completed_steps=
                            completed,

                        total_steps=
                            len(
                                steps
                            ),

                        results=
                            tuple(
                                results
                            ),

                        error=(
                            action.error
                            or (
                                "Workflow step "
                                "failed."
                            )
                        ),
                    )
                )

                self._audit(
                    workflow
                )

                return workflow


        workflow = (
            WorkflowResult(
                workflow_id=
                    workflow_id,

                state=
                    WorkflowState.COMPLETED,

                completed_steps=
                    completed,

                total_steps=
                    len(
                        steps
                    ),

                results=
                    tuple(
                        results
                    ),
            )
        )


        self._audit(
            workflow
        )

        return workflow


workflow_engine = (
    WorkflowEngine()
)
