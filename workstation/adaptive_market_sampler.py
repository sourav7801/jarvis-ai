from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable

from omni.trading_intelligence.adaptive_opportunity_policy import ADAPTIVE_OPPORTUNITY_POLICY


QUANT_BASE = "http://127.0.0.1:8787"
DEFAULT_PROFILES = ("5m_only", "10m_only", "15m_only", "adaptive_intraday", "swing")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quant_json(path: str, params: dict[str, Any] | None = None, *, timeout: float = 15.0) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    url = QUANT_BASE + path + ("?" + query if query else "")
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "JARVIS-V12-Adaptive-Sampler/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read(1_000_000).decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise RuntimeError("Quant endpoint returned a non-object payload")
    return payload


def _sample_profile(symbol: str, profile: str) -> dict[str, Any]:
    try:
        scan = _quant_json("/api/scan", {"symbol": symbol, "profile": profile}, timeout=25.0)
        adaptive = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(scan)
        return {
            "success": bool(scan.get("success")),
            "symbol": scan.get("symbol") or symbol,
            "profile": scan.get("profile") or profile,
            "timeframe": scan.get("timeframe"),
            "legacy_qualified": bool(scan.get("qualified")),
            "legacy_side": scan.get("side"),
            "candidate_side": scan.get("candidate_side"),
            "legacy_score": scan.get("score"),
            "alignment": scan.get("alignment"),
            "risk_reward": scan.get("risk_reward"),
            "regime": scan.get("regime"),
            "legacy_blockers": list(scan.get("blockers") or []),
            "adaptive": adaptive,
            "entry": scan.get("entry"),
            "stop": scan.get("stop"),
            "target": scan.get("target"),
            "message": scan.get("message"),
            "paper_only": True,
            "live_execution": False,
        }
    except Exception as exc:
        return {
            "success": False,
            "symbol": symbol,
            "profile": profile,
            "error": f"{type(exc).__name__}: {exc}"[:500],
            "paper_only": True,
            "live_execution": False,
        }


def sample_market(
    symbol: str = "BTC",
    *,
    profiles: Iterable[str] = DEFAULT_PROFILES,
) -> dict[str, Any]:
    normalized = str(symbol or "BTC").strip().upper() or "BTC"
    selected = []
    for raw in profiles:
        token = str(raw or "").strip()
        if token and token not in selected:
            selected.append(token)
    selected = selected[:8] or list(DEFAULT_PROFILES)

    rows = [_sample_profile(normalized, profile) for profile in selected]
    actionable = [
        row
        for row in rows
        if row.get("success")
        and isinstance(row.get("adaptive"), dict)
        and row["adaptive"].get("executable") is True
    ]
    actionable.sort(
        key=lambda row: (
            float((row.get("adaptive") or {}).get("utility") or -999.0),
            float((row.get("adaptive") or {}).get("expected_value_r") or -999.0),
        ),
        reverse=True,
    )

    try:
        controller = _quant_json("/api/paper/portfolio-controller", timeout=15.0)
    except Exception as exc:
        controller = {
            "success": False,
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }

    best = actionable[0] if actionable else None
    return {
        "success": any(row.get("success") for row in rows),
        "version": "12.0",
        "service": "JARVIS_ADAPTIVE_MARKET_SAMPLER",
        "sampled_at": _now(),
        "symbol": normalized,
        "profiles": selected,
        "samples": rows,
        "actionable_count": len(actionable),
        "best_adaptive_sample": best,
        "portfolio_controller": {
            "success": controller.get("success"),
            "running": controller.get("running"),
            "active_mandates": controller.get("active_mandates") or [],
            "decision_authority": controller.get("decision_authority"),
            "score_contract": controller.get("score_contract") or {},
        },
        "interpretation": (
            "PRIMARY/PROBE is determined from expected value, uncertainty, learning and hard safety/data blockers. "
            "A legacy score below 67/68/70 is not, by itself, a V12 reason to refuse a paper trade."
        ),
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


class AdaptiveMarketSampler:
    def sample(self, symbol: str = "BTC") -> dict[str, Any]:
        return sample_market(symbol)

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "12.0",
            "service": "JARVIS_ADAPTIVE_MARKET_SAMPLER",
            "quant_source": QUANT_BASE,
            "profiles": list(DEFAULT_PROFILES),
            "read_only": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


ADAPTIVE_MARKET_SAMPLER = AdaptiveMarketSampler()

__all__ = ["ADAPTIVE_MARKET_SAMPLER", "DEFAULT_PROFILES", "sample_market"]
