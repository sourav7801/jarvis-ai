"""Durable, governed multi-agent Mission Control for OMNI-JARVIS.

Mission Control turns an outcome into a bounded task graph, runs relevant
specialists concurrently, verifies their combined work, and materializes a
local execution packet.  It deliberately does not perform consequential
external actions: those remain visible, durable approval locks.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from config import MAX_PARALLEL_TASKS, MISSION_STATE_FILE, MISSION_WORKSPACES_DIR

from .agent_registry import AgentRegistry, AgentRequest, AgentResponse
from .runtime import audit_event


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


MISSION_PATTERNS = (
    r"^\s*mission\s*:",
    r"\bcoordinate (?:the |my )?(?:agents|specialists|departments)\b",
    r"\buse (?:all|multiple|the) (?:agents|specialists|departments)\b",
    r"\b(?:create|make|build) (?:a )?(?:complete )?(?:mission|execution) plan\b",
    r"\bplan and (?:execute|build|coordinate)\b",
    r"\bachieve (?:this|the following) (?:goal|outcome|mission)\b",
    r"\brun (?:this|the) (?:as a )?mission\b",
)


def is_mission_request(text: str, context: str = "master") -> bool:
    """Return True only for explicit orchestration requests.

    Ordinary questions stay fast and continue through the existing router.
    The dedicated Mission page treats every sufficiently descriptive request as
    a mission, while Master Command requires an explicit orchestration phrase.
    """

    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) < 12:
        return False
    if str(context or "").strip().lower() == "mission":
        return True
    return any(re.search(pattern, clean, flags=re.IGNORECASE) for pattern in MISSION_PATTERNS)


class MissionControl:
    """Persistent manager-as-orchestrator with bounded specialist fan-out."""

    _SPECIALIST_PROFILES: tuple[tuple[str, frozenset[str], tuple[str, ...]], ...] = (
        (
            "software",
            frozenset(
                {
                    "app", "api", "automation", "code", "dashboard", "data", "database",
                    "engineer", "platform", "product", "security", "software", "system", "website",
                }
            ),
            ("strategy", "product", "engineering", "data_ai", "design", "security", "quality"),
        ),
        (
            "go_to_market",
            frozenset(
                {
                    "audience", "brand", "campaign", "customer", "growth", "launch", "lead",
                    "marketing", "market", "pricing", "revenue", "sales", "sell",
                }
            ),
            ("strategy", "product", "marketing", "sales", "finance", "customer_success", "quality"),
        ),
        (
            "operations",
            frozenset(
                {
                    "company", "department", "hire", "legal", "operation", "policy", "process",
                    "startup", "team", "venture", "workflow",
                }
            ),
            ("strategy", "product", "finance", "legal", "operations", "people", "quality"),
        ),
        (
            "markets",
            frozenset(
                {
                    "backtest", "banknifty", "broker", "fyers", "market", "nifty", "portfolio",
                    "quant", "risk", "sensex", "strategy", "trade", "trading",
                }
            ),
            ("strategy", "engineering", "data_ai", "finance", "trading", "security", "quality"),
        ),
    )
    _DEFAULT_SPECIALISTS = (
        "strategy", "product", "engineering", "data_ai", "operations", "security", "quality"
    )

    def __init__(
        self,
        registry: AgentRegistry,
        state_path: Path | str | None = None,
        workspaces_root: Path | str | None = None,
        max_workers: int | None = None,
    ) -> None:
        self.registry = registry
        self.state_path = Path(state_path or MISSION_STATE_FILE)
        self.workspaces_root = Path(workspaces_root or MISSION_WORKSPACES_DIR)
        self.max_workers = min(max(int(max_workers or MAX_PARALLEL_TASKS), 1), 8)
        self._lock = RLock()
        self._state: dict[str, Any] = {
            "version": 1,
            "mode": "SUPERVISED",
            "latest_mission": None,
            "missions": [],
        }
        self._load()

    @staticmethod
    def _clean(value: str, maximum: int = 4_000) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]

    def _load(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._state.update(payload)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def _select_specialists(self, objective: str) -> tuple[str, ...]:
        tokens = frozenset(re.findall(r"[a-z0-9_]+", objective.lower()))
        scored = [
            (len(tokens.intersection(keywords)), index, names)
            for index, (_profile, keywords, names) in enumerate(self._SPECIALIST_PROFILES)
        ]
        score, _index, selected = max(scored, key=lambda item: (item[0], -item[1]))
        candidates = selected if score else self._DEFAULT_SPECIALISTS
        available = [name for name in candidates if self.registry.get(name) is not None]
        if self.registry.get("operator") is None:
            return tuple(available[:7])
        selected = ["operator"]
        selected.extend(name for name in available if name != "quality")
        selected = selected[:6]
        if "quality" in available and "quality" not in selected:
            selected.append("quality")
        for name in available:
            if len(selected) >= 7:
                break
            if name not in selected:
                selected.append(name)
        return tuple(selected[:7])

    @staticmethod
    def _specialist_prompt(objective: str, name: str) -> str:
        return (
            f"MISSION OBJECTIVE: {objective}\n\n"
            f"You are the {name.replace('_', ' ').title()} specialist in a manager-owned mission. "
            "Produce a concise, decision-ready contribution for your domain. Identify assumptions, "
            "give an evidence-aware sequence, define measurable acceptance evidence, and surface risks. "
            "Do not claim external work was performed. Do not spend money, contact people, create accounts, "
            "publish, deploy to production, sign, file, hire, or trade. Mark such steps for human approval."
        )

    @staticmethod
    def _run_specialist(
        registry: AgentRegistry,
        mission_id: str,
        objective: str,
        name: str,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        response: AgentResponse = registry.execute(
            AgentRequest(
                agent=name,
                text=MissionControl._specialist_prompt(objective, name),
                correlation_id=f"{mission_id}:{name}",
            )
        )
        data = response.data if isinstance(response.data, dict) else None
        return {
            "agent": name,
            "status": response.status.value,
            "success": response.success,
            "message": response.message,
            "output": data,
            "error_type": response.error_type,
            "duration_ms": round((time.perf_counter() - started) * 1_000, 2),
        }

    @staticmethod
    def _critic_review(objective: str, outputs: list[dict[str, Any]]) -> dict[str, Any]:
        successful = [item for item in outputs if item.get("success")]
        failed = [item for item in outputs if not item.get("success")]
        covered = {str(item.get("agent")) for item in successful}
        required = {"strategy", "quality"}
        gaps: list[str] = []
        if "strategy" not in covered:
            gaps.append("No successful strategy framing was produced.")
        if "quality" not in covered:
            gaps.append("No independent quality/risk contribution was produced.")
        if len(successful) < 4:
            gaps.append("Fewer than four specialist perspectives completed successfully.")
        if failed:
            gaps.append("One or more specialist executions failed safely and require review.")
        checks = {
            "objective_preserved": bool(objective),
            "strategy_covered": "strategy" in covered,
            "independent_quality_review": "quality" in covered,
            "multi_domain_coverage": len(covered) >= 4,
            "external_actions_locked": True,
            "all_specialists_succeeded": not failed,
        }
        confidence = max(25, min(96, 48 + len(successful) * 7 - len(failed) * 12))
        return {
            "verdict": "VERIFIED_LOCAL_PACKET" if required.issubset(covered) and len(successful) >= 4 else "NEEDS_HUMAN_REVIEW",
            "confidence": confidence,
            "checks": checks,
            "gaps": gaps,
            "successful_agents": len(successful),
            "failed_agents": len(failed),
            "notice": "Confidence measures workflow coverage, not factual certainty or outcome probability.",
        }

    @staticmethod
    def _task(
        task_id: str,
        title: str,
        owner: str,
        status: str,
        depends_on: list[str] | None = None,
        detail: str = "",
        approval_required: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": task_id,
            "title": title,
            "owner": owner,
            "status": status,
            "depends_on": list(depends_on or []),
            "detail": detail,
            "approval_required": approval_required,
        }

    def _build_tasks(
        self,
        outputs: list[dict[str, Any]],
        critic: dict[str, Any],
    ) -> list[dict[str, Any]]:
        tasks = [
            self._task(
                "M00", "Frame objective and choose specialists", "Master JARVIS", "SUCCEEDED",
                detail="Manager retained ownership of the mission and final synthesis.",
            )
        ]
        specialist_ids: list[str] = []
        for index, output in enumerate(outputs, start=1):
            task_id = f"M{index:02d}"
            specialist_ids.append(task_id)
            tasks.append(
                self._task(
                    task_id,
                    f"{str(output['agent']).replace('_', ' ').title()} contribution",
                    str(output["agent"]),
                    "SUCCEEDED" if output.get("success") else "FAILED_SAFE",
                    ["M00"],
                    str(output.get("message") or "")[:600],
                )
            )
        critic_id = f"M{len(tasks):02d}"
        tasks.append(
            self._task(
                critic_id,
                "Cross-specialist critic and quality gate",
                "Quality Critic",
                "SUCCEEDED" if critic["verdict"] == "VERIFIED_LOCAL_PACKET" else "NEEDS_REVIEW",
                specialist_ids,
                f"{critic['verdict']} · coverage confidence {critic['confidence']}%",
            )
        )
        packet_id = f"M{len(tasks):02d}"
        tasks.append(
            self._task(
                packet_id,
                "Materialize local mission packet",
                "Master JARVIS",
                "SUCCEEDED",
                [critic_id],
                "Brief, specialist outputs, execution plan, risks, approvals, and trace written locally.",
            )
        )
        tasks.append(
            self._task(
                "A01",
                "Execute consequential external actions",
                "Human approver + approved tool",
                "AWAITING_APPROVAL",
                [packet_id],
                "No external action has been taken. Each action requires a fresh explicit approval.",
                approval_required=True,
            )
        )
        return tasks

    @staticmethod
    def _deliverable_lines(output: dict[str, Any]) -> list[str]:
        lines = [
            f"## {str(output['agent']).replace('_', ' ').title()}",
            "",
            f"Status: **{output['status']}**",
            "",
            str(output.get("message") or "No message was produced."),
            "",
        ]
        data = output.get("output") or {}
        deliverable = data.get("deliverable") if isinstance(data, dict) else None
        if isinstance(deliverable, dict):
            assessment = deliverable.get("current_assessment")
            if assessment:
                lines.extend(["### Assessment", "", str(assessment), ""])
            sequence = deliverable.get("recommended_sequence")
            if isinstance(sequence, list):
                lines.extend(["### Recommended sequence", ""])
                lines.extend(f"- {item}" for item in sequence)
                lines.append("")
            gate = deliverable.get("approval_gate")
            if gate:
                lines.extend(["### Approval boundary", "", str(gate), ""])
        return lines

    def _materialize(self, mission: dict[str, Any]) -> list[dict[str, str]]:
        workspace = self.workspaces_root / mission["id"]
        workspace.mkdir(parents=True, exist_ok=True)
        critic = mission["critic"]
        specialist_lines: list[str] = []
        for output in mission["specialist_outputs"]:
            specialist_lines.extend(self._deliverable_lines(output))
        task_lines: list[str] = []
        for task in mission["tasks"]:
            dependencies = ", ".join(task["depends_on"]) or "None"
            lock = " · APPROVAL REQUIRED" if task["approval_required"] else ""
            task_lines.extend(
                [
                    f"## {task['id']} — {task['title']}",
                    "",
                    f"- Owner: {task['owner']}",
                    f"- Status: {task['status']}{lock}",
                    f"- Depends on: {dependencies}",
                    f"- Detail: {task['detail']}",
                    "",
                ]
            )
        files: dict[str, str] = {
            "00-mission-brief.md": "\n".join(
                [
                    f"# {mission['title']}", "", f"Mission ID: `{mission['id']}`",
                    f"Created: {mission['created_at']}", f"Status: **{mission['status']}**", "",
                    "## Objective", "", mission["objective"], "", "## Operating model", "",
                    "Master JARVIS owns the final packet. Selected specialists contribute in parallel; "
                    "the quality critic checks coverage before artifacts are accepted.", "",
                    "## Selected specialists", "", *[f"- {name}" for name in mission["selected_agents"]], "",
                ]
            ),
            "01-specialist-outputs.md": "\n".join(
                [f"# {mission['title']} — Specialist Outputs", "", *specialist_lines]
            ),
            "02-execution-plan.md": "\n".join(
                [f"# {mission['title']} — Execution Task Graph", "", *task_lines]
            ),
            "03-critic-review.md": "\n".join(
                [
                    f"# {mission['title']} — Critic Review", "", f"Verdict: **{critic['verdict']}**",
                    f"Coverage confidence: **{critic['confidence']}%**", "", critic["notice"], "",
                    "## Checks", "", *[f"- {name.replace('_', ' ').title()}: {'PASS' if passed else 'REVIEW'}" for name, passed in critic["checks"].items()], "",
                    "## Gaps", "", *([f"- {gap}" for gap in critic["gaps"]] or ["- No workflow-coverage gaps detected."]), "",
                ]
            ),
            "04-risk-and-approvals.md": "\n".join(
                [
                    f"# {mission['title']} — Risk and Approval Locks", "",
                    "Local analysis, planning, drafting, and reversible workspace artifacts may run automatically. "
                    "The following categories remain locked:", "",
                    *[f"- {item['action']} — {item['reason']}" for item in mission["approval_locks"]], "",
                    "No approval is implied by this document. A fresh explicit approval is required at execution time.", "",
                ]
            ),
            "05-trace.json": json.dumps(mission["trace"], indent=2, ensure_ascii=False, default=str),
        }
        artifacts: list[dict[str, str]] = []
        for name, content in files.items():
            path = workspace / name
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(path)
            artifacts.append({"name": name, "path": str(path)})
        return artifacts

    def create_mission(self, objective: str, title: str | None = None) -> dict[str, Any]:
        mission_started = time.perf_counter()
        clean = self._clean(objective)
        clean = re.sub(r"^jarvis[\s,:-]*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^mission\s*:\s*", "", clean, flags=re.IGNORECASE)
        if len(clean) < 12:
            raise ValueError("Describe the mission objective in at least 12 characters.")
        mission_id = uuid4().hex
        created_at = utc_now()
        selected = self._select_specialists(clean)
        if not selected:
            raise RuntimeError("No eligible Mission Control specialists are configured.")
        audit_event(
            "mission_control", "mission", "STARTED",
            {"mission_id": mission_id, "specialists": list(selected)}, mission_id,
        )

        results_by_name: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(
            max_workers=min(self.max_workers, len(selected)),
            thread_name_prefix="jarvis-mission",
        ) as executor:
            futures = {
                executor.submit(self._run_specialist, self.registry, mission_id, clean, name): name
                for name in selected
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results_by_name[name] = future.result()
                except Exception as error:
                    results_by_name[name] = {
                        "agent": name,
                        "status": "FAILED",
                        "success": False,
                        "message": f"The {name} specialist failed safely.",
                        "output": None,
                        "error_type": type(error).__name__,
                    }
        outputs = [results_by_name[name] for name in selected]
        critic = self._critic_review(clean, outputs)
        status = (
            "LOCAL_PACKET_READY"
            if critic["verdict"] == "VERIFIED_LOCAL_PACKET"
            else "LOCAL_PACKET_NEEDS_REVIEW"
        )
        mission = {
            "id": mission_id,
            "title": self._clean(title or "", 120) or (
                clean if len(clean) <= 78 else clean[:75].rstrip(" ,.;:-") + "…"
            ),
            "objective": clean,
            "created_at": created_at,
            "completed_at": utc_now(),
            "status": status,
            "mode": "SUPERVISED",
            "selected_agents": list(selected),
            "specialist_outputs": outputs,
            "critic": critic,
            "approval_locks": [
                {"action": "Spend, pay, purchase, or enter a financial commitment", "reason": "Explicit amount and human approval required."},
                {"action": "Contact people, publish content, advertise, or represent the user", "reason": "Recipient/content review and human approval required."},
                {"action": "Create accounts, sign contracts, file legally, or make hiring decisions", "reason": "Identity, legal, and employment consequences require human review."},
                {"action": "Deploy to production or access customer, personal, or regulated data", "reason": "Security, privacy, rollback, and human approval required."},
                {"action": "Place trades or move funds", "reason": "Live execution remains disabled."},
            ],
            "tasks": [],
            "artifacts": [],
            "trace": {
                "mission_id": mission_id,
                "manager": "Master JARVIS",
                "started_at": created_at,
                "completed_at": utc_now(),
                "parallelism_limit": self.max_workers,
                "selected_agents": list(selected),
                "agent_statuses": {item["agent"]: item["status"] for item in outputs},
                "agent_durations_ms": {item["agent"]: item.get("duration_ms") for item in outputs},
                "critic_verdict": critic["verdict"],
                "external_actions_executed": False,
                "total_duration_ms": round((time.perf_counter() - mission_started) * 1_000, 2),
            },
        }
        mission["tasks"] = self._build_tasks(outputs, critic)
        mission["artifacts"] = self._materialize(mission)
        summary = {
            "id": mission_id,
            "title": mission["title"],
            "objective": clean,
            "created_at": created_at,
            "status": status,
            "confidence": critic["confidence"],
            "specialists": len(selected),
            "artifacts": len(mission["artifacts"]),
            "approval_locks": len(mission["approval_locks"]),
        }
        with self._lock:
            self._state["latest_mission"] = mission
            self._state["missions"] = ([summary] + list(self._state.get("missions", [])))[:50]
            self._save()
        audit_event(
            "mission_control", "mission", "SUCCEEDED" if status == "LOCAL_PACKET_READY" else "DEGRADED",
            {"mission_id": mission_id, "status": status, "confidence": critic["confidence"], "artifacts": len(mission["artifacts"])},
            mission_id,
        )
        return mission

    def snapshot(self, include_mission: bool = True) -> dict[str, Any]:
        with self._lock:
            latest = self._state.get("latest_mission") if include_mission else None
            missions = list(self._state.get("missions", []))
        return {
            "version": 1,
            "mode": "SUPERVISED",
            "latest_mission": latest,
            "missions": missions,
            "mission_count": len(missions),
            "capabilities": {
                "durable_task_graph": True,
                "parallel_specialists": True,
                "critic_verification": True,
                "artifact_workspace": True,
                "audit_trace": True,
                "external_actions": "EXPLICIT_APPROVAL_REQUIRED",
                "live_trading": "DISABLED",
            },
        }
