from __future__ import annotations

from dataclasses import (
    dataclass,
)

import time
import uuid


@dataclass(frozen=True)
class ObservedStepResult:

    step_id: str

    success: bool

    attempts: int

    output: object

    observations: tuple[object, ...]

    error: str | None = None


@dataclass(frozen=True)
class ObservedWorkflowResult:

    workflow_id: str

    success: bool

    steps: tuple[ObservedStepResult, ...]

    needs_replan: bool

    failed_step: str | None = None


class ObservedWorkflowEngine:

    def __init__(
        self,
        executor,
        observer=None,
    ):

        self.executor = executor

        self.observer = (
            observer
            or (
                lambda:
                    {}
            )
        )


    def run(
        self,
        steps,
    ):

        workflow_id = (
            "observed-"
            + uuid.uuid4()
            .hex[:16]
        )


        results = []


        for index, step in enumerate(
            tuple(
                steps
            ),
            1,
        ):

            step = dict(
                step
            )


            step_id = str(
                step.get(
                    "step_id",
                    (
                        "step-"
                        + str(
                            index
                        )
                    ),
                )
            )


            retries = max(
                0,

                min(
                    int(
                        step.get(
                            "retries",
                            0,
                        )
                    ),
                    3,
                ),
            )


            attempts = 0

            success = False

            output = None

            error = None

            observations = []


            while (
                attempts
                <= retries
            ):

                attempts += 1


                try:

                    observations.append(
                        self.observer()
                    )

                except Exception as exc:

                    observations.append(
                        {
                            "observer_error":
                                (
                                    type(
                                        exc
                                    ).__name__
                                    + ": "
                                    + str(
                                        exc
                                    )
                                )
                        }
                    )


                try:

                    output = (
                        self.executor(
                            step
                        )
                    )


                    if isinstance(
                        output,
                        dict,
                    ):

                        success = bool(
                            output.get(
                                "success",
                                False,
                            )
                        )

                        error = (
                            output.get(
                                "error"
                            )
                        )

                    else:

                        success = bool(
                            output
                        )


                except Exception as exc:

                    success = False

                    error = (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    )


                try:

                    observations.append(
                        self.observer()
                    )

                except Exception:
                    pass


                if success:
                    break


                if (
                    attempts
                    <= retries
                ):

                    time.sleep(
                        min(
                            0.25
                            * attempts,
                            0.75,
                        )
                    )


            step_result = (
                ObservedStepResult(
                    step_id=
                        step_id,

                    success=
                        success,

                    attempts=
                        attempts,

                    output=
                        output,

                    observations=
                        tuple(
                            observations
                        ),

                    error=
                        error,
                )
            )


            results.append(
                step_result
            )


            if not success:

                return (
                    ObservedWorkflowResult(
                        workflow_id=
                            workflow_id,

                        success=False,

                        steps=
                            tuple(
                                results
                            ),

                        needs_replan=True,

                        failed_step=
                            step_id,
                    )
                )


        return (
            ObservedWorkflowResult(
                workflow_id=
                    workflow_id,

                success=True,

                steps=
                    tuple(
                        results
                    ),

                needs_replan=False,
            )
        )
