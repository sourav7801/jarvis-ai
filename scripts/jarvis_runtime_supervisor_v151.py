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
from scripts import jarvis_runtime_supervisor_v15 as v15  # noqa: E402
from scripts.runtime_supervisor_safety_v15 import JarvisRuntimeSupervisorV15, SupervisorLeaseV15  # noqa: E402

MASTER_HOST, MASTER_PORT, MASTER_BASE = v15.MASTER_HOST, v15.MASTER_PORT, v15.MASTER_BASE
QUANT_HOST, QUANT_PORT, QUANT_BASE = v15.QUANT_HOST, v15.QUANT_PORT, v15.QUANT_BASE
COMPLETION_HOST, COMPLETION_PORT, COMPLETION_BASE = v15.COMPLETION_HOST, v15.COMPLETION_PORT, v15.COMPLETION_BASE
_json_http = v15._json_http
_port_open = v15._port_open
_reclaim_listener = v15._reclaim_listener


def master_v151_surface_status() -> dict[str, Any]:
    status, payload = _json_http(MASTER_BASE + "/api/v15.1/paper-authority", timeout=6.0)
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "15.1"
        and payload.get("service") == "JARVIS_MASTER_V151_OPTIONS_EXECUTION_BRIDGE"
        and payload.get("protected_master_identity") == "V8_UNIFIED_INTELLIGENCE"
        and payload.get("v151_bridge_installed") is True
        and payload.get("v15_market_reasoning_preserved") is True
        and payload.get("options_intelligence_ready") is True
        and payload.get("permanent_agents") == 29
        and payload.get("live_execution") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def quant_v151_surface_status() -> dict[str, Any]:
    status, payload = _json_http(QUANT_BASE + "/api/v15.1/status", timeout=8.0)
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "15.1"
        and payload.get("service") == "JARVIS_QUANT_V151_OPTIONS_EXECUTION_INTELLIGENCE"
        and payload.get("v15_market_reasoning_preserved") is True
        and payload.get("read_only_chain_provider_preserved") is True
        and payload.get("long_premium_only") is True
        and payload.get("naked_option_selling") is False
        and payload.get("live_execution") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def completion_v151_surface_status() -> dict[str, Any]:
    status, payload = _json_http(COMPLETION_BASE + "/api/v15.1/status", timeout=8.0)
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "15.1"
        and payload.get("service") == "JARVIS_OPTIONS_EXECUTION_INTELLIGENCE_OS"
        and payload.get("runtime_bridge_installed") is True
        and payload.get("quant_options_ready") is True
        and payload.get("permanent_agents") == 29
        and payload.get("live_execution") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def _trusted_master_process(info: dict[str, Any]) -> bool:
    if v15._trusted_master_process(info):
        return True
    command = str(info.get("CommandLine") or "").lower()
    return "c:\\jarvis" in command and ("start_jarvis_master_v151.py" in command or "jarvis_runtime_supervisor_v151" in command)


def _trusted_completion_process(info: dict[str, Any]) -> bool:
    if v15._trusted_completion_process(info):
        return True
    command = str(info.get("CommandLine") or "").lower()
    return "c:\\jarvis" in command and ("completion_console_v151" in command or "jarvis_runtime_supervisor_v151" in command)


def _reclaim(host: str, port: int, surface: dict[str, Any], trusted, label: str) -> dict[str, Any]:
    result = _reclaim_listener(host=host, port=port, current=bool(surface.get("current")), trusted=trusted, label=label)
    result["surface"] = surface
    return result


def reclaim_obsolete_master_listener() -> dict[str, Any]:
    surface = master_v151_surface_status() if _port_open(MASTER_HOST, MASTER_PORT) else {"current": False}
    return _reclaim(MASTER_HOST, MASTER_PORT, surface, _trusted_master_process, "MASTER")


def reclaim_obsolete_quant_listener() -> dict[str, Any]:
    surface = quant_v151_surface_status() if _port_open(QUANT_HOST, QUANT_PORT) else {"current": False}
    return _reclaim(QUANT_HOST, QUANT_PORT, surface, v15._trusted_jarvis_process, "QUANT")


def reclaim_obsolete_completion_listener() -> dict[str, Any]:
    surface = completion_v151_surface_status() if _port_open(COMPLETION_HOST, COMPLETION_PORT) else {"current": False}
    return _reclaim(COMPLETION_HOST, COMPLETION_PORT, surface, _trusted_completion_process, "COMPLETION")


def v151_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    services: list[ManagedService] = []
    for service in v15.v15_services(root):
        if service.name == "master":
            services.append(ManagedService(
                name="master",
                argv=(python, str(root / "start_jarvis_master_v151.py")),
                health_url=MASTER_BASE + "/api/v15.1/paper-authority",
                expected_service="JARVIS_MASTER_V151_OPTIONS_EXECUTION_BRIDGE",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
        elif service.name == "quant":
            env = dict(service.environment)
            env["JARVIS_V151_OPTIONS_EXECUTION"] = "1"
            services.append(ManagedService(
                name="quant",
                argv=service.argv,
                health_url=QUANT_BASE + "/api/v15.1/status",
                expected_service="JARVIS_QUANT_V151_OPTIONS_EXECUTION_INTELLIGENCE",
                port=service.port,
                health_markers=(),
                environment=tuple(env.items()),
            ))
        elif service.name == "completion":
            services.append(ManagedService(
                name="completion",
                argv=service.argv,
                health_url=COMPLETION_BASE + "/api/v15.1/status",
                expected_service="JARVIS_OPTIONS_EXECUTION_INTELLIGENCE_OS",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
        else:
            services.append(service)
    return tuple(services)


def main() -> int:
    lease = SupervisorLeaseV15(ROOT)
    if not lease.acquire():
        print("JARVIS V15/V15.1 supervisor is already owned by another active process.")
        print("Opening the existing protected Master dashboard instead of starting a duplicate supervisor.")
        if str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}:
            try:
                webbrowser.open(MASTER_BASE)
            except Exception:
                pass
        return 0
    try:
        print("JARVIS V15.1 options execution intelligence runtime preflight...")
        print("Quant ownership preflight:", reclaim_obsolete_quant_listener().get("action"))
        print("Master ownership preflight:", reclaim_obsolete_master_listener().get("action"))
        print("Completion ownership preflight:", reclaim_obsolete_completion_listener().get("action"))
        print("Starting protected V8 Master + V15.1 options Quant + Nautilus + V15.1 Completion.")
        print("V15 market reasoning and V14.1 verified underlying risk geometry remain preserved.")
        print("Option-chain providers remain read-only; option execution is paper long-premium only.")
        print("Live broker execution remains locked.")
        browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}
        return JarvisRuntimeSupervisorV15(root=ROOT, services=v151_services(ROOT), browser=browser).run_forever()
    finally:
        lease.release()


if __name__ == "__main__":
    raise SystemExit(main())
