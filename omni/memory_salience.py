from __future__ import annotations

from dataclasses import dataclass
import re

from omni.memory_scope import MemoryScope


@dataclass(frozen=True)
class SalienceDecision:
    remember: bool
    scope: MemoryScope | None = None
    score: float = 0.0
    reason: str = ""


PREFERENCE_PATTERNS = (
    r"\bchange my preference from\b",
    r"\bi prefer\b",
    r"\bmy preference\b",
    r"\bfrom now on\b",
    r"\balways use\b",
    r"\bnever use\b",
    r"\bdo not use\b",
    r"\bdon't use\b",
    r"\bi want you to always\b",
)

DECISION_PATTERNS = (
    r"\bchange (?:our|the) decision from\b",
    r"\bwe decided\b",
    r"\bwe have decided\b",
    r"\bfinal decision\b",
    r"\bdecision is\b",
    r"\bwe will use\b",
    r"\bwe are using\b",
    r"\bwe're using\b",
    r"\bselected\b",
    r"\bchosen\b",
    r"\bchoose .+ instead of\b",
    r"\buse .+ instead of\b",
)

PROJECT_PATTERNS = (
    r"\bproject goal\b",
    r"\bproject target\b",
    r"\bproject architecture\b",
    r"\barchitecture is\b",
    r"\broadmap\b",
    r"\bmilestone\b",
    r"\bphase\s+[0-9a-z]+\b",
    r"\bwe are building\b",
    r"\bwe're building\b",
)

EXPLICIT_MEMORY_PATTERNS = (
    r"\bremember that\b",
    r"\bremember this\b",
    r"\bkeep this in memory\b",
    r"\bsave this\b",
)

LOW_VALUE_PATTERNS = (
    r"^\s*(hi|hello|hey|thanks|thank you|ok|okay|yes|no)\s*[.!]?\s*$",
    r"^\s*what time",
    r"^\s*open ",
)


def _matches(
    patterns,
    text,
):
    return any(
        re.search(
            pattern,
            text,
            re.I,
        )
        for pattern in patterns
    )


def classify_salience(
    text: str,
    *,
    has_project: bool = False,
) -> SalienceDecision:
    """
    Conservative automatic-memory policy.

    Ordinary questions and chatter are not remembered.
    """

    value = str(
        text or ""
    ).strip()

    if not value:
        return SalienceDecision(
            False,
            reason="empty",
        )

    if len(value) < 8:
        return SalienceDecision(
            False,
            reason="too_short",
        )

    lowered = value.lower()

    if _matches(
        LOW_VALUE_PATTERNS,
        lowered,
    ):
        return SalienceDecision(
            False,
            reason="low_value",
        )

    explicit = _matches(
        EXPLICIT_MEMORY_PATTERNS,
        lowered,
    )

    if _matches(
        PREFERENCE_PATTERNS,
        lowered,
    ):
        return SalienceDecision(
            True,
            MemoryScope.PREFERENCE,
            1.0 if explicit else 0.95,
            "durable_preference",
        )

    if _matches(
        DECISION_PATTERNS,
        lowered,
    ):
        return SalienceDecision(
            True,
            MemoryScope.DECISION,
            1.0 if explicit else 0.93,
            "durable_decision",
        )

    if (
        has_project
        and _matches(
            PROJECT_PATTERNS,
            lowered,
        )
    ):
        return SalienceDecision(
            True,
            MemoryScope.PROJECT,
            1.0 if explicit else 0.90,
            "project_state",
        )

    # Explicit memory requests are retained as decisions
    # when no more specific category is identified.
    if explicit:
        return SalienceDecision(
            True,
            MemoryScope.DECISION,
            1.0,
            "explicit_memory_request",
        )

    return SalienceDecision(
        False,
        reason="not_salient",
    )
