from __future__ import annotations

from dataclasses import (
    dataclass,
)

import time
import uuid


from omni.action_replanner import (
    action_replanner,
)

from omni.approval_batch import (
    approval_batches,
)

from omni.browser_observation_loop import (
    browser_observation_loop,
)

from omni.desktop_state import (
    desktop_state,
)

from omni.document_intelligence import (
    document_intelligence,
)

from omni.git_actions import (
    git_actions,
)

from omni.github_read import (
    github_read,
)

from omni.operator_dsl import (
    is_interactive,
    parse_json,
    planner_prompt,
    validate_plan,
)

from omni.operator_memory import (
    operator_memory,
)

from omni.semantic_ui import (
    semantic_ui,
)

from omni.target_fusion import (
    target_fusion,
)

from omni.vision_runtime import (
    vision_runtime,
)


@dataclass(frozen=True)
class OperatorV2Result:

    operator_id: str

    goal: str

    success: bool

    completed_steps: int

    total_steps: int

    results: tuple[
        dict,
        ...
    ]

    failed_step: str | None = None

    needs_replan: bool = False

    replan: object = None


class ComputerOperatorV2:

    def planner_prompt(
        self,
        goal,
        observations=None,
    ):

        return planner_prompt(
            goal,
            observations,
        )


    def validate_proposal(
        self,
        goal,
        proposal_text,
    ):

        return parse_json(
            goal,
            proposal_text,
            source=
                "brain-or-model-proposal",
        )


    def prepare(
        self,
        plan,
    ):

        validate_plan(
            plan
        )


        bindings = []


        for step in plan.steps:

            if not is_interactive(
                step.action
            ):

                continue


            payload = step.payload


            operation = {
                "browser.observe":
                    "observe",

                "browser.observe_click":
                    "click",

                "browser.observe_fill":
                    "fill",
            }[
                step.action
            ]


            binding = (
                browser_observation_loop
                .binding(
                    operation,

                    payload[
                        "url"
                    ],

                    profile=
                        payload.get(
                            "profile",
                            "default",
                        ),

                    selector=
                        payload.get(
                            "selector"
                        ),

                    value=
                        payload.get(
                            "value"
                        ),
                )
            )


            bindings.append(
                {
                    "step_id":
                        step.step_id,

                    **binding,
                }
            )


        batch = (
            approval_batches
            .create(
                plan.goal,
                bindings,
            )

            if bindings

            else None
        )


        return {
            "success":
                True,

            "plan":
                plan,

            "approval_batch":
                batch,
        }


    def prepare_proposal(
        self,
        goal,
        proposal_text,
    ):

        return self.prepare(
            self.validate_proposal(
                goal,
                proposal_text,
            )
        )


    def _execute_step(
        self,
        step,
        token,
    ):

        payload = step.payload


        if (
            step.action
            == "desktop.observe"
        ):

            return {
                "success":
                    True,

                "snapshot":
                    desktop_state
                    .snapshot(
                        window_title=
                            payload.get(
                                "window_title"
                            ),

                        include_controls=
                            bool(
                                payload.get(
                                    "include_controls",
                                    False,
                                )
                            ),
                    ),
            }


        if (
            step.action
            == "desktop.controls"
        ):

            return {
                "success":
                    True,

                "controls":
                    semantic_ui
                    .controls(
                        payload[
                            "window_title"
                        ],

                        text=
                            payload.get(
                                "text"
                            ),

                        control_type=
                            payload.get(
                                "control_type"
                            ),

                        automation_id=
                            payload.get(
                                "automation_id"
                            ),
                    ),
            }


        if (
            step.action
            == "browser.observe"
        ):

            return (
                browser_observation_loop
                .observe(
                    payload[
                        "url"
                    ],

                    profile=
                        payload.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        token,
                )
            )


        if (
            step.action
            == "browser.observe_click"
        ):

            return (
                browser_observation_loop
                .click(
                    payload[
                        "url"
                    ],

                    payload[
                        "selector"
                    ],

                    profile=
                        payload.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        token,
                )
            )


        if (
            step.action
            == "browser.observe_fill"
        ):

            return (
                browser_observation_loop
                .fill(
                    payload[
                        "url"
                    ],

                    payload[
                        "selector"
                    ],

                    payload[
                        "value"
                    ],

                    profile=
                        payload.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        token,

                    sensitive=
                        bool(
                            payload.get(
                                "sensitive",
                                False,
                            )
                        ),
                )
            )


        if (
            step.action
            == "vision.analyze"
        ):

            return (
                vision_runtime
                .analyze(
                    payload[
                        "path"
                    ]
                )
            )


        if (
            step.action
            == "document.read"
        ):

            return {
                "success":
                    True,

                "document":
                    document_intelligence
                    .read(
                        payload[
                            "path"
                        ]
                    ),
            }


        if (
            step.action
            == "document.search"
        ):

            return {
                "success":
                    True,

                "search":
                    document_intelligence
                    .search(
                        payload[
                            "path"
                        ],

                        payload[
                            "query"
                        ],
                    ),
            }


        if (
            step.action
            == "git.status"
        ):

            result = git_actions.status(
                payload[
                    "repo"
                ]
            )


            return {
                "success":
                    bool(
                        result.get(
                            "success",
                            False,
                        )
                    ),

                "git":
                    result,
            }


        if (
            step.action
            == "git.diff"
        ):

            result = git_actions.diff(
                payload[
                    "repo"
                ]
            )


            return {
                "success":
                    bool(
                        result.get(
                            "success",
                            False,
                        )
                    ),

                "git":
                    result,
            }


        if (
            step.action
            == "git.repository_state"
        ):

            return {
                "success":
                    True,

                "repository":
                    github_read
                    .repository_state(
                        payload[
                            "repo"
                        ]
                    ),
            }


        return {
            "success":
                False,

            "error":
                "No executor for DSL action.",
        }


    def execute(
        self,
        plan,
        *,
        approval_batch_id=None,
        project_id=None,
    ):

        validate_plan(
            plan
        )


        operator_id = (
            "operator-v2-"
            + uuid.uuid4()
            .hex[:16]
        )


        results = []

        completed = 0


        for step in plan.steps:

            token = None


            if is_interactive(
                step.action
            ):

                token = (
                    approval_batches
                    .token_for_step(
                        approval_batch_id,
                        step.step_id,
                    )

                    if approval_batch_id

                    else None
                )


                if not token:

                    return (
                        OperatorV2Result(
                            operator_id=
                                operator_id,

                            goal=
                                plan.goal,

                            success=False,

                            completed_steps=
                                completed,

                            total_steps=
                                len(
                                    plan.steps
                                ),

                            results=
                                tuple(
                                    results
                                ),

                            failed_step=
                                step.step_id,

                            needs_replan=
                                False,

                            replan={
                                "approval_required":
                                    True
                            },
                        )
                    )


            attempts = 0

            success = False

            output = None

            error = None


            while (
                attempts
                <= step.retries
            ):

                attempts += 1


                try:

                    output = (
                        self._execute_step(
                            step,
                            token,
                        )
                    )


                    success = (
                        bool(
                            output.get(
                                "success",
                                False,
                            )
                        )

                        if isinstance(
                            output,
                            dict,
                        )

                        else bool(
                            output
                        )
                    )


                    error = (
                        output.get(
                            "error"
                        )

                        if isinstance(
                            output,
                            dict,
                        )

                        else None
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


                if success:

                    break


                if is_interactive(
                    step.action
                ):

                    break


                if (
                    attempts
                    <= step.retries
                ):

                    time.sleep(
                        min(
                            0.25
                            * attempts,
                            0.5,
                        )
                    )


            results.append(
                {
                    "step_id":
                        step.step_id,

                    "action":
                        step.action,

                    "success":
                        success,

                    "attempts":
                        attempts,

                    "output":
                        output,

                    "error":
                        error,
                }
            )


            if success:

                completed += 1

                continue


            failure = type(
                "OperatorFailure",
                (),
                {
                    "success":
                        False,

                    "failed_step":
                        step.step_id,

                    "steps": (
                        type(
                            "FailedStep",
                            (),
                            {
                                "success":
                                    False,

                                "step_id":
                                    step.step_id,

                                "error":
                                    error,

                                "attempts":
                                    attempts,
                            },
                        )(),
                    ),
                },
            )()


            try:

                replan = (
                    action_replanner
                    .propose(
                        plan.goal,
                        failure,
                    )
                )

            except Exception as exc:

                replan = {
                    "needs_replan":
                        True,

                    "auto_execute":
                        False,

                    "error":
                        (
                            type(
                                exc
                            ).__name__
                            + ": "
                            + str(
                                exc
                            )
                        ),
                }


            operator_memory.record(
                goal=
                    plan.goal,

                success=False,

                steps=
                    len(
                        plan.steps
                    ),

                failed_step=
                    step.step_id,

                lesson=
                    error,

                metadata={
                    "operator_id":
                        operator_id,

                    "dsl_source":
                        plan.source,
                },

                project_id=
                    project_id,
            )


            return OperatorV2Result(
                operator_id=
                    operator_id,

                goal=
                    plan.goal,

                success=False,

                completed_steps=
                    completed,

                total_steps=
                    len(
                        plan.steps
                    ),

                results=
                    tuple(
                        results
                    ),

                failed_step=
                    step.step_id,

                needs_replan=
                    True,

                replan=
                    replan,
            )


        operator_memory.record(
            goal=
                plan.goal,

            success=True,

            steps=
                len(
                    plan.steps
                ),

            metadata={
                "operator_id":
                    operator_id,

                "dsl_source":
                    plan.source,
            },

            project_id=
                project_id,
        )


        return OperatorV2Result(
            operator_id=
                operator_id,

            goal=
                plan.goal,

            success=True,

            completed_steps=
                completed,

            total_steps=
                len(
                    plan.steps
                ),

            results=
                tuple(
                    results
                ),

            needs_replan=False,
        )


    def validate_replan(
        self,
        goal,
        proposal_text,
    ):

        plan = self.validate_proposal(
            goal,
            proposal_text,
        )


        return {
            "valid":
                True,

            "plan":
                plan,

            "auto_execute":
                False,

            "requires_new_approval":
                any(
                    is_interactive(
                        step.action
                    )

                    for step
                    in plan.steps
                ),
        }


    def resolve_target(
        self,
        target,
        *,
        dom=(),
        uia=(),
        screenshot=None,
    ):

        vision = ()


        if screenshot:

            result = (
                vision_runtime
                .analyze(
                    screenshot
                )
            )


            if result.get(
                "success",
                False,
            ):

                vision = tuple(
                    result.get(
                        "analysis",
                        {}
                    )
                    .get(
                        "elements",
                        ()
                    )
                    or ()
                )


        return target_fusion.resolve(
            target,

            dom=dom,

            uia=uia,

            vision=vision,
        )


computer_operator_v2 = (
    ComputerOperatorV2()
)
