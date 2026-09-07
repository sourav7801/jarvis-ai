from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


SYNTHESIS_VERSION = "OPTIONS_VOLATILITY_SYNTHESIS_V13"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number == number else None
    except (TypeError, ValueError):
        return None


def _expected_move_from_analysis(analysis: Mapping[str, Any]) -> dict[str, Any]:
    call = analysis.get("atm_call") if isinstance(analysis.get("atm_call"), Mapping) else {}
    put = analysis.get("atm_put") if isinstance(analysis.get("atm_put"), Mapping) else {}
    call_ltp = _f(call.get("ltp") or call.get("last_price"))
    put_ltp = _f(put.get("ltp") or put.get("last_price"))
    spot = _f(analysis.get("spot"))
    if call_ltp is None or put_ltp is None or spot is None or spot <= 0:
        return {
            "available": False,
            "reason": "ATM_CALL_PUT_PREMIUM_NOT_AVAILABLE",
            "method": "ATM_STRADDLE_PREMIUM",
        }
    move = call_ltp + put_ltp
    return {
        "available": True,
        "method": "ATM_STRADDLE_PREMIUM",
        "absolute": round(move, 4),
        "percent_of_spot": round(move / spot * 100.0, 4),
        "predictive_guarantee": False,
    }


class OptionsVolatilitySynthesisV13:
    """Truthful synthesis over existing read-only option-chain/history engines.

    Dealer inventory/gamma positioning is never inferred from OI alone. If real
    dealer inventory is unavailable, V13 says unavailable rather than presenting
    a fabricated dealer-gamma number.
    """

    def analyze_snapshot(self, snapshot: Any) -> dict[str, Any]:
        from omni.trading_intelligence.option_chain_intelligence import option_chain_intelligence

        analysis = option_chain_intelligence.analyze(snapshot)
        expected_move = _expected_move_from_analysis(analysis)
        return {
            "success": True,
            "version": "13.0",
            "service": SYNTHESIS_VERSION,
            "generated_at": _now(),
            "underlying": analysis.get("underlying"),
            "spot": analysis.get("spot"),
            "timestamp": analysis.get("timestamp"),
            "expiries": analysis.get("expiries") or [],
            "atm_strike": analysis.get("atm_strike"),
            "pcr": {
                "oi": analysis.get("pcr_oi"),
                "volume": analysis.get("pcr_volume"),
                "change_in_oi": analysis.get("pcr_change_in_oi"),
            },
            "open_interest": {
                "call": analysis.get("call_oi"),
                "put": analysis.get("put_oi"),
                "call_change": analysis.get("call_change_in_oi"),
                "put_change": analysis.get("put_change_in_oi"),
                "call_wall": analysis.get("call_oi_wall"),
                "put_wall": analysis.get("put_oi_wall"),
            },
            "volume": {
                "call": analysis.get("call_volume"),
                "put": analysis.get("put_volume"),
                "call_leader": analysis.get("call_volume_leader"),
                "put_leader": analysis.get("put_volume_leader"),
            },
            "volatility": {
                "average_call_iv": analysis.get("average_call_iv"),
                "average_put_iv": analysis.get("average_put_iv"),
                "put_minus_call_iv": analysis.get("put_minus_call_iv"),
                "strike_skew": analysis.get("strike_iv_skew") or [],
            },
            "expected_move": expected_move,
            "liquidity_score": analysis.get("chain_liquidity_score"),
            "unusual_contracts": analysis.get("unusual_contracts") or [],
            "max_pain_research": analysis.get("max_pain_research"),
            "dealer_positioning": {
                "available": False,
                "reason": "NO_VERIFIED_DEALER_INVENTORY",
                "oi_is_not_dealer_inventory": True,
                "gamma_exposure_claim": None,
            },
            "verified_snapshot_only": True,
            "predictive_guarantee": False,
            "research_only": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def history(self, symbol: str, *, lookback: int = 252) -> dict[str, Any]:
        from omni.trading_intelligence.derivatives_history_analytics import derivatives_history_analytics

        analysis = derivatives_history_analytics.analyze(str(symbol or "").strip().upper(), lookback=max(2, min(int(lookback), 1000)))
        if not analysis.get("available"):
            return {
                "success": True,
                "version": "13.0",
                "service": SYNTHESIS_VERSION,
                "symbol": str(symbol or "").strip().upper(),
                "available": False,
                "snapshot_count": 0,
                "iv_rank": None,
                "iv_percentile": None,
                "term_structure": {},
                "oi_change": {"call": None, "put": None},
                "dealer_positioning": {
                    "available": False,
                    "reason": "NO_VERIFIED_DEALER_INVENTORY",
                },
                "no_data_fabrication": True,
                "research_only": True,
                "paper_only": True,
                "live_execution": False,
            }
        return {
            "success": True,
            "version": "13.0",
            "service": SYNTHESIS_VERSION,
            "generated_at": _now(),
            "symbol": analysis.get("symbol"),
            "available": True,
            "snapshot_count": analysis.get("snapshot_count"),
            "latest": analysis.get("latest"),
            "iv_rank": analysis.get("atm_iv_rank"),
            "iv_percentile": analysis.get("atm_iv_percentile"),
            "atm_skew": analysis.get("atm_skew"),
            "pcr_oi": analysis.get("pcr_oi"),
            "oi_change": {
                "call": analysis.get("delta_call_oi"),
                "put": analysis.get("delta_put_oi"),
            },
            "term_structure": analysis.get("term_structure") or {},
            "average_atm_iv": analysis.get("average_atm_iv"),
            "dealer_positioning": {
                "available": False,
                "reason": "NO_VERIFIED_DEALER_INVENTORY",
                "oi_is_not_dealer_inventory": True,
            },
            "verified_history_only": True,
            "no_data_fabrication": True,
            "predictive_guarantee": False,
            "research_only": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def status(self) -> dict[str, Any]:
        from omni.trading_intelligence.option_chain_provider import option_chain_providers

        return {
            "success": True,
            "version": "13.0",
            "service": SYNTHESIS_VERSION,
            "provider_registry": option_chain_providers.status(),
            "features": {
                "iv_rank_percentile_from_verified_history": True,
                "skew": True,
                "term_structure": True,
                "pcr": True,
                "oi_change": True,
                "expected_move_when_atm_premiums_available": True,
                "liquidity": True,
                "unusual_contracts": True,
                "dealer_inventory_fabrication": False,
            },
            "dealer_positioning": "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY",
            "research_only": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


OPTIONS_VOLATILITY_SYNTHESIS_V13 = OptionsVolatilitySynthesisV13()

__all__ = ["OPTIONS_VOLATILITY_SYNTHESIS_V13", "OptionsVolatilitySynthesisV13"]
