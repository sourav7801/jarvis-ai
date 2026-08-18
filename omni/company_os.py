"""Governed idea-to-company planning and department-agent coordination.

This module deliberately separates autonomous local planning from consequential
external actions.  It can create a complete operating blueprint and task graph,
but legal registration, payments, outbound messages, contracts, hiring, and live
trading always remain approval-gated.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from .runtime import audit_event


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DepartmentAgent:
    id: str
    name: str
    department: str
    mission: str
    capabilities: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    autonomy: str = "SUPERVISED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


COMMON_PROHIBITIONS = (
    "No spending, payments, or financial commitments without explicit approval.",
    "No outbound messages, publishing, or account creation without explicit approval.",
    "No legal representation, signatures, or regulatory filings.",
    "No live trades or movement of customer or company funds.",
)


DEPARTMENT_AGENTS: tuple[DepartmentAgent, ...] = (
    DepartmentAgent(
        "executive",
        "Executive Strategy Agent",
        "Executive Office",
        "Turn an idea into priorities, assumptions, decisions, and measurable outcomes.",
        ("strategy", "decision briefs", "OKRs", "portfolio coordination"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "research",
        "Market Research Agent",
        "Research",
        "Build evidence packs for customers, competitors, markets, and risks.",
        ("market mapping", "competitor analysis", "source synthesis", "assumption tests"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "product",
        "Product Agent",
        "Product",
        "Define the smallest valuable product and keep delivery tied to user outcomes.",
        ("product requirements", "roadmaps", "user stories", "prioritization"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "engineering",
        "Engineering Agent",
        "Engineering",
        "Design and build reliable, testable, observable software systems.",
        ("architecture", "implementation plans", "code review", "release readiness"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "data_ai",
        "Data & AI Agent",
        "Data and AI",
        "Create governed data products, evaluations, models, and decision intelligence.",
        ("data design", "model evaluation", "analytics", "AI safety"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "design",
        "Experience Design Agent",
        "Design",
        "Translate user needs into accessible flows, interfaces, and design systems.",
        ("UX flows", "information architecture", "prototypes", "accessibility"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "security",
        "Security Agent",
        "Security",
        "Reduce technical and operational risk through threat-aware design and controls.",
        ("threat modeling", "control review", "secrets hygiene", "incident planning"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "legal",
        "Legal & Compliance Agent",
        "Legal and Compliance",
        "Identify questions, evidence, and professional review required for compliant operation.",
        ("issue spotting", "compliance checklists", "policy drafts", "review routing"),
        COMMON_PROHIBITIONS
        + ("Produces research and drafts only; it is not a lawyer or legal advice.",),
    ),
    DepartmentAgent(
        "finance",
        "Finance Agent",
        "Finance",
        "Model unit economics, budgets, scenarios, runway, and financial controls.",
        ("unit economics", "scenario models", "budgets", "management reporting"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "operations",
        "Operations Agent",
        "Operations",
        "Design repeatable processes, service levels, controls, and operating cadence.",
        ("SOPs", "capacity plans", "vendor criteria", "operating reviews"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "marketing",
        "Marketing Agent",
        "Marketing",
        "Develop positioning, ethical acquisition experiments, and measurable campaigns.",
        ("positioning", "content drafts", "channel tests", "campaign analytics"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "sales",
        "Sales Agent",
        "Sales",
        "Build qualification, discovery, proposals, and forecast processes.",
        ("ICP definition", "discovery guides", "proposal drafts", "pipeline design"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "customer_success",
        "Customer Success Agent",
        "Customer Success",
        "Design onboarding, support, retention, and voice-of-customer loops.",
        ("onboarding", "support playbooks", "health scoring", "feedback analysis"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "people",
        "People Operations Agent",
        "People",
        "Plan roles, hiring criteria, onboarding, and healthy operating practices.",
        ("role design", "interview rubrics", "onboarding", "team health"),
        COMMON_PROHIBITIONS
        + ("No hiring, firing, surveillance, or employment decisions without human review.",),
    ),
    DepartmentAgent(
        "quality",
        "Quality & Risk Agent",
        "Quality and Risk",
        "Verify outputs, test assumptions, track failure modes, and manage release gates.",
        ("quality plans", "risk registers", "acceptance criteria", "release gates"),
        COMMON_PROHIBITIONS,
    ),
    DepartmentAgent(
        "trading_research",
        "Trading Research Agent",
        "Market Intelligence",
        "Analyze broker data across timeframes and explain paper-only market setups.",
        ("market regime", "technical research", "risk framing", "paper simulation"),
        COMMON_PROHIBITIONS
        + ("Never places, modifies, or cancels live orders.",),
    ),
)


class CompanyOperatingSystem:
    """Creates durable, governed company blueprints and mission task graphs."""

    def __init__(self, state_path: Path | None = None, projects_root: Path | None = None):
        self.state_path = state_path or (
            Path(__file__).resolve().parents[1] / "data" / "state" / "company_os.json"
        )
        self.projects_root = projects_root or self.state_path.parent / "company_projects"
        self._lock = RLock()
        self._state: dict[str, Any] = {
            "version": 1,
            "autonomy": "SUPERVISED",
            "latest_plan": None,
            "missions": [],
        }
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._state.update(payload)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(self.state_path)

    @staticmethod
    def _clean(value: str, maximum: int) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]

    @staticmethod
    def _suggest_name(idea: str) -> str:
        ignored = {
            "a", "an", "and", "app", "build", "company", "create", "for", "i",
            "have", "idea", "jarvis", "make", "my", "of", "platform", "startup", "that",
            "the", "this", "to", "want", "with",
        }
        words = [
            word.capitalize()
            for word in re.findall(r"[A-Za-z0-9]+", idea)
            if word.lower() not in ignored
        ]
        return (" ".join(words[:2]) or "New Venture") + " Labs"

    @staticmethod
    def _task(
        order: int,
        department: str,
        title: str,
        deliverable: str,
        *,
        approval_required: bool = False,
        depends_on: tuple[int, ...] = (),
    ) -> dict[str, Any]:
        return {
            "id": f"T{order:02d}",
            "department": department,
            "title": title,
            "deliverable": deliverable,
            "depends_on": [f"T{item:02d}" for item in depends_on],
            "approval_required": approval_required,
            "status": "AWAITING_APPROVAL" if approval_required else "PLANNED",
        }

    def _materialize_operating_packet(self, plan: dict[str, Any]) -> list[dict[str, str]]:
        project = self.projects_root / plan["id"]
        project.mkdir(parents=True, exist_ok=True)
        thesis = plan["venture_thesis"]
        roadmap_lines = []
        for phase in plan["roadmap"]:
            roadmap_lines.extend(
                [f"## {phase['horizon']}", "", phase["goal"], "", f"Tasks: {', '.join(phase['tasks'])}", ""]
            )
        task_lines = []
        for task in plan["tasks"]:
            gate = "LOCKED — EXPLICIT APPROVAL REQUIRED" if task["approval_required"] else "PLANNED — LOCAL WORK"
            dependencies = ", ".join(task["depends_on"]) or "None"
            task_lines.extend(
                [f"## {task['id']} — {task['title']}", "", f"- Department: {task['department']}", f"- Status: {gate}", f"- Dependencies: {dependencies}", f"- Deliverable: {task['deliverable']}", ""]
            )
        departments = []
        for agent in DEPARTMENT_AGENTS:
            departments.extend(
                [f"## {agent.name}", "", f"Department: {agent.department}", "", agent.mission, "", "Capabilities: " + ", ".join(agent.capabilities), ""]
            )
        files = {
            "00-venture-brief.md": "\n".join(
                [
                    f"# {plan['company_name']}", "", f"Plan ID: `{plan['id']}`", f"Created: {plan['created_at']}", "",
                    "## Idea", "", plan["idea"], "", "## Mission", "", thesis["mission"], "",
                    "## Target customer", "", thesis["target_customer"], "", "## Value proposition", "", thesis["value_proposition"], "",
                    "## Business model", "", thesis["business_model"], "", "## MVP", "", thesis["mvp"], "",
                    "## Assumptions to test", "", *[f"- {item}" for item in plan["assumptions_to_test"]], "",
                    "## Success metrics", "", *[f"- {item}" for item in plan["success_metrics"]], "",
                ]
            ),
            "01-roadmap.md": "\n".join([f"# {plan['company_name']} — 30/60/90 Roadmap", "", *roadmap_lines]),
            "02-mission-task-graph.md": "\n".join([f"# {plan['company_name']} — Mission Task Graph", "", *task_lines]),
            "03-department-charters.md": "\n".join([f"# {plan['company_name']} — Department Charters", "", *departments]),
            "04-risk-and-approvals.md": "\n".join(
                [
                    f"# {plan['company_name']} — Risk and Approval Register", "",
                    "JARVIS may autonomously analyze, plan, draft, code, and test local reversible work. The following actions remain locked:", "",
                    *[f"- {item}" for item in plan["approval_gates"]], "",
                    "No approval is implied by this document. Every consequential action requires a fresh, explicit decision at execution time.", "",
                ]
            ),
        }
        artifacts: list[dict[str, str]] = []
        for filename, content in files.items():
            path = project / filename
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(path)
            artifacts.append({"name": filename, "path": str(path)})
        return artifacts

    def create_plan(
        self,
        idea: str,
        company_name: str | None = None,
        context: str = "",
    ) -> dict[str, Any]:
        clean_idea = self._clean(idea, 4_000)
        clean_idea = re.sub(r"^jarvis[\s,:-]*", "", clean_idea, flags=re.IGNORECASE)
        clean_idea = re.sub(
            r"^(?:please\s+)?(?:i\s+have\s+(?:this\s+|an?\s+)?idea\s+(?:for|to)\s+)",
            "",
            clean_idea,
            flags=re.IGNORECASE,
        ).strip()
        clean_idea = re.sub(
            r"^(?:build|create|start|set\s*up|launch)\s+(?:a\s+|my\s+)?(?:company|business|startup|venture)\s+(?:for|that|to)?\s*",
            "",
            clean_idea,
            flags=re.IGNORECASE,
        ).strip()
        if len(clean_idea) < 12:
            raise ValueError("Describe the company idea in at least 12 characters.")
        clean_context = self._clean(context, 4_000)
        name = self._clean(company_name or "", 80) or self._suggest_name(clean_idea)
        plan_id = uuid4().hex
        created_at = utc_now()

        tasks = [
            self._task(1, "Executive Office", "Frame the venture thesis", "One-page thesis with outcomes, constraints, and kill criteria."),
            self._task(2, "Research", "Validate the problem", "Interview guide, evidence matrix, market map, and competitor brief.", depends_on=(1,)),
            self._task(3, "Product", "Define the MVP", "Prioritized user journeys, requirements, non-goals, and acceptance criteria.", depends_on=(1, 2)),
            self._task(4, "Finance", "Model viability", "Pricing hypotheses, unit-economics model, budget, and runway scenarios.", depends_on=(2,)),
            self._task(5, "Legal and Compliance", "Map legal and compliance questions", "Jurisdiction-specific professional-review checklist and draft policy inventory.", depends_on=(1, 3)),
            self._task(6, "Design", "Prototype the experience", "Accessible prototype and lightweight design system.", depends_on=(3,)),
            self._task(7, "Engineering", "Build the validated MVP", "Tested implementation, deployment plan, telemetry, and rollback plan.", depends_on=(3, 6)),
            self._task(8, "Security", "Threat-model the MVP", "Threat model, control checklist, secrets plan, and incident runbook.", depends_on=(3, 7)),
            self._task(9, "Quality and Risk", "Verify release readiness", "Acceptance report, risk register, evidence log, and release recommendation.", depends_on=(4, 5, 7, 8)),
            self._task(10, "Marketing", "Prepare launch experiments", "Positioning, launch content drafts, channel tests, and measurement plan.", depends_on=(2, 3)),
            self._task(11, "Sales", "Design the revenue motion", "ICP, discovery script, qualification criteria, proposal template, and pipeline stages.", depends_on=(2, 4)),
            self._task(12, "Customer Success", "Design onboarding and support", "Onboarding checklist, support playbook, success measures, and feedback loop.", depends_on=(3,)),
            self._task(13, "People", "Define the minimum team", "Role scorecards, hiring sequence, interview rubrics, and onboarding drafts.", depends_on=(3, 4)),
            self._task(14, "Operations", "Create the operating system", "Weekly cadence, SOP index, service levels, dashboards, and decision log.", depends_on=(3, 4, 12)),
            self._task(15, "Legal and Compliance", "Register the legal entity", "Approved incorporation filing through a qualified professional.", approval_required=True, depends_on=(4, 5)),
            self._task(16, "Finance", "Open accounts and fund operations", "Approved bank/payment/vendor accounts and documented controls.", approval_required=True, depends_on=(15,)),
            self._task(17, "Marketing", "Publish the launch", "Approved public launch and measured distribution.", approval_required=True, depends_on=(9, 10)),
            self._task(18, "Sales", "Contact prospects", "Approved outreach to a reviewed prospect list.", approval_required=True, depends_on=(9, 11)),
        ]

        plan = {
            "id": plan_id,
            "company_name": name,
            "created_at": created_at,
            "status": "BLUEPRINT_READY",
            "autonomy": "SUPERVISED",
            "idea": clean_idea,
            "context": clean_context,
            "venture_thesis": {
                "mission": f"Build a focused company that solves: {clean_idea}",
                "target_customer": "To be validated through problem interviews and evidence, not assumed.",
                "value_proposition": "A testable promise will be chosen after research validates the highest-value problem.",
                "business_model": "Pricing and channel hypotheses will be compared with a unit-economics model before commitment.",
                "mvp": "The smallest usable workflow that proves a customer outcome with measurable evidence.",
            },
            "roadmap": [
                {"horizon": "0–30 DAYS", "goal": "Validate the problem, customer, risks, and venture economics.", "tasks": ["T01", "T02", "T04", "T05"]},
                {"horizon": "31–60 DAYS", "goal": "Prototype and build a secure, instrumented MVP.", "tasks": ["T03", "T06", "T07", "T08"]},
                {"horizon": "61–90 DAYS", "goal": "Verify readiness and run approval-gated go-to-market experiments.", "tasks": ["T09", "T10", "T11", "T12", "T14", "T17", "T18"]},
            ],
            "tasks": tasks,
            "approval_gates": [
                "Legal incorporation or regulatory filing",
                "Spending, bank accounts, payments, or vendor commitments",
                "Contracts, hiring decisions, or representation of the company",
                "Outbound messages, publishing, advertising, or customer contact",
                "Production deployment involving personal, customer, or regulated data",
                "Any live trade or movement of funds",
            ],
            "assumptions_to_test": [
                "The target user experiences the stated problem often and urgently.",
                "A meaningfully better workflow can be delivered within the available budget.",
                "A reachable channel and sustainable willingness-to-pay exist.",
                "Legal, data, security, and operational constraints are manageable.",
            ],
            "success_metrics": [
                "Problem interviews with documented evidence",
                "Prototype task-completion and user-value evidence",
                "MVP activation and retained-use signals",
                "Unit economics and risk gates within approved thresholds",
            ],
        }
        plan["artifacts"] = self._materialize_operating_packet(plan)
        mission = {
            "id": plan_id,
            "company_name": name,
            "objective": f"Validate and launch {name}",
            "status": "BLUEPRINT_READY",
            "created_at": created_at,
            "planned_tasks": len(tasks),
            "approval_gates": sum(1 for task in tasks if task["approval_required"]),
            "artifacts": len(plan["artifacts"]),
        }
        with self._lock:
            self._state["latest_plan"] = plan
            self._state["missions"] = ([mission] + self._state.get("missions", []))[:25]
            self._save()
        audit_event(
            "company_os",
            "create_blueprint",
            "SUCCEEDED",
            {"plan_id": plan_id, "planned_tasks": len(tasks), "approval_gates": mission["approval_gates"]},
            plan_id,
        )
        return plan

    def snapshot(self, include_plan: bool = True) -> dict[str, Any]:
        with self._lock:
            latest = self._state.get("latest_plan") if include_plan else None
            missions = list(self._state.get("missions", []))
        return {
            "version": 1,
            "autonomy": "SUPERVISED",
            "agents": [agent.to_dict() for agent in DEPARTMENT_AGENTS],
            "agent_count": len(DEPARTMENT_AGENTS),
            "latest_plan": latest,
            "missions": missions,
            "guardrails": {
                "local_planning": "AUTONOMOUS",
                "drafting_and_analysis": "AUTONOMOUS",
                "external_actions": "EXPLICIT_APPROVAL_REQUIRED",
                "live_trading": "DISABLED",
            },
        }


COMPANY_OS = CompanyOperatingSystem()
