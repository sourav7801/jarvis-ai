from __future__ import annotations

import importlib
import socket
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


WORKSPACES = (
    Workspace("master", "Master JARVIS", "CORE",
              "Conversation, orchestration, voice, tools and multi-agent control.",
              "open master jarvis", "home", "http://127.0.0.1:8797", 8797, "GOVERNED", "main"),
    Workspace("company", "Company OS", "VENTURE",
              "Venture workspace, research, evidence, departments, decisions and launch planning.",
              "open company os", safety="APPROVAL GATED", module="omni.company_os"),
    Workspace("quant", "Quant Trading", "MARKETS",
              "Market intelligence, scanners, options, charts and Nautilus research.",
              "open quant trading terminal", "market", "http://127.0.0.1:8787", 8787,
              "PAPER / RESEARCH", "workstation.quant_terminal_v2"),
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
              safety="DATA ONLY", module="workstation.fyers_live_bridge_service"),
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


def _call_health_contract() -> tuple[str, Any]:
    try:
        module = importlib.import_module("omni.service_health_contract")
    except Exception as exc:
        return "unavailable", {"error": f"{type(exc).__name__}: {exc}"}

    for name in (
        "snapshot", "health_snapshot", "service_health_snapshot",
        "status", "get_status", "get_service_health",
        "build_service_health", "public_state",
    ):
        fn = getattr(module, name, None)
        if callable(fn):
            try:
                value = fn()
                if isinstance(value, (dict, list, tuple)):
                    return f"service_health_contract.{name}", value
            except TypeError:
                continue
            except Exception as exc:
                return f"service_health_contract.{name}", {
                    "error": f"{type(exc).__name__}: {exc}"
                }

    return "service_health_contract.present", {
        "module": "omni.service_health_contract",
        "note": "Contract loaded; Command Center is using its presence plus direct runtime probes.",
    }


def _company_activity() -> tuple[str, str]:
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
        module = importlib.import_module("workstation.app")
        runtime = getattr(module, "PAPER_RUNTIME", None)
        public_state = getattr(runtime, "public_state", None)
        if callable(public_state):
            state = public_state()
            account = dict(state.get("account") or {})
            positions = list(state.get("positions") or [])
            total = account.get("total_pnl")
            if total is None:
                total = float(account.get("realized_pnl") or 0) + float(
                    account.get("unrealized_pnl") or 0
                )
            return "READY", f"{len(positions)} open · P&L ₹{float(total):+,.2f}"
    except Exception:
        pass
    return "READY", "Paper runtime available"


def _workspace_row(spec: Workspace) -> dict[str, Any]:
    row = spec.to_dict()
    if spec.port:
        row["status"] = "READY" if _port_open(spec.port) else "OFFLINE"
        row["activity"] = f"127.0.0.1:{spec.port}"
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
    health_source, health_contract = _call_health_contract()
    rows = [_workspace_row(spec) for spec in WORKSPACES]
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
