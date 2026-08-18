from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

import hashlib
import re
from types import SimpleNamespace
import time
import uuid


from omni.action_replanner import (
    action_replanner,
)

from omni.approval_batch import (
    approval_batches,
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

from omni.operator_schema import (
    OperatorPlan,
    OperatorStep,
    is_interactive,
    validate_plan,
)

from omni.persistent_browser import (
    persistent_browser,
)

from omni.safe_file_handoff import (
    safe_file_handoff,
)

from omni.screen_perception import (
    screen_perception,
)

from omni.semantic_ui import (
    semantic_ui,
)


@dataclass(frozen=True)
class OperatorExecutionResult:

    operator_id: str

    goal: str

    success: bool

    completed_steps: int

    total_steps: int

    results: tuple[dict, ...]

    approval_batch_id: str | None = None

    failed_step: str | None = None

    needs_replan: bool = False

    replan: object = None


class GoalCompiler:

    URL_RE = re.compile(
        r"https?://[^\s<>'\"]+",
        re.IGNORECASE,
    )


    def compile(
        self,
        goal,
        *,
        hints=None,
    ):

        goal = str(
            goal
        ).strip()


        if not goal:

            raise ValueError(
                "goal cannot be empty"
            )


        hints = dict(
            hints
            or {}
        )


        if hints.get(
            "steps"
        ):

            steps = []


            for index, item in enumerate(
                hints[
                    "steps"
                ],
                1,
            ):

                item = dict(
                    item
                )


                steps.append(
                    OperatorStep(
                        step_id=str(
                            item.get(
                                "step_id",
                                (
                                    "step-"
                                    + str(
                                        index
                                    )
                                ),
                            )
                        ),

                        action=str(
                            item[
                                "action"
                            ]
                        ),

                        payload=dict(
                            item.get(
                                "payload",
                                {},
                            )
                        ),

                        retries=int(
                            item.get(
                                "retries",
                                0,
                            )
                        ),

                        observe=bool(
                            item.get(
                                "observe",
                                True,
                            )
                        ),
                    )
                )


            plan = OperatorPlan(
                goal=goal,

                steps=tuple(
                    steps
                ),

                source=
                    "structured-hints",
            )


            validate_plan(
                plan
            )


            return plan


        lower = goal.lower()

        urls = self.URL_RE.findall(
            goal
        )


        steps = []


        def add(
            action,
            payload=None,
            retries=0,
        ):

            steps.append(
                OperatorStep(
                    step_id=(
                        "step-"
                        + str(
                            len(
                                steps
                            )
                            + 1
                        )
                    ),

                    action=
                        action,

                    payload=dict(
                        payload
                        or {}
                    ),

                    retries=
                        retries,

                    observe=
                        True,
                )
            )


        if (
            "window"
            in lower
            or "running app"
            in lower
            or "open app"
            in lower
        ):

            add(
                "ui.windows"
            )


        if (
            hints.get(
                "window_title"
            )

            and (
                hints.get(
                    "control_text"
                )
                or hints.get(
                    "automation_id"
                )
            )
        ):

            if (
                "click"
                in lower
            ):

                add(
                    "ui.click",

                    {
                        "window_title":
                            hints[
                                "window_title"
                            ],

                        "text":
                            hints.get(
                                "control_text"
                            ),

                        "control_type":
                            hints.get(
                                "control_type"
                            ),

                        "automation_id":
                            hints.get(
                                "automation_id"
                            ),
                    },
                )


            elif (
                "type"
                in lower
                or "enter"
                in lower
                or "fill"
                in lower
            ):

                if (
                    "value"
                    not in hints
                ):

                    raise ValueError(
                        "UI text goal requires "
                        "hints['value']."
                    )


                add(
                    "ui.set_text",

                    {
                        "window_title":
                            hints[
                                "window_title"
                            ],

                        "text":
                            hints.get(
                                "control_text"
                            ),

                        "automation_id":
                            hints.get(
                                "automation_id"
                            ),

                        "value":
                            hints[
                                "value"
                            ],

                        "sensitive":
                            bool(
                                hints.get(
                                    "sensitive",
                                    False,
                                )
                            ),
                    },
                )


        if urls:

            url = urls[0]


            if "download" in lower:

                add(
                    "file.download",

                    {
                        "url":
                            url,

                        "filename":
                            hints.get(
                                "filename"
                            ),
                    },
                )


            elif (
                hints.get(
                    "selector"
                )

                and "click"
                in lower
            ):

                add(
                    "browser.click",

                    {
                        "url":
                            url,

                        "selector":
                            hints[
                                "selector"
                            ],

                        "profile":
                            hints.get(
                                "profile",
                                "default",
                            ),
                    },
                )


            elif (
                hints.get(
                    "selector"
                )

                and (
                    "fill"
                    in lower
                    or "type"
                    in lower
                )
            ):

                if (
                    "value"
                    not in hints
                ):

                    raise ValueError(
                        "Browser fill requires "
                        "hints['value']."
                    )


                add(
                    "browser.fill",

                    {
                        "url":
                            url,

                        "selector":
                            hints[
                                "selector"
                            ],

                        "value":
                            hints[
                                "value"
                            ],

                        "profile":
                            hints.get(
                                "profile",
                                "default",
                            ),

                        "sensitive":
                            bool(
                                hints.get(
                                    "sensitive",
                                    False,
                                )
                            ),
                    },
                )


            else:

                add(
                    "browser.inspect",

                    {
                        "url":
                            url,

                        "profile":
                            hints.get(
                                "profile",
                                "default",
                            ),
                    },

                    retries=1,
                )


        if (
            hints.get(
                "document_path"
            )
        ):

            if (
                hints.get(
                    "query"
                )
            ):

                add(
                    "document.search",

                    {
                        "path":
                            hints[
                                "document_path"
                            ],

                        "query":
                            hints[
                                "query"
                            ],
                    },
                )

            else:

                add(
                    "document.read",

                    {
                        "path":
                            hints[
                                "document_path"
                            ],
                    },
                )


        if (
            "git status"
            in lower
        ):

            add(
                "git.status",

                {
                    "repo":
                        hints.get(
                            "repo",
                            r"C:\Jarvis",
                        )
                },
            )


        elif (
            "git diff"
            in lower
        ):

            add(
                "git.diff",

                {
                    "repo":
                        hints.get(
                            "repo",
                            r"C:\Jarvis",
                        )
                },
            )


        elif (
            "repository state"
            in lower
            or "repo state"
            in lower
        ):

            add(
                "git.repository_state",

                {
                    "repo":
                        hints.get(
                            "repo",
                            r"C:\Jarvis",
                        )
                },
            )


        if not steps:

            return OperatorPlan(
                goal=goal,

                steps=(),

                source=
                    "needs-planning",

                executable=False,

                reason=(
                    "Goal could not be safely "
                    "compiled into the bounded "
                    "operator action grammar."
                ),
            )


        plan = OperatorPlan(
            goal=goal,

            steps=tuple(
                steps
            ),

            source=
                "deterministic",
        )


        validate_plan(
            plan
        )


        return plan


class ComputerOperator:

    def __init__(
        self,
        compiler=None,
    ):

        self.compiler = (
            compiler
            or GoalCompiler()
        )


    @staticmethod
    def _browser_binding(
        step,
    ):

        payload = step.payload


        if (
            step.action
            == "browser.inspect"
        ):

            body = {
                "url":
                    str(
                        payload[
                            "url"
                        ]
                    ),

                "profile":
                    str(
                        payload.get(
                            "profile",
                            "default",
                        )
                    ),

                "operation":
                    "inspect",
            }


            return {
                "step_id":
                    step.step_id,

                "action":
                    "persistent_browser.inspect",

                "payload":
                    body,

                "display": {
                    "url":
                        body[
                            "url"
                        ],

                    "profile":
                        body[
                            "profile"
                        ],
                },

                "risk":
                    "browser-session",
            }


        if (
            step.action
            == "browser.click"
        ):

            body = {
                "url":
                    str(
                        payload[
                            "url"
                        ]
                    ),

                "selector":
                    str(
                        payload[
                            "selector"
                        ]
                    ),

                "profile":
                    str(
                        payload.get(
                            "profile",
                            "default",
                        )
                    ),

                "operation":
                    "click",
            }


            return {
                "step_id":
                    step.step_id,

                "action":
                    "persistent_browser.click",

                "payload":
                    body,

                "display":
                    body,

                "risk":
                    "browser-session",
            }


        if (
            step.action
            == "browser.fill"
        ):

            value = str(
                payload[
                    "value"
                ]
            )


            body = {
                "url":
                    str(
                        payload[
                            "url"
                        ]
                    ),

                "selector":
                    str(
                        payload[
                            "selector"
                        ]
                    ),

                "profile":
                    str(
                        payload.get(
                            "profile",
                            "default",
                        )
                    ),

                "value_hash":
                    hashlib.sha256(
                        value.encode(
                            "utf-8"
                        )
                    ).hexdigest(),

                "length":
                    len(
                        value
                    ),

                "operation":
                    "fill",
            }


            return {
                "step_id":
                    step.step_id,

                "action":
                    "persistent_browser.fill",

                "payload":
                    body,

                "display": {
                    "url":
                        body[
                            "url"
                        ],

                    "selector":
                        body[
                            "selector"
                        ],

                    "profile":
                        body[
                            "profile"
                        ],

                    "preview":
                        value[:80],
                },

                "risk":
                    "browser-session",
            }


        return None


    @staticmethod
    def binding_for_step(
        step,
    ):

        if (
            step.action.startswith(
                "browser."
            )
        ):

            return (
                ComputerOperator
                ._browser_binding(
                    step
                )
            )


        if (
            step.action
            == "ui.click"
        ):

            payload = {
                "window_title":
                    str(
                        step.payload[
                            "window_title"
                        ]
                    ),

                "text":
                    step.payload.get(
                        "text"
                    ),

                "control_type":
                    step.payload.get(
                        "control_type"
                    ),

                "automation_id":
                    step.payload.get(
                        "automation_id"
                    ),
            }


            return {
                "step_id":
                    step.step_id,

                "action":
                    "semantic_ui.click",

                "payload":
                    payload,

                "display":
                    payload,

                "risk":
                    "interactive-ui",
            }


        if (
            step.action
            == "ui.set_text"
        ):

            value = str(
                step.payload[
                    "value"
                ]
            )


            payload = {
                "window_title":
                    str(
                        step.payload[
                            "window_title"
                        ]
                    ),

                "text":
                    step.payload.get(
                        "text"
                    ),

                "automation_id":
                    step.payload.get(
                        "automation_id"
                    ),

                "length":
                    len(
                        value
                    ),

                "value_hash":
                    hashlib.sha256(
                        value.encode(
                            "utf-8"
                        )
                    ).hexdigest(),
            }


            return {
                "step_id":
                    step.step_id,

                "action":
                    "semantic_ui.set_text",

                "payload":
                    payload,

                "display": {
                    "window_title":
                        payload[
                            "window_title"
                        ],

                    "target_text":
                        payload[
                            "text"
                        ],

                    "automation_id":
                        payload[
                            "automation_id"
                        ],

                    "preview":
                        value[:80],
                },

                "risk":
                    "interactive-ui",
            }


        if (
            step.action
            == "screen.capture"
        ):

            payload = {
                "path":
                    str(
                        step.payload[
                            "path"
                        ]
                    )
            }


            return {
                "step_id":
                    step.step_id,

                "action":
                    "desktop.screen_capture",

                "payload":
                    payload,

                "display":
                    payload,

                "risk":
                    "interactive",
            }


        if (
            step.action
            == "file.download"
        ):

            binding = (
                safe_file_handoff
                .binding(
                    step.payload[
                        "url"
                    ],

                    filename=
                        step.payload.get(
                            "filename"
                        ),
                )
            )


            return {
                "step_id":
                    step.step_id,

                **binding,
            }


        return None


    def compile(
        self,
        goal,
        *,
        hints=None,
    ):

        return (
            self.compiler
            .compile(
                goal,
                hints=hints,
            )
        )


    def prepare(
        self,
        goal,
        *,
        hints=None,
    ):

        plan = self.compile(
            goal,
            hints=hints,
        )


        if not plan.executable:

            return {
                "success":
                    False,

                "executable":
                    False,

                "plan":
                    plan,

                "reason":
                    plan.reason,

                "approval_batch":
                    None,
            }


        bindings = []


        for step in plan.steps:

            if not is_interactive(
                step.action
            ):

                continue


            binding = (
                self.binding_for_step(
                    step
                )
            )


            if binding:

                bindings.append(
                    binding
                )


        batch = None


        if bindings:

            batch = (
                approval_batches
                .create(
                    plan.goal,
                    bindings,
                )
            )


        return {
            "success":
                True,

            "executable":
                True,

            "plan":
                plan,

            "approval_batch":
                batch,
        }


    @staticmethod
    def _observe_desktop():

        try:

            windows = (
                semantic_ui
                .windows()
            )


            return {
                "visible_windows":
                    len(
                        windows
                    ),

                "titles":
                    tuple(
                        item[
                            "title"
                        ]
                        for item
                        in windows[:20]
                    ),
            }


        except Exception as exc:

            return {
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


    def _execute_step(
        self,
        step,
        approval_id,
    ):

        p = step.payload


        if (
            step.action
            == "ui.windows"
        ):

            return {
                "success":
                    True,

                "windows":
                    semantic_ui.windows(),
            }


        if (
            step.action
            == "ui.controls"
        ):

            return {
                "success":
                    True,

                "controls":
                    semantic_ui.controls(
                        p[
                            "window_title"
                        ],

                        text=
                            p.get(
                                "text"
                            ),

                        control_type=
                            p.get(
                                "control_type"
                            ),

                        automation_id=
                            p.get(
                                "automation_id"
                            ),
                    ),
            }


        if (
            step.action
            == "ui.click"
        ):

            return (
                semantic_ui.click(
                    p[
                        "window_title"
                    ],

                    text=
                        p.get(
                            "text"
                        ),

                    control_type=
                        p.get(
                            "control_type"
                        ),

                    automation_id=
                        p.get(
                            "automation_id"
                        ),

                    approval_id=
                        approval_id,
                )
            )


        if (
            step.action
            == "ui.set_text"
        ):

            return (
                semantic_ui.set_text(
                    p[
                        "window_title"
                    ],

                    p[
                        "value"
                    ],

                    text=
                        p.get(
                            "text"
                        ),

                    automation_id=
                        p.get(
                            "automation_id"
                        ),

                    approval_id=
                        approval_id,

                    sensitive=
                        bool(
                            p.get(
                                "sensitive",
                                False,
                            )
                        ),
                )
            )


        if (
            step.action
            == "browser.inspect"
        ):

            return (
                persistent_browser
                .inspect(
                    p[
                        "url"
                    ],

                    profile=
                        p.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        approval_id,
                )
            )


        if (
            step.action
            == "browser.click"
        ):

            return (
                persistent_browser
                .click(
                    p[
                        "url"
                    ],

                    p[
                        "selector"
                    ],

                    profile=
                        p.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        approval_id,
                )
            )


        if (
            step.action
            == "browser.fill"
        ):

            return (
                persistent_browser
                .fill(
                    p[
                        "url"
                    ],

                    p[
                        "selector"
                    ],

                    p[
                        "value"
                    ],

                    profile=
                        p.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        approval_id,

                    sensitive=
                        bool(
                            p.get(
                                "sensitive",
                                False,
                            )
                        ),
                )
            )


        if (
            step.action
            == "screen.analyze"
        ):

            return {
                "success":
                    True,

                "analysis":
                    screen_perception
                    .analyze_existing(
                        p[
                            "path"
                        ]
                    ),
            }


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
                        p[
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
                        p[
                            "path"
                        ],

                        p[
                            "query"
                        ],
                    ),
            }


        if (
            step.action
            == "git.status"
        ):

            result = git_actions.status(
                p[
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
                p[
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
                        p[
                            "repo"
                        ]
                    ),
            }


        if (
            step.action
            == "file.download"
        ):

            return (
                safe_file_handoff
                .download(
                    p[
                        "url"
                    ],

                    filename=
                        p.get(
                            "filename"
                        ),

                    approval_id=
                        approval_id,
                )
            )


        return {
            "success":
                False,

            "error":
                "No executor for action.",
        }


    def execute(
        self,
        plan,
        *,
        approval_batch_id=None,
    ):

        validate_plan(
            plan
        )


        if not plan.executable:

            return (
                OperatorExecutionResult(
                    operator_id=(
                        "operator-"
                        + uuid.uuid4()
                        .hex[:16]
                    ),

                    goal=
                        plan.goal,

                    success=
                        False,

                    completed_steps=
                        0,

                    total_steps=
                        len(
                            plan.steps
                        ),

                    results=(),

                    needs_replan=
                        True,
                )
            )


        operator_id = (
            "operator-"
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

                if not approval_batch_id:

                    return (
                        OperatorExecutionResult(
                            operator_id=
                                operator_id,

                            goal=
                                plan.goal,

                            success=
                                False,

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

                            approval_batch_id=
                                None,

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


                token = (
                    approval_batches
                    .token_for_step(
                        approval_batch_id,
                        step.step_id,
                    )
                )


                if not token:

                    return (
                        OperatorExecutionResult(
                            operator_id=
                                operator_id,

                            goal=
                                plan.goal,

                            success=
                                False,

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

                            approval_batch_id=
                                approval_batch_id,

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

            output = None

            error = None

            success = False

            observations = []


            while (
                attempts
                <= step.retries
            ):

                attempts += 1


                if step.observe:

                    observations.append(
                        self._observe_desktop()
                    )


                try:

                    output = (
                        self._execute_step(
                            step,
                            token,
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


                        error = output.get(
                            "error"
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


                if step.observe:

                    observations.append(
                        self._observe_desktop()
                    )


                if success:
                    break


                # Approval token is one-time.
                # Never retry an interactive action automatically.
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


            record = {
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

                "observations":
                    tuple(
                        observations
                    ),
            }


            results.append(
                record
            )


            if success:

                completed += 1

                continue


            failed_result = SimpleNamespace(
                success=False,

                failed_step=
                    step.step_id,

                steps=(
                    SimpleNamespace(
                        success=False,

                        step_id=
                            step.step_id,

                        error=
                            error,

                        attempts=
                            attempts,
                    ),
                ),
            )


            try:

                replan = (
                    action_replanner
                    .propose(
                        plan.goal,
                        failed_result,
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


            return (
                OperatorExecutionResult(
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

                    approval_batch_id=
                        approval_batch_id,

                    failed_step=
                        step.step_id,

                    needs_replan=
                        True,

                    replan=
                        replan,
                )
            )


        return (
            OperatorExecutionResult(
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

                approval_batch_id=
                    approval_batch_id,

                needs_replan=
                    False,
            )
        )


    def run_goal(
        self,
        goal,
        *,
        hints=None,
        approval_batch_id=None,
    ):

        plan = self.compile(
            goal,
            hints=hints,
        )


        if not plan.executable:

            try:

                proposal = (
                    action_replanner.brain
                    .plan(
                        (
                            "Create a safe JARVIS computer "
                            "workflow for this goal, but "
                            "do not execute it: "
                            + goal
                        )
                    )
                )

            except Exception as exc:

                proposal = {
                    "error":
                        str(
                            exc
                        )
                }


            return {
                "success":
                    False,

                "executable":
                    False,

                "plan":
                    plan,

                "planner_proposal":
                    proposal,

                "auto_execute":
                    False,
            }


        return self.execute(
            plan,

            approval_batch_id=
                approval_batch_id,
        )


computer_operator = (
    ComputerOperator()
)
