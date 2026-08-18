from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

import json
import re


ALLOWED_ACTIONS = {

    # Desktop
    "desktop.observe",
    "desktop.natural_click",
    "desktop.natural_set_text",

    # Persistent browser
    "browser.start",
    "browser.observe",
    "browser.natural_click",
    "browser.natural_fill",
    "browser.close",

    # Vision / documents
    "vision.analyze",
    "document.read",
    "document.search",

    # Git intelligence
    "git.status",
    "git.diff",
    "git.repository_state",

    # Connected Services
    "google.gmail.search",
    "google.gmail.get",
    "google.gmail.create_draft",
    "google.gmail.send_draft",

    "google.calendar.list",
    "google.calendar.events",
    "google.calendar.create_event",
    "google.calendar.update_event",
    "google.calendar.delete_event",

    "google.contacts.search",
    "google.contacts.resolve",

    "google.gmail.draft_to_contact",

    "google.calendar.check_conflicts",
    "google.calendar.schedule_meeting",
    "google.calendar.schedule_from_email",
    "google.gmail.thread",
    "google.gmail.reply_draft",
    "google.calendar.recommend_slots",

    "github.profile",
    "github.repos",
    "github.issues",
    "github.pulls",
    "github.issue.create",
    "github.comment.create",
    "github.pull.create",

    # Isolated engineering
    "coding.create_worktree",
    "coding.test_worktree",
    "coding.diff_worktree",
}


INTERACTIVE_ACTIONS = {
    "desktop.natural_click",
    "desktop.natural_set_text",

    "browser.start",
    "browser.natural_click",
    "browser.natural_fill",

    "google.gmail.create_draft",
    "google.gmail.send_draft",

    "google.calendar.create_event",
    "google.calendar.update_event",
    "google.calendar.delete_event",

    "google.gmail.draft_to_contact",
    "google.calendar.schedule_meeting",
    "google.calendar.schedule_from_email",
    "google.gmail.reply_draft",

    "github.issue.create",
    "github.comment.create",
    "github.pull.create",

    "coding.create_worktree",
    "coding.test_worktree",
}


BLOCKED_PREFIXES = (
    "shell.",
    "cmd.",
    "powershell.",
    "process.",
    "terminal.",
    "credential.",
    "password.",
    "trade.",
    "trading.",
    "broker.",
    "order.",
    "git.push",
    "git.merge",
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


PAYLOAD_FIELDS = {

    "desktop.observe": {
        "window_title",
        "include_controls",
    },

    "desktop.natural_click": {
        "window_title",
        "target",
        "screenshot",
    },

    "desktop.natural_set_text": {
        "window_title",
        "target",
        "value",
        "sensitive",
    },

    "browser.start": {
        "url",
        "profile",
        "headless",
    },

    "browser.observe": {
        "session_id",
        "session_ref",
    },

    "browser.natural_click": {
        "session_id",
        "session_ref",
        "target",
    },

    "browser.natural_fill": {
        "session_id",
        "session_ref",
        "target",
        "value",
        "sensitive",
    },

    "browser.close": {
        "session_id",
        "session_ref",
    },

    "vision.analyze": {
        "path",
        "window_title",
        "target",
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

    "google.gmail.search": {
        "query",
        "max_results",
    },

    "google.gmail.get": {
        "message_id",
    },

    "google.gmail.create_draft": {
        "to",
        "subject",
        "body",
        "cc",
        "bcc",
    },

    "google.gmail.send_draft": {
        "draft_id",
    },

    "google.calendar.list": {
        "max_results",
    },

    "google.calendar.events": {
        "calendar_id",
        "time_min",
        "time_max",
        "max_results",
        "query",
    },

    "google.calendar.create_event": {
        "calendar_id",
        "event",
        "send_updates",
    },

    "google.calendar.update_event": {
        "calendar_id",
        "event_id",
        "patch",
        "send_updates",
    },

    "google.calendar.delete_event": {
        "calendar_id",
        "event_id",
        "send_updates",
    },

    "google.contacts.search": {
        "query",
        "max_results",
    },

    "google.contacts.resolve": {
        "query",
        "max_results",
        "include_gmail_history",
    },

    "google.gmail.draft_to_contact": {
        "recipients",
        "subject",
        "body",
        "cc",
        "bcc",
    },

    "google.calendar.check_conflicts": {
        "start",
        "end",
        "calendar_id",
    },

    "google.calendar.schedule_meeting": {
        "title",
        "attendees",
        "start",
        "end",
        "description",
        "location",
        "calendar_id",
        "send_updates",
        "time_zone",
        "allow_conflicts",
    },

    "google.calendar.schedule_from_email": {
        "message_id",
        "title",
        "start",
        "end",
        "attendees",
        "description",
        "location",
        "calendar_id",
        "send_updates",
        "time_zone",
        "allow_conflicts",
    },

    "google.gmail.thread": {
        "thread_id",
    },

    "google.gmail.reply_draft": {
        "thread_id",
        "body",
        "reply_all",
    },

    "google.calendar.recommend_slots": {
        "attendees",
        "window_start",
        "window_end",
        "duration_minutes",
        "step_minutes",
        "calendar_id",
        "time_zone",
        "working_hour_start",
        "working_hour_end",
        "strict",
        "max_slots",
    },

    "github.profile": {
    },

    "github.repos": {
        "per_page",
    },

    "github.issues": {
        "owner",
        "repo",
        "state",
        "per_page",
    },

    "github.pulls": {
        "owner",
        "repo",
        "state",
        "per_page",
    },

    "github.issue.create": {
        "owner",
        "repo",
        "title",
        "body",
    },

    "github.comment.create": {
        "owner",
        "repo",
        "issue_number",
        "body",
    },

    "github.pull.create": {
        "owner",
        "repo",
        "title",
        "head",
        "base",
        "body",
    },

    "coding.create_worktree": {
        "repo",
        "name",
    },

    "coding.test_worktree": {
        "worktree",
        "worktree_ref",
        "test_args",
    },

    "coding.diff_worktree": {
        "worktree",
        "worktree_ref",
    },
}


VERIFY_FIELDS = {
    "contains",
    "url_contains",
    "title_contains",
    "changed",
    "window_open",
    "file_exists",
    "min_elements",
}


@dataclass(frozen=True)
class RuntimeStep:

    step_id: str

    action: str

    payload: dict = field(
        default_factory=dict
    )

    verify: dict = field(
        default_factory=dict
    )

    retries: int = 0


@dataclass(frozen=True)
class RuntimePlan:

    goal: str

    steps: tuple[
        RuntimeStep,
        ...
    ]

    source: str = "operator-v4"

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

        for key, child in (
            value.items()
        ):

            key_lower = str(
                key
            ).lower()


            if (
                key_lower
                in SECRET_FIELDS
            ):

                raise PermissionError(
                    "Credential-bearing field "
                    "blocked: "
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
        RuntimePlan,
    ):

        raise TypeError(
            "Expected RuntimePlan."
        )


    if not str(
        plan.goal
    ).strip():

        raise ValueError(
            "Workflow goal cannot be empty."
        )


    if (
        plan.schema_version
        != 1
    ):

        raise ValueError(
            "Unsupported V4 schema."
        )


    if len(
        plan.steps
    ) > 30:

        raise ValueError(
            "V4 workflow cannot exceed "
            "30 steps."
        )


    seen = set()


    for step in plan.steps:

        if not isinstance(
            step,
            RuntimeStep,
        ):

            raise TypeError(
                "Invalid RuntimeStep."
            )


        if step.step_id in seen:

            raise ValueError(
                "Duplicate workflow step ID: "
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
                "Blocked V4 action: "
                + action
            )


        if action not in (
            ALLOWED_ACTIONS
        ):

            raise PermissionError(
                "Unknown V4 action: "
                + action
            )


        if not isinstance(
            step.payload,
            dict,
        ):

            raise TypeError(
                "Payload must be a dict."
            )


        unexpected = (
            set(
                step.payload
            )
            - PAYLOAD_FIELDS[
                action
            ]
        )


        if unexpected:

            raise PermissionError(
                "Unexpected payload field(s) "
                "for "
                + action
                + ": "
                + ", ".join(
                    sorted(
                        unexpected
                    )
                )
            )


        if not isinstance(
            step.verify,
            dict,
        ):

            raise TypeError(
                "Verification specification "
                "must be a dict."
            )


        unknown_verify = (
            set(
                step.verify
            )
            - VERIFY_FIELDS
        )


        if unknown_verify:

            raise PermissionError(
                "Unknown verification field(s): "
                + ", ".join(
                    sorted(
                        unknown_verify
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


        if action in (
            "desktop.natural_set_text",
            "browser.natural_fill",
        ):

            if bool(
                step.payload.get(
                    "sensitive",
                    False,
                )
            ):

                raise PermissionError(
                    "Sensitive text automation "
                    "is blocked."
                )


            target = str(
                step.payload.get(
                    "target",
                    ""
                )
            ).lower()


            if (
                "password"
                in target

                or "passwd"
                in target

                or "credential"
                in target
            ):

                raise PermissionError(
                    "Credential/password target "
                    "is blocked."
                )


        if action.startswith(
            "browser."
        ):

            if action != "browser.start":

                if not (
                    step.payload.get(
                        "session_id"
                    )
                    or step.payload.get(
                        "session_ref"
                    )
                ):

                    raise ValueError(
                        action
                        + " requires session_id "
                        "or session_ref."
                    )


        if action.startswith(
            "coding."
        ):

            if (
                action
                != "coding.create_worktree"

                and not (
                    step.payload.get(
                        "worktree"
                    )
                    or step.payload.get(
                        "worktree_ref"
                    )
                )
            ):

                raise ValueError(
                    action
                    + " requires worktree "
                    "or worktree_ref."
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
            "V4 DSL must be a JSON object."
        )


    raw_steps = data.get(
        "steps",
        ()
    )


    if not isinstance(
        raw_steps,
        (
            list,
            tuple,
        ),
    ):

        raise TypeError(
            "steps must be an array."
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
                "Each workflow step "
                "must be an object."
            )


        steps.append(
            RuntimeStep(
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
                        {}
                    )
                ),

                verify=dict(
                    item.get(
                        "verify",
                        {}
                    )
                ),

                retries=int(
                    item.get(
                        "retries",
                        0,
                    )
                ),
            )
        )


    plan = RuntimePlan(
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
    source="operator-agent",
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


    schema = {
        "schema_version":
            1,

        "steps": [
            {
                "step_id":
                    "step-1",

                "action":
                    "desktop.observe",

                "payload":
                    {},

                "verify":
                    {},

                "retries":
                    0,
            }
        ],
    }


    return (
        "Return JSON only.\n"
        "You are proposing a bounded JARVIS "
        "Computer Operator V4 workflow.\n"
        "You do NOT authorize execution.\n"
        "Do not include credentials, passwords, "
        "tokens, arbitrary shell/process execution, "
        "Git push/merge, broker actions, or trading "
        "execution.\n"
        "Use session_ref to reference a previous "
        "browser.start step.\n"
        "Use worktree_ref to reference a previous "
        "coding.create_worktree step.\n"
        "Use verify when a deterministic success "
        "condition is available.\n\n"
        "Allowed actions:\n"
        + "\n".join(
            " - "
            + action

            for action
            in sorted(
                ALLOWED_ACTIONS
            )
        )
        + "\n\nExample schema:\n"
        + json.dumps(
            schema,
            indent=2,
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
