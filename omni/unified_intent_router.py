"""Unified deterministic intent routing for JARVIS V8.

This layer sits in front of broad agent/model routing for commands that JARVIS
can understand deterministically, especially operating-system workspace
navigation.  It does not execute broker orders, shell commands, or external
consequential actions.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from omni.jarvis_workspace_orchestrator import interpret_workspace_command


@dataclass(frozen=True)
class IntentDecision:
    kind: str
    route: str
    deterministic: bool
    confidence: float
    response: str
    workspace_actions: tuple[dict[str, Any], ...]
    required_capabilities: tuple[str, ...]
    reasons: tuple[str, ...]
    paper_only: bool = True
    live_execution: bool = False
    automatic_broker_order: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_WORKSPACE_LABELS = {
    "core": "Master JARVIS",
    "chart": "Chart Terminal",
    "quant": "Quant / Strategy Lab",
    "paper": "Paper Trading",
    "research": "Research Intelligence",
    "missions": "Mission Control",
    "system": "System Core",
    "evidence": "Evidence / Approvals",
    "apps": "Computer & Apps",
    "company": "Company OS",
    "legacy": "Legacy Trading Workspace",
}

# Workspaces that are separate services/pages rather than desktop windows.
_DEDICATED_WORKSPACES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("completion center", "project completion", "completion workspace", "engineering cockpit"),
     "Project Completion Center", "http://127.0.0.1:8799/"),
    (("memory fabric", "memory workspace", "memory center"),
     "Memory Fabric", "http://127.0.0.1:8799/?section=memory"),
    (("development workspace", "development center", "codex workspace", "code intelligence"),
     "Development / Code Intelligence", "http://127.0.0.1:8799/?section=engineering"),
    (("model router", "model routing"),
     "Model Router", "http://127.0.0.1:8799/?section=models"),
    (("strategy governance", "champion challenger", "champion/challenger"),
     "Strategy Governance", "http://127.0.0.1:8799/?section=strategies"),
    (("fyers data bridge", "fyers bridge"),
     "FYERS Data Bridge", "http://127.0.0.1:8790/"),
)

_NAVIGATION_VERBS = (
    "open", "show", "launch", "go to", "goto", "switch to", "focus",
    "bring up", "display", "close", "hide", "maximize", "maximise",
    "restore", "save",
)

# These phrases prove that a navigation-looking sentence also asks for domain
# work.  A bare word such as "research" is intentionally not included because
# "open research workspace" is a pure UI command and must not fall through to
# a language model.
_NON_NAVIGATION_MARKERS = (
    "analyze", "analyse", "analysis", "explain", "research the", "research about",
    "research latest", "compare", "find trade", "trade setup", "signal",
    "strategy for", "why", "what is", "what are", "how does", "how is",
    "build", "create", "write", "debug", "fix code", "paper trade",
    "take trade", "execute trade", "monitor",
)


def _clean(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    value = re.sub(
        r"^(?:hey\s+|hi\s+|hello\s+|ok(?:ay)?\s+)?jarvis\s*[,;:\-]?\s*",
        "",
        value,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    return value


def _contains_navigation_verb(lowered: str) -> bool:
    return any(
        lowered == verb
        or lowered.startswith(verb + " ")
        or (" " + verb + " ") in (" " + lowered + " ")
        for verb in _NAVIGATION_VERBS
    )


def _dedicated_actions(text: str) -> list[dict[str, Any]]:
    lowered = _clean(text).lower()
    if not _contains_navigation_verb(lowered):
        return []
    actions: list[dict[str, Any]] = []
    for aliases, label, url in _DEDICATED_WORKSPACES:
        if any(alias in lowered for alias in aliases):
            actions.append(
                {
                    "type": "open_url",
                    "url": url,
                    "label": label,
                    "target": "_blank",
                    "loopback_only": True,
                }
            )
    return actions


def workspace_actions(text: str) -> tuple[dict[str, Any], ...]:
    """Return de-duplicated deterministic UI actions for a command."""

    actions: list[dict[str, Any]] = []
    try:
        actions.extend(dict(item) for item in interpret_workspace_command(text))
    except Exception:
        pass
    actions.extend(_dedicated_actions(text))

    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        key = repr(sorted(action.items()))
        if key in seen:
            continue
        seen.add(key)
        output.append(action)
    return tuple(output)


def is_workspace_control_request(text: str, actions: tuple[dict[str, Any], ...] | None = None) -> bool:
    """True when a request is navigation/layout control rather than domain work."""

    value = _clean(text)
    lowered = value.lower()
    actions = tuple(actions if actions is not None else workspace_actions(value))
    if not value or not actions or not _contains_navigation_verb(lowered):
        return False

    # A compound command such as "open NIFTY and analyze it" must continue to
    # the Quant/domain router after the UI action is emitted.
    if any(marker in lowered for marker in _NON_NAVIGATION_MARKERS):
        return False

    allowed_types = {
        "open_window", "open_url", "close_window", "maximize_window", "layout",
        "close_all", "save_workspace", "restore_workspace", "chart_layout",
    }
    return all(str(action.get("type") or "") in allowed_types for action in actions)


def _action_phrase(action: dict[str, Any]) -> str:
    kind = str(action.get("type") or "")
    if kind == "open_window":
        name = str(action.get("window") or "workspace")
        return "opening " + _WORKSPACE_LABELS.get(name, name.replace("_", " ").title())
    if kind == "open_url":
        return "opening " + str(action.get("label") or "workspace")
    if kind == "close_window":
        name = str(action.get("window") or "workspace")
        return "closing " + _WORKSPACE_LABELS.get(name, name.replace("_", " ").title())
    if kind == "maximize_window":
        name = str(action.get("window") or "workspace")
        return "maximizing " + _WORKSPACE_LABELS.get(name, name.replace("_", " ").title())
    if kind == "layout":
        return "switching to the " + str(action.get("layout") or "requested") + " layout"
    if kind == "close_all":
        return "closing specialist windows"
    if kind == "save_workspace":
        return "saving the workspace layout"
    if kind == "restore_workspace":
        return "restoring the saved workspace layout"
    if kind == "chart_layout":
        return "setting a " + str(action.get("count") or "multi") + "-chart layout"
    return "applying the requested workspace action"


def workspace_response(actions: tuple[dict[str, Any], ...]) -> str:
    phrases = [_action_phrase(dict(action)) for action in actions[:4]]
    if not phrases:
        return "Workspace command accepted."
    if len(phrases) == 1:
        return phrases[0].capitalize() + "."
    return (", ".join(phrases[:-1]) + " and " + phrases[-1]).capitalize() + "."


def route_intent(text: str) -> IntentDecision:
    value = _clean(text)
    lowered = value.lower()
    actions = workspace_actions(value)

    if is_workspace_control_request(value, actions):
        return IntentDecision(
            kind="WORKSPACE_CONTROL",
            route="WORKSPACE_CONTROL",
            deterministic=True,
            confidence=1.0,
            response=workspace_response(actions),
            workspace_actions=actions,
            required_capabilities=("workspace.control",),
            reasons=("Deterministic workspace/navigation grammar matched.",),
        )

    if re.search(r"\b(?:mission|coordinate agents|use multiple agents|run this as a mission)\b", lowered):
        return IntentDecision(
            kind="MISSION",
            route="MISSION_CONTROL",
            deterministic=False,
            confidence=0.86,
            response="Mission orchestration candidate.",
            workspace_actions=actions,
            required_capabilities=("agent.coordinate", "goal.plan"),
            reasons=("Mission/orchestration language detected.",),
        )

    if any(word in lowered for word in ("nifty", "banknifty", "bank nifty", "sensex", "btc", "bitcoin", "eth", "crude", "gold", "trading", "market")):
        return IntentDecision(
            kind="MARKETS",
            route="MARKET_INTELLIGENCE",
            deterministic=False,
            confidence=0.78,
            response="Market-domain request detected.",
            workspace_actions=actions,
            required_capabilities=("market.read", "trading.research"),
            reasons=("Market/instrument language detected.",),
        )

    if any(word in lowered for word in ("code", "python", "debug", "repository", "repo", "function", "class", "test")):
        return IntentDecision(
            kind="ENGINEERING",
            route="ENGINEERING",
            deterministic=False,
            confidence=0.76,
            response="Engineering request detected.",
            workspace_actions=actions,
            required_capabilities=("code.analyze",),
            reasons=("Software/repository language detected.",),
        )

    if any(word in lowered for word in ("health", "system", "diagnose", "repair", "status")):
        return IntentDecision(
            kind="SYSTEM",
            route="SYSTEM_CORE",
            deterministic=False,
            confidence=0.72,
            response="System request detected.",
            workspace_actions=actions,
            required_capabilities=("system.health",),
            reasons=("System/reliability language detected.",),
        )

    return IntentDecision(
        kind="CONVERSATION",
        route="MASTER",
        deterministic=False,
        confidence=0.5,
        response="General Master JARVIS request.",
        workspace_actions=actions,
        required_capabilities=("conversation",),
        reasons=("No deterministic specialist contract matched.",),
    )


__all__ = [
    "IntentDecision",
    "is_workspace_control_request",
    "route_intent",
    "workspace_actions",
    "workspace_response",
]
