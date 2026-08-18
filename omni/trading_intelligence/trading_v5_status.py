from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)


class TradingIntelligenceV5Status:

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

            "chronological_train_validation_oos":
                True,

            "oos_tuning":
                False,

            "walk_forward_validation":
                True,

            "rolling_oos_windows":
                True,

            "monte_carlo_bootstrap":
                True,

            "monte_carlo_max_iterations":
                5000,

            "parameter_sensitivity":
                True,

            "automatic_parameter_selection":
                False,

            "cost_stress":
                True,

            "slippage_stress":
                True,

            "spread_stress":
                True,

            "hardcoded_current_fees":
                False,

            "regime_robustness":
                True,

            "data_sufficiency_gate":
                True,

            "overfitting_risk_score":
                True,

            "train_validation_gap":
                True,

            "validation_oos_gap":
                True,

            "walk_forward_penalty":
                True,

            "parameter_instability_penalty":
                True,

            "monte_carlo_tail_risk":
                True,

            "cost_survival_gate":
                True,

            "recommendations": (
                "PROMOTE",
                "KEEP_TESTING",
                "DEGRADE",
                "RETIRE",
            ),

            "promotion_is_research_recommendation_only":
                True,

            "automatic_strategy_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "automatic_strategy_retirement":
                False,

            "automatic_broker_order":
                False,

            "production_self_modification":
                False,
        }


trading_intelligence_v5_status = (
    TradingIntelligenceV5Status()
)
