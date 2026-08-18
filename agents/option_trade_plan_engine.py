# ============================================================
# JARVIS OPTION TRADE PLAN ENGINE
# V1
# ============================================================
#
# Converts a validated option strategy into an option-specific
# trade plan.
#
# Handles:
#   - Entry premium
#   - Stop premium
#   - Target 1 premium
#   - Target 2 premium
#   - Break-even
#   - Max loss
#   - Max profit
#   - Risk/reward
#   - Quantity / lot sizing
#   - Slippage allowance
#   - Fees
#   - Option-specific invalidation
#
# PAPER / RESEARCH ONLY.
# No live broker orders.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime
import math


# ============================================================
# ENGINE
# ============================================================

class OptionTradePlanEngine:

    def __init__(
        self,
        max_risk_per_trade_percent: float = 1.0,
        premium_stop_percent: float = 35.0,
        premium_target_1_percent: float = 50.0,
        premium_target_2_percent: float = 100.0,
        max_slippage_percent: float = 1.0,
        fee_per_lot_round_trip: float = 40.0,
        default_lot_size: int = 1,
        min_risk_reward: float = 1.5,
    ):

        self.max_risk_per_trade_percent = float(
            max_risk_per_trade_percent
        )

        self.premium_stop_percent = float(
            premium_stop_percent
        )

        self.premium_target_1_percent = float(
            premium_target_1_percent
        )

        self.premium_target_2_percent = float(
            premium_target_2_percent
        )

        self.max_slippage_percent = float(
            max_slippage_percent
        )

        self.fee_per_lot_round_trip = float(
            fee_per_lot_round_trip
        )

        self.default_lot_size = int(
            default_lot_size
        )

        self.min_risk_reward = float(
            min_risk_reward
        )

    # ========================================================
    # NUMBER
    # ========================================================

    @staticmethod
    def number(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if value is None:
                return default

            value = float(value)

            if math.isnan(value):
                return default

            if math.isinf(value):
                return default

            return value

        except Exception:

            return default

    # ========================================================
    # OPTION TYPE
    # ========================================================

    @staticmethod
    def normalize_option_type(
        value: Any,
    ) -> str:

        value = (
            str(value or "")
            .upper()
            .strip()
        )

        if value in {
            "CALL",
            "CE",
            "C",
        }:

            return "CALL"

        if value in {
            "PUT",
            "PE",
            "P",
        }:

            return "PUT"

        return value

    # ========================================================
    # VALIDATE BASIC CONTRACT
    # ========================================================

    def validate_contract(
        self,
        strategy: str,
        contract: Dict[str, Any],
    ) -> Dict[str, Any]:

        strategy = (
            str(strategy)
            .upper()
            .strip()
        )

        reasons = []

        if strategy in {
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
        }:

            net_debit = self.number(
                contract.get(
                    "net_debit"
                )
            )

            max_loss = self.number(
                contract.get(
                    "max_loss"
                )
            )

            max_profit = self.number(
                contract.get(
                    "max_profit"
                )
            )

            risk_reward = self.number(
                contract.get(
                    "risk_reward"
                )
            )

            width = self.number(
                contract.get(
                    "width"
                )
            )

            if net_debit <= 0:

                reasons.append(
                    "Net debit must be positive."
                )

            if width <= 0:

                reasons.append(
                    "Spread width must be positive."
                )

            if max_loss <= 0:

                reasons.append(
                    "Maximum loss must be positive."
                )

            if max_profit <= 0:

                reasons.append(
                    "Maximum profit must be positive."
                )

            if net_debit >= width:

                reasons.append(
                    "Net debit must be less than spread width."
                )

            if risk_reward < self.min_risk_reward:

                reasons.append(
                    (
                        f"Spread R/R "
                        f"{risk_reward:.2f} "
                        f"is below "
                        f"{self.min_risk_reward:.2f}."
                    )
                )

        else:

            entry_price = self.number(
                contract.get(
                    "price",
                    contract.get(
                        "premium"
                    )
                )
            )

            if entry_price <= 0:

                reasons.append(
                    "Option premium must be positive."
                )

        return {

            "valid":
                not reasons,

            "reasons":
                reasons,

        }

    # ========================================================
    # SINGLE LEG PLAN
    # ========================================================

    def build_single_leg_plan(
        self,
        strategy: str,
        contract: Dict[str, Any],
        capital: float,
        lot_size: Optional[int] = None,
    ) -> Dict[str, Any]:

        strategy = (
            str(strategy)
            .upper()
            .strip()
        )

        entry = self.number(
            contract.get(
                "price",
                contract.get(
                    "premium"
                )
            )
        )

        if entry <= 0:

            return {

                "success":
                    False,

                "approved":
                    False,

                "message":
                    "Invalid option premium.",

            }

        if lot_size is None:

            lot_size = self.default_lot_size

        lot_size = max(
            1,
            int(lot_size)
        )

        # ----------------------------------------------------
        # Premium-based stops and targets.
        # ----------------------------------------------------

        stop = (
            entry
            *
            (
                1.0
                -
                self.premium_stop_percent
                /
                100.0
            )
        )

        target_1 = (
            entry
            *
            (
                1.0
                +
                self.premium_target_1_percent
                /
                100.0
            )
        )

        target_2 = (
            entry
            *
            (
                1.0
                +
                self.premium_target_2_percent
                /
                100.0
            )
        )

        risk_per_unit = (
            entry
            -
            stop
        )

        reward_1_per_unit = (
            target_1
            -
            entry
        )

        reward_2_per_unit = (
            target_2
            -
            entry
        )

        rr_1 = (
            reward_1_per_unit
            /
            risk_per_unit
            if risk_per_unit > 0
            else 0.0
        )

        rr_2 = (
            reward_2_per_unit
            /
            risk_per_unit
            if risk_per_unit > 0
            else 0.0
        )

        max_risk_amount = (
            capital
            *
            self.max_risk_per_trade_percent
            /
            100.0
        )

        risk_per_lot = (
            risk_per_unit
            *
            lot_size
        )

        quantity_lots = (

            int(
                max_risk_amount
                /
                risk_per_lot
            )

            if risk_per_lot > 0
            else 0

        )

        quantity_lots = max(
            0,
            quantity_lots,
        )

        quantity = (
            quantity_lots
            *
            lot_size
        )

        planned_risk = (
            risk_per_unit
            *
            quantity
        )

        fees = (
            quantity_lots
            *
            self.fee_per_lot_round_trip
        )

        slippage_allowance = (
            entry
            *
            self.max_slippage_percent
            /
            100.0
            *
            2.0
            *
            quantity
        )

        approved = (

            rr_1
            >=
            self.min_risk_reward

            and

            quantity > 0

        )

        reasons = []

        if rr_1 < self.min_risk_reward:

            reasons.append(
                "Target 1 R/R is below minimum."
            )

        if quantity <= 0:

            reasons.append(
                "Available capital does not support one lot "
                "under the configured risk limit."
            )

        return {

            "success":
                True,

            "approved":
                approved,

            "strategy":
                strategy,

            "side":
                "LONG_PREMIUM",

            "option_type":
                self.normalize_option_type(
                    contract.get(
                        "option_type"
                    )
                ),

            "strike":
                contract.get(
                    "strike"
                ),

            "entry_premium":
                entry,

            "stop_premium":
                stop,

            "target_1_premium":
                target_1,

            "target_2_premium":
                target_2,

            "break_even":
                entry,

            "risk_per_unit":
                risk_per_unit,

            "reward_1_per_unit":
                reward_1_per_unit,

            "reward_2_per_unit":
                reward_2_per_unit,

            "risk_reward_target_1":
                rr_1,

            "risk_reward_target_2":
                rr_2,

            "lot_size":
                lot_size,

            "lots":
                quantity_lots,

            "quantity":
                quantity,

            "planned_risk":
                planned_risk,

            "fees":
                fees,

            "slippage_allowance":
                slippage_allowance,

            "capital":
                capital,

            "max_risk_allowed":
                max_risk_amount,

            "reasons":
                reasons,

        }

    # ========================================================
    # DEBIT SPREAD PLAN
    # ========================================================

    def build_debit_spread_plan(
        self,
        strategy: str,
        contract: Dict[str, Any],
        capital: float,
        lot_size: Optional[int] = None,
    ) -> Dict[str, Any]:

        strategy = (
            str(strategy)
            .upper()
            .strip()
        )

        validation = (
            self.validate_contract(
                strategy,
                contract,
            )
        )

        if not validation[
            "valid"
        ]:

            return {

                "success":
                    True,

                "approved":
                    False,

                "strategy":
                    strategy,

                "reasons":
                    validation[
                        "reasons"
                    ],

            }

        if lot_size is None:

            lot_size = self.default_lot_size

        lot_size = max(
            1,
            int(lot_size)
        )

        net_debit = self.number(
            contract.get(
                "net_debit"
            )
        )

        max_profit = self.number(
            contract.get(
                "max_profit"
            )
        )

        max_loss = self.number(
            contract.get(
                "max_loss"
            )
        )

        width = self.number(
            contract.get(
                "width"
            )
        )

        risk_reward = self.number(
            contract.get(
                "risk_reward"
            )
        )

        # ----------------------------------------------------
        # Theoretical spread value levels.
        # ----------------------------------------------------

        # Stop at 50% of maximum debit loss.
        stop_debit = (
            net_debit
            *
            0.50
        )

        target_1 = min(
            max_profit
            *
            0.50,
            max_profit
        )

        target_2 = min(
            max_profit
            *
            0.80,
            max_profit
        )

        risk_per_unit = (
            net_debit
            -
            stop_debit
        )

        reward_1 = (
            target_1
            -
            net_debit
        )

        reward_2 = (
            target_2
            -
            net_debit
        )

        rr_1 = (

            reward_1
            /
            risk_per_unit

            if risk_per_unit > 0

            else
            0.0

        )

        rr_2 = (

            reward_2
            /
            risk_per_unit

            if risk_per_unit > 0

            else
            0.0

        )

        # ----------------------------------------------------
        # Risk sizing.
        # ----------------------------------------------------

        max_risk_amount = (
            capital
            *
            self.max_risk_per_trade_percent
            /
            100.0
        )

        risk_per_lot = (
            risk_per_unit
            *
            lot_size
        )

        lots = (

            int(
                max_risk_amount
                /
                risk_per_lot
            )

            if risk_per_lot > 0

            else
            0

        )

        lots = max(
            0,
            lots,
        )

        quantity = (
            lots
            *
            lot_size
        )

        planned_risk = (
            risk_per_unit
            *
            quantity
        )

        fees = (
            lots
            *
            self.fee_per_lot_round_trip
        )

        # ----------------------------------------------------
        # Slippage
        # ----------------------------------------------------

        slippage_allowance = (

            net_debit
            *
            self.max_slippage_percent
            /
            100.0
            *
            2.0
            *
            quantity

        )

        approved = (

            risk_reward
            >=
            self.min_risk_reward

            and

            rr_1
            >=
            self.min_risk_reward

            and

            max_profit
            > 0

            and

            max_loss
            > 0

            and

            quantity > 0

        )

        reasons = []

        if rr_1 < self.min_risk_reward:

            reasons.append(
                "Option-plan Target 1 R/R is below minimum."
            )

        if quantity <= 0:

            reasons.append(
                "Available capital does not support one lot "
                "under the configured risk limit."
            )

        return {

            "success":
                True,

            "approved":
                approved,

            "strategy":
                strategy,

            "side":
                "LONG_DEBIT_SPREAD",

            "option_type":
                contract.get(
                    "option_type"
                ),

            "long_strike":
                contract.get(
                    "long_strike"
                ),

            "short_strike":
                contract.get(
                    "short_strike"
                ),

            "long_price":
                contract.get(
                    "long_price"
                ),

            "short_price":
                contract.get(
                    "short_price"
                ),

            "spread_width":
                width,

            "entry_debit":
                net_debit,

            "stop_debit":
                stop_debit,

            "target_1_debit":
                target_1,

            "target_2_debit":
                target_2,

            "max_profit":
                max_profit,

            "max_loss":
                max_loss,

            "risk_reward_contract":
                risk_reward,

            "risk_reward_target_1":
                rr_1,

            "risk_reward_target_2":
                rr_2,

            "lot_size":
                lot_size,

            "lots":
                lots,

            "quantity":
                quantity,

            "planned_risk":
                planned_risk,

            "fees":
                fees,

            "slippage_allowance":
                slippage_allowance,

            "capital":
                capital,

            "max_risk_allowed":
                max_risk_amount,

            "reasons":
                reasons,

        }

    # ========================================================
    # BUILD COMPLETE PLAN
    # ========================================================

    def create_plan(
        self,
        decision: Dict[str, Any],
        capital: float = 1_000_000.0,
        lot_size: Optional[int] = None,
    ) -> Dict[str, Any]:

        if not decision.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "approved":
                    False,

                "message":
                    "Option decision was unsuccessful.",

            }

        strategy = str(
            decision.get(
                "decision",
                "WAIT",
            )
        ).upper()

        if strategy == "WAIT":

            return {

                "success":
                    True,

                "approved":
                    False,

                "strategy":
                    "WAIT",

                "message":
                    decision.get(
                        "message",
                        "No option strategy selected.",
                    ),

            }

        contract = decision.get(
            "contract",
            {}
        )

        if not contract:

            return {

                "success":
                    True,

                "approved":
                    False,

                "strategy":
                    strategy,

                "message":
                    "Option contract is missing.",

            }

        if strategy in {
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
        }:

            result = (
                self.build_debit_spread_plan(

                    strategy=strategy,

                    contract=contract,

                    capital=float(
                        capital
                    ),

                    lot_size=lot_size,

                )
            )

        elif strategy in {
            "LONG_CALL",
            "LONG_PUT",
        }:

            result = (
                self.build_single_leg_plan(

                    strategy=strategy,

                    contract=contract,

                    capital=float(
                        capital
                    ),

                    lot_size=lot_size,

                )
            )

        else:

            return {

                "success":
                    True,

                "approved":
                    False,

                "strategy":
                    strategy,

                "message":
                    (
                        "Strategy does not yet have "
                        "an option trade-plan implementation."
                    ),

            }

        result[
            "created_at"
        ] = datetime.now().isoformat(
            timespec="seconds"
        )

        result[
            "source_decision"
        ] = decision

        return result

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS OPTION TRADE PLAN ENGINE"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Strategy: "
            f"{result.get('strategy')}"
        )

        lines.append(
            f"Approved: "
            f"{result.get('approved')}"
        )

        if result.get(
            "entry_debit"
        ) is not None:

            lines.append("")

            lines.append(
                "SPREAD PLAN"
            )

            lines.append(
                f"Long Strike: "
                f"{result.get('long_strike')}"
            )

            lines.append(
                f"Short Strike: "
                f"{result.get('short_strike')}"
            )

            lines.append(
                f"Entry Debit: "
                f"{result.get('entry_debit'):.2f}"
            )

            lines.append(
                f"Stop Debit: "
                f"{result.get('stop_debit'):.2f}"
            )

            lines.append(
                f"Target 1: "
                f"{result.get('target_1_debit'):.2f}"
            )

            lines.append(
                f"Target 2: "
                f"{result.get('target_2_debit'):.2f}"
            )

            lines.append(
                f"Max Profit: "
                f"{result.get('max_profit'):.2f}"
            )

            lines.append(
                f"Max Loss: "
                f"{result.get('max_loss'):.2f}"
            )

            lines.append(
                f"Contract R/R: "
                f"{result.get('risk_reward_contract'):.2f}"
            )

            lines.append(
                f"Plan R/R T1: "
                f"{result.get('risk_reward_target_1'):.2f}"
            )

            lines.append(
                f"Plan R/R T2: "
                f"{result.get('risk_reward_target_2'):.2f}"
            )

        elif result.get(
            "entry_premium"
        ) is not None:

            lines.append("")

            lines.append(
                "OPTION PLAN"
            )

            lines.append(
                f"Strike: "
                f"{result.get('strike')}"
            )

            lines.append(
                f"Entry Premium: "
                f"{result.get('entry_premium'):.2f}"
            )

            lines.append(
                f"Stop Premium: "
                f"{result.get('stop_premium'):.2f}"
            )

            lines.append(
                f"Target 1: "
                f"{result.get('target_1_premium'):.2f}"
            )

            lines.append(
                f"Target 2: "
                f"{result.get('target_2_premium'):.2f}"
            )

            lines.append(
                f"R/R T1: "
                f"{result.get('risk_reward_target_1'):.2f}"
            )

            lines.append(
                f"R/R T2: "
                f"{result.get('risk_reward_target_2'):.2f}"
            )

        lines.append("")

        lines.append(
            "POSITION SIZING"
        )

        lines.append(
            f"Lot Size: "
            f"{result.get('lot_size')}"
        )

        lines.append(
            f"Lots: "
            f"{result.get('lots')}"
        )

        lines.append(
            f"Quantity: "
            f"{result.get('quantity')}"
        )

        lines.append(
            f"Planned Risk: "
            f"{result.get('planned_risk'):.2f}"
        )

        lines.append(
            f"Fees: "
            f"{result.get('fees'):.2f}"
        )

        lines.append(
            f"Slippage Allowance: "
            f"{result.get('slippage_allowance'):.2f}"
        )

        reasons = result.get(
            "reasons",
            []
        )

        if reasons:

            lines.append("")

            lines.append(
                "BLOCK / WARNING REASONS"
            )

            for reason in reasons:

                lines.append(
                    f"- {reason}"
                )

        if result.get(
            "message"
        ):

            lines.append("")

            lines.append(
                f"Message: "
                f"{result.get('message')}"
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Paper/research option planning only. "
            "No order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

option_trade_plan_engine = (
    OptionTradePlanEngine()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION TRADE PLAN ENGINE"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # Synthetic valid bull-call-spread candidate
    # --------------------------------------------------------

    decision = {

        "success":
            True,

        "decision":
            "BULL_CALL_SPREAD",

        "direction":
            "BULLISH",

        "setup_strength":
            86.0,

        "selection_score":
            85.0,

        "contract": {

            "option_type":
                "CALL",

            "long_strike":
                24200,

            "short_strike":
                24400,

            "long_price":
                330.0,

            "short_price":
                299.4,

            "width":
                200.0,

            "net_debit":
                30.6,

            "max_profit":
                169.4,

            "max_loss":
                30.6,

            "risk_reward":
                5.5359,

            "liquidity_score":
                60.0,

        },

    }

    result = (
        option_trade_plan_engine.create_plan(

            decision=decision,

            capital=1_000_000.0,

            lot_size=25,

        )
    )

    print()

    print(
        option_trade_plan_engine.format_result(
            result
        )
    )

    print()

    print(
        "Option Trade Plan Engine loaded successfully."
    )