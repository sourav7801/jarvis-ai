from __future__ import annotations

from omni.trading_intelligence.backtest_schema import (
    ExecutionCostConfig,
)


class ExecutionCostModel:

    def __init__(
        self,
        config=None,
    ):

        self.config = (
            config
            or ExecutionCostConfig()
        )


    def fill(
        self,
        reference_price,
        order_side,
    ):

        reference = float(
            reference_price
        )

        if reference <= 0:

            raise ValueError(
                "reference price must be positive."
            )


        order_side = str(
            order_side
        ).strip().lower()


        if order_side not in {
            "buy",
            "sell",
        }:

            raise ValueError(
                "order_side must be buy or sell."
            )


        friction_bps = (
            float(
                self.config.slippage_bps
            )
            + (
                float(
                    self.config.spread_bps
                )
                / 2.0
            )
        )


        adjustment = (
            reference
            * friction_bps
            / 10000.0
        )


        if order_side == "buy":

            fill = (
                reference
                + adjustment
            )

        else:

            fill = (
                reference
                - adjustment
            )


        return {
            "reference_price":
                reference,

            "fill_price":
                fill,

            "price_friction":
                abs(
                    fill
                    - reference
                ),
        }


    def fees(
        self,
        fill_price,
        quantity,
        multiplier,
        order_side,
    ):

        fill_price = float(
            fill_price
        )

        quantity = float(
            quantity
        )

        multiplier = float(
            multiplier
        )


        notional = (
            abs(
                fill_price
            )
            * quantity
            * multiplier
        )


        order_side = str(
            order_side
        ).strip().lower()


        side_tax_bps = (
            self.config.tax_bps_buy

            if order_side == "buy"

            else self.config.tax_bps_sell
        )


        variable_bps = (
            float(
                self.config.brokerage_bps
            )
            + float(
                self.config.exchange_bps
            )
            + float(
                self.config.other_bps
            )
            + float(
                side_tax_bps
            )
        )


        variable = (
            notional
            * variable_bps
            / 10000.0
        )


        fixed = float(
            self.config.fixed_per_order
        )


        contract_fee = (
            float(
                self.config.per_contract
            )
            * quantity
        )


        return {
            "notional":
                notional,

            "variable":
                variable,

            "fixed":
                fixed,

            "per_contract":
                contract_fee,

            "total":
                (
                    variable
                    + fixed
                    + contract_fee
                ),
        }


    def execution(
        self,
        reference_price,
        order_side,
        quantity,
        multiplier,
    ):

        fill = self.fill(
            reference_price,
            order_side,
        )


        fees = self.fees(
            fill[
                "fill_price"
            ],
            quantity,
            multiplier,
            order_side,
        )


        friction_cost = (
            fill[
                "price_friction"
            ]
            * float(
                quantity
            )
            * float(
                multiplier
            )
        )


        return {
            **fill,

            "fees":
                fees[
                    "total"
                ],

            "friction_cost":
                friction_cost,

            "notional":
                fees[
                    "notional"
                ],
        }
