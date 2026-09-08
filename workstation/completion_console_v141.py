"""JARVIS V14.1 Risk-Geometry Convergence Center."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from omni.loopback_http import exclusive_server
from omni.subsystem_snapshot import sanitize_error
from workstation import completion_console_v14 as v14


HOST = v14.HOST
PORT = v14.PORT
STATIC = v14.STATIC
HEALTH = v14.HEALTH
QUANT_BASE = "http://127.0.0.1:8787"


def _quant_json(path: str, *, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        QUANT_BASE + path,
        headers={"Accept": "application/json", "User-Agent": "JARVIS-V14.1-Completion/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read(1_500_000).decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise RuntimeError("Quant V14.1 endpoint returned non-object payload")
    return payload


def _runtime_status() -> dict[str, Any]:
    from workstation.v141_runtime_bridges import status

    return status()


def overview_payload() -> dict[str, Any]:
    payload = v14.overview_payload()
    payload["version"] = "14.1"
    runtime = _runtime_status()
    payload.setdefault("advanced", {}).update({
        "v14_continuous_execution": True,
        "verified_risk_geometry_convergence": True,
        "legacy_qualification_required_for_risk_geometry": False,
        "invalid_risk_levels_hard_blocker_preserved_when_geometry_unavailable": True,
        "btc_execution_trace": True,
    })
    payload["risk_geometry_v141"] = runtime
    payload.setdefault("safety", {}).update({
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
    })
    return payload


class CompletionHandlerV141(v14.CompletionHandlerV14):
    server_version = "JARVISCompletion/14.1"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/api/overview":
            try:
                return self.send_json(overview_payload())
            except Exception as exc:
                return self.send_json({
                    "success": False,
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                }, 500)
        if path == "/api/v14.1/risk-geometry":
            symbol = urllib.parse.quote(str((params.get("symbol") or ["BTC"])[0]).strip().upper() or "BTC")
            profile = urllib.parse.quote(str((params.get("profile") or ["5m_only"])[0]).strip() or "5m_only")
            try:
                return self.send_json(_quant_json(f"/api/v14.1/risk-geometry?symbol={symbol}&profile={profile}"))
            except Exception as exc:
                return self.send_json({
                    "success": False,
                    "service": "JARVIS_V141_RISK_GEOMETRY_PROXY",
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                }, 503)
        if path == "/api/v14.1/execution-trace":
            symbol = urllib.parse.quote(str((params.get("symbol") or ["BTC"])[0]).strip().upper() or "BTC")
            try:
                return self.send_json(_quant_json(f"/api/v14.1/execution-trace?symbol={symbol}", timeout=90.0))
            except Exception as exc:
                return self.send_json({
                    "success": False,
                    "service": "JARVIS_V141_EXECUTION_TRACE_PROXY",
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                }, 503)
        if path == "/api/v14.1/status":
            runtime = _runtime_status()
            quant_ready = False
            try:
                quant_status = _quant_json("/api/v14.1/status", timeout=8.0)
                quant_ready = quant_status.get("success") is True
            except Exception:
                quant_status = {"success": False}
            return self.send_json({
                "success": True,
                "version": "14.1",
                "service": "JARVIS_RISK_GEOMETRY_CONVERGENCE_OS",
                "runtime_bridge_installed": runtime.get("installed") is True,
                "scan_wrapper_installed": runtime.get("scan_wrapper_installed") is True,
                "quant_risk_geometry_ready": quant_ready,
                "decision_authority": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
                "legacy_qualification_required_for_geometry": False,
                "invalid_risk_levels_hard_blocker_preserved": True,
                "permanent_agents": 29,
                "system_planes_do_not_count_as_agents": True,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
            })
        return super().do_GET()


def main() -> int:
    from workstation.v141_runtime_bridges import install_v141_runtime_bridges

    bridge = install_v141_runtime_bridges()
    server = exclusive_server(HOST, PORT, CompletionHandlerV141)
    print("=" * 72)
    print("JARVIS V14.1 RISK-GEOMETRY CONVERGENCE CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("Risk geometry: VERIFIED COMPLETED-BAR CLOSE + ATR + STRUCTURE")
    print("Legacy qualification required for geometry: NO")
    print("INVALID_RISK_LEVELS: preserved when verified geometry cannot be built")
    print("V14 positive contextual EV authority: PRESERVED")
    print("V14.1 bridge:", "READY" if bridge.get("installed") else "DEGRADED")
    print("Paper trading: PERMITTED")
    print("Live broker execution: LOCKED")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
