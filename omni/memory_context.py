from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable

from omni.hybrid_memory import HybridMemory
from omni.runtime import get_memory_store

from omni.memory_salience import classify_salience

from omni.memory_contradiction import (
    explicit_replacement_hint,
)

from omni.memory_lifecycle import (
    enrich_lifecycle_metadata,
    forget_record,
    mark_superseded,
    recall_eligible,
    recall_weight,
)

from omni.memory_scope import (
    MemoryScope,
    current_memory_context,
    normalize_id,
)


def resolve_memory() -> HybridMemory:

    memory = get_memory_store()

    if not isinstance(
        memory,
        HybridMemory,
    ):
        raise RuntimeError(
            "Invalid canonical HybridMemory store."
        )

    return memory


def _read(
    obj,
    name,
    default=None,
):

    if isinstance(obj, dict):
        return obj.get(
            name,
            default,
        )

    return getattr(
        obj,
        name,
        default,
    )


def _record(hit):

    value = _read(
        hit,
        "record",
        None,
    )

    return (
        value
        if value is not None
        else hit
    )


def _normalize_hit(hit):

    record = _record(hit)

    content = _read(
        record,
        "content",
        None,
    )

    if not isinstance(
        content,
        str,
    ):
        return None

    content = content.strip()

    if not content:
        return None

    metadata = _read(
        record,
        "metadata",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):
        metadata = {}

    tags = _read(
        record,
        "tags",
        (),
    )

    if not isinstance(
        tags,
        (tuple, list, set, frozenset),
    ):
        tags = ()

    return {
        "record_id": (
            _read(
                record,
                "record_id",
                None,
            )
            or
            _read(
                record,
                "id",
                None,
            )
        ),
        "content": content[:2000],
        "kind": _read(
            record,
            "kind",
            None,
        ),
        "source": _read(
            record,
            "source",
            None,
        ),
        "score": (
            _read(
                hit,
                "score",
                None,
            )
            or
            _read(
                hit,
                "semantic_score",
                None,
            )
            or
            _read(
                hit,
                "lexical_score",
                None,
            )
        ),
        "tags": tuple(
            str(x)
            for x in tags
        ),
        "metadata": metadata,
    }


def _item_scope(item):

    metadata = item.get(
        "metadata",
        {},
    )

    value = metadata.get(
        "memory_scope"
    )

    if value:
        return str(value)

    for tag in item.get(
        "tags",
        (),
    ):
        if tag.startswith(
            "scope:"
        ):
            return tag.split(
                ":",
                1,
            )[1]

    return None


def _item_project(item):

    metadata = item.get(
        "metadata",
        {},
    )

    value = metadata.get(
        "project_id"
    )

    if value:
        return normalize_id(
            value
        )

    for tag in item.get(
        "tags",
        (),
    ):
        if tag.startswith(
            "project:"
        ):
            return normalize_id(
                tag.split(
                    ":",
                    1,
                )[1]
            )

    return None


def _item_conversation(item):

    metadata = item.get(
        "metadata",
        {},
    )

    value = metadata.get(
        "conversation_id"
    )

    if value:
        return normalize_id(
            value
        )

    for tag in item.get(
        "tags",
        (),
    ):
        if tag.startswith(
            "conversation:"
        ):
            return normalize_id(
                tag.split(
                    ":",
                    1,
                )[1]
            )

    return None


def remember_scoped(
    content: str,
    scope: MemoryScope | str,
    *,
    source: str = "user",
    project_id: str | None = None,
    conversation_id: str | None = None,
    tags: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
    record_id: str | None = None,
):

    text = str(
        content or ""
    ).strip()

    if not text:
        raise ValueError(
            "Memory content cannot be empty."
        )

    scope = MemoryScope(
        str(
            getattr(
                scope,
                "value",
                scope,
            )
        )
    )

    active = (
        current_memory_context()
    )

    explicit_project = normalize_id(
        project_id
    )

    explicit_conversation = normalize_id(
        conversation_id
    )

    # Preferences are durable/global unless explicitly scoped.
    if scope == MemoryScope.PREFERENCE:

        project_id = explicit_project
        conversation_id = explicit_conversation

    # Decisions inherit project context but not an ephemeral
    # conversation unless explicitly requested.
    elif scope == MemoryScope.DECISION:

        project_id = (
            explicit_project
            or active.project_id
        )

        conversation_id = explicit_conversation

    # Project state belongs to the project.
    elif scope == MemoryScope.PROJECT:

        project_id = (
            explicit_project
            or active.project_id
        )

        conversation_id = explicit_conversation

    # Conversation and agent findings may inherit both.
    else:

        project_id = (
            explicit_project
            or active.project_id
        )

        conversation_id = (
            explicit_conversation
            or active.conversation_id
        )

    project_id = normalize_id(
        project_id
    )

    conversation_id = normalize_id(
        conversation_id
    )

    final_tags = [
        f"scope:{scope.value}",
    ]

    if project_id:
        final_tags.append(
            f"project:{project_id}"
        )

    if conversation_id:
        final_tags.append(
            f"conversation:{conversation_id}"
        )

    final_tags.extend(
        str(tag)
        for tag in tags
    )

    final_metadata = dict(
        metadata or {}
    )

    final_metadata[
        "memory_scope"
    ] = scope.value

    if project_id:
        final_metadata[
            "project_id"
        ] = project_id

    if conversation_id:
        final_metadata[
            "conversation_id"
        ] = conversation_id

    final_metadata = enrich_lifecycle_metadata(
        scope,
        final_metadata,
    )

    if record_id is None:

        digest = sha256(
            (
                scope.value
                + "\n"
                + str(project_id)
                + "\n"
                + str(conversation_id)
                + "\n"
                + text
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:24]

        record_id = (
            f"{scope.value}-{digest}"
        )

    memory = resolve_memory()

    try:
        existing = memory.get(
            record_id
        )
    except Exception:
        existing = None

    if existing is not None:
        return existing

    kind = (
        "semantic"
        if scope
        in {
            MemoryScope.PREFERENCE,
            MemoryScope.PROJECT,
        }
        else "event"
    )

    return memory.remember(
        content=text[:7000],
        kind=kind,
        source=source,
        tags=tuple(
            dict.fromkeys(
                final_tags
            )
        ),
        metadata=final_metadata,
        record_id=record_id,
    )


def recall_scoped(
    query: str,
    *,
    scopes: Iterable[
        MemoryScope | str
    ],
    project_id: str | None = None,
    conversation_id: str | None = None,
    limit: int = 6,
    include_unscoped: bool = False,
):

    text = str(
        query or ""
    ).strip()

    if not text:
        return ()

    active = (
        current_memory_context()
    )

    project_id = normalize_id(
        project_id
        or active.project_id
    )

    conversation_id = normalize_id(
        conversation_id
        or active.conversation_id
    )

    wanted = {
        MemoryScope(
            str(
                getattr(
                    scope,
                    "value",
                    scope,
                )
            )
        ).value
        for scope in scopes
    }

    limit = max(
        1,
        min(
            int(limit),
            12,
        ),
    )

    memory = resolve_memory()

    search_limit = min(
        max(
            limit * 6,
            20,
        ),
        60,
    )

    try:
        hits = memory.search(
            text,
            limit=search_limit,
        )

    except Exception:

        try:
            hits = memory.lexical_search(
                text,
                limit=search_limit,
            )
        except Exception:
            return ()

    selected = []
    seen = set()

    for hit in hits:

        item = _normalize_hit(
            hit
        )

        if item is None:
            continue

        if not recall_eligible(
            memory,
            item,
        ):
            continue

        item[
            "lifecycle_score"
        ] = recall_weight(
            item
        )

        scope = _item_scope(
            item
        )

        if scope is None:

            if not include_unscoped:
                continue

        elif scope not in wanted:
            continue

        item_project = (
            _item_project(item)
        )

        item_conversation = (
            _item_conversation(
                item
            )
        )

        # Never leak another project's memory.
        if item_project:

            if not project_id:
                continue

            if (
                item_project
                != project_id
            ):
                continue

        # Any record explicitly bound to a conversation
        # may only be recalled inside that same conversation.
        # This also protects conversation-bound agent findings
        # and decisions from leaking into another session.
        if item_conversation:

            if not conversation_id:
                continue

            if (
                item_conversation
                != conversation_id
            ):
                continue

        if (
            scope
            == MemoryScope.
            CONVERSATION.value
            and not item_conversation
        ):
            continue

        identity = (
            item["record_id"]
            or item["content"]
        )

        if identity in seen:
            continue

        seen.add(
            identity
        )

        selected.append(
            item
        )

        if len(selected) >= limit:
            break

    return tuple(selected)


def recall_context(
    request: str,
    limit: int = 4,
):
    """
    Default context used by JARVIS collaboration.

    Global:
      preferences
      decisions
      agent findings

    With active project:
      project memories

    With active conversation:
      current conversation memory

    Legacy unscoped records are retained for backward
    compatibility.
    """

    active = (
        current_memory_context()
    )

    scopes = [
        MemoryScope.PREFERENCE,
        MemoryScope.DECISION,
        MemoryScope.AGENT_FINDING,
    ]

    if active.project_id:
        scopes.append(
            MemoryScope.PROJECT
        )

    if active.conversation_id:
        scopes.append(
            MemoryScope.CONVERSATION
        )

    return recall_scoped(
        request,
        scopes=scopes,
        project_id=active.project_id,
        conversation_id=(
            active.conversation_id
        ),
        limit=limit,
        include_unscoped=True,
    )


def remember_preference(
    content: str,
):
    return remember_scoped(
        content,
        MemoryScope.PREFERENCE,
        source="user",
    )


def remember_project(
    project_id: str,
    content: str,
):
    return remember_scoped(
        content,
        MemoryScope.PROJECT,
        source="user",
        project_id=project_id,
    )


def remember_decision(
    content: str,
    *,
    project_id: str | None = None,
):
    return remember_scoped(
        content,
        MemoryScope.DECISION,
        source="user",
        project_id=project_id,
    )


def remember_conversation(
    content: str,
    *,
    conversation_id: str,
    project_id: str | None = None,
):
    return remember_scoped(
        content,
        MemoryScope.CONVERSATION,
        source="conversation",
        project_id=project_id,
        conversation_id=conversation_id,
    )


def remember_agent_finding(
    content: str,
    *,
    project_id: str | None = None,
):
    return remember_scoped(
        content,
        MemoryScope.AGENT_FINDING,
        source="jarvis",
        project_id=project_id,
    )


def remember_collaboration(
    request: str,
    result: Any,
):

    success = bool(
        getattr(
            result,
            "success",
            False,
        )
    )

    answer = getattr(
        result,
        "final_answer",
        None,
    )

    if not success:
        return None

    if not isinstance(
        answer,
        str,
    ):
        return None

    answer = answer.strip()

    if not answer:
        return None

    intent = str(
        getattr(
            result,
            "intent",
            "",
        )
        or ""
    )

    lead = str(
        getattr(
            result,
            "lead_agent",
            "",
        )
        or ""
    )

    content = (
        "JARVIS collaboration outcome\n"
        f"Request: {str(request)[:2000]}\n"
        f"Answer: {answer[:5000]}"
    )

    return remember_scoped(
        content,
        MemoryScope.AGENT_FINDING,
        source="jarvis",
        tags=tuple(
            x
            for x in (
                "collaboration",
                (
                    f"intent:{intent}"
                    if intent
                    else None
                ),
                (
                    f"lead:{lead}"
                    if lead
                    else None
                ),
            )
            if x
        ),
        metadata={
            "request": str(
                request
            )[:2000],
            "intent": intent,
            "lead_agent": lead,
            "success": True,
        },
    )



def remember_salient_input(
    content: str,
    *,
    project_id: str | None = None,
):
    """
    Persist only durable/salient input.

    Automatic supersession requires:
      1. explicit replacement wording
      2. exactly one matching old memory
    """

    active = current_memory_context()

    effective_project = normalize_id(
        project_id
        or active.project_id
    )

    decision = classify_salience(
        content,
        has_project=bool(
            effective_project
        ),
    )

    if not decision.remember:
        return None

    hint = explicit_replacement_hint(
        content,
        decision.scope,
    )

    previous = ()

    if hint is not None:

        try:
            previous = recall_scoped(
                hint.old_query,
                scopes=(
                    hint.scope,
                ),
                project_id=effective_project,
                limit=3,
            )

        except Exception:
            previous = ()

    new_record = remember_scoped(
        content,
        decision.scope,
        source="user",
        project_id=effective_project,
        metadata={
            "automatic_salience": True,
            "salience_score":
                decision.score,
            "salience_reason":
                decision.reason,
        },
    )

    if (
        hint is not None
        and len(previous) == 1
    ):

        old_id = previous[0].get(
            "record_id"
        )

        new_id = (
            getattr(
                new_record,
                "record_id",
                None,
            )
            or
            getattr(
                new_record,
                "id",
                None,
            )
        )

        if (
            old_id
            and new_id
            and str(old_id) != str(new_id)
        ):

            try:
                mark_superseded(
                    resolve_memory(),
                    str(old_id),
                    str(new_id),
                )

            except Exception:
                pass

    return new_record


def forget_memory(
    record_id: str,
    *,
    reason: str = "user_request",
):
    """
    Logically forget a memory without physically deleting it.
    """

    return forget_record(
        resolve_memory(),
        record_id,
        reason=reason,
    )


def supersede_memory(
    old_record_id: str,
    new_content: str,
    scope: MemoryScope | str,
    *,
    project_id: str | None = None,
    conversation_id: str | None = None,
    source: str = "user",
):
    """
    Create a replacement memory and mark the old memory
    as superseded.
    """

    new_record = remember_scoped(
        new_content,
        scope,
        source=source,
        project_id=project_id,
        conversation_id=conversation_id,
    )

    new_record_id = (
        getattr(
            new_record,
            "record_id",
            None,
        )
        or
        getattr(
            new_record,
            "id",
            None,
        )
    )

    if new_record_id is None:

        if isinstance(
            new_record,
            dict,
        ):
            new_record_id = (
                new_record.get(
                    "record_id"
                )
                or
                new_record.get(
                    "id"
                )
            )

    if not new_record_id:
        raise RuntimeError(
            "Replacement memory did not expose "
            "a record ID."
        )

    mark_superseded(
        resolve_memory(),
        old_record_id,
        str(new_record_id),
    )

    return new_record
