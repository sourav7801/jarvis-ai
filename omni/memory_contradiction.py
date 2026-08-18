from __future__ import annotations

from dataclasses import dataclass
import re

from omni.memory_scope import MemoryScope


@dataclass(frozen=True)
class ReplacementHint:
    scope: MemoryScope
    old_query: str
    reason: str = "explicit_replacement"


def explicit_replacement_hint(
    text: str,
    scope: MemoryScope | str,
) -> ReplacementHint | None:
    """
    Detect only explicit replacement language.

    Semantic similarity by itself NEVER supersedes memory.
    """

    value = str(
        text or ""
    ).strip()

    scope = MemoryScope(
        str(
            getattr(
                scope,
                "value",
                scope,
            )
        )
    )

    if scope == MemoryScope.PREFERENCE:

        patterns = (
            (
                r"\bchange my preference from "
                r"(.+?)\s+to\s+(.+)$",
                1,
            ),
            (
                r"\bi (?:now )?prefer "
                r"(.+?)\s+instead of\s+(.+)$",
                2,
            ),
            (
                r"\bfrom now on i prefer "
                r"(.+?)\s+instead of\s+(.+)$",
                2,
            ),
        )

    elif scope == MemoryScope.DECISION:

        patterns = (
            (
                r"\bchange (?:our|the) decision from "
                r"(.+?)\s+to\s+(.+)$",
                1,
            ),
            (
                r"\bwe decided to use "
                r"(.+?)\s+instead of\s+(.+)$",
                2,
            ),
            (
                r"\buse "
                r"(.+?)\s+instead of\s+(.+)$",
                2,
            ),
        )

    else:
        return None

    for pattern, old_group in patterns:

        match = re.search(
            pattern,
            value,
            re.I,
        )

        if not match:
            continue

        old_query = (
            match.group(old_group)
            .strip(" .,:;")
        )

        if old_query:

            return ReplacementHint(
                scope=scope,
                old_query=old_query,
            )

    return None
