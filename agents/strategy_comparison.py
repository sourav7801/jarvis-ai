# ============================================================
# JARVIS STRATEGY COMPARISON
# V1 vs REGIME-AWARE V2
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from agents.technical_engine import technical_engine
from agents.pattern_engine import pattern_engine
from agents.signal_engine import signal_engine
from agents.regime_detector import regime_detector
from agents.regime_aware_signal_engine import (
    regime_aware_signal_engine,
)
from agents.risk_engine import RiskEngine


# ============================================================
# COMPARISON ENGINE
# ============================================================

class StrategyComparison:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        risk_per_trade_percent: float = 1.0,
        commission_per_side: float = 20.0,
        slippage_percent: float = 0.02,
        minimum_history: int = 60,
    ):

        self.starting_capital = float(
            starting_capital
        )

        self.risk_per_trade_percent = float(
            risk_per_trade_percent
        )

        self.commission_per_side = float(
            commission_per_side
        )

        self.slippage_percent = float(
            slippage_percent
        )

        self.minimum_history = int(
            minimum_history
        )

        self.risk_engine = RiskEngine(
            risk_per_trade_percent=
                risk_per_trade_percent
        )

    # ========================================================
    # PREPARE
    # ========================================================

    def prepare(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        if df is None or df.empty:
            return pd.DataFrame()

        data = df.copy()

        data.columns = [
            str(c).strip().lower()
            for c in data.columns
        ]

        required = {
            "open",
            "high",
            "low",
            "close",
        }

        if not required.issubset(
            data.columns
        ):
            return pd.DataFrame()

        for column in required:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        return (
            data.dropna(
                subset=list(required)
            )
            .reset_index(drop=True)
        )

    # ========================================================
    # SLIPPAGE
    # ========================================================

    def execution_price(
        self,
        price: float,
        side: str,
    ) -> float:

        adjustment = (
            float(price)
            * self.slippage_percent
            / 100.0
        )

        if side == "BUY":
            return float(
                price
            ) + adjustment

        return float(
            price
        ) - adjustment

    # ========================================================
    # BACKTEST ONE ENGINE
    # ========================================================

    def run_engine(
        self,
        data: pd.DataFrame,
        engine_name: str,
    ) -> Dict[str, Any]:

        equity = (
            self.starting_capital
        )

        equity_curve = [
            equity
        ]

        trades: List[
            Dict[str, Any]
        ] = []

        position = None

        trade_id = 0

        for index in range(
            self.minimum_history,
            len(data),
        ):

            candle = data.iloc[
                index
            ]

            # ------------------------------------------------
            # Manage position
            # ------------------------------------------------

            if position is not None:

                high = float(
                    candle["high"]
                )

                low = float(
                    candle["low"]
                )

                exit_price = None
                exit_reason = None

                if position["side"] == "LONG":

                    if (
                        low
                        <=
                        position["stop"]
                    ):

                        exit_price = (
                            position["stop"]
                        )

                        exit_reason = (
                            "STOP_LOSS"
                        )

                    elif (
                        high
                        >=
                        position["target"]
                    ):

                        exit_price = (
                            position["target"]
                        )

                        exit_reason = (
                            "TAKE_PROFIT"
                        )

                else:

                    if (
                        high
                        >=
                        position["stop"]
                    ):

                        exit_price = (
                            position["stop"]
                        )

                        exit_reason = (
                            "STOP_LOSS"
                        )

                    elif (
                        low
                        <=
                        position["target"]
                    ):

                        exit_price = (
                            position["target"]
                        )

                        exit_reason = (
                            "TAKE_PROFIT"
                        )

                if exit_price is not None:

                    exit_side = (
                        "SELL"
                        if position["side"]
                        == "LONG"
                        else "BUY"
                    )

                    executed_exit = (
                        self.execution_price(
                            exit_price,
                            exit_side,
                        )
                    )

                    if position["side"] == "LONG":

                        gross_pnl = (
                            executed_exit
                            -
                            position["entry"]
                        ) * position[
                            "quantity"
                        ]

                    else:

                        gross_pnl = (
                            position["entry"]
                            -
                            executed_exit
                        ) * position[
                            "quantity"
                        ]

                    fees = (
                        self.commission_per_side
                        * 2
                    )

                    net_pnl = (
                        gross_pnl
                        - fees
                    )

                    equity += net_pnl

                    trade_id += 1

                    trades.append({

                        "trade_id":
                            trade_id,

                        "side":
                            position["side"],

                        "entry_index":
                            position["entry_index"],

                        "exit_index":
                            index,

                        "entry":
                            position["entry"],

                        "exit":
                            executed_exit,

                        "quantity":
                            position["quantity"],

                        "gross_pnl":
                            gross_pnl,

                        "fees":
                            fees,

                        "net_pnl":
                            net_pnl,

                        "reason":
                            exit_reason,

                    })

                    position = None

                equity_curve.append(
                    equity
                )

                continue

            # ------------------------------------------------
            # History
            # ------------------------------------------------

            history = data.iloc[
                :index + 1
            ].copy()

            technical = (
                technical_engine.analyze(
                    history
                )
            )

            if not technical.get(
                "success",
                False,
            ):

                equity_curve.append(
                    equity
                )

                continue

            patterns = (
                pattern_engine.analyze(
                    history
                )
            )

            if not patterns.get(
                "success",
                False,
            ):

                equity_curve.append(
                    equity
                )

                continue

            regime = (
                regime_detector.analyze(
                    history
                )
            )

            if not regime.get(
                "success",
                False,
            ):

                equity_curve.append(
                    equity
                )

                continue

            # ------------------------------------------------
            # Signal
            # ------------------------------------------------

            if engine_name == "V1":

                signal = (
                    signal_engine.generate_signal(
                        technical,
                        patterns,
                    )
                )

            else:

                signal = (
                    regime_aware_signal_engine.generate_signal(
                        technical,
                        patterns,
                        regime,
                    )
                )

            if not signal.get(
                "success",
                False,
            ):

                equity_curve.append(
                    equity
                )

                continue

            action = signal.get(
                "action"
            )

            if action not in {
                "BUY",
                "SELL",
            }:

                equity_curve.append(
                    equity
                )

                continue

            entry = signal.get(
                "entry"
            )

            stop = signal.get(
                "stop_loss"
            )

            target = signal.get(
                "target"
            )

            if any(
                value is None
                for value in [
                    entry,
                    stop,
                    target,
                ]
            ):

                equity_curve.append(
                    equity
                )

                continue

            entry = float(entry)
            stop = float(stop)
            target = float(target)

            risk = (
                self.risk_engine.evaluate_trade(
                    account_equity=equity,
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                )
            )

            if not risk.approved:

                equity_curve.append(
                    equity
                )

                continue

            quantity = float(
                risk.position_size
            )

            if quantity <= 0:

                equity_curve.append(
                    equity
                )

                continue

            entry_side = (
                "BUY"
                if action == "BUY"
                else "SELL"
            )

            executed_entry = (
                self.execution_price(
                    entry,
                    entry_side,
                )
            )

            equity -= (
                self.commission_per_side
            )

            position = {

                "side":
                    (
                        "LONG"
                        if action == "BUY"
                        else "SHORT"
                    ),

                "entry_index":
                    index,

                "entry":
                    executed_entry,

                "quantity":
                    quantity,

                "stop":
                    stop,

                "target":
                    target,

            }

            equity_curve.append(
                equity
            )

        # ----------------------------------------------------
        # Force close
        # ----------------------------------------------------

        if position is not None:

            final_index = (
                len(data) - 1
            )

            raw_exit = float(
                data.iloc[
                    final_index
                ]["close"]
            )

            exit_side = (
                "SELL"
                if position["side"]
                == "LONG"
                else "BUY"
            )

            executed_exit = (
                self.execution_price(
                    raw_exit,
                    exit_side,
                )
            )

            if position["side"] == "LONG":

                gross_pnl = (
                    executed_exit
                    -
                    position["entry"]
                ) * position["quantity"]

            else:

                gross_pnl = (
                    position["entry"]
                    -
                    executed_exit
                ) * position["quantity"]

            fees = (
                self.commission_per_side
                * 2
            )

            net_pnl = (
                gross_pnl
                - fees
            )

            equity += net_pnl

            trade_id += 1

            trades.append({

                "trade_id":
                    trade_id,

                "side":
                    position["side"],

                "entry_index":
                    position["entry_index"],

                "exit_index":
                    final_index,

                "entry":
                    position["entry"],

                "exit":
                    executed_exit,

                "quantity":
                    position["quantity"],

                "gross_pnl":
                    gross_pnl,

                "fees":
                    fees,

                "net_pnl":
                    net_pnl,

                "reason":
                    "END_OF_DATA",

            })

            equity_curve.append(
                equity
            )

        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        pnls = [
            trade["net_pnl"]
            for trade
            in trades
        ]

        wins = [
            value
            for value
            in pnls
            if value > 0
        ]

        losses = [
            value
            for value
            in pnls
            if value < 0
        ]

        gross_profit = sum(
            wins
        )

        gross_loss = sum(
            abs(value)
            for value
            in losses
        )

        if gross_loss > 0:

            profit_factor = (
                gross_profit
                / gross_loss
            )

        else:

            profit_factor = None

        if pnls:

            win_rate = (
                len(wins)
                / len(pnls)
                * 100
            )

            expectancy = (
                sum(pnls)
                / len(pnls)
            )

        else:

            win_rate = 0.0

            expectancy = 0.0

        # Drawdown
        peak = (
            equity_curve[0]
        )

        max_drawdown = 0.0

        for value in equity_curve:

            peak = max(
                peak,
                value,
            )

            max_drawdown = max(
                max_drawdown,
                peak - value,
            )

        return {

            "engine":
                engine_name,

            "starting_capital":
                self.starting_capital,

            "final_equity":
                equity,

            "net_pnl":
                equity
                - self.starting_capital,

            "return_percent":
                (
                    equity
                    -
                    self.starting_capital
                )
                /
                self.starting_capital
                * 100,

            "trades":
                len(trades),

            "wins":
                len(wins),

            "losses":
                len(losses),

            "win_rate":
                win_rate,

            "profit_factor":
                profit_factor,

            "expectancy":
                expectancy,

            "max_drawdown":
                max_drawdown,

            "max_drawdown_percent":
                max_drawdown
                /
                self.starting_capital
                * 100,

            "equity_curve":
                equity_curve,

            "trade_list":
                trades,

        }

    # ========================================================
    # FULL COMPARISON
    # ========================================================

    def compare(
        self,
        df: pd.DataFrame,
        symbol: str = "NIFTY",
    ) -> Dict[str, Any]:

        data = self.prepare(
            df
        )

        if len(data) < (
            self.minimum_history * 2
        ):

            return {

                "success":
                    False,

                "message":
                    "Not enough data for comparison.",

            }

        split = int(
            len(data) * 0.70
        )

        train = data.iloc[
            :split
        ].reset_index(
            drop=True
        )

        test = data.iloc[
            split:
        ].reset_index(
            drop=True
        )

        # ----------------------------------------------------
        # TRAIN
        # ----------------------------------------------------

        v1_train = self.run_engine(
            train,
            "V1",
        )

        v2_train = self.run_engine(
            train,
            "REGIME_AWARE_V2",
        )

        # ----------------------------------------------------
        # OUT OF SAMPLE
        # ----------------------------------------------------

        v1_test = self.run_engine(
            test,
            "V1",
        )

        v2_test = self.run_engine(
            test,
            "REGIME_AWARE_V2",
        )

        return {

            "success":
                True,

            "symbol":
                symbol,

            "total_bars":
                len(data),

            "train_bars":
                len(train),

            "test_bars":
                len(test),

            "train": {

                "v1":
                    v1_train,

                "v2":
                    v2_train,

            },

            "test": {

                "v1":
                    v1_test,

                "v2":
                    v2_test,

            },

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format(
        self,
        result: Dict[str, Any],
    ) -> str:

        if not result.get(
            "success",
            False,
        ):

            return (
                "STRATEGY COMPARISON FAILED\n"
                +
                str(
                    result.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        lines = []

        lines.append(
            "JARVIS STRATEGY COMPARISON"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: {result['symbol']}"
        )

        lines.append(
            f"Total Bars: {result['total_bars']:,}"
        )

        lines.append(
            f"Train Bars: {result['train_bars']:,}"
        )

        lines.append(
            f"Test Bars: {result['test_bars']:,}"
        )

        for period in [
            "train",
            "test",
        ]:

            lines.append("")

            lines.append(
                period.upper()
                +
                " PERFORMANCE"
            )

            for engine_name, metrics in (
                result[period].items()
            ):

                lines.append(
                    ""
                )

                lines.append(
                    f"{engine_name}"
                )

                lines.append(
                    f"  Return: "
                    f"{metrics['return_percent']:.2f}%"
                )

                lines.append(
                    f"  Net P&L: "
                    f"{metrics['net_pnl']:,.2f}"
                )

                lines.append(
                    f"  Trades: "
                    f"{metrics['trades']}"
                )

                lines.append(
                    f"  Win Rate: "
                    f"{metrics['win_rate']:.2f}%"
                )

                lines.append(
                    f"  Profit Factor: "
                    f"{metrics['profit_factor']}"
                )

                lines.append(
                    f"  Expectancy: "
                    f"{metrics['expectancy']:,.2f}"
                )

                lines.append(
                    f"  Max Drawdown: "
                    f"{metrics['max_drawdown']:,.2f}"
                )

        lines.append("")

        lines.append(
            "INTERPRETATION"
        )

        test_v1 = result[
            "test"
        ][
            "v1"
        ]

        test_v2 = result[
            "test"
        ][
            "v2"
        ]

        lines.append(
            f"Out-of-sample V1 return: "
            f"{test_v1['return_percent']:.2f}%"
        )

        lines.append(
            f"Out-of-sample V2 return: "
            f"{test_v2['return_percent']:.2f}%"
        )

        lines.append(
            f"Out-of-sample V1 profit factor: "
            f"{test_v1['profit_factor']}"
        )

        lines.append(
            f"Out-of-sample V2 profit factor: "
            f"{test_v2['profit_factor']}"
        )

        lines.append("")

        lines.append(
            "Do not select a strategy from training "
            "performance alone. The out-of-sample "
            "result is the primary comparison."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

strategy_comparison = (
    StrategyComparison()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    from agents.market_data_agent import (
        get_market_data,
    )

    print(
        "=" * 60
    )

    print(
        "JARVIS STRATEGY COMPARISON"
    )

    print(
        "=" * 60
    )

    result = get_market_data(
        "NIFTY",
        market="india",
        timeframe="1d",
        bars=1000,
    )

    if not result.get(
        "success",
        False,
    ):

        print(
            "Market data failed:"
        )

        print(
            result.get(
                "message"
            )
        )

    else:

        comparison = (
            strategy_comparison.compare(
                result["data"],
                symbol="NIFTY",
            )
        )

        print(
            strategy_comparison.format(
                comparison
            )
        )

    print()

    print(
        "Strategy Comparison loaded successfully."
    )