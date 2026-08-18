"""Bounded specialist entrypoints used by the governed company operating system."""

from __future__ import annotations

import re
from typing import Any


ROLE_GUIDANCE: dict[str, tuple[str, tuple[str, ...]]] = {
    "strategy": ("Executive Strategy", ("objective", "assumptions", "options", "decision criteria", "next evidence")),
    "product": ("Product", ("user outcome", "MVP scope", "non-goals", "acceptance criteria", "learning metric")),
    "engineering": ("Engineering", ("architecture", "interfaces", "delivery slices", "tests", "operational risks")),
    "data_ai": ("Data & AI", ("data contract", "evaluation", "model approach", "quality controls", "failure modes")),
    "design": ("Experience Design", ("primary journey", "interaction model", "accessibility", "prototype", "usability test")),
    "security": ("Security", ("assets", "threats", "controls", "verification", "incident response")),
    "legal": ("Legal & Compliance Research", ("jurisdictions", "legal questions", "policies", "evidence", "professional review")),
    "finance": ("Finance", ("revenue drivers", "cost drivers", "unit economics", "runway scenarios", "controls")),
    "operations": ("Operations", ("workflow", "owners", "service levels", "exceptions", "operating cadence")),
    "marketing": ("Marketing", ("audience", "positioning", "channels", "experiments", "measurement")),
    "sales": ("Sales", ("ideal customer", "qualification", "discovery", "proposal", "pipeline metrics")),
    "customer_success": ("Customer Success", ("onboarding", "time to value", "support", "health signals", "feedback loop")),
    "people": ("People Operations", ("roles", "scorecards", "hiring sequence", "onboarding", "team health")),
    "quality": ("Quality & Risk", ("acceptance evidence", "risk register", "test strategy", "release gates", "monitoring")),
}


def _analyze(role: str, text: str) -> dict[str, Any]:
    objective = re.sub(r"\s+", " ", str(text or "")).strip()
    if not objective:
        raise ValueError("A department objective is required.")
    mission_match = re.search(
        r"MISSION OBJECTIVE:\s*(.+?)(?:\n\s*\n|$)",
        str(text or ""),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if mission_match:
        objective = re.sub(r"\s+", " ", mission_match.group(1)).strip()
    label, lenses = ROLE_GUIDANCE[role]
    return {
        "message": f"{label} brief prepared for: {objective[:500]}",
        "department": label,
        "objective": objective[:4_000],
        "analysis_lenses": list(lenses),
        "deliverable": {
            "current_assessment": "Evidence is required before treating the request's assumptions as facts.",
            "recommended_sequence": [
                f"Define the {lenses[0]}.",
                f"Document the {lenses[1]}.",
                f"Test the {lenses[2]} with measurable evidence.",
                f"Review {lenses[3]} before committing resources.",
                f"Track {lenses[4]} and revise the plan.",
            ],
            "approval_gate": "Any external communication, spending, contract, account, filing, hiring decision, or production action requires explicit human approval.",
        },
    }


def strategy(text: str) -> dict[str, Any]: return _analyze("strategy", text)
def product(text: str) -> dict[str, Any]: return _analyze("product", text)
def engineering(text: str) -> dict[str, Any]: return _analyze("engineering", text)
def data_ai(text: str) -> dict[str, Any]: return _analyze("data_ai", text)
def design(text: str) -> dict[str, Any]: return _analyze("design", text)
def security(text: str) -> dict[str, Any]: return _analyze("security", text)
def legal(text: str) -> dict[str, Any]: return _analyze("legal", text)
def finance(text: str) -> dict[str, Any]: return _analyze("finance", text)
def operations(text: str) -> dict[str, Any]: return _analyze("operations", text)
def marketing(text: str) -> dict[str, Any]: return _analyze("marketing", text)
def sales(text: str) -> dict[str, Any]: return _analyze("sales", text)
def customer_success(text: str) -> dict[str, Any]: return _analyze("customer_success", text)
def people(text: str) -> dict[str, Any]: return _analyze("people", text)
def quality(text: str) -> dict[str, Any]: return _analyze("quality", text)
