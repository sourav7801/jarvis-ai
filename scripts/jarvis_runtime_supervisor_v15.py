from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jarvis_runtime_supervisor import ManagedService  # noqa: E402
from scripts import jarvis_runtime_supervisor_v141 as v141  # noqa: E402
from scripts.jarvis_runtime_supervisor_v62 import _port_open, _trusted_jarvis_process  # noqa: E402
from scripts.runtime_supervisor_safety_v15 import (  # noqa: E402
    JarvisRuntimeSupervisorV15,
    SupervisorLeaseV15,
)

MASTER_HOST = v141.MASTER_HOST
MASTER_PORT = v141.MASTER_PORT
MASTER_BASE = v141.MASTER_BASE
QUANT_HOST = v141.QUANT_HOST
QUANT_PORT = v141.QUANT_PORT
QUANT_BASE = v141.QUANT_BASE
COMPLETION_HOST = v141.COMPLETION_HOST
COMPLETION_PORT = v141.COMPLETION_PORT
COMPLETION_BASE = v141.COMPLETION_BASE
_json_http = v141._json_http
_reclaim_listener = v141._reclaim_listener


def master_v15_surface_status() -> dict[str, Any]:
    status, payload = _json_http(MASTER_BASE + "/api/v15/paper-authority", timeout=6.0)
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "15.0"
        and payload.get("service") == "JARVIS_MASTER_V15_AUTONOMOUS_MARKET_REASONING_BRIDGE"
        and payload.get("protected_master_identity") == "V8_UNIFIED_INTELLIGENCE"
        and payload.get("v15_bridge_installed") is True
        and payload.get("market_reasoning_ready") is True
        and payload.get("portfolio_allocator_ready") is True
        and payload.get("v141_risk_geometry_preserved") is True
        and payload.get("permanent_agents") == 29
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def quant_v15_surface_status() -> dict[str, Any]:
    status, payload = _json_http(QUANT_BASE + "/api/v15/status", timeout=8.0)
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "15.0"
        and payload.get("service") == "JARVIS_QUANT_V15_AUTONOMOUS_MARKET_REASONING"
        and runtime.get("installed") is True
        and runtime.get("v141_risk_geometry_installed") is True
        and runtime.get("fractional_constraint_aware_sizing") is True
        and decision.get("decision_authority") == "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK"
        and decision.get("portfolio_allocator_can_only_reduce_v14_risk") is True
        and payload.get("invalid_risk_levels_hard_blocker_preserved") is True
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def completion_v15_surface_status() -> dict[str, Any]:
    status, payload = _json_http(COMPLETION_BASE + "/api/v15/status", timeout=8.0)
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "15.0"
        and payload.get("service") == "JARVIS_AUTONOMOUS_MARKET_REASONING_OS"
        and payload.get("runtime_bridge_installed") is True
        and payload.get("quant_reasoning_ready") is True
        and payload.get("v141_risk_geometry_preserved") is True
        and payload.get("permanent_agents") == 29
        and payload.get("system_planes_do_not_count_as_agents") is True
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
        and payload.get("automatic_production_strategy_rewrite") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def _trusted_master_process(info: dict[str, Any]) -> bool:
    if v141._trusted_master_process(info):
        return True
    root = str(ROOT).lower().rstrip("\\/")
    command = str(info.get("CommandLine") or "").lower()
    executable = str(info.get("ExecutablePath") or "").lower()
    return bool(
        (executable.startswith(root + "\\") or root in command)
        and ("start_jarvis_master_v15.py" in command or "jarvis_runtime_supervisor_v15" in command)
    )


def _trusted_completion_process(info: dict[str, Any]) -> bool:
    if v141._trusted_completion_process(info):
        return True
    root = str(ROOT).lower().rstrip("\\/")
    command = str(info.get("CommandLine") or "").lower()
    executable = str(info.get("ExecutablePath") or "").lower()
    return bool(
        (executable.startswith(root + "\\") or root in command)
        and ("completion_console_v15" in command or "jarvis_runtime_supervisor_v15" in command)
    )


def reclaim_obsolete_master_listener() -> dict[str, Any]:
    surface = master_v15_surface_status() if _port_open(MASTER_HOST, MASTER_PORT) else {"current": False}
    result = _reclaim_listener(
        host=MASTER_HOST,
        port=MASTER_PORT,
        current=bool(surface.get("current")),
        trusted=_trusted_master_process,
        label="MASTER",
    )
    result["surface"] = surface
    return result


def reclaim_obsolete_quant_listener() -> dict[str, Any]:
    surface = quant_v15_surface_status() if _port_open(QUANT_HOST, QUANT_PORT) else {"current": False}
    result = _reclaim_listener(
        host=QUANT_HOST,
        port=QUANT_PORT,
        current=bool(surface.get("current")),
        trusted=_trusted_jarvis_process,
        label="QUANT",
    )
    result["surface"] = surface
    return result


def reclaim_obsolete_completion_listener() -> dict[str, Any]:
    surface = completion_v15_surface_status() if _port_open(COMPLETION_HOST, COMPLETION_PORT) else {"current": False}
    result = _reclaim_listener(
        host=COMPLETION_HOST,
        port=COMPLETION_PORT,
        current=bool(surface.get("current")),
        trusted=_trusted_completion_process,
        label="COMPLETION",
    )
    result["surface"] = surface
    return result


def v15_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    master_wrapper = root / "start_jarvis_master_v15.py"
    services: list[ManagedService] = []
    for service in v141.v141_services(root):
        if service.name == "master":
            services.append(ManagedService(
                name="master",
                argv=(python, str(master_wrapper)),
                health_url=MASTER_BASE + "/api/v15/paper-authority",
                expected_service="JARVIS_MASTER_V15_AUTONOMOUS_MARKET_REASONING_BRIDGE",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
            continue
        if service.name == "quant":
            environment = dict(service.environment)
            environment["JARVIS_V15_AUTONOMOUS_REASONING"] = "1"
            services.append(ManagedService(
                name="quant",
                argv=service.argv,
                health_url=QUANT_BASE + "/api/v15/status",
                expected_service="JARVIS_QUANT_V15_AUTONOMOUS_MARKET_REASONING",
                port=service.port,
                health_markers=(),
                environment=tuple(environment.items()),
            ))
            continue
        if service.name == "completion":
            services.append(ManagedService(
                name="completion",
                argv=service.argv,
                health_url=COMPLETION_BASE + "/api/v15/status",
                expected_service="JARVIS_AUTONOMOUS_MARKET_REASONING_OS",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
            continue
        services.append(service)
    return tuple(services)


def main() -> int:
    lease = SupervisorLeaseV15(ROOT)
    if not lease.acquire():
        print("JARVIS V15 supervisor is already owned by another active process.")
        print("Opening the existing protected Master dashboard instead of starting a duplicate supervisor.")
        if str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}:
            try:
                webbrowser.open(MASTER_BASE)
            except Exception:
                pass
        return 0
    try:
        print("JARVIS V15 autonomous market reasoning runtime preflight...")
        quant = reclaim_obsolete_quant_listener()
        print("Quant ownership preflight:", quant.get("action"))
        master = reclaim_obsolete_master_listener()
        print("Master ownership preflight:", master.get("action"))
        completion = reclaim_obsolete_completion_listener()
        print("Completion ownership preflight:", completion.get("action"))
        print("Starting protected V8 Master + V15 reasoning Quant + Nautilus + V15 Completion.")
        print("V14.1 verified risk geometry remains upstream of portfolio-adjusted V15 utility.")
        print("A second JARVIS.bat will not start a duplicate supervisor.")
        print("Live broker execution remains locked.")
        browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}
        return JarvisRuntimeSupervisorV15(
            root=ROOT,
            services=v15_services(ROOT),
            browser=browser,
        ).run_forever()
    finally:
        lease.release()


if __name__ == "__main__":
    raise SystemExit(main())
