from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from typing import Any

from omni.memory_scope import use_memory_context
from omni.session_context import get_session_id

from omni.collaboration_runtime import build_runtime

from omni.memory_context import (
    recall_context,
    remember_collaboration,
    remember_salient_input,
)


MAX_INTERNAL_CONTEXT_CHARS = 8000


def _contextual_prompt(
    prompt: str,
    collaboration_context: dict[str, Any] | None,
    memories,
) -> str:
    """
    AgentRequest currently transports text rather than a
    dedicated context field.

    Serialize bounded internal collaboration + memory context
    into the governed request text.
    """

    internal = dict(
        collaboration_context
        or {}
    )

    if memories:

        internal[
            "relevant_memory"
        ] = memories

    if not internal:
        return str(prompt)

    try:
        serialized = json.dumps(
            internal,
            ensure_ascii=False,
            default=str,
        )

    except Exception:
        serialized = str(
            internal
        )

    serialized = serialized[
        :MAX_INTERNAL_CONTEXT_CHARS
    ]

    return (
        f"{prompt}\n\n"
        "[JARVIS INTERNAL CONTEXT]\n"
        "Use this context only when relevant. "
        "The current user request has priority. "
        "Do not invent facts missing from the context.\n"
        f"{serialized}\n"
        "[END JARVIS INTERNAL CONTEXT]"
    )


def _collaborate_in_context(
    request: str,
):
    """
    Memory-aware governed collaboration.

    request
      -> memory recall
      -> Brain plan
      -> specialist collaboration
      -> lead synthesis
      -> successful result remembered
    """

    text = str(
        request or ""
    ).strip()

    if not text:
        raise ValueError(
            "A collaboration request is required."
        )

    memories = recall_context(
        text,
        limit=4,
    )

    runtime = build_runtime()

    def memory_aware_runner(
        agent,
        prompt,
        context,
    ):

        governed_text = (
            _contextual_prompt(
                prompt,
                context,
                memories,
            )
        )

        # AgentRegistry remains the only executor.
        return runtime.runner(
            agent,
            governed_text,
            {},
        )

    result = (
        runtime.engine.collaborate(
            text,
            memory_aware_runner,
        )
    )

    try:
        remember_collaboration(
            text,
            result,
        )

    except Exception:
        # Memory write failure must never destroy a
        # valid governed answer.
        pass

    return result



def collaborate(
    request: str,
    project_id: str | None = None,
    conversation_id: str | None = None,
    channel: str = "main",
):
    """
    Governed collaboration with automatic session context
    and conservative salient-memory capture.
    """

    if conversation_id is None:
        conversation_id = get_session_id(
            channel
        )

    with use_memory_context(
        project_id=project_id,
        conversation_id=conversation_id,
    ):

        try:
            remember_salient_input(
                request,
                project_id=project_id,
            )
        except Exception:
            # Memory capture must never block execution.
            pass

        return _collaborate_in_context(
            request
        )

def result_payload(
    result: Any,
) -> dict[str, Any]:

    if is_dataclass(result):

        data = asdict(
            result
        )

    elif isinstance(
        result,
        dict,
    ):

        data = dict(
            result
        )

    else:

        data = {
            "success": True,
            "final_answer": str(
                result
            ),
        }

    contributions = data.get(
        "contributions",
        [],
    )

    agents = []

    for item in contributions:

        if isinstance(
            item,
            dict,
        ):

            agent = item.get(
                "agent"
            )

            if agent:
                agents.append(
                    agent
                )

    return {
        "success": bool(
            data.get(
                "success",
                True,
            )
        ),
        "intent": data.get(
            "intent"
        ),
        "lead_agent": data.get(
            "lead_agent"
        ),
        "participating_agents": agents,
        "final_answer": str(
            data.get(
                "final_answer",
                "",
            )
        ),
        "contributions": contributions,
    }


def collaborate_payload(
    request: str,
    project_id: str | None = None,
    conversation_id: str | None = None,
    channel: str = "workstation",
):

    try:

        return result_payload(
            collaborate(
                request,
                project_id=project_id,
                conversation_id=conversation_id,
                channel=channel,
            )
        )

    except Exception as exc:

        return {
            "success": False,
            "intent": None,
            "lead_agent": None,
            "participating_agents": [],
            "final_answer": "",
            "contributions": [],
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }
