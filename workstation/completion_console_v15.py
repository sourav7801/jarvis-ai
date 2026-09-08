"""JARVIS V15 Autonomous Market Reasoning Completion Center."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from omni.loopback_http import exclusive_server
from omni.subsystem_snapshot import sanitize_error
from workstation import completion_console_v141 as v141


HOST = v141.HOST
PORT = v141.PORT
STATIC = v141.STATIC
HEALTH = v141.HEALTH
QUANT_BASE = "http://127.0.0.1:8787"


def _quant_json(path: str, *, timeout: float = 30.0) -> dict[str, Any]:
    request = urllib.request.Request(
        QUANT_BASE + path,
        headers={"Accept": "application/json", "User-Agent": "JARVIS-V15-Completion/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read(2_000_000).decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise RuntimeError("Quant V15 endpoint returned non-object payload")
    return payload


def _runtime_status() -> dict[str, Any]:
    from workstation.v15_runtime_bridges import status
    return status()


def overview_payload() -> dict[str, Any]:
    payload = v141.overview_payload()
    payload["version"] = "15.0"
    runtime = _runtime_status()
    payload.setdefault("advanced", {}).update({
        "v141_verified_risk_geometry": True,
        "autonomous_market_reasoning": True,
        "persistent_market_beliefs": True,
        "multi_hypothesis_reasoning": True,
        "portfolio_opportunity_cost": True,
        "position_intelligence": True,
        "causal_trade_review": True,
        "execution_forensics": True,
        "supervisor_single_instance_safety": True,
    })
    payload["v15_runtime"] = runtime
    payload["decision_authority"] = {
        "version": "15.0",
        "model": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK",
        "v14_positive_contextual_ev_preserved": True,
        "v141_verified_risk_geometry_preserved": True,
        "legacy_score": "OBSERVABILITY_ONLY",
        "confidence": "POSITION_SIZE_INPUT_NOT_BINARY_GATE",
        "portfolio_allocator_can_only_reduce_v14_risk": True,
    }
    payload.setdefault("safety", {}).update({
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    })
    return payload


class CompletionHandlerV15(v141.CompletionHandlerV141):
    server_version = "JARVISCompletion/15.0"

    def _proxy(self, path: str, timeout: float = 30.0) -> None:
        try:
            return self.send_json(_quant_json(path, timeout=timeout))
        except Exception as exc:
            return self.send_json({
                "success": False,
                "version": "15.0",
                "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                "paper_only": True,
                "live_execution": False,
            }, 503)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v15_market_reasoning.js":
            return self.send_file(STATIC / "v15_market_reasoning.js", "application/javascript; charset=utf-8")
        if path == "/api/overview":
            try:
                payload = overview_payload()
                if payload.get("overall") == "READY":
                    HEALTH.mark_success()
                return self.send_json(payload)
            except Exception as exc:
                HEALTH.mark_error(exc)
                return self.send_json({
                    "success": False,
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                }, 500)
        if path == "/api/v15/reasoning-trace":
            symbol = urllib.parse.quote(str((params.get("symbol") or ["BTC"])[0]).strip().upper() or "BTC")
            return self._proxy(f"/api/v15/reasoning-trace?symbol={symbol}", timeout=100.0)
        if path == "/api/v15/market-beliefs":
            symbol = urllib.parse.quote(str((params.get("symbol") or ["BTC"])[0]).strip().upper() or "BTC")
            profile = urllib.parse.quote(str((params.get("profile") or ["5m_only"])[0]).strip() or "5m_only")
            return self._proxy(f"/api/v15/market-beliefs?symbol={symbol}&profile={profile}")
        if path == "/api/v15/position-intelligence":
            return self._proxy("/api/v15/position-intelligence")
        if path == "/api/v15/causal-trade-review":
            return self._proxy("/api/v15/causal-trade-review")
        if path == "/api/v15/execution-forensics":
            symbol = urllib.parse.quote(str((params.get("symbol") or [""])[0]).strip().upper())
            suffix = f"?symbol={symbol}" if symbol else ""
            return self._proxy("/api/v15/execution-forensics" + suffix)
        if path == "/api/v15/status":
            runtime = _runtime_status()
            quant_ready = False
            try:
                quant_status = _quant_json("/api/v15/status", timeout=8.0)
                quant_ready = (
                    quant_status.get("success") is True
                    and quant_status.get("service") == "JARVIS_QUANT_V15_AUTONOMOUS_MARKET_REASONING"
                )
            except Exception:
                quant_status = {"success": False}
            return self.send_json({
                "success": True,
                "version": "15.0",
                "service": "JARVIS_AUTONOMOUS_MARKET_REASONING_OS",
                "runtime_bridge_installed": runtime.get("installed") is True,
                "quant_reasoning_ready": quant_ready,
                "decision_authority": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK",
                "market_belief_model": True,
                "multi_hypothesis_reasoning": True,
                "portfolio_opportunity_cost": True,
                "position_intelligence": True,
                "causal_trade_review": True,
                "execution_forensics": True,
                "v141_risk_geometry_preserved": runtime.get("v141_risk_geometry_installed") is True,
                "invalid_risk_levels_hard_blocker_preserved": True,
                "permanent_agents": 29,
                "system_planes_do_not_count_as_agents": True,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
                "external_actions": "APPROVAL_GATED",
            })
        return super().do_GET()


def main() -> int:
    from workstation.v15_runtime_bridges import install_v15_runtime_bridges

    bridge = install_v15_runtime_bridges()
    server = exclusive_server(HOST, PORT, CompletionHandlerV15)
    print("=" * 72)
    print("JARVIS V15 AUTONOMOUS MARKET REASONING CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("Market beliefs: VERIFIED COMPLETED-BAR EVIDENCE")
    print("Hypotheses: COMPETING / EXPLAINABLE / MODEL ESTIMATES")
    print("Decision authority: PORTFOLIO-ADJUSTED CONTEXTUAL UTILITY")
    print("V14.1 risk geometry: PRESERVED")
    print("Portfolio allocator: CAN ONLY REDUCE V14 PAPER RISK")
    print("Decision quality: SEPARATE FROM OUTCOME")
    print("V15 bridge:", "READY" if bridge.get("installed") else "DEGRADED")
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
