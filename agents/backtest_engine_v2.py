# ============================================================
# JARVIS BACKTEST ENGINE V2
# ============================================================
#
# Research-grade baseline backtester.
#
# Features:
#   - Train / test split
#   - Walk-forward testing
#   - Commission
#   - Slippage
#   - Equity curve
#   - Drawdown
#   - Monthly returns
#   - Trade statistics
#   - Out-of-sample summary
#
# IMPORTANT:
#   Simulation only.
#   No broker connection.
#   No live orders.
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from agents.technical_engine import technical_engine
from agents.pattern_engine import pattern_engine
from agents.signal_engine import signal_engine
from agents.risk_engine import RiskEngine


# ============================================================
# TRADE MODEL
# ============================================================

@dataclass
class V2Trade:

    trade_id: int

    side: str

    entry_index: int
    entry_price: float

    exit_index: int
    exit_price: float

    quantity: float

    stop_loss: float
    target: float

    gross_pnl: float
    fees: float
    slippage_cost: float
    net_pnl: float

    exit_reason: str


# ============================================================
# ENGINE
# ============================================================

class BacktestEngineV2:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        risk_per_trade_percent: float = 1.0,
        commission_per_side: float = 20.0,
        slippage_percent: float = 0.02,
        minimum_history: int = 60,
        train_percent: float = 70.0,
    ):

        if starting_capital <= 0:
            raise ValueError(
                "starting_capital must be positive."
            )

        if not 0 < train_percent < 100:
            raise ValueError(
                "train_percent must be between 0 and 100."
            )

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

        self.train_percent = float(
            train_percent
        )

        self.risk_engine = RiskEngine(
            risk_per_trade_percent=
                risk_per_trade_percent
        )

    # ========================================================
    # DATA PREPARATION
    # ========================================================

    def prepare_data(
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

        if "volume" not in data.columns:
            data["volume"] = 0.0

        for column in [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        data = data.dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
            ]
        )

        return data.reset_index(
            drop=True
        )

    # ========================================================
    # SLIPPAGE
    # ========================================================

    def execution_price(
        self,
        price: float,
        side: str,
    ) -> float:

        price = float(price)

        adjustment = (
            price
            * self.slippage_percent
            / 100.0
        )

        if side == "BUY":
            return price + adjustment

        return price - adjustment

    # ========================================================
    # EXIT CHECK
    # ========================================================

    def check_exit(
        self,
        side: str,
        candle: pd.Series,
        stop_loss: float,
        target: float,
    ) -> Optional[Tuple[float, str]]:

        high = float(candle["high"])
        low = float(candle["low"])

        if side == "LONG":

            stop_hit = low <= stop_loss
            target_hit = high >= target

            # Conservative ordering:
            # stop is assumed first when both occur.
            if stop_hit:
                return stop_loss, "STOP_LOSS"

            if target_hit:
                return target, "TAKE_PROFIT"

        else:

            stop_hit = high >= stop_loss
            target_hit = low <= target

            if stop_hit:
                return stop_loss, "STOP_LOSS"

            if target_hit:
                return target, "TAKE_PROFIT"

        return None

    # ========================================================
    # SPLIT
    # ========================================================

    def split_data(
        self,
        data: pd.DataFrame,
    ) -> Tuple[
        pd.DataFrame,
        pd.DataFrame,
    ]:

        split_index = int(
            len(data)
            * self.train_percent
            / 100.0
        )

        split_index = max(
            self.minimum_history,
            min(
                split_index,
                len(data) - 1,
            ),
        )

        train = data.iloc[
            :split_index
        ].copy()

        test = data.iloc[
            split_index:
        ].copy()

        return train, test

    # ========================================================
    # SINGLE PERIOD BACKTEST
    # ========================================================

    def run_period(
        self,
        data: pd.DataFrame,
        starting_equity: float,
        symbol: str,
        period_name: str,
    ) -> Dict[str, Any]:

        if len(data) < self.minimum_history:
            return {
                "success": False,
                "message":
                    (
                        f"{period_name} period requires "
                        f"at least {self.minimum_history} bars."
                    ),
            }

        equity = float(
            starting_equity
        )

        equity_curve = [
            equity
        ]

        trades: List[V2Trade] = []

        current = None
        trade_id = 0

        for index in range(
            self.minimum_history,
            len(data),
        ):

            candle = data.iloc[index]

            # ------------------------------------------------
            # MANAGE OPEN TRADE
            # ------------------------------------------------

            if current is not None:

                exit_event = (
                    self.check_exit(
                        side=current["side"],
                        candle=candle,
                        stop_loss=current["stop_loss"],
                        target=current["target"],
                    )
                )

                if exit_event is not None:

                    raw_exit, reason = (
                        exit_event
                    )

                    exit_side = (
                        "SELL"
                        if current["side"] == "LONG"
                        else "BUY"
                    )

                    exit_price = (
                        self.execution_price(
                            raw_exit,
                            exit_side,
                        )
                    )

                    if current["side"] == "LONG":

                        gross_pnl = (
                            exit_price
                            - current["entry_price"]
                        ) * current["quantity"]

                    else:

                        gross_pnl = (
                            current["entry_price"]
                            - exit_price
                        ) * current["quantity"]

                    fees = (
                        self.commission_per_side
                        * 2.0
                    )

                    slippage_cost = (
                        abs(
                            exit_price
                            - raw_exit
                        )
                        * current["quantity"]
                    )

                    net_pnl = (
                        gross_pnl
                        - fees
                    )

                    equity += net_pnl

                    trade_id += 1

                    trades.append(

                        V2Trade(

                            trade_id=trade_id,

                            side=current["side"],

                            entry_index=current[
                                "entry_index"
                            ],

                            entry_price=current[
                                "entry_price"
                            ],

                            exit_index=index,

                            exit_price=exit_price,

                            quantity=current[
                                "quantity"
                            ],

                            stop_loss=current[
                                "stop_loss"
                            ],

                            target=current[
                                "target"
                            ],

                            gross_pnl=gross_pnl,

                            fees=fees,

                            slippage_cost=
                                slippage_cost,

                            net_pnl=net_pnl,

                            exit_reason=reason,

                        )

                    )

                    current = None

                equity_curve.append(
                    equity
                )

                continue

            # ------------------------------------------------
            # HISTORY
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

            signal = (
                signal_engine.generate_signal(
                    technical,
                    patterns,
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

            risk_decision = (
                self.risk_engine.evaluate_trade(

                    account_equity=equity,

                    entry_price=entry,

                    stop_price=stop,

                    target_price=target,

                )
            )

            if not risk_decision.approved:

                equity_curve.append(
                    equity
                )
                continue

            quantity = float(
                risk_decision.position_size
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

            entry_slippage = (
                abs(
                    executed_entry
                    - entry
                )
                * quantity
            )

            equity -= (
                self.commission_per_side
            )

            current = {

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

                "stop_loss":
                    stop,

                "target":
                    target,

                "entry_slippage":
                    entry_slippage,

            }

            equity_curve.append(
                equity
            )

        # ----------------------------------------------------
        # End-of-data exit
        # ----------------------------------------------------

        if current is not None:

            index = (
                len(data) - 1
            )

            raw_exit = float(
                data.iloc[index]["close"]
            )

            exit_side = (
                "SELL"
                if current["side"] == "LONG"
                else "BUY"
            )

            exit_price = (
                self.execution_price(
                    raw_exit,
                    exit_side,
                )
            )

            if current["side"] == "LONG":

                gross_pnl = (
                    exit_price
                    - current["entry_price"]
                ) * current["quantity"]

            else:

                gross_pnl = (
                    current["entry_price"]
                    - exit_price
                ) * current["quantity"]

            fees = (
                self.commission_per_side
                * 2.0
            )

            slippage_cost = (
                current["entry_slippage"]
                +
                abs(
                    exit_price
                    - raw_exit
                )
                * current["quantity"]
            )

            net_pnl = (
                gross_pnl
                - fees
            )

            equity += net_pnl

            trade_id += 1

            trades.append(

                V2Trade(

                    trade_id=trade_id,

                    side=current["side"],

                    entry_index=current[
                        "entry_index"
                    ],

                    entry_price=current[
                        "entry_price"
                    ],

                    exit_index=index,

                    exit_price=exit_price,

                    quantity=current[
                        "quantity"
                    ],

                    stop_loss=current[
                        "stop_loss"
                    ],

                    target=current[
                        "target"
                    ],

                    gross_pnl=gross_pnl,

                    fees=fees,

                    slippage_cost=
                        slippage_cost,

                    net_pnl=net_pnl,

                    exit_reason=
                        "END_OF_DATA",

                )

            )

            equity_curve.append(
                equity
            )

        performance = (
            self.calculate_performance(
                trades,
                equity_curve,
                starting_equity,
            )
        )

        return {

            "success":
                True,

            "symbol":
                symbol,

            "period":
                period_name,

            "trades":
                [
                    asdict(trade)
                    for trade in trades
                ],

            "equity_curve":
                equity_curve,

            "performance":
                performance,

            "final_equity":
                equity,

        }

    # ========================================================
    # PERFORMANCE
    # ========================================================

    def calculate_performance(
        self,
        trades: List[V2Trade],
        equity_curve: List[float],
        starting_equity: float,
    ) -> Dict[str, Any]:

        pnls = [
            trade.net_pnl
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

        total_trades = len(
            trades
        )

        if total_trades:

            win_rate = (
                len(wins)
                / total_trades
                * 100
            )

        else:

            win_rate = 0.0

        if gross_loss:

            profit_factor = (
                gross_profit
                / gross_loss
            )

        else:

            profit_factor = None

        net_pnl = (
            sum(pnls)
        )

        average_trade = (
            net_pnl
            / total_trades
            if total_trades
            else 0.0
        )

        max_drawdown = (
            self.calculate_max_drawdown(
                equity_curve
            )
        )

        return {

            "starting_equity":
                starting_equity,

            "final_equity":
                equity_curve[-1],

            "net_pnl":
                net_pnl,

            "return_percent":
                (
                    net_pnl
                    / starting_equity
                    * 100
                )
                if starting_equity
                else 0.0,

            "total_trades":
                total_trades,

            "wins":
                len(wins),

            "losses":
                len(losses),

            "win_rate":
                round(
                    win_rate,
                    2,
                ),

            "gross_profit":
                gross_profit,

            "gross_loss":
                gross_loss,

            "profit_factor":
                profit_factor,

            "average_trade":
                average_trade,

            "average_win":
                (
                    sum(wins) / len(wins)
                    if wins
                    else 0.0
                ),

            "average_loss":
                (
                    sum(losses) / len(losses)
                    if losses
                    else 0.0
                ),

            "max_drawdown":
                max_drawdown,

            "max_drawdown_percent":
                (
                    max_drawdown
                    / starting_equity
                    * 100
                )
                if starting_equity
                else 0.0,

        }

    # ========================================================
    # MAX DRAWDOWN
    # ========================================================

    def calculate_max_drawdown(
        self,
        curve: List[float],
    ) -> float:

        if not curve:
            return 0.0

        peak = curve[0]
        maximum = 0.0

        for value in curve:

            peak = max(
                peak,
                value,
            )

            drawdown = (
                peak
                - value
            )

            maximum = max(
                maximum,
                drawdown,
            )

        return float(
            maximum
        )

    # ========================================================
    # MONTHLY RETURNS
    # ========================================================

    def monthly_returns(
        self,
        data: pd.DataFrame,
        trades: List[Dict[str, Any]],
    ) -> Dict[str, float]:

        if data is None or data.empty:
            return {}

        # Determine a usable date column.
        date_column = None

        for column in [
            "date",
            "datetime",
            "timestamp",
        ]:

            if column in data.columns:
                date_column = column
                break

        if date_column is None:

            # If the original index represents dates.
            if isinstance(
                data.index,
                pd.DatetimeIndex,
            ):

                dates = data.index

            else:

                return {}

        else:

            dates = pd.to_datetime(
                data[date_column],
                errors="coerce",
            )

        if len(dates) == 0:
            return {}

        result = {}

        for trade in trades:

            exit_index = trade.get(
                "exit_index"
            )

            if exit_index is None:
                continue

            if (
                exit_index < 0
                or
                exit_index >= len(dates)
            ):
                continue

            date = dates[
                exit_index
            ]

            if pd.isna(date):
                continue

            month = (
                date.strftime(
                    "%Y-%m"
                )
            )

            result[
                month
            ] = (
                result.get(
                    month,
                    0.0,
                )
                +
                float(
                    trade.get(
                        "net_pnl",
                        0.0,
                    )
                )
            )

        return result

    # ========================================================
    # WALK-FORWARD
    # ========================================================

    def walk_forward(
        self,
        data: pd.DataFrame,
        symbol: str = "UNKNOWN",
        windows: int = 3,
    ) -> Dict[str, Any]:

        data = self.prepare_data(
            data
        )

        if len(data) < (
            self.minimum_history
            * 2
        ):

            return {

                "success":
                    False,

                "message":
                    "Insufficient data for walk-forward testing.",

            }

        if windows < 1:
            windows = 1

        results = []

        total_length = len(data)

        window_size = (
            total_length
            // windows
        )

        for window in range(
            windows
        ):

            start = (
                window
                * window_size
            )

            end = (
                total_length
                if window
                == windows - 1
                else
                (
                    window + 1
                )
                * window_size
            )

            segment = data.iloc[
                start:end
            ].copy()

            if len(segment) <= (
                self.minimum_history
            ):
                continue

            train_size = int(
                len(segment)
                * 0.5
            )

            train = segment.iloc[
                :train_size
            ]

            test = segment.iloc[
                train_size:
            ]

            if len(train) < (
                self.minimum_history
            ):

                continue

            if len(test) == 0:
                continue

            # Use training-period equity as the
            # starting capital of this window.
            train_result = (
                self.run_period(

                    train,

                    self.starting_capital,

                    symbol,

                    f"TRAIN_{window + 1}",

                )
            )

            train_equity = (
                train_result.get(
                    "final_equity",
                    self.starting_capital,
                )
            )

            test_result = (
                self.run_period(

                    test,

                    train_equity,

                    symbol,

                    f"TEST_{window + 1}",

                )
            )

            results.append({

                "window":
                    window + 1,

                "train":
                    train_result,

                "test":
                    test_result,

            })

        return {

            "success":
                True,

            "symbol":
                symbol,

            "windows":
                results,

        }

    # ========================================================
    # FULL V2 TEST
    # ========================================================

    def run(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
        market: str = "INDIA",
    ) -> Dict[str, Any]:

        data = self.prepare_data(
            df
        )

        if data.empty:

            return {

                "success":
                    False,

                "message":
                    "No valid OHLCV data supplied.",

            }

        if len(data) < (
            self.minimum_history * 2
        ):

            return {

                "success":
                    False,

                "message":
                    (
                        "Not enough history. "
                        "Need at least "
                        f"{self.minimum_history * 2} bars."
                    ),

            }

        train, test = (
            self.split_data(
                data
            )
        )

        train_result = (
            self.run_period(

                train,

                self.starting_capital,

                symbol,

                "TRAIN",

            )
        )

        train_equity = (
            train_result.get(
                "final_equity",
                self.starting_capital,
            )
        )

        test_result = (
            self.run_period(

                test,

                train_equity,

                symbol,

                "OUT_OF_SAMPLE_TEST",

            )
        )

        walk_forward = (
            self.walk_forward(
                data,
                symbol=symbol,
                windows=3,
            )
        )

        return {

            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "bars":
                len(data),

            "train_bars":
                len(train),

            "test_bars":
                len(test),

            "train":
                train_result,

            "test":
                test_result,

            "walk_forward":
                walk_forward,

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
                "BACKTEST V2 FAILED\n"
                "--------------------------------------------------\n"
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
            "JARVIS BACKTEST V2"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: {result.get('symbol')}"
        )

        lines.append(
            f"Market: {result.get('market')}"
        )

        lines.append(
            f"Total Bars: {result.get('bars', 0):,}"
        )

        lines.append(
            f"Train Bars: {result.get('train_bars', 0):,}"
        )

        lines.append(
            f"Test Bars: {result.get('test_bars', 0):,}"
        )

        # ----------------------------------------------------
        # TRAIN
        # ----------------------------------------------------

        train_perf = (
            result.get(
                "train",
                {}
            )
            .get(
                "performance",
                {},
            )
        )

        lines.append("")
        lines.append(
            "TRAIN PERFORMANCE"
        )

        self._append_performance(
            lines,
            train_perf,
        )

        # ----------------------------------------------------
        # OUT-OF-SAMPLE
        # ----------------------------------------------------

        test_perf = (
            result.get(
                "test",
                {}
            )
            .get(
                "performance",
                {},
            )
        )

        lines.append("")
        lines.append(
            "OUT-OF-SAMPLE TEST"
        )

        self._append_performance(
            lines,
            test_perf,
        )

        # ----------------------------------------------------
        # WALK FORWARD
        # ----------------------------------------------------

        walk = result.get(
            "walk_forward",
            {},
        )

        windows = walk.get(
            "windows",
            [],
        )

        if windows:

            lines.append("")
            lines.append(
                "WALK-FORWARD WINDOWS"
            )

            for item in windows:

                test = item.get(
                    "test",
                    {},
                )

                performance = test.get(
                    "performance",
                    {},
                )

                lines.append(

                    f"Window {item['window']}: "

                    f"Return="
                    f"{performance.get('return_percent', 0):.2f}%  "

                    f"WinRate="
                    f"{performance.get('win_rate', 0):.2f}%  "

                    f"PF="
                    f"{performance.get('profit_factor')}"

                )

        lines.append("")

        lines.append(
            "IMPORTANT"
        )

        lines.append(
            "The out-of-sample and walk-forward "
            "results are more informative than the "
            "training result. This remains a research "
            "simulation and does not guarantee future performance."
        )

        return "\n".join(
            lines
        )

    # ========================================================
    # APPEND PERFORMANCE
    # ========================================================

    def _append_performance(
        self,
        lines: List[str],
        performance: Dict[str, Any],
    ):

        lines.append(

            f"Starting Equity: "
            f"{performance.get('starting_equity', 0):,.2f}"

        )

        lines.append(

            f"Final Equity: "
            f"{performance.get('final_equity', 0):,.2f}"

        )

        lines.append(

            f"Net P&L: "
            f"{performance.get('net_pnl', 0):,.2f}"

        )

        lines.append(

            f"Return: "
            f"{performance.get('return_percent', 0):.2f}%"

        )

        lines.append(

            f"Trades: "
            f"{performance.get('total_trades', 0)}"

        )

        lines.append(

            f"Win Rate: "
            f"{performance.get('win_rate', 0):.2f}%"

        )

        lines.append(

            f"Profit Factor: "
            f"{performance.get('profit_factor')}"

        )

        lines.append(

            f"Average Trade: "
            f"{performance.get('average_trade', 0):,.2f}"

        )

        lines.append(

            f"Max Drawdown: "
            f"{performance.get('max_drawdown', 0):,.2f}"

        )

        lines.append(

            f"Max Drawdown %: "
            f"{performance.get('max_drawdown_percent', 0):.2f}%"

        )


# ============================================================
# GLOBAL
# ============================================================

backtest_engine_v2 = (
    BacktestEngineV2()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def backtest_v2(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    market: str = "INDIA",
):

    return backtest_engine_v2.run(
        df=df,
        symbol=symbol,
        market=market,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    import numpy as np

    print("=" * 60)
    print("JARVIS BACKTEST ENGINE V2")
    print("=" * 60)
    print()

    np.random.seed(11)

    rows = 600

    prices = (
        100
        +
        np.cumsum(
            np.random.normal(
                0.08,
                1.0,
                rows,
            )
        )
    )

    dates = pd.date_range(
        "2021-01-01",
        periods=rows,
        freq="D",
    )

    data = pd.DataFrame({

        "date":
            dates,

        "open":
            prices
            + np.random.normal(
                0,
                0.5,
                rows,
            ),

        "high":
            prices
            + np.random.uniform(
                0.2,
                1.5,
                rows,
            ),

        "low":
            prices
            - np.random.uniform(
                0.2,
                1.5,
                rows,
            ),

        "close":
            prices,

        "volume":
            np.random.randint(
                10_000,
                100_000,
                rows,
            ),

    })

    engine = BacktestEngineV2(
        starting_capital=100_000.0,
        risk_per_trade_percent=1.0,
        commission_per_side=5.0,
        slippage_percent=0.02,
        minimum_history=60,
        train_percent=70.0,
    )

    result = engine.run(
        data,
        symbol="TEST",
        market="TEST",
    )

    print(
        engine.format_result(
            result
        )
    )

    print()

    print(
        "Backtest Engine V2 loaded successfully."
    )