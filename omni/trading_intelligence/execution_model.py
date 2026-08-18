from __future__ import annotations

from dataclasses import (
    dataclass,
)


from omni.trading_intelligence.cost_model import (
    ExecutionCostModel,
)


@dataclass
class SimulatedPosition:

    side: int

    entry_time: str

    entry_index: int

    entry_reference_price: float

    entry_fill_price: float

    quantity: float

    multiplier: float

    entry_fee: float

    entry_friction: float

    stop_price: float | None

    target_price: float | None

    trailing_stop_price: float | None

    highest_price: float

    lowest_price: float


class ExecutionSimulator:

    def __init__(
        self,
        config,
    ):

        self.config = config

        self.costs = (
            ExecutionCostModel(
                config.cost
            )
        )


    @staticmethod
    def _time(
        value,
    ):

        if hasattr(
            value,
            "isoformat",
        ):

            return value.isoformat()


        return str(
            value
        )


    def open_position(
        self,
        side,
        reference_price,
        timestamp,
        index,
    ):

        side = int(
            side
        )


        if side not in {
            -1,
            1,
        }:

            raise ValueError(
                "side must be +1 or -1."
            )


        order_side = (
            "buy"
            if side == 1
            else "sell"
        )


        execution = (
            self.costs
            .execution(
                reference_price,
                order_side,
                self.config.quantity,
                self.config.contract_multiplier,
            )
        )


        entry_reference = float(
            reference_price
        )


        stop = None

        target = None

        trailing = None


        if (
            self.config.stop_loss_pct
            is not None
        ):

            if side == 1:

                stop = (
                    entry_reference
                    * (
                        1.0
                        - self.config.stop_loss_pct
                    )
                )

            else:

                stop = (
                    entry_reference
                    * (
                        1.0
                        + self.config.stop_loss_pct
                    )
                )


        if (
            self.config.target_pct
            is not None
        ):

            if side == 1:

                target = (
                    entry_reference
                    * (
                        1.0
                        + self.config.target_pct
                    )
                )

            else:

                target = (
                    entry_reference
                    * (
                        1.0
                        - self.config.target_pct
                    )
                )


        if (
            self.config.trailing_stop_pct
            is not None
        ):

            if side == 1:

                trailing = (
                    entry_reference
                    * (
                        1.0
                        - self.config.trailing_stop_pct
                    )
                )

            else:

                trailing = (
                    entry_reference
                    * (
                        1.0
                        + self.config.trailing_stop_pct
                    )
                )


        return SimulatedPosition(
            side=
                side,

            entry_time=
                self._time(
                    timestamp
                ),

            entry_index=
                int(
                    index
                ),

            entry_reference_price=
                entry_reference,

            entry_fill_price=
                execution[
                    "fill_price"
                ],

            quantity=
                self.config.quantity,

            multiplier=
                self.config.contract_multiplier,

            entry_fee=
                execution[
                    "fees"
                ],

            entry_friction=
                execution[
                    "friction_cost"
                ],

            stop_price=
                stop,

            target_price=
                target,

            trailing_stop_price=
                trailing,

            highest_price=
                entry_reference,

            lowest_price=
                entry_reference,
        )


    @staticmethod
    def effective_stop(
        position,
    ):

        values = [
            value

            for value in (
                position.stop_price,
                position.trailing_stop_price,
            )

            if value is not None
        ]


        if not values:

            return None


        if position.side == 1:

            return max(
                values
            )


        return min(
            values
        )


    def protective_exit(
        self,
        position,
        bar,
    ):

        stop = self.effective_stop(
            position
        )

        target = position.target_price


        open_price = float(
            bar.open
        )

        high = float(
            bar.high
        )

        low = float(
            bar.low
        )


        if position.side == 1:

            # Gap through stop.
            if (
                stop is not None
                and open_price <= stop
            ):

                return (
                    open_price,
                    "stop_gap",
                )


            # Gap beyond target.
            if (
                target is not None
                and open_price >= target
            ):

                return (
                    open_price,
                    "target_gap",
                )


            stop_hit = (
                stop is not None
                and low <= stop
            )

            target_hit = (
                target is not None
                and high >= target
            )


        else:

            if (
                stop is not None
                and open_price >= stop
            ):

                return (
                    open_price,
                    "stop_gap",
                )


            if (
                target is not None
                and open_price <= target
            ):

                return (
                    open_price,
                    "target_gap",
                )


            stop_hit = (
                stop is not None
                and high >= stop
            )

            target_hit = (
                target is not None
                and low <= target
            )


        if (
            stop_hit
            and target_hit
        ):

            if (
                self.config
                .ambiguous_bar_policy
                == "target_first"
            ):

                return (
                    target,
                    "target",
                )


            return (
                stop,
                "stop",
            )


        if stop_hit:

            return (
                stop,
                "stop",
            )


        if target_hit:

            return (
                target,
                "target",
            )


        return None


    def update_trailing(
        self,
        position,
        bar,
    ):

        position.highest_price = max(
            position.highest_price,
            float(
                bar.high
            ),
        )


        position.lowest_price = min(
            position.lowest_price,
            float(
                bar.low
            ),
        )


        trailing_pct = (
            self.config
            .trailing_stop_pct
        )


        if trailing_pct is None:

            return


        if position.side == 1:

            candidate = (
                position.highest_price
                * (
                    1.0
                    - trailing_pct
                )
            )


            if (
                position.trailing_stop_price
                is None
            ):

                position.trailing_stop_price = (
                    candidate
                )

            else:

                position.trailing_stop_price = max(
                    position.trailing_stop_price,
                    candidate,
                )


        else:

            candidate = (
                position.lowest_price
                * (
                    1.0
                    + trailing_pct
                )
            )


            if (
                position.trailing_stop_price
                is None
            ):

                position.trailing_stop_price = (
                    candidate
                )

            else:

                position.trailing_stop_price = min(
                    position.trailing_stop_price,
                    candidate,
                )


    def close_position(
        self,
        position,
        reference_price,
        timestamp,
        index,
        reason,
    ):

        exit_order_side = (
            "sell"
            if position.side == 1
            else "buy"
        )


        execution = (
            self.costs
            .execution(
                reference_price,
                exit_order_side,
                position.quantity,
                position.multiplier,
            )
        )


        gross_pnl = (
            (
                float(
                    reference_price
                )
                - position.entry_reference_price
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


        friction = (
            position.entry_friction
            + execution[
                "friction_cost"
            ]
        )


        net_pnl = (
            gross_pnl
            - fees
            - friction
        )


        return {
            "side":
                (
                    "LONG"
                    if position.side == 1
                    else "SHORT"
                ),

            "entry_time":
                position.entry_time,

            "exit_time":
                self._time(
                    timestamp
                ),

            "entry_index":
                position.entry_index,

            "exit_index":
                int(
                    index
                ),

            "entry_reference_price":
                position.entry_reference_price,

            "entry_fill_price":
                position.entry_fill_price,

            "exit_reference_price":
                float(
                    reference_price
                ),

            "exit_fill_price":
                execution[
                    "fill_price"
                ],

            "quantity":
                position.quantity,

            "multiplier":
                position.multiplier,

            "gross_pnl":
                gross_pnl,

            "fees":
                fees,

            "slippage":
                friction,

            "net_pnl":
                net_pnl,

            "turnover":
                (
                    abs(
                        position.entry_fill_price
                    )
                    + abs(
                        execution[
                            "fill_price"
                        ]
                    )
                )
                * position.quantity
                * position.multiplier,

            "bars_held":
                (
                    int(
                        index
                    )
                    - position.entry_index
                    + 1
                ),

            "exit_reason":
                str(
                    reason
                ),

            "research_only":
                True,
        }
