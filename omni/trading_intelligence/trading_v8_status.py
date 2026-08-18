from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)


def trading_v8_status():

    core = verify_protected_core()


    return {
        "protected_core":
            core.ok,

        "research_only":
            True,

        "paper_only":
            True,

        "live_execution":
            False,

        "governed_capture_plans":
            True,

        "expiry_aware_capture_plans":
            True,

        "nearest_expiry_capture":
            True,

        "explicit_expiry_capture":
            True,

        "max_expiries_per_plan":
            4,

        "session_aware_collector":
            True,

        "interval_aware_collector":
            True,

        "collector_state_persistence":
            True,

        "background_collection":
            False,

        "explicit_collector_run":
            True,

        "real_fyers_market_data":
            True,

        "v7_history_store_reused":
            True,

        "historical_feature_dataset":
            True,

        "rolling_iv_rank":
            True,

        "rolling_iv_percentile":
            True,

        "delta_oi_features":
            True,

        "pcr_change_features":
            True,

        "skew_change_features":
            True,

        "oi_imbalance_features":
            True,

        "feature_lookahead":
            False,

        "underlying_futures_options_sync":
            True,

        "derivatives_regime_datasets":
            True,

        "v4_derivatives_evolution_adapter":
            True,

        "v5_candidate_validation_adapter":
            True,

        "v5_walk_forward_adapter":
            True,

        "nautilus_c3_derivatives_adapter":
            True,

        "cross_asset_regime_graph":
            True,

        "cross_asset_minimum_history_enforced":
            True,

        "research_portfolio_optimizer":
            True,

        "research_weights_drive_broker_capital":
            False,

        "automatic_execution_profile_selection":
            False,

        "automatic_strategy_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_capital_allocation":
            False,

        "automatic_portfolio_rebalance":
            False,

        "automatic_broker_order":
            False,

        "production_self_modification":
            False,

        "single_leg_naked_option_short":
            False,

        "v5_authoritative":
            True,

        "nautilus_c3_preserved":
            True,

        "trading_v7_preserved":
            True,
    }
