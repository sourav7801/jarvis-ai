from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
import re


class MemoryScope(str, Enum):
    PREFERENCE = "preference"
    PROJECT = "project"
    DECISION = "decision"
    CONVERSATION = "conversation"
    AGENT_FINDING = "agent_finding"


@dataclass(frozen=True)
class ActiveMemoryContext:
    project_id: str | None = None
    conversation_id: str | None = None


_ACTIVE_CONTEXT: ContextVar[ActiveMemoryContext] = (
    ContextVar(
        "jarvis_memory_context",
        default=ActiveMemoryContext(),
    )
)


def normalize_id(
    value: str | None,
) -> str | None:

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    normalized = re.sub(
        r"[^a-zA-Z0-9_.-]+",
        "-",
        value,
    ).strip("-").lower()

    return normalized[:100] or None


def current_memory_context():
    return _ACTIVE_CONTEXT.get()


@contextmanager
def use_memory_context(
    project_id: str | None = None,
    conversation_id: str | None = None,
):

    context = ActiveMemoryContext(
        project_id=normalize_id(
            project_id
        ),
        conversation_id=normalize_id(
            conversation_id
        ),
    )

    token = _ACTIVE_CONTEXT.set(
        context
    )

    try:
        yield context

    finally:
        _ACTIVE_CONTEXT.reset(
            token
        )
