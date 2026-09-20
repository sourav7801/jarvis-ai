from __future__ import annotations

"""Supervise JARVIS V17 as one local product.

Services preserve the proven V15/V16 ownership machinery while replacing the
Master and Quant launchers with V17 identities:
- 8797: protected Master + V17 workstation bridge
- 8787: V17 autonomous-options professional PAPER terminal

V17 additionally refuses to adopt an already-running Quant process unless that
process proves the current adaptive-crypto status contract.  This prevents an
older terminal from surviving a Git pull merely because its generic health
endpoint still answers with a compatible service name.
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
from scripts import jarvis_runtime_supervisor_v16 as v16  # noqa: E402
from scripts.runtime_supervisor_safety_v15 import (  # noqa: E402
    JarvisRuntimeSupervisorV15,
    SupervisorLeaseV15,
)

MASTER_HOST = v16.MASTER_HOST
MASTER_PORT = v16.MASTER_PORT
MASTER_BASE = v16.MASTER_BASE
QUANT_HOST = v16.QUANT_HOST
QUANT_PORT = v16.QUANT_PORT
QUANT_BASE = v16.QUANT_BASE
_json_http = v16._json_http

V17_QUANT_SERVICE = "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME"
V17_CRYPTO_SERVICE = "JARVIS_V17_CANONICAL_CRYPTO_UNDERLYING_PAPER"
V17_ADAPTIVE_AUTHORITY = "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE"


def master_v17_surface_status() -> dict[str, Any]:
    status, payload = _json_http(MASTER_BASE + "/api/v17/status", timeout=5.0)
    trading = payload.get("trading") if isinstance(payload.get("trading"), dict) else {}
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "17.0"
        and payload.get("service") == "JARVIS_MASTER_V17_AUTONOMOUS_OPTIONS"
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
        and trading.get("same_origin_gateway") is True
        and trading.get("live_orders_locked") is True
        and trading.get("manual_option_selection_required") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def _current_quant_contract(payload: dict[str, Any] | None) -> bool:
    """Return True only for the current V17 adaptive-crypto Quant contract."""
    if not isinstance(payload, dict):
        return False
    if payload.get("success") is not True or payload.get("service") != V17_QUANT_SERVICE:
        return False
    crypto = payload.get("crypto_underlying_paper")
    if not isinstance(crypto, dict):
        return False
    if crypto.get("service") != V17_CRYPTO_SERVICE:
        return False
    if str(crypto.get("qualification_authority") or "") != V17_ADAPTIVE_AUTHORITY:
        return False
    if str(crypto.get("decision_authority") or "") != V17_ADAPTIVE_AUTHORITY:
        return False
    if not str(crypto.get("adaptive_policy_version") or "").strip():
        return False
    if crypto.get("legacy_numeric_gates_are_execution_authority") is not False:
        return False
    if crypto.get("paper_only") is not True or crypto.get("live_execution") is not False:
        return False
    if not isinstance(crypto.get("last_rows_summary"), list):
        return False
    return True


class JarvisRuntimeSupervisorV17(JarvisRuntimeSupervisorV15):
    """V17 supervisor that refuses stale-but-responsive Quant runtimes."""

    @staticmethod
    def _health_payload(url: str, timeout: float = 1.5) -> dict[str, Any] | None:
        payload = JarvisRuntimeSupervisorV15._health_payload(url, timeout)
        if "/api/v17/trading/status" in str(url):
            return payload if _current_quant_contract(payload) else None
        return payload


def v17_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    # NautilusTrader is intentionally isolated from the main V17 environment.
    # Prefer the dedicated environment when it exists; fall back to the main
    # interpreter only when the package was installed there.
    nautilus_candidates = [
        Path(os.getenv("JARVIS_NAUTILUS_PY", "")).expanduser() if os.getenv("JARVIS_NAUTILUS_PY") else None,
        root / ".venv-nautilus-new" / "Scripts" / "python.exe",
        root / ".venv-nautilus" / "Scripts" / "python.exe",
        Path(python),
    ]
    nautilus_python = next(
        (str(path.resolve()) for path in nautilus_candidates if path and path.exists()),
        python,
    )
    services: list[ManagedService] = []
    for service in v16.v16_services(root):
        if service.name == "master":
            env = dict(service.environment)
            env.update(
                {
                    "JARVIS_NO_BROWSER": "1",
                    "JARVIS_AUTO_PAPER_START": "0",
                    "JARVIS_V12_AUTO_PAPER_START": "0",
                    "JARVIS_V17_AUTONOMOUS_OPTIONS": "1",
                    "JARVIS_LIVE_EXECUTION": "0",
                }
            )
            services.append(
                ManagedService(
                    name="master",
                    argv=(python, str(root / "start_jarvis_master_v17.py")),
                    health_url=MASTER_BASE + "/api/v17/status",
                    expected_service="JARVIS_MASTER_V17_AUTONOMOUS_OPTIONS",
                    port=MASTER_PORT,
                    health_markers=(),
                    environment=tuple(env.items()),
                )
            )
            continue
        if service.name == "quant":
            env = dict(service.environment)
            env.update(
                {
                    "JARVIS_NO_BROWSER": "1",
                    "JARVIS_AUTO_PAPER_START": "0",
                    "JARVIS_V12_AUTO_PAPER_START": "0",
                    "JARVIS_V17_AUTONOMOUS_OPTIONS": "1",
                    "JARVIS_LIVE_EXECUTION": "0",
                }
            )
            services.append(
                ManagedService(
                    name="quant",
                    argv=(python, str(root / "start_jarvis_professional_terminal_v17.py")),
                    health_url=QUANT_BASE + "/api/v17/trading/status?workspace=OPTIONS",
                    expected_service=V17_QUANT_SERVICE,
                    port=QUANT_PORT,
                    health_markers=(),
                    environment=tuple(env.items()),
                )
            )
            continue
        services.append(service)

    # Make the V17 service set explicit so a future V16 lineage change cannot
    # silently drop Nautilus from the supervised product.
    if not any(service.name == "nautilus" for service in services):
        services.append(
            ManagedService(
                name="nautilus",
                argv=(nautilus_python, str(root / "start_jarvis_nautilus_core.py")),
                health_url="http://127.0.0.1:8792/health",
                expected_service="JARVIS_NAUTILUS_QUANT_CORE",
                port=8792,
                environment=(),
            )
        )
    else:
        services = [
            ManagedService(
                name=service.name,
                argv=(nautilus_python, service.argv[1]) if service.name == "nautilus" else service.argv,
                health_url=service.health_url,
                expected_service=service.expected_service,
                port=service.port,
                health_markers=service.health_markers,
                environment=service.environment,
            )
            for service in services
        ]
    return tuple(services)


def status() -> dict[str, Any]:
    return {
        "success": True,
        "version": "17.0",
        "service": "JARVIS_RUNTIME_SUPERVISOR_V17",
        "master": "JARVIS_MASTER_V17_AUTONOMOUS_OPTIONS",
        "trading": V17_QUANT_SERVICE,
        "single_supervisor_os_lease": True,
        "atomic_runtime_snapshot": True,
        "unknown_process_termination": False,
        "strict_quant_contract_adoption": True,
        "crypto_adaptive_authority_required": V17_ADAPTIVE_AUTHORITY,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "manual_option_selection_required": False,
        "forced_trade_quota": False,
    }


def main() -> int:
    lease = SupervisorLeaseV15(ROOT)
    if not lease.acquire():
        existing = master_v17_surface_status()
        if existing.get("current"):
            print("JARVIS V17 supervisor is already owned. Opening the existing workstation.")
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
        print("JARVIS V17 unified workstation preflight...")
        print("Master target: V17 unified workstation on 8797")
        print("Trading target: autonomous-options PAPER service on 8787")
        print("Quant adoption contract: current adaptive crypto PAPER status is REQUIRED")
        print("Verified V12-V16 intelligence and canonical Paper Desk are preserved.")
        print("Start INTRADAY/SWING once; option contract selection is automatic thereafter.")
        print("Broad scanning is allowed; no forced trade quota exists.")
        print("Live broker execution remains LOCKED.")
        browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}
        return JarvisRuntimeSupervisorV17(
            root=ROOT,
            services=v17_services(ROOT),
            browser=browser,
        ).run_forever()
    finally:
        lease.release()


if __name__ == "__main__":
    raise SystemExit(main())
