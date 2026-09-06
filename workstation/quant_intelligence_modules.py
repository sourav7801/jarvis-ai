from __future__ import annotations

"""Read-only intelligence surfaces used by the standalone Quant modules.

This module deliberately composes existing verified-data engines.  It does not
place orders, manufacture unavailable values, or relax any Paper Desk gate.
"""

from datetime import datetime, timezone
from typing import Any


SUPPORTED_MODULES = {
    "option-chain",
    "oi-iv",
    "fvg",
    "structure",
    "heatmaps",
    "portfolio-risk",
    "trade-journal",
}


def _safe_failure(module: str, symbol: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "module": module,
        "symbol": symbol,
        "message": str(message)[:500],
        "paper_only": True,
        "live_execution": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _feature_rows(symbol: str, profile: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from workstation.quant_terminal_v2 import scan_payload

    scan = scan_payload(symbol, profile=profile)
    rows: list[dict[str, Any]] = []
    for item in list(scan.get("evidence") or []):
        features = item.get("features") if isinstance(item, dict) else None
        if not isinstance(features, dict):
            features = {}
        rows.append(
            {
                "timeframe": item.get("timeframe"),
                "available": bool(item.get("available", features.get("success"))),
                "source": item.get("source"),
                "data_quality": item.get("data_quality"),
                "fresh": item.get("fresh"),
                "structure": dict(features.get("structure") or {}),
                "support_resistance": dict(features.get("support_resistance") or {}),
                "supply_demand": list(features.get("supply_demand") or []),
                "fair_value_gaps": list(
                    (features.get("liquidity") or {}).get("fair_value_gaps") or []
                ),
                "patterns": dict(features.get("patterns") or {}),
                "price": features.get("price", item.get("close")),
            }
        )
    return scan, rows


def _options_payload(module: str, symbol: str, expiry: str | None = None) -> dict[str, Any]:
    canonical = str(symbol or "NIFTY").upper().replace(" ", "")
    aliases = {"NIFTY50": "NIFTY", "BANKNIFTY": "BANKNIFTY", "BANKNIFTYINDEX": "BANKNIFTY"}
    canonical = aliases.get(canonical, canonical)
    if canonical in {"NIFTY", "BANKNIFTY", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}:
        from workstation.india_options_intelligence import option_chain_snapshot

        result = option_chain_snapshot(canonical, expiry=expiry) or {}
        return {
            **result,
            "success": bool(result.get("success")),
            "module": module,
            "symbol": canonical,
            "paper_only": True,
            "live_execution": False,
        }
    if canonical in {"BTC", "ETH"}:
        from workstation.crypto_options_intelligence import option_chain_snapshot

        result = option_chain_snapshot(canonical, expiry=expiry)
        return {
            **result,
            "success": bool(result.get("success")),
            "module": module,
            "symbol": canonical,
            "paper_only": True,
            "live_execution": False,
        }
    return _safe_failure(
        module,
        canonical,
        "Verified option chains are available for NIFTY, BANKNIFTY, BTC, ETH and supported MCX commodities when the provider exposes a current listed chain.",
    )


def _heatmap_payload(module: str, symbol: str, universe: str | None) -> dict[str, Any]:
    from workstation.multi_market_scanner import MULTI_MARKET_SCANNER

    requested = str(universe or "").strip().upper()
    if not requested:
        requested = {
            "NIFTY": "NIFTY50",
            "NIFTY50": "NIFTY50",
            "BANKNIFTY": "BANKNIFTY",
            "SENSEX": "SENSEX30",
            "BTC": "CRYPTO_MAJOR",
            "ETH": "CRYPTO_MAJOR",
            "SOL": "CRYPTO_MAJOR",
            "CRUDEOIL": "MCX_MAJOR",
            "GOLD": "MCX_MAJOR",
            "SILVER": "MCX_MAJOR",
            "NATURALGAS": "MCX_MAJOR",
        }.get(str(symbol or "NIFTY").upper(), "NIFTY50")
    snapshot = MULTI_MARKET_SCANNER.status()
    rows = [
        dict(row)
        for row in list(snapshot.get("results") or [])
        if row.get("success") and requested in list(row.get("universes") or [])
    ]
    return {
        "success": True,
        "module": module,
        "symbol": str(symbol or "NIFTY").upper(),
        "universe": requested,
        "rows": rows,
        "scanner_running": bool(snapshot.get("running")),
        "scanner_completed_at": snapshot.get("completed_at"),
        "source": "MULTI_MARKET_SCANNER_COMPLETED_BARS",
        "message": (
            f"Loaded {len(rows)} verified completed-bar heatmap rows for {requested}."
            if rows
            else f"No completed {requested} scanner rows are cached. Run the governed multi-market scan first."
        ),
        "paper_only": True,
        "live_execution": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _paper_payload(module: str, symbol: str) -> dict[str, Any]:
    from workstation.paper_trading_desk import paper_dashboard_payload, paper_desk

    dashboard = paper_dashboard_payload()
    result = {
        "success": True,
        "module": module,
        "symbol": str(symbol or "NIFTY").upper(),
        "paper_only": True,
        "live_execution": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if module == "trade-journal":
        result.update(
            {
                "closed_positions": list(dashboard.get("closed_positions") or []),
                "events": list(dashboard.get("events") or []),
                "review": paper_desk.performance_review(days=31),
                "message": "Durable Paper Desk journal loaded with frozen entry evidence where available.",
            }
        )
    else:
        result.update(
            {
                "portfolio": dict(dashboard.get("portfolio") or {}),
                "autonomy": dict(dashboard.get("autonomy") or {}),
                "defined_risk_option_spreads": dict(
                    dashboard.get("defined_risk_option_spreads") or {}
                ),
                "message": "Paper portfolio risk and autonomy gates loaded.",
            }
        )
    return result


def intelligence_module_payload(
    module: str,
    symbol: str = "NIFTY",
    *,
    universe: str | None = None,
    profile: str = "intraday",
    expiry: str | None = None,
) -> dict[str, Any]:
    name = str(module or "").strip().lower()
    canonical = str(symbol or "NIFTY").strip().upper()
    if name not in SUPPORTED_MODULES:
        return _safe_failure(name or "unknown", canonical, "Unknown Quant intelligence module.")
    try:
        if name in {"option-chain", "oi-iv"}:
            return _options_payload(name, canonical, expiry)
        if name == "heatmaps":
            return _heatmap_payload(name, canonical, universe)
        if name in {"portfolio-risk", "trade-journal"}:
            return _paper_payload(name, canonical)

        scan, rows = _feature_rows(canonical, profile)
        return {
            "success": bool(scan.get("success")),
            "module": name,
            "symbol": canonical,
            "profile": profile,
            "timeframes": rows,
            "decision": {
                key: scan.get(key)
                for key in (
                    "qualified", "candidate_side", "score", "regime", "alignment",
                    "blockers", "entry", "stop", "target", "risk_reward", "message",
                )
            },
            "source": "UNIFIED_FEATURE_ENGINE_COMPLETED_BARS",
            "message": scan.get("message") or f"{name.upper()} evidence loaded.",
            "paper_only": True,
            "live_execution": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        if (
            name in {"option-chain", "oi-iv"}
            and canonical in {"NIFTY", "BANKNIFTY", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}
            and ("401" in message or "unauthorized" in message.lower())
        ):
            message = (
                "FYERS rejected the read-only option request. The daily FYERS session "
                "has expired or is unauthorized; run the local FYERS login and refresh. "
                "JARVIS did not substitute synthetic OI, IV, Greeks or contracts."
            )
        elif (
            name in {"option-chain", "oi-iv"}
            and canonical in {"NIFTY", "BANKNIFTY", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}
            and ("429" in message or "too many requests" in message.lower())
        ):
            message = (
                "FYERS temporarily rate-limited the read-only option request. "
                "JARVIS preserved the last verified cache when available and did not invent "
                "contracts, OI, IV or Greeks. Wait briefly, then refresh once."
            )
        return _safe_failure(name, canonical, message)
