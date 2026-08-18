from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)


class TradingIntelligenceV4Status:

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

            "strategy_genomes":
                True,

            "parameter_mutation":
                True,

            "numeric_rule_mutation":
                True,

            "strategy_crossover":
                True,

            "historical_compatibility_gate":
                True,

            "regime_aware_evaluation":
                True,

            "multi_regime_fitness":
                True,

            "expectancy_component":
                True,

            "profit_factor_component":
                True,

            "return_component":
                True,

            "drawdown_penalty":
                True,

            "trade_count_penalty":
                True,

            "regime_stability_penalty":
                True,

            "worst_regime_component":
                True,

            "champion_challenger":
                True,

            "retirement_proposals":
                True,

            "candidate_limit":
                50,

            "evolution_artifact_store":
                True,

            "automatic_registry_mutation":
                False,

            "automatic_strategy_promotion":
                False,

            "automatic_strategy_retirement":
                False,

            "automatic_broker_order":
                False,

            "production_self_modification":
                False,
        }


trading_intelligence_v4_status = (
    TradingIntelligenceV4Status()
)
