from __future__ import annotations

import re

from omni.autonomy_engine import (
    autonomy_engine,
)


MISSION_PATTERNS = (
    r"^(?:jarvis[,\s]+)?mission\s*:\s*(.+)$",
    r"^(?:jarvis[,\s]+)?goal\s*:\s*(.+)$",
    r"^(?:jarvis[,\s]+)?run mission\s+(.+)$",
)


PLAN_PATTERNS = (
    r"^(?:jarvis[,\s]+)?plan mission\s*:\s*(.+)$",
    r"^(?:jarvis[,\s]+)?plan goal\s*:\s*(.+)$",
)


def _extract(
    text,
    patterns,
):

    for pattern in patterns:

        match = re.match(
            pattern,
            text,
            re.I | re.S,
        )

        if match:

            value = (
                match.group(1)
                .strip()
            )

            if value:

                return value

    return None


def _format_plan(
    plan,
):

    lines = [
        (
            "MISSION: "
            + plan.mission_id
        ),
        (
            "GOAL: "
            + plan.goal
        ),
        (
            "LEAD: "
            + plan.lead_agent
        ),
        "",
        "TASKS:",
    ]

    for index, task in enumerate(
        plan.tasks,
        1,
    ):

        dependencies = (
            ", ".join(
                task.dependencies
            )
            if task.dependencies
            else "none"
        )

        lines.append(
            (
                f"{index}. "
                f"{task.agent} "
                f"[{task.role}] "
                f"depends on: "
                f"{dependencies}"
            )
        )

    if plan.requires_approval:

        lines.extend(
            [
                "",
                "APPROVAL REQUIRED",
            ]
        )

    return "\n".join(
        lines
    )


def mission_command_answer(
    text,
    *,
    project_id=None,
):

    value = str(
        text or ""
    ).strip()

    if not value:

        return None


    preview = _extract(
        value,
        PLAN_PATTERNS,
    )

    if preview:

        return _format_plan(
            autonomy_engine.plan(
                preview
            )
        )


    goal = _extract(
        value,
        MISSION_PATTERNS,
    )

    if not goal:

        return None


    result = (
        autonomy_engine.execute(
            goal,
            project_id=project_id,
        )
    )


    if (
        result.status.value
        == "blocked"
    ):

        return (
            f"Mission {result.mission_id} "
            "requires approval."
        )


    if not result.success:

        errors = "; ".join(
            result.errors
        )

        return (
            f"Mission {result.mission_id} failed."
            + (
                f" Errors: {errors}"
                if errors
                else ""
            )
        )


    verification = (
        "VERIFIED"
        if result.verified
        else "UNVERIFIED"
    )


    return (
        f"[{result.mission_id} | "
        f"{verification}]\n"
        f"{result.final_answer}"
    )
