"""Fail-closed risk-policy enforcement and result verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    risk: str
    reason: str


def authorize_tool(
    tool_name: str,
    risk: str,
    required_capabilities=frozenset(),
    approved_capabilities=frozenset(),
) -> SafetyDecision:
    normalized = str(risk or "CRITICAL").upper().strip()
    if normalized not in RISK_LEVELS:
        return SafetyDecision(
            False,
            "CRITICAL",
            f"Tool '{tool_name}' has an unknown risk classification.",
        )
    required = frozenset(required_capabilities)
    approved = frozenset(approved_capabilities)
    if normalized in {"HIGH", "CRITICAL"} and (
        not required or not required.issubset(approved)
    ):
        return SafetyDecision(
            False,
            normalized,
            (
                f"Tool '{tool_name}' requires explicit approval, but no "
                "trusted approval channel is configured."
            ),
        )
    return SafetyDecision(True, normalized, "Allowed by local policy.")


def verify_tool_result(result) -> dict:
    """Return a small, consistent post-execution verification record."""
    if isinstance(result, dict):
        success = bool(result.get("success", False))
        return {
            "verified": success,
            "message": result.get("message", str(result)),
        }
    return {
        "verified": result is not None,
        "message": str(result),
    }


def verify_tool_postcondition(tool_name: str, arguments: dict, result) -> dict:
    """Apply deterministic checks available after a registered tool runs."""
    base = verify_tool_result(result)
    if not base["verified"]:
        return base

    if isinstance(result, dict) and result.get("tool") not in {None, tool_name}:
        return {
            "verified": False,
            "message": "Tool result identity did not match the requested tool.",
        }

    path_checks = {
        "open_folder": "directory",
        "list_files": "directory",
        "search_files": "directory",
        "open_file": "file",
    }
    expected = path_checks.get(tool_name)
    if expected:
        path = Path(str(arguments.get("path", ""))).expanduser()
        exists = path.is_dir() if expected == "directory" else path.is_file()
        if not exists:
            return {
                "verified": False,
                "message": f"Postcondition failed: expected {expected} is unavailable.",
            }

    if tool_name == "current_time" and "Current date and time:" not in base["message"]:
        return {
            "verified": False,
            "message": "Postcondition failed: time response format is invalid.",
        }

    return base
