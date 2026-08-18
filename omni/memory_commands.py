from __future__ import annotations

import re
from typing import Any

from omni.memory_context import (
    forget_memory,
    recall_context,
    recall_scoped,
    remember_salient_input,
    resolve_memory,
    supersede_memory,
)

from omni.memory_scope import (
    MemoryScope,
    normalize_id,
    use_memory_context,
)

from omni.session_context import (
    get_session_id,
)


ALL_SCOPES = (
    MemoryScope.PREFERENCE,
    MemoryScope.PROJECT,
    MemoryScope.DECISION,
    MemoryScope.CONVERSATION,
    MemoryScope.AGENT_FINDING,
)


def _read(
    obj: Any,
    name: str,
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


def _record_id(
    record,
):

    return (
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
    )


def _format_memories(
    results,
):

    if not results:
        return (
            "I don't have an active memory "
            "matching that."
        )

    lines = []

    for index, item in enumerate(
        results,
        1,
    ):

        content = str(
            item.get(
                "content",
                "",
            )
        )

        content = " ".join(
            content.split()
        )

        if len(content) > 220:
            content = (
                content[:217]
                + "..."
            )

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
            "memory_scope",
            item.get(
                "kind",
                "memory",
            ),
        )

        record_id = (
            item.get(
                "record_id"
            )
            or "unknown"
        )

        lines.append(
            f"{index}. [{scope}] "
            f"{content} "
            f"(id: {record_id})"
        )

    return "\n".join(
        lines
    )


def _scope_from_word(
    word: str,
):

    value = str(
        word or ""
    ).lower()

    if "preference" in value:
        return MemoryScope.PREFERENCE

    if "decision" in value:
        return MemoryScope.DECISION

    if "project" in value:
        return MemoryScope.PROJECT

    if (
        "finding" in value
        or "research" in value
    ):
        return MemoryScope.AGENT_FINDING

    if "conversation" in value:
        return MemoryScope.CONVERSATION

    return None


def _unique_target(
    query: str,
    *,
    scopes,
    project_id=None,
):

    results = recall_scoped(
        query,
        scopes=scopes,
        project_id=project_id,
        limit=5,
    )

    if len(results) == 1:
        return results[0], None

    if not results:

        return (
            None,
            "I couldn't find an active "
            "memory matching that.",
        )

    return (
        None,
        "I found multiple matching memories, "
        "so I did not change anything.\n"
        + _format_memories(
            results
        ),
    )


def _replace_by_id(
    record_id: str,
    new_content: str,
):

    memory = resolve_memory()

    old = memory.get(
        record_id
    )

    if old is None:

        return (
            f"I couldn't find memory "
            f"'{record_id}'."
        )

    metadata = _read(
        old,
        "metadata",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):
        metadata = {}

    scope_value = metadata.get(
        "memory_scope"
    )

    if not scope_value:

        return (
            "That legacy memory has no scope metadata, "
            "so I won't replace it automatically."
        )

    try:
        scope = MemoryScope(
            scope_value
        )

    except Exception:

        return (
            "That memory has an unsupported scope."
        )

    new_record = supersede_memory(
        record_id,
        new_content,
        scope,
        project_id=metadata.get(
            "project_id"
        ),
        conversation_id=metadata.get(
            "conversation_id"
        ),
        source="user",
    )

    return (
        "Memory replaced safely. "
        f"Old: {record_id}; "
        f"new: {_record_id(new_record)}."
    )


def memory_command_answer(
    text: str,
    *,
    project_id: str | None = None,
    conversation_id: str | None = None,
    channel: str = "main",
):
    """
    Deterministic natural-language memory commands.

    Normal non-memory commands return None.
    """

    original = str(
        text or ""
    ).strip()

    if not original:
        return None

    lowered = original.lower()

    if conversation_id is None:

        conversation_id = (
            get_session_id(
                channel
            )
        )

    with use_memory_context(
        project_id=project_id,
        conversation_id=conversation_id,
    ):

        # ----------------------------------------------------
        # PROJECT RECALL
        # ----------------------------------------------------

        match = re.match(
            r"^(?:jarvis[,\s]+)?"
            r"(?:what do you remember about|"
            r"what do you know about|recall)\s+"
            r"project\s+(.+?)\??$",
            original,
            re.I,
        )

        if match:

            project_name = (
                match.group(1)
                .strip()
            )

            normalized = normalize_id(
                project_name
            )

            results = recall_scoped(
                project_name,
                scopes=ALL_SCOPES,
                project_id=normalized,
                conversation_id=conversation_id,
                limit=6,
            )

            return _format_memories(
                results
            )


        # ----------------------------------------------------
        # GENERAL RECALL
        # ----------------------------------------------------

        match = re.match(
            r"^(?:jarvis[,\s]+)?"
            r"(?:what do you remember about|"
            r"what do you know about|"
            r"recall(?: memory)? about)\s+"
            r"(.+?)\??$",
            original,
            re.I,
        )

        if match:

            query = (
                match.group(1)
                .strip()
            )

            return _format_memories(
                recall_context(
                    query,
                    limit=6,
                )
            )


        # ----------------------------------------------------
        # FORGET BY ID
        # ----------------------------------------------------

        match = re.match(
            r"^(?:jarvis[,\s]+)?"
            r"forget memory\s+"
            r"([a-zA-Z0-9_.-]+)\s*$",
            original,
            re.I,
        )

        if match:

            record_id = match.group(
                1
            )

            try:

                forget_memory(
                    record_id,
                    reason=(
                        "explicit_user_command"
                    ),
                )

            except KeyError:

                return (
                    f"I couldn't find memory "
                    f"'{record_id}'."
                )

            return (
                f"Memory {record_id} is now "
                "logically forgotten."
            )


        # ----------------------------------------------------
        # FORGET BY QUERY + SCOPE
        # ----------------------------------------------------

        match = re.match(
            r"^(?:jarvis[,\s]+)?"
            r"forget\s+(?:that\s+|the\s+)?"
            r"(decision|preference|project memory|"
            r"finding|research finding|"
            r"conversation memory)"
            r"\s+(?:about|regarding)\s+"
            r"(.+?)\s*$",
            original,
            re.I,
        )

        if match:

            scope = _scope_from_word(
                match.group(1)
            )

            query = (
                match.group(2)
                .strip()
            )

            target, error = (
                _unique_target(
                    query,
                    scopes=(
                        scope,
                    ),
                    project_id=project_id,
                )
            )

            if error:
                return error

            record_id = target.get(
                "record_id"
            )

            if not record_id:

                return (
                    "That memory has no stable ID, "
                    "so I did not modify it."
                )

            forget_memory(
                record_id,
                reason="explicit_user_command",
            )

            return (
                f"Memory {record_id} is now "
                "logically forgotten."
            )


        # ----------------------------------------------------
        # REPLACE BY ID
        # ----------------------------------------------------

        match = re.match(
            r"^(?:jarvis[,\s]+)?"
            r"replace memory\s+"
            r"([a-zA-Z0-9_.-]+)"
            r"\s+with\s+(.+)$",
            original,
            re.I | re.S,
        )

        if match:

            return _replace_by_id(
                match.group(1),
                match.group(2).strip(),
            )


        # ----------------------------------------------------
        # EXPLICIT REMEMBER
        # ----------------------------------------------------

        if re.match(
            r"^(?:jarvis[,\s]+)?"
            r"(?:please\s+)?"
            r"remember (?:that\s+)?",
            original,
            re.I,
        ):

            record = (
                remember_salient_input(
                    original,
                    project_id=project_id,
                )
            )

            if record is None:

                return (
                    "I did not store that because "
                    "it did not pass the durable "
                    "memory policy."
                )

            record_id = _record_id(
                record
            )

            return (
                "Remembered."
                + (
                    f" Memory id: "
                    f"{record_id}."
                    if record_id
                    else ""
                )
            )


        # ----------------------------------------------------
        # EXPLICIT CHANGE / CONTRADICTION
        # ----------------------------------------------------

        if (
            re.search(
                r"\bchange my preference from\b",
                lowered,
            )
            or
            re.search(
                r"\bchange (?:our|the) "
                r"decision from\b",
                lowered,
            )
        ):

            record = (
                remember_salient_input(
                    original,
                    project_id=project_id,
                )
            )

            if record is None:

                return (
                    "I could not classify that as "
                    "a durable memory change."
                )

            return (
                "Memory updated."
                + (
                    f" New memory id: "
                    f"{_record_id(record)}."
                    if _record_id(record)
                    else ""
                )
            )


    return None
