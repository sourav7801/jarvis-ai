from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.nautilus_c3_bridge import (
    nautilus_c3_portfolio_bridge,
)


def nautilus_c3_status():

    core = verify_protected_core()


    return {
        "protected_core":
            core.ok,

        "available":
            nautilus_c3_portfolio_bridge.available(),

        "engine":
            "BacktestEngine",

        "single_event_driven_engine":
            True,

        "multi_instrument":
            True,

        "multiple_strategy_instances":
            True,

        "unified_venue_account":
            True,

        "single_base_currency_per_portfolio":
            True,

        "cross_instrument_correlation":
            True,

        "concentration_analytics":
            True,

        "concentration_uses_input_notional_proxy":
            True,

        "drawdown_attribution":
            True,

        "drawdown_attribution_is_signal_proxy":
            True,

        "engine_account_report":
            True,

        "engine_fill_report":
            True,

        "engine_position_report":
            True,

        "execution_profile_stress_matrix":
            True,

        "automatic_execution_profile_selection":
            False,

        "nautilus_walk_forward_campaign":
            True,

        "chronological_oos":
            True,

        "oos_tuning":
            False,

        "candidate_reoptimized_on_oos":
            False,

        "v5_campaign_gate":
            True,

        "single_leg_option_short":
            False,

        "live_execution":
            False,

        "trading_node":
            False,

        "broker_adapter":
            False,

        "automatic_strategy_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_portfolio_allocation":
            False,

        "automatic_portfolio_rebalance":
            False,

        "automatic_broker_order":
            False,

        "production_self_modification":
            False,

        "research_only":
            True,
    }
