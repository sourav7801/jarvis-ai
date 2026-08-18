from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.derivatives_strategy_registry import (
    ensure_derivatives_strategies,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.option_chain_provider import (
    option_chain_providers,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)


class TradingIntelligenceV3Status:

    def status(
        self,
    ):

        core = verify_protected_core()


        ensure_derivatives_strategies()


        fyers = (
            FyersReadOnlyAdapter()
            .capabilities()
        )


        return {
            "protected_core":
                core.ok,

            "research_only":
                True,

            "live_execution":
                False,

            "option_chain_schema":
                True,

            "provider_neutral_option_chain":
                True,

            "registered_chain_providers":
                option_chain_providers.status(),

            "native_fyers_option_chain":
                fyers.get(
                    "option_chain"
                ),

            "native_fyers_market_depth":
                fyers.get(
                    "market_depth"
                ),

            "iv_rank":
                True,

            "iv_percentile":
                True,

            "strike_iv_skew":
                True,

            "iv_term_structure":
                True,

            "pcr_oi":
                True,

            "pcr_volume":
                True,

            "change_in_oi_structure":
                True,

            "oi_walls":
                True,

            "volume_leaders":
                True,

            "atm_relationships":
                True,

            "unusual_volume_oi":
                True,

            "max_pain_research":
                True,

            "max_pain_predictive_claim":
                False,

            "liquidity_scoring":
                True,

            "underlying_futures_options_confirmation":
                True,

            "expiry_intelligence":
                True,

            "defined_risk_vertical_spreads":
                True,

            "naked_option_selling":
                False,

            "commodity_contract_intelligence":
                True,

            "commodity_session_intelligence":
                True,

            "commodity_roll_intelligence":
                True,

            "derivatives_strategy_count":
                3,

            "total_runtime_strategy_count":
                len(
                    strategy_registry.all()
                ),

            "automatic_strategy_promotion":
                False,

            "automatic_parameter_promotion":
                False,

            "automatic_broker_order":
                False,
        }


trading_intelligence_v3_status = (
    TradingIntelligenceV3Status()
)
