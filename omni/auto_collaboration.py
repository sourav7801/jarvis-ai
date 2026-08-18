from __future__ import annotations

from typing import Any

from omni.brain import brain


COMPLEX_MARKERS = (
    " and ",
    " then ",
    " compare ",
    " assess ",
    " evaluate ",
    " research ",
    " analyze ",
    " analyse ",
    " strategy",
    " plan ",
    " build ",
    " investigate ",
    " review ",
    " find ",
)

BLOCKED_FAST_PATHS = (
    "what time",
    "current time",
    "open notepad",
    "open calculator",
    "open website",
    "open folder",
    "list files",
    "system info",
)


def should_auto_collaborate(request: str) -> bool:
    """
    Return True only for high-confidence requests where
    JarvisBrain already selected multiple specialists.

    Deterministic tool commands stay on the existing fast path.
    """

    text = str(request or "").strip()
    lowered = text.lower()

    if not lowered:
        return False

    if any(
        marker in lowered
        for marker in BLOCKED_FAST_PATHS
    ):
        return False

    decision = brain.decide(text)
    plan = brain.plan(text)

    if decision.confidence < 0.90:
        return False

    if plan.agent_count < 2:
        return False

    if decision.intent in {
        "conversation",
        "health",
        "office",
        "operator",
    }:
        return False

    word_count = len(text.split())

    complex_language = any(
        marker in f" {lowered} "
        for marker in COMPLEX_MARKERS
    )

    # Multi-specialist + sufficient task complexity.
    return (
        plan.agent_count >= 3
        and (
            word_count >= 6
            or complex_language
        )
    )


def auto_collaborate(request: str):
    """
    Attempt governed collaboration.

    Returns None when:
      - collaboration is unnecessary
      - collaboration cannot execute safely
      - collaboration fails

    Existing routing can then continue normally.
    """

    if not should_auto_collaborate(request):
        return None

    try:
        from omni.collaboration_service import (
            collaborate,
        )

        result = collaborate(request)

    except Exception:
        return None

    if not getattr(result, "success", False):
        return None

    return result


def auto_collaboration_answer(
    request: str,
) -> str | None:

    result = auto_collaborate(request)

    if result is None:
        return None

    answer = getattr(
        result,
        "final_answer",
        None,
    )

    if not answer:
        return None

    return str(answer)
