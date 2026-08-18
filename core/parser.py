from __future__ import annotations

import json
from typing import Any, Dict

from core.types import AgentDecision, ToolCall


class DecisionParseError(ValueError):
    pass


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise DecisionParseError("Model response did not contain valid JSON.")
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise DecisionParseError(f"Invalid JSON from model: {exc}") from exc

    if not isinstance(value, dict):
        raise DecisionParseError("Model decision must be a JSON object.")

    return value


def parse_decision(text: str) -> AgentDecision:
    payload = _extract_json(text)

    # Compatibility with the old Jarvis format:
    # {"action":"current_time", ...}
    # is normalized to the new tool-call format.
    tool_name = payload.get("tool") or payload.get("action")

    if tool_name:
        arguments = payload.get("arguments") or payload.get("args") or {}
        if not isinstance(arguments, dict):
            raise DecisionParseError("'arguments' must be a JSON object.")

        # Critical safety/reliability rule:
        # Any "response" supplied alongside a tool request is ignored.
        # The actual Python tool result is the source of truth.
        return AgentDecision(
            kind="tool_call",
            tool_call=ToolCall(name=str(tool_name), arguments=arguments),
            raw=payload,
        )

    final_text = (
        payload.get("final")
        or payload.get("answer")
        or payload.get("response")
    )

    if isinstance(final_text, str) and final_text.strip():
        return AgentDecision(
            kind="final",
            final_text=final_text.strip(),
            raw=payload,
        )

    raise DecisionParseError(
        "Decision must contain either a tool/action field or a final/answer/response field."
    )
