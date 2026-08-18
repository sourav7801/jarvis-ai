from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

import json
import re


ALLOWED_ACTIONS = {
    "desktop.observe",
    "desktop.controls",

    "browser.observe",
    "browser.observe_click",
    "browser.observe_fill",

    "vision.analyze",

    "document.read",
    "document.search",

    "git.status",
    "git.diff",
    "git.repository_state",
}


INTERACTIVE_ACTIONS = {
    "browser.observe",
    "browser.observe_click",
    "browser.observe_fill",
}


BLOCKED_PREFIXES = (
    "shell.",
    "cmd.",
    "powershell.",
    "process.",
    "credential.",
    "trade.",
    "trading.",
    "broker.",
    "order.",
)


SECRET_FIELDS = {
    "password",
    "passwd",
    "credential",
    "credentials",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
}


ALLOWED_PAYLOADS = {

    "desktop.observe": {
        "window_title",
        "include_controls",
    },

    "desktop.controls": {
        "window_title",
        "text",
        "control_type",
        "automation_id",
    },

    "browser.observe": {
        "url",
        "profile",
    },

    "browser.observe_click": {
        "url",
        "selector",
        "profile",
    },

    "browser.observe_fill": {
        "url",
        "selector",
        "value",
        "profile",
        "sensitive",
    },

    "vision.analyze": {
        "path",
    },

    "document.read": {
        "path",
    },

    "document.search": {
        "path",
        "query",
    },

    "git.status": {
        "repo",
    },

    "git.diff": {
        "repo",
    },

    "git.repository_state": {
        "repo",
    },
}


@dataclass(frozen=True)
class DSLStep:

    step_id: str

    action: str

    payload: dict = field(
        default_factory=dict
    )

    retries: int = 0

    observe: bool = True


@dataclass(frozen=True)
class DSLPlan:

    goal: str

    steps: tuple[
        DSLStep,
        ...
    ]

    source: str = "validated-dsl"

    schema_version: int = 1


def is_interactive(
    action,
):

    return (
        str(
            action
        )
        in INTERACTIVE_ACTIONS
    )


def _scan_secrets(
    value,
    path="payload",
):

    if isinstance(
        value,
        dict,
    ):

        for key, child in value.items():

            if (
                str(
                    key
                ).lower()
                in SECRET_FIELDS
            ):

                raise PermissionError(
                    "Credential-bearing DSL "
                    "field blocked: "
                    + path
                    + "."
                    + str(
                        key
                    )
                )

            _scan_secrets(
                child,
                path
                + "."
                + str(
                    key
                ),
            )


    elif isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        for index, child in enumerate(
            value
        ):

            _scan_secrets(
                child,
                (
                    path
                    + "["
                    + str(
                        index
                    )
                    + "]"
                ),
            )


def validate_plan(
    plan,
):

    if not isinstance(
        plan,
        DSLPlan,
    ):

        raise TypeError(
            "Expected DSLPlan."
        )


    if not str(
        plan.goal
    ).strip():

        raise ValueError(
            "Goal cannot be empty."
        )


    if (
        plan.schema_version
        != 1
    ):

        raise ValueError(
            "Unsupported DSL schema."
        )


    if len(
        plan.steps
    ) > 20:

        raise ValueError(
            "Operator DSL cannot exceed "
            "20 steps."
        )


    seen = set()


    for step in plan.steps:

        if step.step_id in seen:

            raise ValueError(
                "Duplicate step ID: "
                + step.step_id
            )


        seen.add(
            step.step_id
        )


        action = str(
            step.action
        )


        if action.startswith(
            BLOCKED_PREFIXES
        ):

            raise PermissionError(
                "Blocked action: "
                + action
            )


        if action not in (
            ALLOWED_ACTIONS
        ):

            raise PermissionError(
                "Unknown action: "
                + action
            )


        if not isinstance(
            step.payload,
            dict,
        ):

            raise TypeError(
                "Payload must be a dictionary."
            )


        unexpected = (
            set(
                step.payload
            )
            - ALLOWED_PAYLOADS[
                action
            ]
        )


        if unexpected:

            raise PermissionError(
                "Unexpected payload fields "
                "for "
                + action
                + ": "
                + ", ".join(
                    sorted(
                        unexpected
                    )
                )
            )


        _scan_secrets(
            step.payload
        )


        if not (
            0
            <= step.retries
            <= 2
        ):

            raise ValueError(
                "Retries must be 0-2."
            )


        if (
            action
            == "browser.observe_fill"
        ):

            selector = str(
                step.payload.get(
                    "selector",
                    ""
                )
            ).lower()


            if (
                bool(
                    step.payload.get(
                        "sensitive",
                        False,
                    )
                )

                or "password"
                in selector

                or "passwd"
                in selector
            ):

                raise PermissionError(
                    "Password/credential "
                    "automation is blocked."
                )


    return True


def from_dict(
    goal,
    data,
    *,
    source="model-proposal",
):

    if not isinstance(
        data,
        dict,
    ):

        raise TypeError(
            "DSL document must be an object."
        )


    raw_steps = data.get(
        "steps",
        []
    )


    if not isinstance(
        raw_steps,
        (
            list,
            tuple,
        ),
    ):

        raise TypeError(
            "DSL steps must be an array."
        )


    steps = []


    for index, item in enumerate(
        raw_steps,
        1,
    ):

        if not isinstance(
            item,
            dict,
        ):

            raise TypeError(
                "DSL step must be an object."
            )


        steps.append(
            DSLStep(
                step_id=str(
                    item.get(
                        "step_id",
                        "step-"
                        + str(
                            index
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


    plan = DSLPlan(
        goal=str(
            goal
        ),

        steps=tuple(
            steps
        ),

        source=str(
            source
        ),

        schema_version=int(
            data.get(
                "schema_version",
                1,
            )
        ),
    )


    validate_plan(
        plan
    )


    return plan


def parse_json(
    goal,
    text,
    *,
    source="model-proposal",
):

    text = str(
        text
    ).strip()


    if text.startswith(
        "```"
    ):

        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )


    return from_dict(
        goal,
        json.loads(
            text
        ),
        source=source,
    )


def planner_prompt(
    goal,
    observations=None,
):

    observations = (
        observations
        if observations is not None
        else {}
    )


    return (
        "Return JSON only.\n"
        "Propose a JARVIS computer workflow.\n"
        "You are NOT authorizing execution.\n"
        "Do not include shell commands, PowerShell, "
        "credentials, passwords, tokens, broker or "
        "trading execution.\n\n"
        "Allowed actions:\n"
        + "\n".join(
            " - "
            + action
            for action
            in sorted(
                ALLOWED_ACTIONS
            )
        )
        + "\n\nGoal:\n"
        + str(
            goal
        )
        + "\n\nObservations:\n"
        + json.dumps(
            observations,
            ensure_ascii=False,
            default=str,
        )
    )
