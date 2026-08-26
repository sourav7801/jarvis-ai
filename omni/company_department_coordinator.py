"""Bounded parallel department coordination for Company OS ventures.

The coordinator produces local, reviewable department briefs.  It has no tool
surface for publishing, spending, filing, hiring, contacting people, moving
funds, or placing broker orders.  Production execution is supplied through the
governed AgentRegistry by the caller, which keeps the execution boundary
auditable and easy to replace in tests.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Iterable


DepartmentExecutor = Callable[[str, str, str], dict[str, Any]]


@dataclass(frozen=True)
class DepartmentAssignment:
    department_id: str
    registry_agent: str
    outcome: str


ASSIGNMENTS: tuple[DepartmentAssignment, ...] = (
    DepartmentAssignment("executive", "strategy", "venture decisions, kill criteria, and measurable gates"),
    DepartmentAssignment("research", "research", "citation-first customer, market, competitor, and constraint evidence"),
    DepartmentAssignment("product", "product", "MVP scope, non-goals, acceptance evidence, and learning metrics"),
    DepartmentAssignment("engineering", "engineering", "testable architecture, delivery slices, observability, and rollback"),
    DepartmentAssignment("data_ai", "data_ai", "data contracts, evaluations, quality controls, and failure modes"),
    DepartmentAssignment("design", "design", "accessible user journeys, prototype plan, and usability tests"),
    DepartmentAssignment("security", "security", "threat model, controls, verification, and incident readiness"),
    DepartmentAssignment("legal", "legal", "legal questions and a qualified-professional review checklist"),
    DepartmentAssignment("finance", "finance", "unit economics, budget scenarios, runway gates, and controls"),
    DepartmentAssignment("operations", "operations", "SOPs, ownership, service levels, exceptions, and cadence"),
    DepartmentAssignment("marketing", "marketing", "positioning and draft experiments with measurable evidence"),
    DepartmentAssignment("sales", "sales", "ICP, qualification, discovery, proposal, and pipeline design"),
    DepartmentAssignment("customer_success", "customer_success", "onboarding, support, retention, and feedback loops"),
    DepartmentAssignment("people", "people", "role scorecards, hiring sequence, onboarding, and team-health controls"),
    DepartmentAssignment("quality", "quality", "acceptance evidence, risk register, test plan, and release gates"),
    DepartmentAssignment("trading_research", "trading", "paper-only market research when relevant; otherwise an explicit not-applicable result"),
)


def _prompt(plan: dict[str, Any], assignment: DepartmentAssignment) -> str:
    idea = str(plan.get("idea") or "").strip()
    company = str(plan.get("company_name") or "New Venture").strip()
    return (
        f"MISSION OBJECTIVE: Build a supervised evidence-first operating packet for {company}.\n\n"
        f"VENTURE IDEA: {idea}\n\n"
        f"DEPARTMENT OUTCOME: Produce {assignment.outcome}.\n\n"
        "Return a concise local brief with assumptions, dependencies, evidence required, "
        "30/90-day actions, year-1 decision gates, risks, and measurable acceptance criteria. "
        "Do not claim that public research, interviews, prototypes, accounts, posts, outreach, "
        "contracts, filings, hiring, production deployment, payments, or trades were completed. "
        "External communication, publishing, spending, identity/account actions, legal actions, "
        "production deployment, and live trading require explicit human approval."
    )


def coordinate_departments(
    plan: dict[str, Any],
    executor: DepartmentExecutor,
    *,
    assignments: Iterable[DepartmentAssignment] = ASSIGNMENTS,
    max_workers: int = 6,
) -> dict[str, Any]:
    """Run each department through the supplied governed executor."""

    selected = tuple(assignments)
    if not selected:
        raise ValueError("At least one department assignment is required.")
    started = time.perf_counter()
    plan_id = str(plan.get("id") or "company-plan")
    results: dict[str, dict[str, Any]] = {}

    def run_one(assignment: DepartmentAssignment) -> dict[str, Any]:
        item_started = time.perf_counter()
        correlation_id = f"company:{plan_id}:{assignment.department_id}"
        try:
            response = executor(
                assignment.registry_agent,
                _prompt(plan, assignment),
                correlation_id,
            )
            success = bool(response.get("success"))
            return {
                "department_id": assignment.department_id,
                "agent": assignment.registry_agent,
                "status": "LOCAL_BRIEF_READY" if success else "FAILED_SAFE",
                "success": success,
                "message": str(response.get("message") or "")[:2_000],
                "output": response.get("data") if isinstance(response.get("data"), dict) else None,
                "error_type": response.get("error_type"),
                "correlation_id": correlation_id,
                "duration_ms": round((time.perf_counter() - item_started) * 1_000, 2),
            }
        except Exception as error:  # each department must fail independently
            return {
                "department_id": assignment.department_id,
                "agent": assignment.registry_agent,
                "status": "FAILED_SAFE",
                "success": False,
                "message": f"{assignment.department_id} failed safely.",
                "output": None,
                "error_type": type(error).__name__,
                "correlation_id": correlation_id,
                "duration_ms": round((time.perf_counter() - item_started) * 1_000, 2),
            }

    with ThreadPoolExecutor(
        max_workers=min(max(int(max_workers), 1), 8, len(selected)),
        thread_name_prefix="jarvis-company",
    ) as pool:
        futures = {pool.submit(run_one, item): item.department_id for item in selected}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    ordered = [results[item.department_id] for item in selected]
    successes = sum(1 for item in ordered if item["success"])
    return {
        "plan_id": plan_id,
        "status": "LOCAL_DEPARTMENT_PACKET_READY" if successes == len(ordered) else "LOCAL_DEPARTMENT_PACKET_DEGRADED",
        "department_count": len(ordered),
        "successful_departments": successes,
        "failed_departments": len(ordered) - successes,
        "results": ordered,
        "external_actions_executed": False,
        "live_execution": False,
        "approval_boundary": (
            "Publishing, outreach, spending, accounts, contracts, filings, hiring, production actions, "
            "movement of funds, and live trading remain locked."
        ),
        "duration_ms": round((time.perf_counter() - started) * 1_000, 2),
    }

