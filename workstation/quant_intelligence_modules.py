from __future__ import annotations

"""Read-only intelligence surfaces used by the standalone Quant modules.

This module composes the existing verified-data engines into one advanced
research surface. It never places broker orders, fabricates unavailable values,
or relaxes any Paper Desk gate.
"""

from datetime import datetime, timezone
from typing import Any


SUPPORTED_MODULES = {
    "adaptive-brain",
    "option-chain",
    "oi-iv",
    "fvg",
    "liquidity",
    "order-flow",
    "structure",
    "patterns",
    "heatmaps",
    "portfolio-risk",
    "trade-journal",
    "learning",
    "strategy-lab",
    "self-improvement",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_failure(module: str, symbol: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "module": module,
        "symbol": symbol,
        "message": str(message)[:700],
        "paper_only": True,
        "live_execution": False,
        "generated_at": _now(),
    }


def _analysis_timeframe(profile: str) -> str:
    value = str(profile or "adaptive_intraday").strip().lower()
    mapping = {
        "1m": "1m",
        "1m_only": "1m",
        "3m": "3m",
        "5m": "5m",
        "5m_only": "5m",
        "15m": "15m",
        "15m_only": "15m",
        "30m": "30m",
        "1h": "1h",
        "1h_only": "1h",
        "2h": "2h",
        "4h": "4h",
        "1d": "1d",
        "swing": "1h",
        "adaptive_intraday": "15m",
        "paper_exploration": "15m",
        "intraday": "15m",
    }
    return mapping.get(value, "15m")


def _feature_rows(
    symbol: str,
    profile: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from workstation.quant_terminal_v2 import scan_payload

    scan = scan_payload(symbol, profile=profile)
    rows: list[dict[str, Any]] = []
    for item in list(scan.get("evidence") or []):
        features = item.get("features") if isinstance(item, dict) else None
        if not isinstance(features, dict):
            features = {}
        liquidity = (
            features.get("liquidity")
            if isinstance(features.get("liquidity"), dict)
            else {}
        )
        indicators = (
            features.get("indicators")
            if isinstance(features.get("indicators"), dict)
            else {}
        )
        structure = (
            features.get("structure")
            if isinstance(features.get("structure"), dict)
            else {}
        )
        patterns = features.get("patterns")
        rows.append(
            {
                "timeframe": item.get("timeframe"),
                "available": bool(item.get("available", features.get("success"))),
                "source": item.get("source"),
                "data_quality": item.get("data_quality"),
                "fresh": item.get("fresh"),
                "structure": dict(structure),
                "support_resistance": dict(features.get("support_resistance") or {}),
                "supply_demand": list(features.get("supply_demand") or []),
                "liquidity": dict(liquidity),
                "fair_value_gaps": list(liquidity.get("fair_value_gaps") or []),
                "patterns": patterns if isinstance(patterns, (dict, list)) else {},
                "indicators": dict(indicators),
                "order_flow_proxy": {
                    "relative_volume": indicators.get("relative_volume"),
                    "volume_ratio": item.get("volume_ratio"),
                    "liquidity_sweeps": list(liquidity.get("sweeps") or []),
                    "equal_highs": list(liquidity.get("equal_highs") or []),
                    "equal_lows": list(liquidity.get("equal_lows") or []),
                    "fair_value_gaps": list(liquidity.get("fair_value_gaps") or []),
                    "premium_discount": liquidity.get("premium_discount"),
                    "dealing_range": dict(liquidity.get("dealing_range") or {}),
                    "identity_claim": (
                        "COMPLETED_BAR_PRICE_VOLUME_PROXY_NOT_L2_DOM_OR_TICK_TAPE"
                    ),
                },
                "price": features.get("price", item.get("close")),
            }
        )
    return scan, rows


def _options_payload(
    module: str,
    symbol: str,
    expiry: str | None = None,
) -> dict[str, Any]:
    canonical = str(symbol or "NIFTY").upper().replace(" ", "")
    aliases = {
        "NIFTY50": "NIFTY",
        "BANKNIFTY": "BANKNIFTY",
        "BANKNIFTYINDEX": "BANKNIFTY",
    }
    canonical = aliases.get(canonical, canonical)
    if canonical in {
        "NIFTY",
        "BANKNIFTY",
        "CRUDEOIL",
        "GOLD",
        "SILVER",
        "NATURALGAS",
    }:
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
        "Verified option chains are available for NIFTY, BANKNIFTY, BTC, ETH "
        "and supported MCX commodities when the provider exposes a current "
        "listed chain.",
    )


def _heatmap_payload(
    module: str,
    symbol: str,
    universe: str | None,
) -> dict[str, Any]:
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
            else f"No completed {requested} scanner rows are cached. Run the governed "
            "multi-market scan first."
        ),
        "paper_only": True,
        "live_execution": False,
        "generated_at": _now(),
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
        "generated_at": _now(),
    }
    if module == "trade-journal":
        result.update(
            {
                "closed_positions": list(dashboard.get("closed_positions") or []),
                "events": list(dashboard.get("events") or []),
                "review": paper_desk.performance_review(days=31),
                "message": (
                    "Durable Paper Desk journal loaded with frozen entry evidence "
                    "where available."
                ),
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


def _adaptive_payload(
    module: str,
    symbol: str,
    profile: str,
) -> dict[str, Any]:
    from workstation.quant_firm_runtime import decision_payload

    timeframe = _analysis_timeframe(profile)
    decision = decision_payload(symbol, timeframe)
    return {
        "success": bool(decision.get("success")),
        "module": module,
        "symbol": symbol,
        "profile": profile,
        "timeframe": timeframe,
        "decision": decision,
        "source": "ADAPTIVE_QUANT_BRAIN_VERIFIED_CANDLES",
        "message": (
            decision.get("message")
            or "Adaptive Quant Brain decision, structure, indicators and votes loaded."
        ),
        "paper_only": True,
        "live_execution": False,
        "generated_at": _now(),
    }


def _learning_payload(module: str, symbol: str) -> dict[str, Any]:
    from omni.trading_intelligence.trade_learning_engine import learning_engine

    status = learning_engine.status()
    mistakes = learning_engine.mistake_report()
    return {
        "success": True,
        "module": module,
        "symbol": symbol,
        "learning": status,
        "strategy_leaderboard": list(status.get("strategy_leaderboard") or []),
        "family_weights": dict(status.get("family_weights") or {}),
        "mistakes": list(mistakes.get("ranked_mistakes") or []),
        "recent_losses": list(mistakes.get("recent_losses") or []),
        "source": "PERSISTENT_BOUNDED_PAPER_TRADE_LEARNING",
        "message": (
            "Bounded paper-outcome learning loaded. Reliability weights remain "
            "clamped and production code is never rewritten automatically."
        ),
        "paper_only": True,
        "live_execution": False,
        "generated_at": _now(),
    }


def _strategy_lab_payload(
    module: str,
    symbol: str,
    profile: str,
) -> dict[str, Any]:
    from omni.trading_intelligence.strategy_research_lab import research_candidates
    from workstation.quant_terminal_v2 import candles_payload

    timeframe = _analysis_timeframe(profile)
    market = candles_payload(symbol, timeframe, 950)
    candles = list(market.get("candles") or []) if market.get("success") else []
    if len(candles) < 120:
        return _safe_failure(
            module,
            symbol,
            f"Strategy Lab requires at least 120 verified {timeframe} historical "
            f"candles; only {len(candles)} are currently available.",
        )
    research = research_candidates(symbol, timeframe, candles)
    return {
        **research,
        "success": bool(research.get("success", True)),
        "module": module,
        "symbol": symbol,
        "profile": profile,
        "timeframe": timeframe,
        "source": market.get("source") or "VERIFIED_HISTORICAL_CANDLES",
        "message": (
            "Strategy Lab synthesis, backtest and walk-forward research completed. "
            "Only governed paper challengers may pass; no live promotion occurs."
        ),
        "paper_only": True,
        "live_execution": False,
        "generated_at": _now(),
    }


def _self_improvement_payload(module: str, symbol: str) -> dict[str, Any]:
    from omni.trading_intelligence.self_improvement_coordinator import (
        self_improvement_coordinator,
    )

    status = self_improvement_coordinator.status()
    return {
        "success": True,
        "module": module,
        "symbol": symbol,
        "self_improvement": status,
        "source": "GOVERNED_BACKGROUND_RESEARCH_COORDINATOR",
        "message": (
            "Self-improvement research status loaded. It can generate paper "
            "challengers, but cannot edit production strategy code or enable "
            "live execution."
        ),
        "paper_only": True,
        "live_execution": False,
        "generated_at": _now(),
    }


def _feature_payload(
    module: str,
    symbol: str,
    profile: str,
) -> dict[str, Any]:
    scan, rows = _feature_rows(symbol, profile)
    descriptions = {
        "fvg": "Fair-value-gap and supply/demand evidence loaded.",
        "liquidity": (
            "Liquidity pools, sweeps, dealing range, premium/discount and FVG "
            "evidence loaded."
        ),
        "order-flow": (
            "Completed-bar price/volume and liquidity proxy loaded. This is not "
            "exchange L2/DOM/tick-tape order flow."
        ),
        "structure": "BOS/CHOCH, swing structure and support/resistance evidence loaded.",
        "patterns": "Candlestick and higher-order chart-pattern evidence loaded.",
    }
    return {
        "success": bool(scan.get("success")),
        "module": module,
        "symbol": symbol,
        "profile": profile,
        "timeframes": rows,
        "decision": {
            key: scan.get(key)
            for key in (
                "qualified",
                "candidate_side",
                "score",
                "regime",
                "alignment",
                "blockers",
                "entry",
                "stop",
                "target",
                "risk_reward",
                "message",
            )
        },
        "source": "UNIFIED_FEATURE_ENGINE_COMPLETED_BARS",
        "message": scan.get("message") or descriptions.get(
            module,
            f"{module.upper()} evidence loaded.",
        ),
        "paper_only": True,
        "live_execution": False,
        "generated_at": _now(),
    }


def intelligence_module_payload(
    module: str,
    symbol: str = "NIFTY",
    *,
    universe: str | None = None,
    profile: str = "adaptive_intraday",
    expiry: str | None = None,
) -> dict[str, Any]:
    name = str(module or "").strip().lower()
    canonical = str(symbol or "NIFTY").strip().upper()
    if name not in SUPPORTED_MODULES:
        return _safe_failure(
            name or "unknown",
            canonical,
            "Unknown Quant intelligence module.",
        )
    try:
        if name in {"option-chain", "oi-iv"}:
            return _options_payload(name, canonical, expiry)
        if name == "heatmaps":
            return _heatmap_payload(name, canonical, universe)
        if name in {"portfolio-risk", "trade-journal"}:
            return _paper_payload(name, canonical)
        if name == "adaptive-brain":
            return _adaptive_payload(name, canonical, profile)
        if name == "learning":
            return _learning_payload(name, canonical)
        if name == "strategy-lab":
            return _strategy_lab_payload(name, canonical, profile)
        if name == "self-improvement":
            return _self_improvement_payload(name, canonical)
        return _feature_payload(name, canonical, profile)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        if (
            name in {"option-chain", "oi-iv"}
            and canonical
            in {"NIFTY", "BANKNIFTY", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}
            and ("401" in message or "unauthorized" in message.lower())
        ):
            message = (
                "FYERS rejected the read-only option request. The daily FYERS "
                "session has expired or is unauthorized; run the local FYERS "
                "login and refresh. JARVIS did not substitute synthetic OI, IV, "
                "Greeks or contracts."
            )
        elif (
            name in {"option-chain", "oi-iv"}
            and canonical
            in {"NIFTY", "BANKNIFTY", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}
            and ("429" in message or "too many requests" in message.lower())
        ):
            message = (
                "FYERS temporarily rate-limited the read-only option request. "
                "JARVIS preserved the last verified cache when available and did "
                "not invent contracts, OI, IV or Greeks. Wait briefly, then "
                "refresh once."
            )
        return _safe_failure(name, canonical, message)
