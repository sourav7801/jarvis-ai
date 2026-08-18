"""Generalist operator brief used by manager-owned JARVIS missions.

The operator is broad but not omnipotent: it may plan, coordinate, and verify
local reversible work.  Consequential actions remain behind explicit approval
and the canonical tool/agent boundaries.
"""

from __future__ import annotations

import re
from typing import Any


OPERATOR_PATTERNS = (
    r"^\s*(?:universal |general |master )?operator\s*:",
    r"\bdo (?:this|it) end[- ]to[- ]end\b",
    r"\bhandle (?:this|everything) end[- ]to[- ]end\b",
    r"\btake (?:this|the following) from idea to completion\b",
    r"\buse whatever agents (?:are needed|you need)\b",
    r"\bfull autonomous mission\b",
)


def is_operator_request(text: str) -> bool:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return len(clean) >= 12 and any(
        re.search(pattern, clean, flags=re.IGNORECASE)
        for pattern in OPERATOR_PATTERNS
    )


def operator(text: str) -> dict[str, Any]:
    objective = re.sub(r"\s+", " ", str(text or "")).strip()
    mission_match = re.search(
        r"MISSION OBJECTIVE:\s*(.+?)(?:\n\s*\n|$)",
        str(text or ""),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if mission_match:
        objective = re.sub(r"\s+", " ", mission_match.group(1)).strip()
    objective = re.sub(
        r"^(?:jarvis[\s,:-]*)?(?:universal |general |master )?operator\s*:\s*",
        "",
        objective,
        flags=re.IGNORECASE,
    )
    if len(objective) < 8:
        raise ValueError("The Universal Operator requires a concrete objective.")
    return {
        "success": True,
        "type": "universal_operator",
        "message": f"Universal Operator execution brief prepared for: {objective[:500]}",
        "objective": objective[:4_000],
        "deliverable": {
            "current_assessment": (
                "The objective is treated as an outcome to decompose across evidence, "
                "specialist work, verification, artifacts, and approval boundaries."
            ),
            "recommended_sequence": [
                "Define the outcome, constraints, success evidence, and stop conditions.",
                "Select only the agents and approved local tools needed for the objective.",
                "Run independent workstreams concurrently where dependencies allow.",
                "Verify outputs with tests, provenance, critic review, and observable results.",
                "Materialize the result locally and surface each consequential action for approval.",
            ],
            "approval_gate": (
                "Destructive filesystem changes, credentials, spending, external communication, "
                "account creation, contracts, publishing, production deployment, and movement "
                "of funds require explicit scoped approval."
            ),
        },
        "operating_contract": {
            "local_reversible_work": "AUTONOMOUS",
            "read_only_research": "AUTONOMOUS_WITH_PROVENANCE",
            "consequential_external_work": "EXPLICIT_APPROVAL_REQUIRED",
            "live_trading": "DISABLED",
        },
    }
