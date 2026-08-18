# ============================================================
# JARVIS BACKTEST ENGINE
# V1
# ============================================================
#
# Purpose:
#   Replay historical OHLCV data and evaluate a strategy.
#
# Uses:
#   - Technical Engine
#   - Pattern Engine
#   - Signal Engine
#   - Risk Engine
#
# Features:
#   - Historical replay
#   - Long/short simulation
#   - Stop loss
#   - Take profit
#   - Position sizing
#   - Fees
#   - Slippage
#   - Equity curve
#   - Win rate
#   - Profit factor
#   - Max drawdown
#   - Expectancy
#
# IMPORTANT:
#   This is research/simulation only.
#   It does not connect to a broker.
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import math
import pandas as pd

from agents.technical_engine import (
    technical_engine,
)

from agents.pattern_engine import (
    pattern_engine,
)

from agents.signal_engine import (
    signal_engine,
)

from agents.risk_engine import (
    risk_engine,
)


# ============================================================
# TRADE MODEL
# ============================================================

@dataclass
class BacktestTrade:

    trade_id: int

    side: str

    entry_index: int
    entry_price: float

    quantity: float

    stop_loss: float
    target: float

    exit_index: int
    exit_price: float

    pnl: float

    fees: float
    net_pnl: float

    exit_reason: str


# ============================================================
# ENGINE
# ============================================================

class BacktestEngine:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        risk_per_trade_percent: float = 1.0,
        fee_per_trade: float = 0.0,
        slippage_percent: float = 0.0,
        minimum_history: int = 60,
    ):

        if starting_capital <= 0:

            raise ValueError(
                "starting_capital must be positive."
            )

        self.starting_capital = float(
            starting_capital
        )

        self.risk_per_trade_percent = float(
            risk_per_trade_percent
        )

        self.fee_per_trade = float(
            fee_per_trade
        )

        self.slippage_percent = float(
            slippage_percent
        )

        self.minimum_history = int(
            minimum_history
        )

    # ========================================================
    # PREPARE DATA
    # ========================================================

    def prepare_data(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        if df is None or df.empty:

            return pd.DataFrame()

        data = df.copy()

        data.columns = [
            str(column)
            .strip()
            .lower()
            for column
            in data.columns
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

            data[
                "volume"
            ] = 0.0

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

    def apply_slippage(
        self,
        price: float,
        side: str,
    ) -> float:

        if self.slippage_percent <= 0:

            return float(price)

        adjustment = (
            price
            * self.slippage_percent
            / 100.0
        )

        if side == "BUY":

            return (
                float(price)
                + adjustment
            )

        return (
            float(price)
            - adjustment
        )

    # ========================================================
    # EXIT CHECK
    # ========================================================

    def check_exit(
        self,
        side: str,
        candle,
        stop_loss: float,
        target: float,
    ) -> Optional[Dict[str, Any]]:

        high = float(
            candle["high"]
        )

        low = float(
            candle["low"]
        )

        # ----------------------------------------------------
        # LONG
        # ----------------------------------------------------

        if side == "LONG":

            stop_hit = (
                low <= stop_loss
            )

            target_hit = (
                high >= target
            )

            # Conservative assumption:
            # if both are touched in the same candle,
            # stop is assumed to happen first.
            if stop_hit:

                return {

                    "price":
                        stop_loss,

                    "reason":
                        "STOP_LOSS",

                }

            if target_hit:

                return {

                    "price":
                        target,

                    "reason":
                        "TAKE_PROFIT",

                }

        # ----------------------------------------------------
        # SHORT
        # ----------------------------------------------------

        else:

            stop_hit = (
                high >= stop_loss
            )

            target_hit = (
                low <= target
            )

            if stop_hit:

                return {

                    "price":
                        stop_loss,

                    "reason":
                        "STOP_LOSS",

                }

            if target_hit:

                return {

                    "price":
                        target,

                    "reason":
                        "TAKE_PROFIT",

                }

        return None

    # ========================================================
    # P&L
    # ========================================================

    def calculate_pnl(
        self,
        side: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
    ) -> float:

        if side == "LONG":

            return (
                exit_price
                - entry_price
            ) * quantity

        return (
            entry_price
            - exit_price
        ) * quantity

    # ========================================================
    # MAX DRAWDOWN
    # ========================================================

    def max_drawdown(
        self,
        equity_curve: List[float],
    ) -> float:

        if not equity_curve:

            return 0.0

        peak = equity_curve[0]

        maximum = 0.0

        for value in equity_curve:

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
    # PERFORMANCE
    # ========================================================

    def performance(
        self,
        trades: List[BacktestTrade],
        equity_curve: List[float],
    ) -> Dict[str, Any]:

        if not equity_curve:

            final_equity = (
                self.starting_capital
            )

        else:

            final_equity = (
                equity_curve[-1]
            )

        net_pnl = (
            final_equity
            - self.starting_capital
        )

        winners = [
            trade.net_pnl
            for trade in trades
            if trade.net_pnl > 0
        ]

        losers = [
            trade.net_pnl
            for trade in trades
            if trade.net_pnl < 0
        ]

        total_trades = len(
            trades
        )

        winning_trades = len(
            winners
        )

        losing_trades = len(
            losers
        )

        if total_trades > 0:

            win_rate = (
                winning_trades
                / total_trades
                * 100.0
            )

        else:

            win_rate = 0.0

        gross_profit = sum(
            winners
        )

        gross_loss = sum(
            abs(value)
            for value in losers
        )

        if gross_loss > 0:

            profit_factor = (
                gross_profit
                / gross_loss
            )

        else:

            profit_factor = None

        average_trade = (

            net_pnl
            / total_trades

            if total_trades > 0

            else 0.0

        )

        expectancy = average_trade

        if winners:

            average_win = (
                sum(winners)
                / len(winners)
            )

        else:

            average_win = 0.0

        if losers:

            average_loss = (
                sum(losers)
                / len(losers)
            )

        else:

            average_loss = 0.0

        maximum_drawdown = (
            self.max_drawdown(
                equity_curve
            )
        )

        if self.starting_capital > 0:

            maximum_drawdown_percent = (
                maximum_drawdown
                / self.starting_capital
                * 100.0
            )

            total_return_percent = (
                net_pnl
                / self.starting_capital
                * 100.0
            )

        else:

            maximum_drawdown_percent = 0.0
            total_return_percent = 0.0

        return {

            "starting_capital":
                self.starting_capital,

            "final_equity":
                final_equity,

            "net_pnl":
                net_pnl,

            "total_return_percent":
                total_return_percent,

            "total_trades":
                total_trades,

            "winning_trades":
                winning_trades,

            "losing_trades":
                losing_trades,

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

            "expectancy":
                expectancy,

            "average_win":
                average_win,

            "average_loss":
                average_loss,

            "max_drawdown":
                maximum_drawdown,

            "max_drawdown_percent":
                maximum_drawdown_percent,

        }

    # ========================================================
    # BACKTEST
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
                    (
                        "No valid OHLCV data supplied."
                    ),

            }

        if len(data) < (
            self.minimum_history
        ):

            return {

                "success":
                    False,

                "message":
                    (
                        f"At least "
                        f"{self.minimum_history} "
                        f"bars are required."
                    ),

            }

        trades: List[
            BacktestTrade
        ] = []

        equity_curve = [
            self.starting_capital
        ]

        equity = (
            self.starting_capital
        )

        current_position = None

        trade_counter = 0

        # ----------------------------------------------------
        # Walk forward candle by candle
        # ----------------------------------------------------

        for index in range(
            self.minimum_history,
            len(data),
        ):

            # =================================================
            # MANAGE EXISTING POSITION
            # =================================================

            if current_position is not None:

                exit_result = (
                    self.check_exit(
                        side=current_position[
                            "side"
                        ],

                        candle=data.iloc[
                            index
                        ],

                        stop_loss=current_position[
                            "stop_loss"
                        ],

                        target=current_position[
                            "target"
                        ],
                    )
                )

                if exit_result is not None:

                    raw_exit_price = (
                        float(
                            exit_result[
                                "price"
                            ]
                        )
                    )

                    if (
                        current_position[
                            "side"
                        ]
                        ==
                        "LONG"
                    ):

                        exit_side = "SELL"

                    else:

                        exit_side = "BUY"

                    exit_price = (
                        self.apply_slippage(
                            raw_exit_price,
                            exit_side,
                        )
                    )

                    pnl = (
                        self.calculate_pnl(
                            side=current_position[
                                "side"
                            ],

                            entry_price=current_position[
                                "entry_price"
                            ],

                            exit_price=exit_price,

                            quantity=current_position[
                                "quantity"
                            ],
                        )
                    )

                    fees = (
                        self.fee_per_trade
                        * 2.0
                    )

                    net_pnl = (
                        pnl
                        - fees
                    )

                    equity += (
                        net_pnl
                    )

                    trade_counter += 1

                    trades.append(

                        BacktestTrade(

                            trade_id=trade_counter,

                            side=current_position[
                                "side"
                            ],

                            entry_index=current_position[
                                "entry_index"
                            ],

                            entry_price=current_position[
                                "entry_price"
                            ],

                            quantity=current_position[
                                "quantity"
                            ],

                            stop_loss=current_position[
                                "stop_loss"
                            ],

                            target=current_position[
                                "target"
                            ],

                            exit_index=index,

                            exit_price=exit_price,

                            pnl=pnl,

                            fees=fees,

                            net_pnl=net_pnl,

                            exit_reason=exit_result[
                                "reason"
                            ],

                        )

                    )

                    current_position = None

                equity_curve.append(
                    equity
                )

                # Don't create another position
                # on the same candle after an exit.
                continue

            # =================================================
            # ANALYSIS WINDOW
            # =================================================

            history = data.iloc[
                : index + 1
            ].copy()

            # =================================================
            # TECHNICAL
            # =================================================

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

            # =================================================
            # PATTERNS
            # =================================================

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

            # =================================================
            # SIGNAL
            # =================================================

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

            # We only enter when the complete signal
            # has a defined trade candidate.
            if action not in {
                "BUY",
                "SELL",
            }:

                equity_curve.append(
                    equity
                )

                continue

            entry_price = signal.get(
                "entry"
            )

            stop_loss = signal.get(
                "stop_loss"
            )

            target = signal.get(
                "target"
            )

            if not all(
                value is not None
                for value in [
                    entry_price,
                    stop_loss,
                    target,
                ]
            ):

                equity_curve.append(
                    equity
                )

                continue

            entry_price = float(
                entry_price
            )

            stop_loss = float(
                stop_loss
            )

            target = float(
                target
            )

            # =================================================
            # RISK
            # =================================================

            risk_decision = (
                risk_engine.evaluate_trade(
                    account_equity=equity,

                    entry_price=entry_price,

                    stop_price=stop_loss,

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

            # =================================================
            # ENTRY
            # =================================================

            entry_side = (
                "BUY"
                if action == "BUY"
                else
                "SELL"
            )

            executed_entry = (
                self.apply_slippage(
                    entry_price,
                    entry_side,
                )
            )

            current_position = {

                "side":
                    (
                        "LONG"
                        if action == "BUY"
                        else
                        "SHORT"
                    ),

                "entry_index":
                    index,

                "entry_price":
                    executed_entry,

                "quantity":
                    quantity,

                "stop_loss":
                    stop_loss,

                "target":
                    target,

            }

            # Deduct entry fee.
            equity -= (
                self.fee_per_trade
            )

            equity_curve.append(
                equity
            )

        # =====================================================
        # FORCE CLOSE AT END
        # =====================================================

        if current_position is not None:

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
                if current_position[
                    "side"
                ] == "LONG"
                else
                "BUY"
            )

            exit_price = (
                self.apply_slippage(
                    raw_exit,
                    exit_side,
                )
            )

            pnl = (
                self.calculate_pnl(
                    side=current_position[
                        "side"
                    ],

                    entry_price=current_position[
                        "entry_price"
                    ],

                    exit_price=exit_price,

                    quantity=current_position[
                        "quantity"
                    ],
                )
            )

            fees = (
                self.fee_per_trade
                * 2.0
            )

            net_pnl = (
                pnl
                - fees
            )

            equity += net_pnl

            trade_counter += 1

            trades.append(

                BacktestTrade(

                    trade_id=trade_counter,

                    side=current_position[
                        "side"
                    ],

                    entry_index=current_position[
                        "entry_index"
                    ],

                    entry_price=current_position[
                        "entry_price"
                    ],

                    quantity=current_position[
                        "quantity"
                    ],

                    stop_loss=current_position[
                        "stop_loss"
                    ],

                    target=current_position[
                        "target"
                    ],

                    exit_index=final_index,

                    exit_price=exit_price,

                    pnl=pnl,

                    fees=fees,

                    net_pnl=net_pnl,

                    exit_reason="END_OF_DATA",

                )

            )

            equity_curve.append(
                equity
            )

        # =====================================================
        # PERFORMANCE
        # =====================================================

        performance = (
            self.performance(
                trades,
                equity_curve,
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

            "trades":
                [
                    asdict(trade)
                    for trade
                    in trades
                ],

            "equity_curve":
                equity_curve,

            "performance":
                performance,

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
                "BACKTEST FAILED\n"
                "--------------------------------------------------\n"
                +
                str(
                    result.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        performance = result.get(
            "performance",
            {},
        )

        lines = []

        lines.append(
            "JARVIS BACKTEST RESULT"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: "
            f"{result.get('symbol')}"
        )

        lines.append(
            f"Market: "
            f"{result.get('market')}"
        )

        lines.append(
            f"Historical Bars: "
            f"{result.get('bars', 0):,}"
        )

        lines.append("")

        lines.append(
            "PERFORMANCE"
        )

        lines.append(
            f"Starting Capital: "
            f"{performance.get('starting_capital', 0):,.2f}"
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
            f"{performance.get('total_return_percent', 0):.2f}%"
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
            f"Expectancy: "
            f"{performance.get('expectancy', 0):,.2f}"
        )

        lines.append(
            f"Average Win: "
            f"{performance.get('average_win', 0):,.2f}"
        )

        lines.append(
            f"Average Loss: "
            f"{performance.get('average_loss', 0):,.2f}"
        )

        lines.append(
            f"Max Drawdown: "
            f"{performance.get('max_drawdown', 0):,.2f}"
        )

        lines.append(
            f"Max Drawdown %: "
            f"{performance.get('max_drawdown_percent', 0):.2f}%"
        )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "This is a historical simulation, "
            "not a guarantee of future performance."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL ENGINE
# ============================================================

backtest_engine = BacktestEngine()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def backtest(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    market: str = "INDIA",
):

    return backtest_engine.run(
        df=df,
        symbol=symbol,
        market=market,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS BACKTEST ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    import numpy as np

    np.random.seed(
        7
    )

    rows = 300

    base = (
        100
        +
        np.cumsum(
            np.random.normal(
                0.15,
                1.0,
                rows,
            )
        )
    )

    data = pd.DataFrame({

        "open":
            base
            + np.random.normal(
                0,
                0.4,
                rows,
            ),

        "high":
            base
            + np.random.uniform(
                0.2,
                1.2,
                rows,
            ),

        "low":
            base
            - np.random.uniform(
                0.2,
                1.2,
                rows,
            ),

        "close":
            base,

        "volume":
            np.random.randint(
                10_000,
                100_000,
                rows,
            ),

    })

    engine = BacktestEngine(
        starting_capital=100_000.0,

        risk_per_trade_percent=1.0,

        fee_per_trade=5.0,

        slippage_percent=0.01,

        minimum_history=60,
    )

    result = engine.run(
        data,
        symbol="TEST",
        market="TEST",
    )

    print()

    print(
        engine.format_result(
            result
        )
    )

    print()

    print(
        "Backtest Engine loaded successfully."
    )