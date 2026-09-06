from __future__ import annotations

import importlib
import importlib.util
import json
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Workspace:
    key: str
    title: str
    group: str
    description: str
    command: str
    mode: str = ""
    url: str = ""
    port: int | None = None
    safety: str = "GOVERNED"
    module: str = ""
    health_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


WORKSPACES = (
    Workspace("master", "Master JARVIS", "CORE",
              "Conversation, orchestration, voice, tools and multi-agent control.",
              "open master jarvis", "home", "http://127.0.0.1:8797", 8797, "GOVERNED", "main"),
    Workspace("company", "Company OS", "VENTURE",
              "Venture workspace, research, evidence, departments, decisions and launch planning.",
              "open company os", url="http://127.0.0.1:8797/company.html",
              safety="APPROVAL GATED", module="omni.company_os"),
    Workspace("quant", "Quant Trading", "MARKETS",
              "Market intelligence, scanners, options, charts and Nautilus research.",
              "open quant trading terminal", "market", "http://127.0.0.1:8787", 8787,
              "PAPER / RESEARCH", "workstation.quant_terminal_v2", "/api/health"),
    Workspace("paper", "Paper Trading", "MARKETS",
              "Synthetic portfolio, P&L, positions, risk, scan ledger and paper learning.",
              "open papertrading pnl", safety="PAPER ONLY", module="workstation.paper_trading_desk"),
    Workspace("research", "Research Intelligence", "INTELLIGENCE",
              "Public research, source evidence and web-intelligence workflows.",
              "open research workspace", "intel", safety="READ / RESEARCH", module="agents.research_agent"),
    Workspace("missions", "Mission Control", "AUTONOMY",
              "Governed multi-agent missions, evidence and resumable work.",
              "open mission control", "mission", safety="GOVERNED", module="omni.mission_control"),
    Workspace("memory", "Memory Fabric", "INTELLIGENCE",
              "Hybrid durable memory for projects, decisions and preferences.",
              "show memory", safety="LOCAL", module="omni.hybrid_memory"),
    Workspace("voice", "Voice", "INTERFACE",
              "Native/hybrid speech recognition and conversational voice.",
              "show voice status", safety="LOCAL", module="omni.voice_adapter"),
    Workspace("apps", "Computer & Apps", "OPERATOR",
              "Applications, browser, files, folders and governed computer actions.",
              "open apps workspace", safety="GOVERNED", module="tools.computer"),
    Workspace("system", "System Core", "CORE",
              "Protected Core, service health, reliability, audit and diagnostics.",
              "show system health", "system", safety="PROTECTED", module="omni.reliability_supervisor"),
    Workspace("dev", "Development / Codex", "ENGINEERING",
              "Governed coding, tests, branches and self-improvement pipeline.",
              "open development workspace", safety="DEV GATED", module="tools.jarvis_dev_agent"),
    Workspace("fyers", "FYERS Data Bridge", "MARKETS",
              "Live market-data bridge. Broker-order execution remains locked.",
              "show fyers status", url="http://127.0.0.1:8790", port=8790,
              safety="DATA ONLY", module="workstation.fyers_live_bridge_service",
              health_path="/api/health"),
)


def _port_open(port: int, timeout: float = 0.12) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _module_available(name: str) -> bool:
    if not name:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _fetch_health_payload(
    port: int,
    path: str,
    timeout: float = 0.35,
) -> dict[str, Any] | None:
    if not path:
        return None
    request = urllib.request.Request(
        f"http://127.0.0.1:{int(port)}{path}",
        headers={"Accept": "application/json", "User-Agent": "JARVIS-Command-Center/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read(500_000).decode("utf-8"))
    except (OSError, ValueError, TypeError, urllib.error.URLError):
        return None
    return value if isinstance(value, dict) else None


def _call_health_contract(rows: list[dict[str, Any]]) -> tuple[str, Any]:
    services = {
        str(row.get("key")): str(row.get("status") or "UNKNOWN")
        for row in rows
        if row.get("port")
    }
    states = set(services.values())
    if "OFFLINE" in states:
        overall = "OFFLINE"
    elif "DEGRADED" in states or "UNAVAILABLE" in states:
        overall = "DEGRADED"
    else:
        overall = "READY"
    return "LOOPBACK_SERVICE_HEALTH_ENDPOINTS", {
        "schema": "JARVIS_COMMAND_CENTER_HEALTH_V1",
        "overall": overall,
        "services": services,
        "note": "Runtime services are derived from their loopback health contracts; port-only rows are explicit.",
    }


def _company_activity() -> tuple[str, str]:
    try:
        state = json.loads(
            (ROOT / "data" / "state" / "company_os.json").read_text(encoding="utf-8")
        )
        latest = dict(state.get("latest_plan") or {})
        company_name = str(latest.get("company_name") or "").strip()
        if company_name:
            return "READY", company_name
    except (FileNotFoundError, OSError, ValueError, TypeError):
        pass

    roots = (
        ROOT / "data" / "state" / "company_projects",
        ROOT / "data" / "company_projects",
        ROOT / "company_projects",
    )
    projects = []
    for root in roots:
        if root.exists():
            projects.extend(path for path in root.iterdir() if path.is_dir())

    if projects:
        newest = max(projects, key=lambda path: path.stat().st_mtime)
        return "READY", newest.name

    return ("READY", "Company OS available") if _module_available("omni.company_os") else (
        "UNAVAILABLE", "Company OS module unavailable"
    )


def _paper_activity() -> tuple[str, str]:
    try:
        module = importlib.import_module("workstation.paper_trading_desk")
        desk = getattr(module, "paper_desk", None)
        snapshot = getattr(desk, "snapshot", None)
        if callable(snapshot):
            state = snapshot()
            return (
                "READY",
                f"{int(state.get('open_count') or 0)} open · P&L ₹{float(state.get('total_pnl') or 0):+,.2f}",
            )
    except Exception:
        pass
    return "READY", "Paper runtime available"


def _workspace_row(spec: Workspace) -> dict[str, Any]:
    row = spec.to_dict()
    if spec.port:
        health = _fetch_health_payload(spec.port, spec.health_path)
        port_open = _port_open(spec.port)
        if health is not None:
            row["status"] = str(health.get("status") or "DEGRADED").upper()
            row["activity"] = str(
                health.get("last_error")
                or health.get("service")
                or f"127.0.0.1:{spec.port}"
            )
            row["health"] = health
        else:
            row["status"] = "READY" if port_open and not spec.health_path else (
                "DEGRADED" if port_open else "OFFLINE"
            )
            row["activity"] = (
                f"127.0.0.1:{spec.port} · health endpoint unavailable"
                if port_open and spec.health_path
                else f"127.0.0.1:{spec.port}"
            )
            row["health"] = None
    elif spec.key == "company":
        row["status"], row["activity"] = _company_activity()
    elif spec.key == "paper":
        row["status"], row["activity"] = _paper_activity()
    else:
        present = _module_available(spec.module)
        row["status"] = "READY" if present else "UNAVAILABLE"
        row["activity"] = "Internal capability" if present else "Module unavailable"
    return row


def snapshot() -> dict[str, Any]:
    rows = [_workspace_row(spec) for spec in WORKSPACES]
    health_source, health_contract = _call_health_contract(rows)
    return {
        "ok": True,
        "version": "6.1",
        "title": "JARVIS Command Center",
        "workspace_count": len(rows),
        "health_source": health_source,
        "health_contract": health_contract,
        "codex_foundations": {
            "service_health_contract": _module_available("omni.service_health_contract"),
            "loopback_http": _module_available("omni.loopback_http"),
            "official_exchange_calendar": _module_available("workstation.official_exchange_calendar"),
            "paper_scan_ledger": _module_available("workstation.paper_scan_ledger"),
        },
        "safety": {
            "protected_core": "REQUIRED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "external_actions": "APPROVAL_GATED",
        },
        "rows": rows,
    }


def get_workspace(key: str) -> dict[str, Any] | None:
    value = str(key or "").strip().lower()
    spec = next((item for item in WORKSPACES if item.key == value), None)
    return _workspace_row(spec) if spec else None
