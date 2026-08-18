from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
import math
from hashlib import sha256
from typing import Any

from omni.memory_scope import MemoryScope


IMPORTANCE_DEFAULTS = {
    MemoryScope.PREFERENCE.value: 0.95,
    MemoryScope.DECISION.value: 0.92,
    MemoryScope.PROJECT.value: 0.85,
    MemoryScope.AGENT_FINDING.value: 0.72,
    MemoryScope.CONVERSATION.value: 0.55,
}


HALF_LIFE_DAYS = {
    # Preferences should be effectively long-lived.
    MemoryScope.PREFERENCE.value: 3650.0,

    # Decisions remain important but may eventually
    # become stale unless superseded explicitly.
    MemoryScope.DECISION.value: 730.0,

    MemoryScope.PROJECT.value: 365.0,

    # Research findings age materially faster.
    MemoryScope.AGENT_FINDING.value: 45.0,

    # Conversation memories are deliberately short-lived.
    MemoryScope.CONVERSATION.value: 7.0,
}


def utc_now():
    return datetime.now(
        timezone.utc
    )


def utc_iso():
    return utc_now().isoformat()


def _scope_value(
    scope: MemoryScope | str | None,
):

    if scope is None:
        return None

    return str(
        getattr(
            scope,
            "value",
            scope,
        )
    )


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 1.0,
):
    return max(
        low,
        min(
            float(value),
            high,
        ),
    )


def default_importance(
    scope: MemoryScope | str | None,
):

    value = _scope_value(
        scope
    )

    return IMPORTANCE_DEFAULTS.get(
        value,
        0.65,
    )


def enrich_lifecycle_metadata(
    scope: MemoryScope | str,
    metadata: dict[str, Any] | None = None,
):
    """
    Add lifecycle metadata to newly created memories.

    Existing explicit metadata always takes precedence.
    """

    result = dict(
        metadata or {}
    )

    value = _scope_value(
        scope
    )

    result.setdefault(
        "memory_state",
        "active",
    )

    result.setdefault(
        "created_at",
        utc_iso(),
    )

    result.setdefault(
        "last_recalled_at",
        None,
    )

    salience = result.get(
        "salience_score"
    )

    importance = result.get(
        "importance"
    )

    if importance is None:

        if salience is not None:

            try:
                importance = (
                    0.60
                    * default_importance(value)
                    + 0.40
                    * clamp(float(salience))
                )

            except Exception:
                importance = (
                    default_importance(value)
                )

        else:
            importance = (
                default_importance(value)
            )

    result[
        "importance"
    ] = clamp(
        importance
    )

    return result


def _parse_datetime(
    value,
):

    if not value:
        return None

    if isinstance(
        value,
        datetime,
    ):

        result = value

    else:

        try:
            result = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

        except Exception:
            return None

    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )

    return result.astimezone(
        timezone.utc
    )


def age_days(
    metadata: dict[str, Any],
    *,
    now: datetime | None = None,
):

    created = _parse_datetime(
        metadata.get(
            "created_at"
        )
    )

    if created is None:
        return 0.0

    now = (
        now
        or utc_now()
    )

    seconds = max(
        0.0,
        (
            now - created
        ).total_seconds(),
    )

    return seconds / 86400.0


def decay_factor(
    scope: MemoryScope | str | None,
    metadata: dict[str, Any],
    *,
    now: datetime | None = None,
):
    """
    Exponential memory decay.

    This changes recall priority/eligibility.
    It does NOT physically delete memories.
    """

    value = _scope_value(
        scope
    )

    half_life = HALF_LIFE_DAYS.get(
        value,
        180.0,
    )

    age = age_days(
        metadata,
        now=now,
    )

    if age <= 0:
        return 1.0

    return math.pow(
        0.5,
        age / half_life,
    )


def effective_importance(
    scope: MemoryScope | str | None,
    metadata: dict[str, Any],
    *,
    now: datetime | None = None,
):
    base = metadata.get(
        "importance",
        default_importance(scope),
    )

    try:
        base = clamp(
            float(base)
        )
    except Exception:
        base = default_importance(
            scope
        )

    return clamp(
        base
        * decay_factor(
            scope,
            metadata,
            now=now,
        )
    )


def _control_id(
    action: str,
    record_id: str,
):

    digest = sha256(
        str(record_id).encode(
            "utf-8"
        )
    ).hexdigest()[:24]

    return (
        f"memory-control-"
        f"{action}-"
        f"{digest}"
    )


def forget_marker_id(
    record_id: str,
):
    return _control_id(
        "forget",
        record_id,
    )


def supersede_marker_id(
    record_id: str,
):
    return _control_id(
        "supersede",
        record_id,
    )


def control_status(
    memory,
    record_id: str | None,
):
    """
    Return:
      active
      forgotten
      superseded
    """

    if not record_id:
        return "active"

    try:
        forgotten = memory.get(
            forget_marker_id(
                record_id
            )
        )
    except Exception:
        forgotten = None

    if forgotten is not None:
        return "forgotten"

    try:
        superseded = memory.get(
            supersede_marker_id(
                record_id
            )
        )
    except Exception:
        superseded = None

    if superseded is not None:
        return "superseded"

    return "active"


def recall_eligible(
    memory,
    item: dict[str, Any],
    *,
    now: datetime | None = None,
):
    """
    Decide whether a memory may participate in recall.
    """

    metadata = item.get(
        "metadata",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):
        metadata = {}

    # Control/tombstone records are never normal memories.
    if metadata.get(
        "memory_control"
    ):
        return False

    state = metadata.get(
        "memory_state",
        "active",
    )

    if state != "active":
        return False

    status = control_status(
        memory,
        item.get(
            "record_id"
        ),
    )

    if status != "active":
        return False

    scope = metadata.get(
        "memory_scope"
    )

    importance = effective_importance(
        scope,
        metadata,
        now=now,
    )

    # Very old low-value memories naturally fall out
    # of active recall, but remain stored.
    if importance < 0.05:
        return False

    return True


def recall_weight(
    item: dict[str, Any],
    *,
    now: datetime | None = None,
):
    """
    Weight available to future ranking logic.
    """

    metadata = item.get(
        "metadata",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):
        metadata = {}

    scope = metadata.get(
        "memory_scope"
    )

    importance = effective_importance(
        scope,
        metadata,
        now=now,
    )

    raw_score = item.get(
        "score"
    )

    try:
        relevance = float(
            raw_score
        )
    except Exception:
        relevance = 1.0

    relevance = clamp(
        relevance
    )

    # Semantic relevance remains dominant.
    return clamp(
        (
            0.75 * relevance
            + 0.25 * importance
        )
    )


def forget_record(
    memory,
    record_id: str,
    *,
    reason: str = "user_request",
):
    """
    Soft-forget a memory.

    No physical SQLite deletion is performed.
    """

    record_id = str(
        record_id or ""
    ).strip()

    if not record_id:
        raise ValueError(
            "record_id cannot be empty"
        )

    existing = memory.get(
        record_id
    )

    if existing is None:
        raise KeyError(
            f"Memory record not found: "
            f"{record_id}"
        )

    marker_id = forget_marker_id(
        record_id
    )

    marker = memory.get(
        marker_id
    )

    if marker is not None:
        return marker

    return memory.remember(
        content=(
            "Memory lifecycle control: "
            f"forget {record_id}"
        ),
        kind="event",
        source="jarvis",
        tags=(
            "memory-control",
            "forget",
        ),
        metadata={
            "memory_control": "forget",
            "target_record_id": record_id,
            "reason": str(reason),
            "created_at": utc_iso(),
        },
        record_id=marker_id,
    )


def mark_superseded(
    memory,
    old_record_id: str,
    new_record_id: str,
):
    """
    Mark an older memory as replaced by a newer memory.
    """

    old_record_id = str(
        old_record_id or ""
    ).strip()

    new_record_id = str(
        new_record_id or ""
    ).strip()

    if not old_record_id:
        raise ValueError(
            "old_record_id cannot be empty"
        )

    if not new_record_id:
        raise ValueError(
            "new_record_id cannot be empty"
        )

    if old_record_id == new_record_id:
        raise ValueError(
            "A memory cannot supersede itself."
        )

    old = memory.get(
        old_record_id
    )

    if old is None:
        raise KeyError(
            f"Old memory not found: "
            f"{old_record_id}"
        )

    new = memory.get(
        new_record_id
    )

    if new is None:
        raise KeyError(
            f"Replacement memory not found: "
            f"{new_record_id}"
        )

    marker_id = (
        supersede_marker_id(
            old_record_id
        )
    )

    existing = memory.get(
        marker_id
    )

    if existing is not None:
        return existing

    return memory.remember(
        content=(
            "Memory lifecycle control: "
            f"{old_record_id} superseded by "
            f"{new_record_id}"
        ),
        kind="event",
        source="jarvis",
        tags=(
            "memory-control",
            "supersede",
        ),
        metadata={
            "memory_control": "supersede",
            "target_record_id": old_record_id,
            "replacement_record_id": new_record_id,
            "created_at": utc_iso(),
        },
        record_id=marker_id,
    )
