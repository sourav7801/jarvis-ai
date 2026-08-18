from __future__ import annotations

from dataclasses import (
    dataclass,
)

from omni.trading_intelligence.backtest_schema import (
    ExecutionCostConfig,
)

from omni.trading_intelligence.cost_model import (
    ExecutionCostModel,
)


@dataclass
class VirtualPosition:

    side: int

    entry_time: str

    entry_ltp: float

    entry_reference: float

    entry_fill: float

    entry_fee: float

    quantity: float

    multiplier: float


class PaperExecutionEngine:

    def __init__(
        self,
        config,
    ):

        self.config = config

        self.position = None

        self.trades = []

        self.initial_capital = float(
            config.initial_capital
        )

        self.realized_pnl = 0.0

        self.kill_switch = False

        self.kill_reason = None


        self.cost_model = ExecutionCostModel(
            ExecutionCostConfig(
                fixed_per_order=
                    config.fixed_fee,

                slippage_bps=
                    config.slippage_bps,

                spread_bps=
                    0.0,
            )
        )


    @staticmethod
    def _reference(
        snapshot,
        order_side,
    ):

        if (
            order_side == "buy"
            and snapshot.ask is not None
            and snapshot.ask > 0
        ):

            return float(
                snapshot.ask
            )


        if (
            order_side == "sell"
            and snapshot.bid is not None
            and snapshot.bid > 0
        ):

            return float(
                snapshot.bid
            )


        return float(
            snapshot.ltp
        )


    def _execution(
        self,
        snapshot,
        order_side,
    ):

        reference = self._reference(
            snapshot,
            order_side,
        )


        execution = self.cost_model.execution(
            reference,
            order_side,
            self.config.quantity,
            self.config.multiplier,
        )


        market_spread_friction = (
            abs(
                reference
                - float(
                    snapshot.ltp
                )
            )
            * self.config.quantity
            * self.config.multiplier
        )


        execution[
            "market_spread_friction"
        ] = market_spread_friction


        return execution


    def open(
        self,
        snapshot,
        side,
    ):

        if self.kill_switch:

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "kill_switch",
            }


        if self.position is not None:

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "position_already_open",
            }


        side = int(side)


        if side not in {
            -1,
            1,
        }:

            raise ValueError(
                "side must be +1 or -1."
            )


        if (
            side == -1
            and not self.config.allow_short
        ):

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "short_disabled",
            }


        order_side = (
            "buy"
            if side == 1
            else "sell"
        )


        execution = self._execution(
            snapshot,
            order_side,
        )


        self.position = VirtualPosition(
            side=
                side,

            entry_time=
                snapshot.timestamp.isoformat(),

            entry_ltp=
                float(
                    snapshot.ltp
                ),

            entry_reference=
                execution[
                    "reference_price"
                ],

            entry_fill=
                execution[
                    "fill_price"
                ],

            entry_fee=
                execution[
                    "fees"
                ],

            quantity=
                self.config.quantity,

            multiplier=
                self.config.multiplier,
        )


        return {
            "success":
                True,

            "paper_only":
                True,

            "action":
                "VIRTUAL_OPEN",

            "side":
                (
                    "LONG"
                    if side == 1
                    else "SHORT"
                ),

            "fill_price":
                execution[
                    "fill_price"
                ],
        }


    def close(
        self,
        snapshot,
        *,
        reason="signal_exit",
    ):

        if self.position is None:

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "no_open_position",
            }


        position = self.position


        order_side = (
            "sell"
            if position.side == 1
            else "buy"
        )


        execution = self._execution(
            snapshot,
            order_side,
        )


        gross_pnl = (
            (
                execution[
                    "fill_price"
                ]
                - position.entry_fill
            )
            * position.side
            * position.quantity
            * position.multiplier
        )


        fees = (
            position.entry_fee
            + execution[
                "fees"
            ]
        )


        net_pnl = (
            gross_pnl
            - fees
        )


        trade = {
            "side":
                (
                    "LONG"
                    if position.side == 1
                    else "SHORT"
                ),

            "entry_time":
                position.entry_time,

            "exit_time":
                snapshot.timestamp.isoformat(),

            "entry_price":
                position.entry_fill,

            "exit_price":
                execution[
                    "fill_price"
                ],

            "entry_ltp":
                position.entry_ltp,

            "exit_ltp":
                float(
                    snapshot.ltp
                ),

            "quantity":
                position.quantity,

            "multiplier":
                position.multiplier,

            "gross_pnl":
                gross_pnl,

            "fees":
                fees,

            "slippage":
                (
                    abs(
                        position.entry_fill
                        - position.entry_reference
                    )
                    * position.quantity
                    * position.multiplier
                    + execution[
                        "friction_cost"
                    ]
                ),

            "net_pnl":
                net_pnl,

            "turnover":
                (
                    abs(
                        position.entry_fill
                    )
                    + abs(
                        execution[
                            "fill_price"
                        ]
                    )
                )
                * position.quantity
                * position.multiplier,

            "exit_reason":
                str(
                    reason
                ),

            "paper_only":
                True,

            "broker_order":
                False,
        }


        self.trades.append(
            trade
        )


        self.realized_pnl += net_pnl

        self.position = None


        return {
            "success":
                True,

            "paper_only":
                True,

            "action":
                "VIRTUAL_CLOSE",

            "trade":
                trade,
        }


    def on_signal(
        self,
        snapshot,
        signal,
    ):

        signal = str(
            signal
        ).upper()


        if signal == "FLAT":

            return {
                "success":
                    True,

                "action":
                    "NO_ACTION",

                "paper_only":
                    True,
            }


        if signal == "EXIT":

            return self.close(
                snapshot,
                reason="exit_signal",
            )


        desired_side = (
            1
            if signal == "LONG"
            else -1
            if signal == "SHORT"
            else None
        )


        if desired_side is None:

            raise ValueError(
                "Unsupported paper signal."
            )


        if self.position is None:

            return self.open(
                snapshot,
                desired_side,
            )


        if (
            self.position.side
            == desired_side
        ):

            return {
                "success":
                    True,

                "action":
                    "HOLD",

                "paper_only":
                    True,
            }


        # Opposite signal closes only.
        # No same-tick reversal.
        return self.close(
            snapshot,
            reason="opposite_signal",
        )


    def kill(
        self,
        reason="manual",
    ):

        self.kill_switch = True

        self.kill_reason = str(
            reason
        )


        return {
            "success":
                True,

            "kill_switch":
                True,

            "reason":
                self.kill_reason,

            "paper_only":
                True,
        }


    def resume(
        self,
    ):

        self.kill_switch = False
        self.kill_reason = None


        return {
            "success":
                True,

            "kill_switch":
                False,

            "paper_only":
                True,
        }


    def status(
        self,
    ):

        return {
            "initial_capital":
                self.initial_capital,

            "realized_pnl":
                self.realized_pnl,

            "equity":
                (
                    self.initial_capital
                    + self.realized_pnl
                ),

            "trade_count":
                len(
                    self.trades
                ),

            "position_open":
                self.position
                is not None,

            "position_side":
                (
                    self.position.side
                    if self.position
                    is not None
                    else None
                ),

            "kill_switch":
                self.kill_switch,

            "kill_reason":
                self.kill_reason,

            "paper_only":
                True,

            "live_execution":
                False,
        }


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        forbidden = (
            "place_order",
            "send_order",
            "broker_order",
            "modify_order",
            "cancel_order",
            "live_order",
            "execute_trade",
        )


        if any(
            token in lower

            for token in forbidden
        ):

            raise PermissionError(
                "PaperExecutionEngine cannot access broker orders."
            )


        raise AttributeError(
            name
        )
