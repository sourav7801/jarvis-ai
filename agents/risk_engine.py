# ============================================================
# JARVIS RISK ENGINE
# ============================================================

from dataclasses import dataclass


@dataclass
class RiskDecision:

    approved: bool

    reason: str

    risk_amount: float

    position_size: float

    stop_loss: float

    target: float


class RiskEngine:

    def __init__(
        self,
        risk_per_trade_percent=1.0,
        max_daily_loss_percent=3.0,
        max_leverage=1.0,
    ):

        self.risk_per_trade_percent = (
            risk_per_trade_percent
        )

        self.max_daily_loss_percent = (
            max_daily_loss_percent
        )

        self.max_leverage = (
            max_leverage
        )

    def evaluate_trade(
        self,
        account_equity: float,
        entry_price: float,
        stop_price: float,
        target_price: float,
    ) -> RiskDecision:

        if account_equity <= 0:

            return RiskDecision(
                False,
                "Account equity must be positive.",
                0.0,
                0.0,
                stop_price,
                target_price,
            )

        if entry_price <= 0:

            return RiskDecision(
                False,
                "Entry price must be positive.",
                0.0,
                0.0,
                stop_price,
                target_price,
            )

        if stop_price <= 0:

            return RiskDecision(
                False,
                "Stop loss is required.",
                0.0,
                0.0,
                stop_price,
                target_price,
            )

        if target_price <= 0:

            return RiskDecision(
                False,
                "Target price must be positive.",
                0.0,
                0.0,
                stop_price,
                target_price,
            )

        risk_per_unit = abs(
            entry_price - stop_price
        )

        reward_per_unit = abs(
            target_price - entry_price
        )

        if risk_per_unit <= 0:

            return RiskDecision(
                False,
                "Stop loss cannot equal entry.",
                0.0,
                0.0,
                stop_price,
                target_price,
            )

        risk_reward = (
            reward_per_unit
            / risk_per_unit
        )

        if risk_reward < 1.5:

            return RiskDecision(
                False,
                f"Risk/reward {risk_reward:.2f} "
                "is below the minimum requirement.",
                0.0,
                0.0,
                stop_price,
                target_price,
            )

        maximum_risk = (
            account_equity
            * self.risk_per_trade_percent
            / 100.0
        )

        position_size = (
            maximum_risk
            / risk_per_unit
        )

        if position_size <= 0:

            return RiskDecision(
                False,
                "Calculated position size is invalid.",
                0.0,
                0.0,
                stop_price,
                target_price,
            )

        return RiskDecision(
            True,
            f"Trade approved with "
            f"risk/reward {risk_reward:.2f}.",
            maximum_risk,
            position_size,
            stop_price,
            target_price,
        )


risk_engine = RiskEngine()