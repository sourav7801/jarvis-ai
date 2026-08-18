from __future__ import annotations


class AccountSimulator:

    def __init__(
        self,
        initial_capital,
    ):

        initial_capital = float(
            initial_capital
        )


        if initial_capital <= 0:

            raise ValueError(
                "initial capital must be positive."
            )


        self.initial_capital = (
            initial_capital
        )

        self.equity = (
            initial_capital
        )

        self.peak_equity = (
            initial_capital
        )

        self.realized_pnl = 0.0

        self.total_fees = 0.0

        self.total_friction = 0.0

        self.max_drawdown = 0.0

        self.rejected_entries = 0

        self._curve = []


    def can_open(
        self,
        quantity,
        required_per_unit=None,
    ):

        if required_per_unit is None:

            return True


        required = (
            float(
                quantity
            )
            * float(
                required_per_unit
            )
        )


        return (
            required
            <= self.equity
        )


    def reject_entry(
        self,
    ):

        self.rejected_entries += 1


    def record_trade(
        self,
        trade,
    ):

        net = float(
            trade[
                "net_pnl"
            ]
        )


        self.realized_pnl += net

        self.total_fees += float(
            trade.get(
                "fees",
                0.0,
            )
        )

        self.total_friction += float(
            trade.get(
                "slippage",
                0.0,
            )
        )


        self.equity = (
            self.initial_capital
            + self.realized_pnl
        )


        self.peak_equity = max(
            self.peak_equity,
            self.equity,
        )


        drawdown = (
            self.peak_equity
            - self.equity
        )


        self.max_drawdown = max(
            self.max_drawdown,
            drawdown,
        )


        drawdown_pct = (
            drawdown
            / self.peak_equity
            if self.peak_equity > 0
            else 0.0
        )


        self._curve.append(
            {
                "timestamp":
                    trade[
                        "exit_time"
                    ],

                "equity":
                    self.equity,

                "cumulative_pnl":
                    self.realized_pnl,

                "drawdown":
                    drawdown,

                "drawdown_pct":
                    drawdown_pct,
            }
        )


    def curve(
        self,
    ):

        return tuple(
            self._curve
        )


    def status(
        self,
    ):

        return {
            "initial_capital":
                self.initial_capital,

            "ending_equity":
                self.equity,

            "realized_pnl":
                self.realized_pnl,

            "return_pct":
                (
                    self.realized_pnl
                    / self.initial_capital
                ),

            "total_fees":
                self.total_fees,

            "total_execution_friction":
                self.total_friction,

            "max_drawdown":
                self.max_drawdown,

            "rejected_entries":
                self.rejected_entries,
        }
