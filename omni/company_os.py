"""Governed idea-to-company planning and department-agent coordination.

This module deliberately separates autonomous local planning from consequential
external actions.  It can create a complete operating blueprint and task graph,
but legal registration, payments, outbound messages, contracts, hiring, and live
trading always remain approval-gated.
"""

from __future__ import annotations

import json
import re
from html import escape
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock, Thread
from typing import Any
from uuid import uuid4

from .company_action_queue import CompanyActionQueue
from .company_department_coordinator import coordinate_departments
from .opportunity_radar_scheduler import OpportunityRadarScheduler
from .runtime import audit_event
from .venture_evidence_engine import run_venture_evidence_program
from .venture_research_program import build_venture_research_program


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
        self._background_research_enabled = state_path is None
        self.state_path = state_path or (
            Path(__file__).resolve().parents[1] / "data" / "state" / "company_os.json"
        )
        self.projects_root = projects_root or self.state_path.parent / "company_projects"
        self.action_queue = CompanyActionQueue(
            self.state_path.with_name(f"{self.state_path.stem}_actions.json")
        )
        self.opportunity_scheduler = OpportunityRadarScheduler(
            self.state_path.with_name(f"{self.state_path.stem}_opportunity_schedule.json")
        )
        self._lock = RLock()
        self._state: dict[str, Any] = {
            "version": 1,
            "autonomy": "SUPERVISED",
            "latest_plan": None,
            "missions": [],
            "autopilot_runs": [],
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
        safe_name = escape(plan["company_name"])
        safe_idea = escape(plan["idea"])
        research_questions = (
            "Who experiences this problem most urgently?",
            "What substitutes and direct competitors already serve them?",
            "What evidence demonstrates willingness to pay?",
            "Which legal, privacy, platform, and distribution constraints apply?",
            "What measurable result would make the first customer retain the product?",
        )
        files.update(
            {
                "09-venture-research-program.json": json.dumps(
                    plan["research_program"], indent=2, ensure_ascii=False
                ),
                "10-long-horizon-roadmap.md": "\n".join(
                    [
                        f"# {plan['company_name']} — Long-Horizon Evidence Roadmap", "",
                        "These are governed decision gates, not forecasts or promises.", "",
                        *[
                            line
                            for phase in plan["research_program"]["horizons"]
                            for line in (
                                f"## {phase['horizon']} — {phase['gate']}", "", phase["outcome"], ""
                            )
                        ],
                    ]
                ),
                "11-department-workboard.json": json.dumps(
                    plan["research_program"]["department_work_orders"], indent=2, ensure_ascii=False
                ),
                "12-hypothesis-and-obstacle-ledger.md": "\n".join(
                    [
                        f"# {plan['company_name']} — Hypothesis and Obstacle Ledger", "",
                        "Every item begins UNTESTED. Evidence may validate, weaken or falsify it.", "",
                        "## Hypotheses", "",
                        *[
                            line
                            for item in plan["research_program"]["hypotheses"]
                            for line in (
                                f"### {item['id']} · {item['status']} · owner {item['owner']}", "",
                                item["statement"], "", f"Evidence required: {item['evidence_required']}",
                                f"Falsification: {item['falsification']}", "",
                            )
                        ],
                        "## Obstacles", "",
                        *[
                            f"- **{item['category']}** · owner {item['owner']} · {item['response']}"
                            for item in plan["research_program"]["obstacle_register"]
                        ], "",
                    ]
                ),
                "05-market-research-evidence.md": "\n".join(
                    [
                        f"# {plan['company_name']} — Market Research Evidence", "",
                        "Status: RESEARCH QUEUED — citation-first public-web evidence will be appended automatically.", "",
                        "## Research questions", "",
                        *[f"- {item}" for item in research_questions], "",
                        "## Evidence standard", "",
                        "Claims must link to accessible public sources. Search snippets, inaccessible pages, assumptions, and verified text remain separately labelled.", "",
                    ]
                ),
                "06-brand-and-website-copy.md": "\n".join(
                    [
                        f"# {plan['company_name']} — Brand and Website Draft", "",
                        "Status: LOCAL DRAFT — NOT PUBLISHED", "",
                        "## Positioning", "",
                        plan["venture_thesis"]["mission"], "",
                        "## Home page", "",
                        f"Headline: {plan['company_name']} turns a difficult workflow into a focused, measurable outcome.", "",
                        f"Supporting copy: {plan['idea']}", "",
                        "CTA: Join the validation list", "",
                        "## Product page", "",
                        plan["venture_thesis"]["mvp"], "",
                        "## About page", "",
                        "We are validating the problem openly, measuring customer outcomes, and building only what evidence supports.", "",
                    ]
                ),
                "07-social-content-studio.md": "\n".join(
                    [
                        f"# {plan['company_name']} — Social Content Studio", "",
                        "Status: DRAFT LIBRARY — PUBLISHING REQUIRES APPROVAL AND CONNECTED ACCOUNTS", "",
                        "## Content pillars", "",
                        "- Problem education", "- Build-in-public evidence", "- Customer workflow lessons", "- Product demonstrations", "- Founder decisions and metrics", "",
                        "## Instagram / short-form drafts", "",
                        f"1. Hook: Why {plan['idea']} is still harder than it should be.",
                        "2. Carousel: Five signs the current workflow is costing time or money.",
                        "3. Reel: A 30-second before-and-after product workflow.",
                        "4. Story poll: Which part of this problem is most painful?", "",
                        "## YouTube drafts", "",
                        f"1. Why we are building {plan['company_name']} — problem, evidence, and constraints.",
                        "2. Product walkthrough — the smallest workflow that proves customer value.",
                        "3. Customer research review — what changed after real interviews.",
                        "4. Monthly operating report — experiments, metrics, failures, and next decisions.", "",
                        "## Approval checklist", "",
                        "- Verify claims and source rights", "- Review brand and privacy risk", "- Approve exact channel, audience, date, and account", "- Record published URL and performance metrics", "",
                    ]
                ),
                "08-executive-autopilot-report.md": "\n".join(
                    [
                        f"# {plan['company_name']} — Executive Autopilot Report", "",
                        f"Generated: {plan['created_at']}", "",
                        "## Completed locally", "",
                        "- Venture thesis and 30/60/90 roadmap", "- Department charters and dependency-aware task graph", "- Research queue and evidence standard", "- Multi-page website prototype", "- Social and video content draft library", "- Approval and risk register", "",
                        "## Awaiting evidence", "",
                        "- Customer interviews", "- Citable competitor and market research", "- Pricing and channel validation", "",
                        "## Locked external actions", "",
                        "- Domain purchase or production deployment", "- Instagram/YouTube/account creation or publishing", "- Advertising, outreach, contracts, incorporation, hiring, or spending", "",
                        "JARVIS will keep local drafting and analysis autonomous. Every consequential external action remains queued for an explicit approval with the exact payload and destination.", "",
                    ]
                ),
                "website/styles.css": """
:root{color-scheme:dark;--bg:#061019;--panel:#0b1b27;--line:#1b5068;--text:#effaff;--accent:#72dcff;--good:#79f2b3}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#123044,var(--bg) 44%);color:var(--text);font:16px/1.6 Inter,Segoe UI,sans-serif}nav{display:flex;gap:1rem;align-items:center;padding:1rem 6vw;border-bottom:1px solid var(--line);position:sticky;top:0;background:#061019e8}nav b{margin-right:auto;letter-spacing:.2em}a{color:var(--accent);text-decoration:none}main{max-width:1100px;margin:auto;padding:7rem 6vw}.eyebrow{color:var(--good);letter-spacing:.14em;font-size:.75rem}.hero h1{font-size:clamp(2.6rem,7vw,5.8rem);line-height:1;margin:.4rem 0 1.4rem}.hero p{max-width:760px;color:#b7cad5;font-size:1.2rem}.cta{display:inline-block;margin-top:1.5rem;padding:.8rem 1.2rem;border:1px solid var(--accent);border-radius:9px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem;margin-top:4rem}.card{padding:1.3rem;border:1px solid var(--line);border-radius:14px;background:var(--panel)}footer{padding:2rem 6vw;border-top:1px solid var(--line);color:#8ba4b2}@media(max-width:650px){nav{flex-wrap:wrap}main{padding-top:4rem}}
""".strip(),
                "website/index.html": f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{safe_name}</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><nav><b>{safe_name}</b><a href=\"index.html\">Home</a><a href=\"product.html\">Product</a><a href=\"about.html\">About</a><a href=\"contact.html\">Contact</a></nav><main><section class=\"hero\"><div class=\"eyebrow\">VALIDATION-FIRST COMPANY</div><h1>Make the hard workflow measurable.</h1><p>{safe_idea}</p><a class=\"cta\" href=\"contact.html\">Join the validation list</a></section><section class=\"grid\"><article class=\"card\"><h2>Focused</h2><p>Start with the smallest customer outcome that can be proved.</p></article><article class=\"card\"><h2>Evidence-led</h2><p>Research, product decisions, and claims stay traceable.</p></article><article class=\"card\"><h2>Measurable</h2><p>Every experiment has an owner, metric, and stop condition.</p></article></section></main><footer>Local JARVIS prototype — not yet published.</footer></body></html>""",
                "website/product.html": f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Product · {safe_name}</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><nav><b>{safe_name}</b><a href=\"index.html\">Home</a><a href=\"product.html\">Product</a><a href=\"about.html\">About</a><a href=\"contact.html\">Contact</a></nav><main><div class=\"eyebrow\">PRODUCT DRAFT</div><h1>The smallest workflow that proves value.</h1><p>{escape(plan['venture_thesis']['mvp'])}</p><section class=\"grid\"><article class=\"card\"><h2>Discover</h2><p>Validate the problem with citable evidence and interviews.</p></article><article class=\"card\"><h2>Deliver</h2><p>Build only the workflow required for the first measurable outcome.</p></article><article class=\"card\"><h2>Learn</h2><p>Review usage, failures, retention, and unit economics.</p></article></section></main><footer>Draft product page — claims require validation.</footer></body></html>""",
                "website/about.html": f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>About · {safe_name}</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><nav><b>{safe_name}</b><a href=\"index.html\">Home</a><a href=\"product.html\">Product</a><a href=\"about.html\">About</a><a href=\"contact.html\">Contact</a></nav><main><div class=\"eyebrow\">WHY THIS COMPANY</div><h1>Evidence before scale.</h1><p>{escape(plan['venture_thesis']['mission'])}</p><section class=\"card\"><h2>Operating principle</h2><p>We publish what is verified, measure what matters, and change direction when customer evidence disproves an assumption.</p></section></main><footer>Draft about page.</footer></body></html>""",
                "website/contact.html": f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Contact · {safe_name}</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><nav><b>{safe_name}</b><a href=\"index.html\">Home</a><a href=\"product.html\">Product</a><a href=\"about.html\">About</a><a href=\"contact.html\">Contact</a></nav><main><div class=\"eyebrow\">VALIDATION LIST</div><h1>Help shape the first useful workflow.</h1><p>This local prototype intentionally has no active form or tracking. Connect an approved form and privacy notice before deployment.</p><section class=\"card\"><h2>Next step</h2><p>Define the interview audience, consent language, data retention, and reviewed destination before collecting information.</p></section></main><footer>No data is collected by this draft.</footer></body></html>""",
            }
        )
        artifacts: list[dict[str, str]] = []
        for filename, content in files.items():
            path = project / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(path)
            artifacts.append({"name": filename, "path": str(path)})
        return artifacts

    def _update_autopilot(
        self,
        plan_id: str,
        *,
        status: str,
        research: str,
        message: str = "",
    ) -> None:
        with self._lock:
            latest = self._state.get("latest_plan")
            if not isinstance(latest, dict) or latest.get("id") != plan_id:
                return
            autopilot = latest.setdefault("autopilot", {})
            autopilot.update(
                {
                    "status": status,
                    "research": research,
                    "last_update": utc_now(),
                    "message": self._clean(message, 500),
                }
            )
            self._save()

    def _research_worker(self, plan: dict[str, Any]) -> None:
        plan_id = str(plan["id"])
        schedule = self.opportunity_scheduler.snapshot(plan_id)
        next_due = schedule.get("next_due_at") if isinstance(schedule, dict) else None
        if next_due:
            try:
                if datetime.now(timezone.utc) < datetime.fromisoformat(str(next_due)):
                    self._update_autopilot(
                        plan_id,
                        status="LOCAL_OPERATING_SYSTEM_READY",
                        research="NOT_DUE",
                        message=f"Opportunity and venture evidence refresh is next due at {next_due}.",
                    )
                    return
            except ValueError:
                pass
        self._update_autopilot(
            plan_id,
            status="RESEARCHING_PUBLIC_SOURCES",
            research="RUNNING",
            message="Citation-first market and competitor research is running.",
        )
        try:
            from agents.web_intelligence_agent import web_intelligence

            result = run_venture_evidence_program(plan, web_intelligence)
            sources = list(result.get("sources") or [])
            evidence_lines = [
                f"# {plan['company_name']} — Market Research Evidence",
                "",
                f"Research status: {result['status']}",
                "",
                f"Coverage: {result['covered_tracks']}/{result['track_count']} research tracks",
                f"Retrieved text: {result['retrieved_text_sources']} · Discovery leads: {result['discovery_leads']}",
                "",
                "## Research-track coverage",
                "",
            ]
            for track in result["tracks"]:
                evidence_lines.extend(
                    [
                        f"- **{track['track_id']} · {track['status']}** — {track['title']}",
                        f"  Query: {track['query']}",
                        f"  Sources: {len(track['source_urls'])}",
                    ]
                )
            evidence_lines.extend(["", "## Citable findings", ""])
            for index, source in enumerate(sources[:10], start=1):
                evidence_lines.extend(
                    [
                        f"### {index}. {source.get('title') or 'Public source'}",
                        "",
                        str(source.get("excerpt") or "No extract was accessible; treat this as a discovery result."),
                        "",
                        f"Source: {source.get('url')}",
                        f"Provider: {source.get('provider') or 'PUBLIC_WEB'}",
                        f"Read status: {source.get('read_status') or 'UNKNOWN'}",
                        f"Evidence grade: {source.get('evidence_grade') or 'DISCOVERY_LEAD'}",
                        f"Research tracks: {', '.join(source.get('tracks') or [])}",
                        "",
                    ]
                )
            evidence_lines.extend(
                [
                    "## Guardrail",
                    "",
                    result["truth_policy"],
                    "Sources with discovery-only snippets are not verified article evidence. Every consequential conclusion requires review.",
                    "",
                ]
            )
            path = self.projects_root / plan_id / "05-market-research-evidence.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".md.tmp")
            temporary.write_text("\n".join(evidence_lines), encoding="utf-8")
            temporary.replace(path)
            program_path = self.projects_root / plan_id / "15-venture-evidence-ledger.json"
            temporary = program_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(result, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            temporary.replace(program_path)
            completed = result["status"] == "EVIDENCE_READY_FOR_REVIEW"
            radar_run = self.opportunity_scheduler.run_if_due(
                plan_id,
                lambda: {
                    "status": result["opportunity_radar"]["status"],
                    "covered_tracks": result["covered_tracks"],
                    "source_count": len(sources),
                    "external_actions_executed": False,
                },
            )
            self._update_autopilot(
                plan_id,
                status="LOCAL_OPERATING_SYSTEM_READY" if completed else "LOCAL_ASSETS_READY_RESEARCH_PARTIAL",
                research=result["status"],
                message=(
                    f"Research covered {result['covered_tracks']}/{result['track_count']} tracks with {len(sources)} unique public sources. Website and content drafts are ready for review."
                    if completed
                    else f"Local assets are ready; research remains partial with {result['covered_tracks']}/{result['track_count']} tracks covered and requires review."
                ),
            )
            with self._lock:
                latest = self._state.get("latest_plan")
                if isinstance(latest, dict) and latest.get("id") == plan_id:
                    latest["venture_evidence"] = {
                        key: value for key, value in result.items() if key != "sources"
                    }
                    latest.setdefault("artifacts", []).append(
                        {"name": program_path.name, "path": str(program_path)}
                    )
                    latest.setdefault("autopilot", {})["opportunity_radar"] = result["opportunity_radar"]["status"]
                    latest["opportunity_radar_schedule"] = self.opportunity_scheduler.snapshot(plan_id)
                    latest["autopilot"]["opportunity_radar_run"] = radar_run["status"]
                    self._save()
            with self._lock:
                self._state["autopilot_runs"] = (
                    [
                        {
                            "plan_id": plan_id,
                            "completed_at": utc_now(),
                            "type": "VENTURE_EVIDENCE",
                            "status": "SUCCEEDED" if completed else "PARTIAL",
                            "source_count": len(sources),
                            "covered_tracks": result["covered_tracks"],
                        }
                    ]
                    + list(self._state.get("autopilot_runs", []))
                )[:25]
                self._save()
            audit_event(
                "company_os",
                "background_research",
                "SUCCEEDED" if completed else "DEGRADED",
                {
                    "plan_id": plan_id,
                    "source_count": len(sources),
                    "covered_tracks": result["covered_tracks"],
                    "track_count": result["track_count"],
                },
                plan_id,
            )
        except Exception as error:
            self._update_autopilot(
                plan_id,
                status="LOCAL_ASSETS_READY_RESEARCH_DEGRADED",
                research="DEGRADED",
                message=f"{type(error).__name__}: {error}",
            )
            audit_event(
                "company_os",
                "background_research",
                "FAILED",
                {"plan_id": plan_id, "error": type(error).__name__},
                plan_id,
            )

    def _start_background_research(self, plan: dict[str, Any]) -> None:
        if not self._background_research_enabled:
            return
        Thread(
            target=self._research_worker,
            args=(dict(plan),),
            name=f"JarvisCompanyResearch-{str(plan['id'])[:8]}",
            daemon=True,
        ).start()

    @staticmethod
    def _registry_executor(agent: str, text: str, correlation_id: str) -> dict[str, Any]:
        """Execute only through the canonical governed AgentRegistry."""

        from main import AGENT_REGISTRY
        from omni.agent_registry import AgentRequest

        response = AGENT_REGISTRY.execute(
            AgentRequest(agent=agent, text=text, correlation_id=correlation_id)
        )
        return {
            "success": response.success,
            "message": response.message,
            "data": response.data if isinstance(response.data, dict) else None,
            "error_type": response.error_type,
        }

    def _department_worker(self, plan: dict[str, Any]) -> None:
        plan_id = str(plan["id"])
        with self._lock:
            latest = self._state.get("latest_plan")
            if not isinstance(latest, dict) or latest.get("id") != plan_id:
                return
            latest.setdefault("autopilot", {})["department_workboard"] = "SPECIALISTS_RUNNING"
            self._save()
        try:
            packet = coordinate_departments(plan, self._registry_executor)
            project = self.projects_root / plan_id
            project.mkdir(parents=True, exist_ok=True)
            json_path = project / "13-department-specialist-packet.json"
            markdown_path = project / "14-department-specialist-report.md"
            temporary = json_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(packet, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            temporary.replace(json_path)
            report_lines = [
                f"# {plan['company_name']} — Department Specialist Report",
                "",
                f"Status: **{packet['status']}**",
                "",
                packet["approval_boundary"],
                "",
            ]
            for item in packet["results"]:
                report_lines.extend(
                    [
                        f"## {item['department_id'].replace('_', ' ').title()}",
                        "",
                        f"Status: **{item['status']}**",
                        "",
                        str(item.get("message") or "No brief was produced."),
                        "",
                    ]
                )
            temporary = markdown_path.with_suffix(".md.tmp")
            temporary.write_text("\n".join(report_lines), encoding="utf-8")
            temporary.replace(markdown_path)

            successful_ids = {
                str(item["department_id"])
                for item in packet["results"]
                if item.get("success")
            }
            department_map = {
                "Executive Office": "executive",
                "Research": "research",
                "Product": "product",
                "Engineering": "engineering",
                "Finance": "finance",
                "Legal and Compliance": "legal",
                "Design": "design",
                "Security": "security",
                "Quality and Risk": "quality",
                "Marketing": "marketing",
                "Sales": "sales",
                "Customer Success": "customer_success",
                "People": "people",
                "Operations": "operations",
            }
            with self._lock:
                latest = self._state.get("latest_plan")
                if not isinstance(latest, dict) or latest.get("id") != plan_id:
                    return
                latest["department_run"] = packet
                latest.setdefault("artifacts", []).extend(
                    [
                        {"name": json_path.name, "path": str(json_path)},
                        {"name": markdown_path.name, "path": str(markdown_path)},
                    ]
                )
                for task in latest.get("tasks", []):
                    role = department_map.get(str(task.get("department")))
                    if (
                        role in successful_ids
                        and not task.get("approval_required")
                        and task.get("status") == "PLANNED"
                    ):
                        task["status"] = "LOCAL_BRIEF_READY"
                autopilot = latest.setdefault("autopilot", {})
                autopilot["department_workboard"] = packet["status"]
                autopilot["department_specialists"] = (
                    f"{packet['successful_departments']}/{packet['department_count']} LOCAL BRIEFS READY"
                )
                autopilot["last_update"] = utc_now()
                self._state["autopilot_runs"] = (
                    [
                        {
                            "plan_id": plan_id,
                            "completed_at": utc_now(),
                            "type": "DEPARTMENT_COORDINATION",
                            "status": packet["status"],
                            "successful_departments": packet["successful_departments"],
                        }
                    ]
                    + list(self._state.get("autopilot_runs", []))
                )[:25]
                self._save()
            audit_event(
                "company_os",
                "department_coordination",
                "SUCCEEDED" if packet["failed_departments"] == 0 else "DEGRADED",
                {
                    "plan_id": plan_id,
                    "successful_departments": packet["successful_departments"],
                    "failed_departments": packet["failed_departments"],
                    "external_actions_executed": False,
                },
                plan_id,
            )
        except Exception as error:
            with self._lock:
                latest = self._state.get("latest_plan")
                if isinstance(latest, dict) and latest.get("id") == plan_id:
                    latest.setdefault("autopilot", {})["department_workboard"] = "FAILED_SAFE"
                    latest["autopilot"]["department_error"] = type(error).__name__
                    latest["autopilot"]["last_update"] = utc_now()
                    self._save()
            audit_event(
                "company_os",
                "department_coordination",
                "FAILED",
                {"plan_id": plan_id, "error": type(error).__name__},
                plan_id,
            )

    def _start_department_coordination(self, plan: dict[str, Any]) -> None:
        if not self._background_research_enabled:
            return
        Thread(
            target=self._department_worker,
            args=(dict(plan),),
            name=f"JarvisCompanyDepartments-{str(plan['id'])[:8]}",
            daemon=True,
        ).start()

    def _prepare_external_actions(self, plan: dict[str, Any]) -> list[dict[str, Any]]:
        """Prepare exact local drafts without implying approval or execution."""

        project = self.projects_root / plan["id"]
        specifications = (
            (
                "Marketing", "DEPLOY_WEBSITE_DRAFT", "website_hosting",
                {"artifact_directory": str(project / "website"), "environment": "preview", "production": False},
            ),
            (
                "Marketing", "PUBLISH_INSTAGRAM_DRAFT", "instagram",
                {"source_artifact": str(project / "07-social-content-studio.md"), "content_slot": 1, "publish": False},
            ),
            (
                "Marketing", "PUBLISH_YOUTUBE_DRAFT", "youtube",
                {"source_artifact": str(project / "07-social-content-studio.md"), "content_slot": 1, "publish": False},
            ),
            (
                "Sales", "SEND_PROSPECT_OUTREACH_DRAFT", "sales_outreach",
                {"source_artifact": str(project / "02-mission-task-graph.md"), "audience": "REVIEWED_LIST_REQUIRED", "send": False},
            ),
        )
        packets = []
        for department, action_type, connector, payload in specifications:
            packets.append(
                self.action_queue.prepare(
                    plan_id=plan["id"], department=department,
                    action_type=action_type, connector=connector,
                    destination="UNCONFIGURED", payload=payload,
                )
            )
        return packets

    def _write_executive_status(self, plan: dict[str, Any]) -> dict[str, str]:
        project = self.projects_root / plan["id"]
        queue = self.action_queue.snapshot(plan["id"])
        schedule = self.opportunity_scheduler.snapshot(plan["id"])
        tasks = list(plan.get("tasks", []))
        local_ready = sum(1 for item in tasks if item.get("status") == "LOCAL_BRIEF_READY")
        locked = sum(1 for item in tasks if item.get("approval_required"))
        report = {
            "plan_id": plan["id"], "generated_at": utc_now(),
            "company_name": plan["company_name"], "status": plan["status"],
            "task_count": len(tasks), "local_briefs_ready": local_ready,
            "approval_gated_tasks": locked,
            "external_action_queue": queue,
            "opportunity_radar_schedule": schedule,
            "physical_work_required": [
                "Build and safely test a physical prototype where the idea requires one.",
                "Conduct consented customer interviews and record evidence.",
                "Use qualified legal, tax, engineering and regulatory professionals where required.",
            ],
            "truth_boundary": "Plans and hypotheses are not forecasts. External actions have not executed.",
        }
        json_path = project / "15-executive-status-report.json"
        md_path = project / "15-executive-status-report.md"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(
            "\n".join(
                [
                    f"# {plan['company_name']} — Executive Status", "",
                    f"Generated: {report['generated_at']}", "",
                    f"- Tasks: {len(tasks)}", f"- Local department briefs ready: {local_ready}",
                    f"- Approval-gated tasks: {locked}",
                    f"- External action drafts awaiting configuration/review: {len(queue['actions'])}",
                    f"- Opportunity radar next due: {schedule.get('next_due_at', 'NOT ENROLLED')}", "",
                    "## What JARVIS prepared", "",
                    "- Evidence research program and obstacle ledger", "- 30/60/90 and 1/4/5-year decision gates",
                    "- Department work orders and local specialist briefs", "- Website, social, video and outreach drafts",
                    "- Tamper-evident action packets for exact-payload approval", "",
                    "## Physical and professional work still required", "",
                    *[f"- {item}" for item in report["physical_work_required"]], "",
                    "No external action, live trade, payment, filing, publication or outreach was executed.", "",
                ]
            ),
            encoding="utf-8",
        )
        return {"json": str(json_path), "markdown": str(md_path)}

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
            "research_program": build_venture_research_program(clean_idea),
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
            "autopilot": {
                "mode": "LOCAL_BUILD_AND_DRAFT",
                "status": "LOCAL_ASSETS_READY_RESEARCH_QUEUED",
                "research": "QUEUED",
                "website": "FOUR_PAGE_LOCAL_PROTOTYPE_READY",
                "content_studio": "INSTAGRAM_AND_YOUTUBE_DRAFTS_READY",
                "reporting": "EXECUTIVE_REPORT_READY",
                "department_workboard": "QUEUED_WITH_DEPENDENCIES",
                "long_horizon_research": "ONE_FOUR_FIVE_YEAR_GATES_READY",
                "opportunity_radar": "EVIDENCE_PROTOCOL_READY_NOT_CONTINUOUSLY_SCANNING",
                "publishing": "EXPLICIT_APPROVAL_AND_CONNECTED_ACCOUNT_REQUIRED",
                "connectors": {
                    "website_hosting": "NOT_CONNECTED",
                    "design_and_media": "NOT_CONNECTED",
                    "instagram": "NOT_CONNECTED",
                    "youtube": "NOT_CONNECTED",
                },
            },
        }
        plan["artifacts"] = self._materialize_operating_packet(plan)
        plan["external_actions"] = self._prepare_external_actions(plan)
        plan["opportunity_radar_schedule"] = self.opportunity_scheduler.enroll(plan_id)
        report_paths = self._write_executive_status(plan)
        plan["artifacts"].extend(
            [
                {"name": "15-executive-status-report.json", "path": report_paths["json"]},
                {"name": "15-executive-status-report.md", "path": report_paths["markdown"]},
            ]
        )
        plan["autopilot"]["opportunity_radar"] = "ENROLLED_DUE_FOR_EVIDENCE_REFRESH"
        plan["autopilot"]["external_action_queue"] = "4 EXACT DRAFTS · DESTINATIONS UNCONFIGURED · NOTHING EXECUTED"
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
        self._start_background_research(plan)
        self._start_department_coordination(plan)
        return plan

    def snapshot(self, include_plan: bool = True) -> dict[str, Any]:
        with self._lock:
            latest = self._state.get("latest_plan") if include_plan else None
            missions = list(self._state.get("missions", []))
            autopilot_runs = list(self._state.get("autopilot_runs", []))[:10]
        return {
            "version": 1,
            "autonomy": "SUPERVISED",
            "agents": [agent.to_dict() for agent in DEPARTMENT_AGENTS],
            "agent_count": len(DEPARTMENT_AGENTS),
            "latest_plan": latest,
            "missions": missions,
            "autopilot_runs": autopilot_runs,
            "external_action_queue": self.action_queue.snapshot(
                str(latest.get("id")) if isinstance(latest, dict) else None
            ),
            "opportunity_radar_schedule": self.opportunity_scheduler.snapshot(
                str(latest.get("id")) if isinstance(latest, dict) else None
            ),
            "guardrails": {
                "local_planning": "AUTONOMOUS",
                "drafting_and_analysis": "AUTONOMOUS",
                "external_actions": "EXPLICIT_APPROVAL_REQUIRED",
                "live_trading": "DISABLED",
            },
        }


COMPANY_OS = CompanyOperatingSystem()
