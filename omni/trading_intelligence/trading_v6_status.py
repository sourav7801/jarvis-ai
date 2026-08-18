from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)


class TradingIntelligenceV6Status:

    def status(
        self,
    ):

        core = verify_protected_core()


        fyers = (
            FyersReadOnlyAdapter()
            .capabilities()
        )


        return {
            "protected_core":
                core.ok,

            "research_only":
                True,

            "paper_only":
                True,

            "live_execution":
                False,

            "live_market_read_bridge":
                True,

            "canonical_fyers_quote":
                fyers.get(
                    "quote"
                ),

            "canonical_fyers_history":
                fyers.get(
                    "history"
                ),

            "native_fyers_option_chain":
                fyers.get(
                    "option_chain"
                ),

            "virtual_fills":
                True,

            "virtual_long":
                True,

            "virtual_short":
                True,

            "same_tick_reversal":
                False,

            "market_freshness_guard":
                True,

            "future_timestamp_guard":
                True,

            "stale_data_execution":
                False,

            "kill_switch":
                True,

            "explicit_resume":
                True,

            "evidence_ledger":
                True,

            "performance_drift":
                True,

            "research_strategy_weighting":
                True,

            "research_weights_drive_broker_capital":
                False,

            "shadow_champion_challenger":
                True,

            "paper_performance_summary":
                True,

            "background_market_polling":
                False,

            "automatic_strategy_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "automatic_broker_order":
                False,

            "automatic_live_position_management":
                False,

            "production_self_modification":
                False,
        }


trading_intelligence_v6_status = (
    TradingIntelligenceV6Status()
)
