from __future__ import annotations

import importlib.util

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.nautilus_bridge import (
    nautilus_research_bridge,
)


def nautilus_kernel_status():

    core = verify_protected_core()

    kernel = (
        nautilus_research_bridge
        .status()
    )


    return {
        "protected_core":
            core.ok,

        "available":
            bool(
                kernel.get(
                    "available"
                )
            ),

        "version":
            kernel.get(
                "nautilus_version"
            ),

        "engine":
            kernel.get(
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

        "jarvis_bar_bridge":
            True,

        "signal_replay_adapter":
            True,

        "simulated_venue":
            True,

        "simulated_account":
            True,

        "virtual_order_lifecycle":
            True,

        "event_driven_backtest":
            True,

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

        "automatic_broker_order":
            False,

        "production_self_modification":
            False,

        "research_only":
            True,
    }
