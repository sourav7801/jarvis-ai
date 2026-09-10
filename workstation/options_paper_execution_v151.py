from __future__ import annotations

from typing import Any, Mapping


SERVICE_VERSION = "OPTIONS_PAPER_EXECUTION_V15_1"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


class OptionsPaperExecutionV151:
    """Paper-only option execution adapter.

    The option-chain provider remains read-only. This adapter consumes a V15.1
    plan and opens a LONG premium position in PaperTradingDesk only. It has no
    broker client and no live order surface.
    """

    def open_plan(
        self,
        plan: Mapping[str, Any],
        *,
        desk=None,
        portfolio_bucket: str = "INTRADAY",
        bucket_allocation_fraction: float = 0.50,
        session_generation: int | None = None,
        signal_id: str | None = None,
    ) -> dict[str, Any]:
        payload = dict(plan or {})
        if payload.get("executable") is not True:
            return {
                "success": False,
                "reason": str(payload.get("reason") or "OPTION_PLAN_NOT_EXECUTABLE"),
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            }
        selected = payload.get("selected") if isinstance(payload.get("selected"), Mapping) else {}
        risk_plan = selected.get("risk_plan") if isinstance(selected.get("risk_plan"), Mapping) else {}
        spec = selected.get("instrument_spec") if isinstance(selected.get("instrument_spec"), Mapping) else {}
        symbol = str(selected.get("symbol") or "").strip().upper()
        entry = _f(risk_plan.get("entry"))
        stop = _f(risk_plan.get("stop"))
        target = _f(risk_plan.get("target"))
        risk_multiplier = max(0.0, min(_f(selected.get("risk_multiplier")), 1.0))
        lot_size = _f(spec.get("lot_size") or spec.get("contract_multiplier"))
        tick_size = _f(spec.get("tick_size"))
        if not symbol or spec.get("verified") is not True or lot_size <= 0.0 or tick_size <= 0.0:
            return {
                "success": False,
                "reason": "OPTION_INSTRUMENT_SPEC_UNVERIFIED",
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            }
        if not (0.0 < stop < entry < target):
            return {
                "success": False,
                "reason": "INVALID_OPTION_PREMIUM_RISK_LEVELS",
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            }
        if risk_multiplier <= 0.0:
            return {
                "success": False,
                "reason": "OPTION_RISK_MULTIPLIER_ZERO",
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            }

        if desk is None:
            from workstation.paper_autonomy_engine import paper_desk
            desk = paper_desk

        instrument_spec = {
            **dict(spec),
            "symbol": symbol,
            "provider_symbol": str(spec.get("provider_symbol") or symbol),
            "asset_class": "OPTION",
            "instrument_type": "OPTION",
            "quantity_step": 1.0,
            "contract_multiplier": lot_size,
            "tick_size": tick_size,
            "verified": True,
            "verification_reason": str(spec.get("verification_reason") or "VERIFIED_INSTRUMENT_MASTER"),
            "cost_model_status": str(spec.get("cost_model_status") or "UNCONFIGURED"),
        }
        metadata = {
            "session_generation": session_generation,
            "v151_option_execution": True,
            "underlying": payload.get("underlying"),
            "underlying_side": (payload.get("underlying_decision") or {}).get("side"),
            "underlying_expected_value_r": (payload.get("underlying_decision") or {}).get("expected_value_r"),
            "option_expected_value_r": selected.get("option_expected_value_r"),
            "option_utility": selected.get("option_utility"),
            "expiry": selected.get("expiry"),
            "strike": selected.get("strike"),
            "option_type": selected.get("option_type"),
            "verified_greeks": {
                name: (selected.get("quote") or {}).get(name)
                for name in ("delta", "gamma", "theta", "vega")
            },
            "implied_volatility": (selected.get("quote") or {}).get("implied_volatility"),
            "premium_risk_plan": dict(risk_plan),
            "premium_levels_are_risk_plan_estimates": True,
            "premium_levels_are_market_quotes": False,
            "long_premium_only": True,
            "naked_option_selling": False,
            "dealer_positioning": "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY",
            "paper_only": True,
            "live_execution": False,
        }
        from workstation.workspace_accounts import is_enabled
        if is_enabled(desk):
            from workstation.paper_trading_desk import live_mark_snapshot
            certificate = live_mark_snapshot(symbol)
            if not certificate.get("eligible_for_entry") or not certificate.get("bid") or not certificate.get("ask"):
                return {"success": False, "reason": certificate.get("reason") or "OPTION_EXECUTABLE_QUOTE_REQUIRED", "paper_only": True, "live_execution": False}
            entry = float(certificate["ask"])
            if not stop < entry < target:
                return {"success": False, "reason": "LIVE_OPTION_QUOTE_OUTSIDE_SETUP", "paper_only": True, "live_execution": False}
            metadata["entry_certificate"] = certificate
        result = desk.open_position(
            symbol=symbol,
            side="LONG",
            entry=entry,
            stop=stop,
            target=target,
            quantity=None,
            timeframe="OPTIONS",
            strategy="QUANT_OPTIONS_EXECUTION_V15_1",
            score=None,
            source="V15_1_OPTIONS_INTELLIGENCE",
            asset_type="OPTION",
            risk_multiplier=risk_multiplier,
            valuation_multiplier=1.0,
            instrument_spec=instrument_spec,
            portfolio_bucket=str(portfolio_bucket or "INTRADAY").upper(),
            bucket_allocation_fraction=max(0.0, min(float(bucket_allocation_fraction), 1.0)),
            metadata=metadata,
            external_id=("option:" + str(portfolio_bucket) + ":" + symbol + ":" + str(signal_id)) if signal_id else None,
        )
        return {
            **dict(result),
            "option_contract": symbol,
            "option_type": selected.get("option_type"),
            "long_premium_only": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "15.1",
            "service": SERVICE_VERSION,
            "paper_desk_final_authority": True,
            "long_premium_only": True,
            "naked_option_selling": False,
            "verified_instrument_spec_required": True,
            "verified_lot_size_required": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "paper_only": True,
        }


OPTIONS_PAPER_EXECUTION_V151 = OptionsPaperExecutionV151()

__all__ = ["OPTIONS_PAPER_EXECUTION_V151", "OptionsPaperExecutionV151", "SERVICE_VERSION"]
