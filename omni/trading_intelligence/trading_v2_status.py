from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)


class TradingIntelligenceV2Status:

    def status(
        self,
    ):

        core = verify_protected_core()


        return {
            "protected_core":
                core.ok,

            "research_only":
                True,

            "live_execution":
                False,

            "historical_backtester":
                True,

            "next_bar_open_execution":
                True,

            "long_simulation":
                True,

            "short_simulation":
                True,

            "option_long_premium_simulation":
                True,

            "naked_option_premium_short":
                False,

            "commodity_future_simulation":
                True,

            "currency_future_simulation":
                True,

            "fixed_stop":
                True,

            "profit_target":
                True,

            "trailing_stop":
                True,

            "max_holding_period":
                True,

            "opposite_signal_exit":
                True,

            "intrabar_ambiguity_policy":
                True,

            "gap_stop_handling":
                True,

            "brokerage_model":
                "configurable",

            "tax_model":
                "configurable",

            "exchange_fee_model":
                "configurable",

            "spread_model":
                "configurable",

            "slippage_model":
                "configurable",

            "hardcoded_current_market_fees":
                False,

            "multi_timeframe_features":
                True,

            "fyers_history_normalizer":
                True,

            "canonical_fyers_history_bridge":
                True,

            "parameter_sweep":
                True,

            "parameter_sweep_max_combinations":
                200,

            "automatic_parameter_promotion":
                False,

            "strategy_comparison":
                True,

            "trade_journal":
                True,

            "equity_curve":
                True,

            "drawdown_analytics":
                True,

            "account_simulator":
                True,

            "automatic_broker_order":
                False,
        }


trading_intelligence_v2_status = (
    TradingIntelligenceV2Status()
)
