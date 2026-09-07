"""JARVIS V12 Adaptive Market Intelligence Completion surface.

Extends V11 cognitive execution with a continuous expected-value paper policy
and a live, read-only multi-profile market sampler.  V12 removes static Quant
score thresholds from paper execution authority while retaining hard data,
accounting, session, stale-feed and portfolio-risk boundaries.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Callable

from omni.loopback_http import exclusive_server
from omni.subsystem_snapshot import SubsystemSnapshotCollector, sanitize_error
from workstation import completion_console_v11 as v11


HOST = v11.HOST
PORT = v11.PORT
STATIC = v11.STATIC
HEALTH = v11.HEALTH
V12 = SubsystemSnapshotCollector(max_inflight=3)


def _adaptive_policy() -> dict[str, Any]:
    from omni.trading_intelligence.adaptive_opportunity_policy import ADAPTIVE_OPPORTUNITY_POLICY

    return ADAPTIVE_OPPORTUNITY_POLICY.status()


def _adaptive_sampler_status() -> dict[str, Any]:
    from workstation.adaptive_market_sampler import ADAPTIVE_MARKET_SAMPLER

    return ADAPTIVE_MARKET_SAMPLER.status()


def _direct_bridge_status() -> dict[str, Any]:
    from workstation.adaptive_direct_trade_bridge import status

    return status()


def _v12_providers() -> dict[str, Callable[[], Any]]:
    return {
        "adaptive_opportunity_policy": _adaptive_policy,
        "adaptive_market_sampler": _adaptive_sampler_status,
        "adaptive_direct_trade_bridge": _direct_bridge_status,
    }


def overview_payload() -> dict[str, Any]:
    payload = v11.overview_payload()
    payload["version"] = "12.0"
    advanced = V12.collect(_v12_providers(), timeout=2.0)
    payload.setdefault("subsystems", {}).update(advanced)
    for name, row in advanced.items():
        payload[name] = row.get("data") if row.get("healthy") else None
    if not all(row.get("healthy") for row in advanced.values()):
        payload["overall"] = "DEGRADED"
    payload.setdefault("advanced", {}).update({
        "adaptive_expected_value_execution": True,
        "static_score_threshold_execution_authority": False,
        "adaptive_primary_probe_wait": True,
        "outcome_learning_calibration": True,
        "confidence_scaled_paper_risk": True,
        "live_multi_profile_market_sampler": True,
        "hard_data_safety_blockers_preserved": True,
        "quant_runtime_authoritative": True,
    })
    payload["decision_authority"] = {
        "version": "12.0",
        "model": "CONTINUOUS_EVIDENCE_EXPECTED_VALUE",
        "static_score_67_68_70": "OBSERVABILITY_ONLY",
        "static_alignment_gate": "OBSERVABILITY_ONLY",
        "static_risk_reward_profile_gate": "OBSERVABILITY_ONLY",
        "hard_blockers": "DATA / STALE / SESSION / ACCOUNTING / PORTFOLIO SAFETY",
        "actions": ["PRIMARY", "PROBE", "WAIT"],
    }
    payload.setdefault("safety", {}).update({
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    })
    return payload


class CompletionHandlerV12(v11.CompletionHandlerV11):
    server_version = "JARVISCompletion/12.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v12_adaptive_market.js":
            return self.send_file(STATIC / "v12_adaptive_market.js", "application/javascript; charset=utf-8")
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
                    "automatic_broker_order": False,
                }, 500)
        if path == "/api/adaptive-policy":
            return self.send_json(_adaptive_policy())
        if path == "/api/adaptive-market/sample":
            from workstation.adaptive_market_sampler import sample_market

            symbol = str((params.get("symbol") or ["BTC"])[0]).strip() or "BTC"
            try:
                payload = sample_market(symbol)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json({
                    "success": False,
                    "message": sanitize_error(exc)[:500],
                    "symbol": symbol,
                    "paper_only": True,
                    "live_execution": False,
                }, 503)
        if path == "/api/v12/status":
            return self.send_json({
                "success": True,
                "version": "12.0",
                "service": "JARVIS_ADAPTIVE_MARKET_INTELLIGENCE",
                "features": {
                    "v11_cognitive_execution": True,
                    "adaptive_expected_value_execution": True,
                    "static_score_threshold_execution_authority": False,
                    "primary_probe_wait": True,
                    "outcome_learning_calibration": True,
                    "confidence_scaled_paper_risk": True,
                    "live_multi_profile_sampler": True,
                    "adaptive_direct_trade_bridge": True,
                    "hard_safety_blockers_preserved": True,
                },
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
    # V11 completed-bar and discovery-routing bridges remain authoritative in
    # Quant. Completion only exposes policy/sampling observability.
    server = exclusive_server(HOST, PORT, CompletionHandlerV12)
    print("=" * 72)
    print("JARVIS V12 ADAPTIVE MARKET INTELLIGENCE CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("Decision authority: CONTINUOUS EXPECTED VALUE / UNCERTAINTY / LEARNING")
    print("Static score 67/68/70: OBSERVABILITY ONLY")
    print("Adaptive actions: PRIMARY / LOW-RISK PROBE / WAIT")
    print("Hard safety/data/accounting blockers: PRESERVED")
    print("Live market sampling: READ-ONLY QUANT LOOPBACK")
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
