from __future__ import annotations

import importlib.util


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.nautilus_c2_bridge import (
    nautilus_c2_bridge,
)


def nautilus_c2_status():

    core = verify_protected_core()

    capabilities = (
        nautilus_c2_bridge
        .capabilities()
    )


    return {
        "protected_core":
            core.ok,

        "available":
            capabilities.get(
                "available",
                False,
            ),

        "version":
            capabilities.get(
                "nautilus_version"
            ),

        "engine":
            capabilities.get(
                "engine"
            ),

        "isolated_subprocess":
            True,

        "main_venv_imports_nautilus":
            (
                importlib.util.find_spec(
                    "nautilus_trader"
                )
                is not None
            ),

        "supported_instruments":
            capabilities.get(
                "supported_instruments",
                (),
            ),

        "execution_profiles":
            capabilities.get(
                "execution_profiles",
                (),
            ),

        "fx":
            True,

        "equity":
            True,

        "future":
            True,

        "commodity_future":
            True,

        "listed_option":
            True,

        "single_leg_option_short":
            False,

        "fill_model_profiles":
            True,

        "fee_model_profiles":
            True,

        "latency_model_profiles":
            True,

        "native_nautilus_reconciliation":
            True,

        "v5_validation_adapter":
            True,

        "portfolio_research_foundation":
            True,

        "timing_semantics_calibrated":
            True,

        "exact_pnl_equivalence_required":
            False,

        "paper_only":
            True,

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

        "automatic_broker_order":
            False,

        "automatic_portfolio_rebalance":
            False,

        "production_self_modification":
            False,

        "research_only":
            True,
    }
