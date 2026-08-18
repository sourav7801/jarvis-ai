from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)


ALLOWED_ACTIONS = {
    "ui.windows",
    "ui.controls",
    "ui.click",
    "ui.set_text",

    "browser.inspect",
    "browser.click",
    "browser.fill",

    "screen.analyze",
    "screen.capture",

    "document.read",
    "document.search",

    "git.status",
    "git.diff",
    "git.repository_state",

    "file.download",
}


INTERACTIVE_ACTIONS = {
    "ui.click",
    "ui.set_text",

    "browser.inspect",
    "browser.click",
    "browser.fill",

    "screen.capture",

    "file.download",
}


BLOCKED_ACTION_PREFIXES = (
    "shell.",
    "powershell.",
    "cmd.",
    "process.exec",
    "trade.",
    "broker.",
    "order.",
    "credential.",
)


@dataclass(frozen=True)
class OperatorStep:

    step_id: str

    action: str

    payload: dict = field(
        default_factory=dict
    )

    retries: int = 0

    observe: bool = True


@dataclass(frozen=True)
class OperatorPlan:

    goal: str

    steps: tuple[
        OperatorStep,
        ...
    ]

    source: str = "deterministic"

    executable: bool = True

    reason: str = ""


def is_interactive(
    action,
):

    return (
        str(
            action
        )
        in INTERACTIVE_ACTIONS
    )


def validate_plan(
    plan,
):

    if not isinstance(
        plan,
        OperatorPlan,
    ):

        raise TypeError(
            "Expected OperatorPlan."
        )


    if not str(
        plan.goal
    ).strip():

        raise ValueError(
            "Operator goal cannot be empty."
        )


    if len(
        plan.steps
    ) > 20:

        raise ValueError(
            "Operator plans are limited "
            "to 20 steps."
        )


    seen = set()


    for step in plan.steps:

        if not isinstance(
            step,
            OperatorStep,
        ):

            raise TypeError(
                "Invalid OperatorStep."
            )


        if step.step_id in seen:

            raise ValueError(
                "Duplicate operator step ID: "
                + step.step_id
            )


        seen.add(
            step.step_id
        )


        action = str(
            step.action
        )


        if action.startswith(
            BLOCKED_ACTION_PREFIXES
        ):

            raise PermissionError(
                "Blocked operator action: "
                + action
            )


        if action not in (
            ALLOWED_ACTIONS
        ):

            raise PermissionError(
                "Unknown operator action: "
                + action
            )


        if not isinstance(
            step.payload,
            dict,
        ):

            raise TypeError(
                "Step payload must be a dict."
            )


        if (
            step.retries < 0
            or step.retries > 2
        ):

            raise ValueError(
                "Operator retries must be "
                "between 0 and 2."
            )


    return True
