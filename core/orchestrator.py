from __future__ import annotations

import json
from typing import Dict, List

from core.executor import ToolExecutor
from core.model import ModelProvider
from core.parser import DecisionParseError, parse_decision
from core.prompts import build_system_prompt
from tools.registry import tool_schemas


class JarvisAgent:
    def __init__(
        self,
        model: ModelProvider,
        *,
        max_steps: int = 8,
    ):
        self.model = model
        self.max_steps = max_steps
        self.executor = ToolExecutor()

    def run(self, user_input: str) -> str:
        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": build_system_prompt(tool_schemas()),
            },
            {
                "role": "user",
                "content": user_input,
            },
        ]

        for step in range(1, self.max_steps + 1):
            raw = self.model.complete(messages)

            try:
                decision = parse_decision(raw)
            except DecisionParseError as exc:
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was not a valid JARVIS decision. "
                        f"Parser error: {exc}. Return ONLY a valid JSON decision."
                    ),
                })
                continue

            if decision.kind == "final":
                return decision.final_text or ""

            assert decision.tool_call is not None

            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "tool": decision.tool_call.name,
                    "arguments": decision.tool_call.arguments,
                }),
            })

            result = self.executor.execute(decision.tool_call)

            messages.append({
                "role": "user",
                "content": (
                    "TOOL OBSERVATION:\n"
                    + json.dumps(result.to_dict(), ensure_ascii=False)
                    + "\nDecide the next action. Use another tool if needed, "
                      "otherwise return a final answer."
                ),
            })

        return (
            f"I could not complete the task safely within {self.max_steps} agent steps."
        )
