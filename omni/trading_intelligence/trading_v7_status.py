from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.fyers_v7_bridge import (
    fyers_v7_readonly_bridge,
)


def trading_v7_status():

    core = verify_protected_core()

    fyers = (
        fyers_v7_readonly_bridge
        .status()
    )


    return {
        "protected_core":
            core.ok,

        "research_only":
            True,

        "live_execution":
            False,

        "paper_only":
            True,

        "fyers_sdk_isolated":
            True,

        "fyers_sdk_version":
            fyers.get(
                "sdk_version"
            ),

        "fyers_option_chain_method":
            fyers.get(
                "option_chain_method"
            ),

        "fyers_market_depth_method":
            fyers.get(
                "depth_method"
            ),

        "real_option_chain_read":
            bool(
                fyers.get(
                    "available"
                )
            ),

        "real_market_depth_read":
            bool(
                fyers.get(
                    "available"
                )
            ),

        "api_call_during_install":
            False,

        "background_option_chain_polling":
            False,

        "historical_chain_store":
            True,

        "raw_chain_persistence":
            True,

        "historical_option_legs":
            True,

        "historical_atm_iv":
            True,

        "historical_iv_rank":
            True,

        "historical_iv_percentile":
            True,

        "historical_skew":
            True,

        "historical_pcr":
            True,

        "historical_oi":
            True,

        "historical_delta_oi":
            True,

        "expiry_term_structure":
            True,

        "underlying_futures_options_sync":
            True,

        "backward_asof_only":
            True,

        "future_data_leakage":
            False,

        "derivatives_regime_engine":
            True,

        "strategy_ensemble_research":
            True,

        "bounded_research_campaign":
            True,

        "campaign_candidate_limit":
            50,

        "v5_authoritative":
            True,

        "nautilus_c3_preserved":
            True,

        "legacy_v6_fyers_bridge_preserved":
            True,

        "single_leg_naked_option_short":
            False,

        "automatic_strategy_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_capital_allocation":
            False,

        "automatic_broker_order":
            False,

        "production_self_modification":
            False,
    }
