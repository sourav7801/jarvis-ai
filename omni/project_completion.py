"""Repository-controlled JARVIS completion audit.

This module is deliberately conservative.  It distinguishes capabilities that
can be completed inside the repository from integrations that need licensed
services, hardware, credentials, production infrastructure, or a separate live
execution review.  A missing evidence file downgrades the declared capability
rather than manufacturing readiness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"PRESENT", "PARTIAL", "MISSING", "BROKEN", "BLOCKED_EXTERNAL"}


@dataclass(frozen=True)
class CompletionItem:
    key: str
    title: str
    domain: str
    status: str
    weight: float
    evidence: tuple[str, ...]
    detail: str
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence_present"] = [
            path for path in self.evidence if (ROOT / path).exists()
        ]
        value["evidence_missing"] = [
            path for path in self.evidence if not (ROOT / path).exists()
        ]
        return value


def _item(
    key: str,
    title: str,
    domain: str,
    status: str,
    weight: float,
    evidence: tuple[str, ...],
    detail: str,
    next_action: str = "",
) -> CompletionItem:
    normalized = str(status).upper()
    if normalized not in VALID_STATUSES:
        raise ValueError(f"Unsupported completion status: {status}")
    return CompletionItem(
        key=key,
        title=title,
        domain=domain,
        status=normalized,
        weight=max(0.1, float(weight)),
        evidence=evidence,
        detail=detail,
        next_action=next_action,
    )


def declared_items() -> tuple[CompletionItem, ...]:
    """Return the audited V7 capability matrix before filesystem validation."""

    return (
        _item(
            "master_control_plane", "Master control plane", "CORE", "PRESENT", 5,
            ("workstation/jarvis_os_v3.py", "omni/control_plane.py", "omni/agent_registry.py"),
            "Master routing, typed agents, diagnostics and fail-closed authority boundaries are implemented.",
        ),
        _item(
            "workspace_command_center", "Command Center and workspaces", "CORE", "PRESENT", 4,
            ("omni/workspace_command_center.py", "workstation/jarvis_os_v3_assets/index.html"),
            "Canonical workspaces and service-health aggregation are present.",
        ),
        _item(
            "runtime_recovery", "Owned-process runtime recovery", "RELIABILITY", "PRESENT", 5,
            ("scripts/jarvis_runtime_supervisor.py", "scripts/jarvis_runtime_supervisor_v62.py"),
            "Bounded restart, port ownership and stale-Quant protection are present.",
        ),
        _item(
            "voice", "Voice reliability", "INTERFACE", "PARTIAL", 3,
            ("start_jarvis_native_voice.ps1", "workstation/native_voice/JarvisVoiceService.cs"),
            "Voice lifecycle and browser fallback exist; native recognition depends on a compatible Windows recognizer.",
            "Repair/install the machine speech recognizer for native recognition readiness.",
        ),
        _item(
            "memory", "Hybrid durable memory", "INTELLIGENCE", "PRESENT", 4,
            ("omni/hybrid_memory.py", "omni/memory_context.py"),
            "SQLite lexical memory and semantic-fusion interface are present.",
        ),
        _item(
            "memory_lifecycle", "Memory lifecycle governance", "INTELLIGENCE", "PRESENT", 2,
            ("omni/memory_lifecycle.py",),
            "V7 adds non-destructive age/kind statistics and retention previews.",
        ),
        _item(
            "model_router", "Provider-neutral model router", "INTELLIGENCE", "PRESENT", 3,
            ("omni/model_router.py",),
            "Local privacy/tier/context/capability routing exists.",
        ),
        _item(
            "model_metrics", "Model routing telemetry", "INTELLIGENCE", "PRESENT", 2,
            ("omni/model_router_telemetry.py",),
            "V7 adds persistent bounded routing/outcome/latency telemetry without enabling cloud models.",
        ),
        _item(
            "mission_control", "Multi-agent Mission Control", "AUTONOMY", "PRESENT", 5,
            ("omni/mission_control.py", "agents/universal_operator_agent.py"),
            "Manager-owned bounded specialist fan-out, critic verification and durable mission artifacts are present.",
        ),
        _item(
            "mission_queue", "Resumable local mission queue", "AUTONOMY", "PRESENT", 3,
            ("omni/mission_queue.py",),
            "V7 adds a persistent lease/retry/recovery queue. It does not bypass approval gates.",
        ),
        _item(
            "approvals", "Scoped approval queue", "SAFETY", "PRESENT", 4,
            ("omni/approval_queue.py",),
            "Payload-bound, expiring, one-time approvals are present; V7 exposes deliberate approve/reject UI controls only.",
        ),
        _item(
            "company_os", "Company operating system", "VENTURE", "PRESENT", 4,
            ("omni/company_os.py", "workstation/jarvis_os_v3_assets/company.html"),
            "Sixteen-department local venture planning/research/artifact workflow is present with external actions gated.",
        ),
        _item(
            "coding_intelligence", "Repository code intelligence", "ENGINEERING", "PRESENT", 3,
            ("omni/code_intelligence.py", "agents/coding_agent.py"),
            "V7 adds a bounded AST/project index. Code execution and production edits remain separately governed.",
        ),
        _item(
            "market_data_contract", "Canonical market-data contract", "TRADING", "PRESENT", 5,
            ("workstation/market_data_contract.py", "workstation/market_event_bus.py"),
            "Provider provenance, freshness, typed events and venue sessions are implemented.",
        ),
        _item(
            "market_event_publishers", "Market-event publisher adapters", "TRADING", "PRESENT", 3,
            ("workstation/market_event_publishers.py",),
            "V7 adds verified adapters for options, OI, volatility, order book, news and provider health.",
        ),
        _item(
            "feature_engine", "Unified feature/structure engine", "TRADING", "PRESENT", 5,
            ("workstation/unified_feature_engine.py", "workstation/indicator_registry.py", "workstation/multi_timeframe_feature_store.py"),
            "Structure, zones, FVG/liquidity, patterns, volatility context and a deterministic indicator registry are present.",
        ),
        _item(
            "adaptive_quant", "Adaptive Quant decision engine", "TRADING", "PRESENT", 5,
            ("omni/trading_intelligence/adaptive_quant_brain.py", "workstation/quant_firm_runtime.py"),
            "Regime-aware explainable adaptive paper/research decisions are present.",
        ),
        _item(
            "options_desk", "Options intelligence and defined-risk paper desk", "TRADING", "PRESENT", 4,
            ("workstation/options_chain_analytics.py", "workstation/defined_risk_options_paper_desk.py", "workstation/options_paper_autonomy.py"),
            "Verified chains, descriptive analytics and defined-risk paper spreads are present.",
        ),
        _item(
            "paper_portfolio", "Persistent autonomous paper portfolio", "TRADING", "PRESENT", 5,
            ("workstation/paper_trading_desk.py", "workstation/paper_portfolio_controller.py", "workstation/paper_autonomy_engine.py"),
            "Portfolio risk gates, managed exits, journal, autonomy and bounded learning are present.",
        ),
        _item(
            "correlation_intelligence", "Rolling correlation intelligence", "TRADING", "PRESENT", 3,
            ("workstation/correlation_risk_engine.py",),
            "V7 adds deterministic rolling-return correlation clusters as research/risk evidence without silently changing existing limits.",
        ),
        _item(
            "strategy_research", "Strategy Research Lab", "TRADING", "PRESENT", 4,
            ("omni/trading_intelligence/strategy_research_lab.py",),
            "Hypotheses, fee/slippage backtests and walk-forward research are present.",
        ),
        _item(
            "robust_validation", "Robust OOS/Monte-Carlo/cost validation", "TRADING", "PRESENT", 4,
            ("omni/trading_intelligence/robust_validation.py",),
            "V7 adds deterministic OOS degradation, bootstrap tail, walk-forward and cost-stress gates.",
        ),
        _item(
            "champion_challenger", "Champion/challenger research registry", "TRADING", "PRESENT", 4,
            ("omni/trading_intelligence/champion_challenger.py",),
            "V7 adds a durable paper/research registry. No production strategy promotion is automatic.",
        ),
        _item(
            "professional_quant_ui", "Professional Quant intelligence terminal", "INTERFACE", "PRESENT", 4,
            ("workstation/quant_terminal_v2_static/index.html", "workstation/quant_terminal_v2_static/intelligence.html"),
            "Charts, intelligence modules, portfolio/journal, Adaptive Brain and strategy research surfaces are present.",
        ),
        _item(
            "completion_center", "Project Completion Center", "CORE", "PRESENT", 3,
            ("workstation/completion_console.py", "workstation/completion_console_static/index.html"),
            "V7 adds one operator-facing completion, diagnostics, approvals, queue and research-governance console.",
        ),
        _item(
            "licensed_l2_data", "Exchange-grade L2/L3 and licensed tick data", "EXTERNAL", "BLOCKED_EXTERNAL", 0.1,
            (), "Requires licensed data/vendor infrastructure; repository code cannot truthfully manufacture this capability.",
        ),
        _item(
            "live_broker_execution", "Reviewed live broker execution", "EXTERNAL", "BLOCKED_EXTERNAL", 0.1,
            (), "Intentionally excluded until a separate execution/reconciliation/security review and explicit authorization.",
        ),
        _item(
            "premium_research", "Premium news/academic/proprietary data", "EXTERNAL", "BLOCKED_EXTERNAL", 0.1,
            (), "Requires external licensed accounts/connectors.",
        ),
        _item(
            "hardware_authorization", "Hardware-backed/biometric authorization", "EXTERNAL", "BLOCKED_EXTERNAL", 0.1,
            (), "Requires trusted hardware/OS integration and enrollment outside repository-only work.",
        ),
        _item(
            "production_isolation", "Production VM/container isolation and independent review", "EXTERNAL", "BLOCKED_EXTERNAL", 0.1,
            (), "Requires deployment infrastructure, OS quotas, monitoring, backups and independent security review.",
        ),
    )


def audited_items() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for declared in declared_items():
        row = declared.to_dict()
        if declared.status in {"PRESENT", "PARTIAL"} and declared.evidence:
            missing = list(row["evidence_missing"])
            if missing:
                row["status"] = "PARTIAL" if row["evidence_present"] else "MISSING"
                row["detail"] += " Filesystem audit downgraded this row because required evidence is missing."
        rows.append(row)
    return rows


def snapshot() -> dict[str, Any]:
    rows = audited_items()
    repo_rows = [row for row in rows if row["status"] != "BLOCKED_EXTERNAL"]
    external_rows = [row for row in rows if row["status"] == "BLOCKED_EXTERNAL"]
    score_value = {"PRESENT": 1.0, "PARTIAL": 0.5, "MISSING": 0.0, "BROKEN": 0.0}
    total_weight = sum(float(row["weight"]) for row in repo_rows) or 1.0
    earned = sum(
        float(row["weight"]) * score_value.get(str(row["status"]), 0.0)
        for row in repo_rows
    )
    repo_percent = round(100.0 * earned / total_weight, 1)
    counts = {status: 0 for status in sorted(VALID_STATUSES)}
    for row in rows:
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
    remaining = [
        row for row in repo_rows if row["status"] in {"PARTIAL", "MISSING", "BROKEN"}
    ]
    return {
        "success": True,
        "service": "JARVIS_PROJECT_COMPLETION_AUDIT",
        "version": "7.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository_completion_percent": repo_percent,
        "repository_complete": not remaining,
        "remaining_repository_items": remaining,
        "external_blockers": external_rows,
        "counts": counts,
        "items": rows,
        "definition_of_done": {
            "repository_scope": "Repository-controlled local-first capabilities",
            "external_scope": "Licensed data, live execution, hardware authorization and production infrastructure remain separate",
            "safety": "PAPER_RESEARCH_ONLY",
        },
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "external_actions": "APPROVAL_GATED",
    }


__all__ = ["CompletionItem", "audited_items", "declared_items", "snapshot"]
