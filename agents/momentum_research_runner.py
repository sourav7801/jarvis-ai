# ============================================================
# JARVIS MOMENTUM RESEARCH RUNNER
# V1
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from agents.market_data_agent import get_market_data
from agents.momentum_strategy import momentum_strategy
from agents.risk_engine import RiskEngine
from agents.research_edge_engine import research_edge_engine


class MomentumResearchRunner:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        risk_per_trade_percent: float = 1.0,
        commission_per_side: float = 20.0,
        slippage_percent: float = 0.02,
        minimum_history: int = 60,
    ):

        self.starting_capital = float(starting_capital)

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
    # EXECUTION
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
            return float(price) + adjustment

        return float(price) - adjustment

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
            str(column).strip().lower()
            for column in data.columns
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

        if "volume" not in data.columns:
            data["volume"] = 0.0

        data["volume"] = pd.to_numeric(
            data["volume"],
            errors="coerce",
        ).fillna(0.0)

        return (
            data
            .dropna(
                subset=list(required)
            )
            .reset_index(drop=True)
        )

    # ========================================================
    # SIMULATION
    # ========================================================

    def simulate_period(
        self,
        data: pd.DataFrame,
        starting_equity: float,
        start_index: int,
        end_index: int,
    ) -> Dict[str, Any]:

        equity = float(
            starting_equity
        )

        equity_curve = [equity]

        trades: List[
            Dict[str, Any]
        ] = []

        position = None

        trade_id = 0

        for index in range(
            start_index,
            end_index,
        ):

            candle = data.iloc[index]

            # ------------------------------------------------
            # Manage open position
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

                    if low <= position["stop"]:

                        exit_price = (
                            position["stop"]
                        )

                        exit_reason = "STOP_LOSS"

                    elif high >= position["target"]:

                        exit_price = (
                            position["target"]
                        )

                        exit_reason = "TAKE_PROFIT"

                else:

                    if high >= position["stop"]:

                        exit_price = (
                            position["stop"]
                        )

                        exit_reason = "STOP_LOSS"

                    elif low <= position["target"]:

                        exit_price = (
                            position["target"]
                        )

                        exit_reason = "TAKE_PROFIT"

                if exit_price is not None:

                    exit_side = (
                        "SELL"
                        if position["side"] == "LONG"
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
                            - position["entry_price"]
                        ) * position["quantity"]

                    else:

                        gross_pnl = (
                            position["entry_price"]
                            - executed_exit
                        ) * position["quantity"]

                    fees = (
                        self.commission_per_side
                        * 2.0
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

                        "entry_index":
                            position["entry_index"],

                        "exit_index":
                            index,

                        "side":
                            position["side"],

                        "entry_price":
                            position["entry_price"],

                        "exit_price":
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
            # Generate momentum signal
            # ------------------------------------------------

            history = data.iloc[
                :index + 1
            ].copy()

            signal = (
                momentum_strategy.signal(
                    history
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
                for value in (
                    entry,
                    stop,
                    target,
                )
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

                "entry_price":
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

            final_index = end_index - 1

            raw_exit = float(
                data.iloc[
                    final_index
                ]["close"]
            )

            exit_side = (
                "SELL"
                if position["side"] == "LONG"
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
                    - position["entry_price"]
                ) * position["quantity"]

            else:

                gross_pnl = (
                    position["entry_price"]
                    - executed_exit
                ) * position["quantity"]

            fees = (
                self.commission_per_side
                * 2.0
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

                "entry_index":
                    position["entry_index"],

                "exit_index":
                    final_index,

                "side":
                    position["side"],

                "entry_price":
                    position["entry_price"],

                "exit_price":
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

        return {

            "success":
                True,

            "final_equity":
                equity,

            "performance":
                self.performance(
                    trades,
                    equity_curve,
                    starting_equity,
                ),

            "trades":
                trades,

            "equity_curve":
                equity_curve,

        }

    # ========================================================
    # PERFORMANCE
    # ========================================================

    def performance(
        self,
        trades: List[
            Dict[str, Any]
        ],
        equity_curve: List[float],
        starting_equity: float,
    ) -> Dict[str, Any]:

        pnls = [
            float(
                trade.get(
                    "net_pnl",
                    0.0,
                )
            )
            for trade in trades
        ]

        wins = [
            value
            for value in pnls
            if value > 0
        ]

        losses = [
            value
            for value in pnls
            if value < 0
        ]

        gross_profit = sum(
            wins
        )

        gross_loss = sum(
            abs(value)
            for value in losses
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else None
        )

        total_trades = len(
            pnls
        )

        win_rate = (
            len(wins)
            / total_trades
            * 100.0
            if total_trades
            else 0.0
        )

        final_equity = (
            equity_curve[-1]
            if equity_curve
            else starting_equity
        )

        net_pnl = (
            final_equity
            - starting_equity
        )

        peak = (
            equity_curve[0]
            if equity_curve
            else starting_equity
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

        max_drawdown_percent = (
            max_drawdown
            / starting_equity
            * 100.0
            if starting_equity > 0
            else 0.0
        )

        return {

            "starting_equity":
                starting_equity,

            "final_equity":
                final_equity,

            "net_pnl":
                net_pnl,

            "return_percent":
                (
                    net_pnl
                    / starting_equity
                    * 100.0
                )
                if starting_equity
                else 0.0,

            "total_trades":
                total_trades,

            "win_rate":
                win_rate,

            "profit_factor":
                profit_factor,

            "average_trade":
                (
                    sum(pnls)
                    / total_trades
                )
                if total_trades
                else 0.0,

            "max_drawdown":
                max_drawdown,

            "max_drawdown_percent":
                max_drawdown_percent,

        }

    # ========================================================
    # EXPANDING WALK FORWARD
    # ========================================================

    def walk_forward(
        self,
        data: pd.DataFrame,
        windows: int = 3,
    ) -> Dict[str, Any]:

        results = []

        n = len(data)

        minimum_train = (
            self.minimum_history
            + 30
        )

        if n < (
            minimum_train + 120
        ):

            return {

                "windows":
                    [],

                "profitable_windows":
                    0,

                "total_windows":
                    0,

                "average_profit_factor":
                    0.0,

                "stable":
                    False,

            }

        available_test = (
            n
            - minimum_train
        )

        test_size = max(
            40,
            available_test
            // windows,
        )

        for window in range(
            windows
        ):

            train_end = (
                minimum_train
                +
                window
                * test_size
            )

            test_start = train_end

            test_end = min(
                test_start
                + test_size,
                n,
            )

            if test_start >= n:
                continue

            if (
                test_end
                - test_start
                < 40
            ):
                continue

            train_result = (
                self.simulate_period(

                    data,

                    self.starting_capital,

                    start_index=
                        self.minimum_history,

                    end_index=
                        train_end,

                )
            )

            test_result = (
                self.simulate_period(

                    data,

                    train_result[
                        "final_equity"
                    ],

                    start_index=
                        test_start,

                    end_index=
                        test_end,

                )
            )

            results.append({

                "window":
                    window + 1,

                "train_end":
                    train_end,

                "test_start":
                    test_start,

                "test_end":
                    test_end,

                "train":
                    train_result,

                "test":
                    test_result,

            })

        profitable = 0
        profit_factors = []

        for result in results:

            performance = (
                result["test"][
                    "performance"
                ]
            )

            return_percent = float(
                performance.get(
                    "return_percent",
                    0.0,
                )
            )

            pf = performance.get(
                "profit_factor"
            )

            if (
                return_percent > 0
                and
                pf is not None
                and
                float(pf) >= 1.0
            ):

                profitable += 1

            if (
                pf is not None
                and
                float(pf) > 0
            ):

                profit_factors.append(
                    float(pf)
                )

        total_windows = len(
            results
        )

        average_pf = (
            sum(profit_factors)
            / len(profit_factors)
            if profit_factors
            else 0.0
        )

        stable = (
            total_windows >= 2
            and
            profitable >= (
                total_windows * 0.66
            )
            and
            average_pf >= 1.0
        )

        return {

            "windows":
                results,

            "profitable_windows":
                profitable,

            "total_windows":
                total_windows,

            "average_profit_factor":
                average_pf,

            "stable":
                stable,

        }

    # ========================================================
    # RESEARCH
    # ========================================================

    def research(
        self,
        symbol: str = "NIFTY",
        market: str = "india",
        timeframe: str = "1d",
        bars: int = 1000,
    ) -> Dict[str, Any]:

        print(
            "JARVIS MOMENTUM RESEARCH > "
            f"Loading {symbol} {timeframe}..."
        )

        market_data = get_market_data(

            symbol=symbol,

            market=market,

            timeframe=timeframe,

            bars=bars,

        )

        if not market_data.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    market_data.get(
                        "message",
                        "Market data failed.",
                    ),

            }

        data = self.prepare(
            market_data["data"]
        )

        print(
            "JARVIS MOMENTUM RESEARCH > "
            f"Loaded {len(data):,} bars."
        )

        if len(data) < (
            self.minimum_history * 2
        ):

            return {

                "success":
                    False,

                "message":
                    "Insufficient historical data.",

            }

        split = int(
            len(data) * 0.70
        )

        train_result = (
            self.simulate_period(

                data,

                self.starting_capital,

                start_index=
                    self.minimum_history,

                end_index=
                    split,

            )
        )

        test_result = (
            self.simulate_period(

                data,

                train_result[
                    "final_equity"
                ],

                start_index=
                    split,

                end_index=
                    len(data),

            )
        )

        walk_forward = (
            self.walk_forward(
                data,
                windows=3,
            )
        )

        backtest_result = {

            "train":
                train_result,

            "test":
                test_result,

            "walk_forward":
                walk_forward,

        }

        evaluation = (
            research_edge_engine.evaluate(

                strategy=
                    "MOMENTUM",

                symbol=
                    symbol,

                market=
                    market,

                timeframe=
                    timeframe,

                backtest_result=
                    backtest_result,

            )
        )

        if not evaluation.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Research edge evaluation failed.",

            }

        store = (
            research_edge_engine.store(
                evaluation
            )
        )

        return {

            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "bars":
                len(data),

            "backtest":
                backtest_result,

            "evaluation":
                evaluation,

            "store":
                store,

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        if not result.get(
            "success",
            False,
        ):

            return (
                "MOMENTUM RESEARCH FAILED\n"
                "--------------------------------------------------\n"
                +
                str(
                    result.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        test_performance = (
            result[
                "backtest"
            ][
                "test"
            ][
                "performance"
            ]
        )

        walk = (
            result[
                "backtest"
            ][
                "walk_forward"
            ]
        )

        evaluation = (
            result[
                "evaluation"
            ]
        )

        lines = []

        lines.append(
            "JARVIS MOMENTUM RESEARCH"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: "
            f"{result.get('symbol')}"
        )

        lines.append(
            f"Timeframe: "
            f"{result.get('timeframe')}"
        )

        lines.append(
            f"Historical Bars: "
            f"{result.get('bars', 0):,}"
        )

        lines.append("")

        lines.append(
            "OUT-OF-SAMPLE"
        )

        lines.append(
            f"Return: "
            f"{test_performance.get('return_percent', 0):.2f}%"
        )

        lines.append(
            f"Profit Factor: "
            f"{test_performance.get('profit_factor')}"
        )

        lines.append(
            f"Win Rate: "
            f"{test_performance.get('win_rate', 0):.2f}%"
        )

        lines.append(
            f"Trades: "
            f"{test_performance.get('total_trades', 0)}"
        )

        lines.append(
            f"Max Drawdown: "
            f"{test_performance.get('max_drawdown_percent', 0):.2f}%"
        )

        lines.append("")

        lines.append(
            "WALK-FORWARD"
        )

        lines.append(
            f"Profitable Windows: "
            f"{walk.get('profitable_windows', 0)}/"
            f"{walk.get('total_windows', 0)}"
        )

        lines.append(
            f"Average PF: "
            f"{walk.get('average_profit_factor', 0):.2f}"
        )

        lines.append(
            f"Stable: "
            f"{walk.get('stable')}"
        )

        lines.append("")

        lines.append(
            "RESEARCH EDGE"
        )

        lines.append(
            f"Score: "
            f"{evaluation.get('research_score')}/100"
        )

        lines.append(
            f"Quality: "
            f"{evaluation.get('quality')}"
        )

        lines.append(
            f"Validated: "
            f"{evaluation.get('validated')}"
        )

        warnings = evaluation.get(
            "warnings",
            [],
        )

        if warnings:

            lines.append("")

            lines.append(
                "WARNINGS"
            )

            for warning in warnings:

                lines.append(
                    f"- {warning}"
                )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Historical research only. "
            "No live order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

momentum_research_runner = (
    MomentumResearchRunner()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS MOMENTUM RESEARCH RUNNER"
    )

    print(
        "=" * 60
    )

    result = (
        momentum_research_runner.research(

            symbol="NIFTY",

            market="india",

            timeframe="1d",

            bars=1000,

        )
    )

    print()

    print(
        momentum_research_runner.format_result(
            result
        )
    )

    print()

    print(
        "Momentum Research Runner loaded successfully."
    )