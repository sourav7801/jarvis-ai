from __future__ import annotations

"""Supervise the V16 full workstation as one local product.

This keeps the proven V15 process-ownership/atomic-state machinery and changes
only the Master and Quant service identities:
- 8797: protected V8 Master with the V16 workstation bridge
- 8787: professional paper-terminal runtime used as an internal trading service
All other supervised services preserve their verified V15 lineage.
"""

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
from scripts.runtime_supervisor_safety_v15 import (  # noqa: E402
    JarvisRuntimeSupervisorV15,
    SupervisorLeaseV15,
)

MASTER_HOST = v15.MASTER_HOST
MASTER_PORT = v15.MASTER_PORT
MASTER_BASE = v15.MASTER_BASE
QUANT_HOST = v15.QUANT_HOST
QUANT_PORT = v15.QUANT_PORT
QUANT_BASE = v15.QUANT_BASE
COMPLETION_HOST = v15.COMPLETION_HOST
COMPLETION_PORT = v15.COMPLETION_PORT
COMPLETION_BASE = v15.COMPLETION_BASE
_json_http = v15._json_http


def master_v16_surface_status() -> dict[str, Any]:
    status, payload = _json_http(MASTER_BASE + "/api/v16/status", timeout=5.0)
    trading = payload.get("trading") if isinstance(payload.get("trading"), dict) else {}
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "16.0"
        and payload.get("service") == "JARVIS_MASTER_V16_UNIFIED_WORKSTATION_BRIDGE"
        and payload.get("protected_master_identity") == "V8_UNIFIED_INTELLIGENCE"
        and payload.get("verified_parent") == "V15_AUTONOMOUS_MARKET_REASONING"
        and payload.get("permanent_agents") == 29
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
        and trading.get("same_origin_gateway") is True
        and trading.get("live_orders_locked") is True
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def quant_v16_surface_status() -> dict[str, Any]:
    status, payload = _json_http(QUANT_BASE + "/api/terminal/health", timeout=4.0)
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("service") == "JARVIS_PROFESSIONAL_PAPER_TERMINAL"
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def v16_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    services: list[ManagedService] = []
    for service in v15.v15_services(root):
        if service.name == "master":
            env = dict(service.environment)
            env["JARVIS_NO_BROWSER"] = "1"
            env["JARVIS_AUTO_PAPER_START"] = "0"
            env["JARVIS_V12_AUTO_PAPER_START"] = "0"
            services.append(
                ManagedService(
                    name="master",
                    argv=(python, str(root / "start_jarvis_master_v16.py")),
                    health_url=MASTER_BASE + "/api/v16/status",
                    expected_service="JARVIS_MASTER_V16_UNIFIED_WORKSTATION_BRIDGE",
                    port=MASTER_PORT,
                    health_markers=(),
                    environment=tuple(env.items()),
                )
            )
            continue
        if service.name == "quant":
            env = dict(service.environment)
            env["JARVIS_NO_BROWSER"] = "1"
            env["JARVIS_AUTO_PAPER_START"] = "0"
            env["JARVIS_V12_AUTO_PAPER_START"] = "0"
            services.append(
                ManagedService(
                    name="quant",
                    argv=(python, str(root / "start_jarvis_professional_terminal_v16.py")),
                    health_url=QUANT_BASE + "/api/terminal/health",
                    expected_service="JARVIS_PROFESSIONAL_PAPER_TERMINAL",
                    port=QUANT_PORT,
                    health_markers=(),
                    environment=tuple(env.items()),
                )
            )
            continue
        services.append(service)
    return tuple(services)


def status() -> dict[str, Any]:
    return {
        "success": True,
        "version": "16.0",
        "service": "JARVIS_RUNTIME_SUPERVISOR_V16",
        "master": "JARVIS_MASTER_V16_UNIFIED_WORKSTATION_BRIDGE",
        "trading": "JARVIS_PROFESSIONAL_PAPER_TERMINAL",
        "single_supervisor_os_lease": True,
        "atomic_runtime_snapshot": True,
        "unknown_process_termination": False,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def main() -> int:
    lease = SupervisorLeaseV15(ROOT)
    if not lease.acquire():
        existing = master_v16_surface_status()
        if existing.get("current"):
            print("JARVIS V16 supervisor is already owned. Opening the existing unified workstation.")
        else:
            print("Another JARVIS supervisor owns the runtime lease.")
            print("Stop the existing JARVIS supervisor before switching runtime generations.")
        if str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}:
            try:
                webbrowser.open(MASTER_BASE)
            except Exception:
                pass
        return 0 if existing.get("current") else 1

    try:
        print("JARVIS V16 unified workstation preflight...")
        print("Master target: V16 unified workstation on 8797")
        print("Trading target: professional paper service on 8787")
        print("Verified V15 intelligence, Nautilus and completion lineage are preserved.")
        print("Entry sessions begin PAUSED; existing paper positions remain monitorable.")
        print("Live broker execution remains LOCKED.")
        browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}
        return JarvisRuntimeSupervisorV15(
            root=ROOT,
            services=v16_services(ROOT),
            browser=browser,
        ).run_forever()
    finally:
        lease.release()


if __name__ == "__main__":
    raise SystemExit(main())
