from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.trading_guardrails import (
    trading_research_guard,
)


class TradingIntelligenceV1Status:

    def status(
        self,
    ):

        integrity = (
            verify_protected_core()
        )


        adapter = (
            FyersReadOnlyAdapter()
        )


        fyers = (
            adapter.capabilities()
        )


        bridge = (
            adapter.bridge_status()
        )


        return {
            "protected_core":
                integrity.ok,

            "research_only":
                True,

            "live_execution":
                False,

            "paper_only":
                True,

            "universal_instrument_schema":
                True,

            "equity_support":
                True,

            "index_support":
                True,

            "futures_support":
                True,

            "options_support":
                True,

            "commodity_schema_support":
                True,

            "currency_schema_support":
                True,

            "forex_schema_support":
                True,

            "crypto_schema_support":
                True,

            "feature_engine":
                True,

            "options_feature_engine":
                True,

            "greeks_engine":
                True,

            "regime_engine":
                True,

            "safe_strategy_dsl":
                True,

            "signal_engine":
                True,

            "performance_metrics":
                True,

            "dataset_engine":
                True,

            "strategy_count":
                len(
                    strategy_registry.all()
                ),

            "canonical_fyers_bridge":
                bridge,

            "fyers_discovered_capabilities":
                fyers,

            "guardrails": {
                "live_execution":
                    trading_research_guard
                    .LIVE_EXECUTION,

                "paper_only":
                    trading_research_guard
                    .PAPER_ONLY,
            },

            "automatic_strategy_promotion":
                False,

            "automatic_parameter_optimization":
                False,

            "automatic_broker_order":
                False,
        }


trading_intelligence_v1_status = (
    TradingIntelligenceV1Status()
)
