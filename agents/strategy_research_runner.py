# ============================================================
# JARVIS STRATEGY RESEARCH RUNNER
# V1
# ============================================================
#
# Purpose:
#   Run REAL historical research and store the results in the
#   Research Edge database.
#
# IMPORTANT:
#   This V1 deliberately does NOT pretend that the existing
#   generic signal engine represents separate strategies.
#
#   V1 supports:
#
#       REGIME_AWARE_BASELINE
#
#   It is the current real strategy pipeline:
#
#       Technical
#       + Patterns
#       + Regime
#       + Regime-aware signal
#       + Risk
#       + Backtest
#
#   Once dedicated strategy engines exist, they can be plugged
#   into this runner without changing the research database.
#
# NO LIVE ORDERS ARE PLACED.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from agents.market_data_agent import (
    get_market_data,
)

from agents.backtest_engine_v2 import (
    BacktestEngineV2,
)

from agents.research_edge_engine import (
    research_edge_engine,
)

from agents.technical_engine import (
    technical_engine,
)

from agents.pattern_engine import (
    pattern_engine,
)

from agents.regime_detector import (
    regime_detector,
)

from agents.regime_aware_signal_engine import (
    regime_aware_signal_engine,
)


# ============================================================
# STRATEGY ADAPTER
# ============================================================

class StrategyAdapter:

    """
    Base interface for research strategies.

    A future dedicated strategy should implement:

        prepare_signal(...)
    """

    name = "BASE"

    def prepare_signal(
        self,
        technical: Dict[str, Any],
        patterns: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> Dict[str, Any]:

        raise NotImplementedError


# ============================================================
# REAL CURRENT BASELINE
# ============================================================

class RegimeAwareBaselineStrategy(
    StrategyAdapter
):

    name = "REGIME_AWARE_BASELINE"

    def prepare_signal(
        self,
        technical: Dict[str, Any],
        patterns: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> Dict[str, Any]:

        return (
            regime_aware_signal_engine.generate_signal(

                technical=technical,

                patterns=patterns,

                regime=regime,

            )
        )


# ============================================================
# RUNNER
# ============================================================

class StrategyResearchRunner:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        risk_per_trade_percent: float = 1.0,
        commission_per_side: float = 20.0,
        slippage_percent: float = 0.02,
        minimum_history: int = 60,
    ):

        self.backtester = (
            BacktestEngineV2(

                starting_capital=
                    starting_capital,

                risk_per_trade_percent=
                    risk_per_trade_percent,

                commission_per_side=
                    commission_per_side,

                slippage_percent=
                    slippage_percent,

                minimum_history=
                    minimum_history,

                train_percent=
                    70.0,

            )
        )

        self.strategies = {

            "REGIME_AWARE_BASELINE":
                RegimeAwareBaselineStrategy(),

        }

    # ========================================================
    # REGISTER STRATEGY
    # ========================================================

    def register_strategy(
        self,
        strategy: StrategyAdapter,
    ):

        if not strategy.name:

            raise ValueError(
                "Strategy must have a name."
            )

        self.strategies[
            strategy.name
        ] = strategy

    # ========================================================
    # DATA
    # ========================================================

    def load_data(
        self,
        symbol: str,
        market: str,
        timeframe: str,
        bars: int,
    ) -> Dict[str, Any]:

        result = get_market_data(

            symbol=symbol,

            market=market,

            timeframe=timeframe,

            bars=bars,

        )

        return result

    # ========================================================
    # RAW SIGNAL RESEARCH
    # ========================================================

    def analyze_bar(
        self,
        history: pd.DataFrame,
        strategy: StrategyAdapter,
    ) -> Dict[str, Any]:

        technical = (
            technical_engine.analyze(
                history
            )
        )

        if not technical.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Technical analysis failed.",

            }

        patterns = (
            pattern_engine.analyze(
                history
            )
        )

        if not patterns.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Pattern analysis failed.",

            }

        regime = (
            regime_detector.analyze(
                history
            )
        )

        if not regime.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Regime detection failed.",

            }

        signal = (
            strategy.prepare_signal(

                technical=technical,

                patterns=patterns,

                regime=regime,

            )
        )

        return {

            "success":
                True,

            "technical":
                technical,

            "patterns":
                patterns,

            "regime":
                regime,

            "signal":
                signal,

        }

    # ========================================================
    # STRATEGY-BACKTEST
    # ========================================================

    def run_strategy(
        self,
        data: pd.DataFrame,
        strategy: StrategyAdapter,
        symbol: str,
        market: str,
        timeframe: str,
    ) -> Dict[str, Any]:

        if data is None or data.empty:

            return {

                "success":
                    False,

                "message":
                    "No data supplied.",

            }

        # ----------------------------------------------------
        # This function is intentionally conservative.
        #
        # It runs the current regime-aware signal as the
        # baseline strategy through the research backtester.
        #
        # Dedicated strategy implementations should be added
        # as separate adapters later.
        # ----------------------------------------------------

        result = (
            self._backtest_adapter(
                data=data,
                strategy=strategy,
                symbol=symbol,
                market=market,
                timeframe=timeframe,
            )
        )

        return result

    # ========================================================
    # ADAPTER BACKTEST
    # ========================================================

    def _backtest_adapter(
        self,
        data: pd.DataFrame,
        strategy: StrategyAdapter,
        symbol: str,
        market: str,
        timeframe: str,
    ) -> Dict[str, Any]:

        prepared = (
            self.backtester.prepare_data(
                data
            )
        )

        if prepared.empty:

            return {

                "success":
                    False,

                "message":
                    "Prepared historical data is empty.",

            }

        if len(prepared) < (
            self.backtester.minimum_history
            * 2
        ):

            return {

                "success":
                    False,

                "message":
                    (
                        "Not enough historical bars. "
                        f"Need at least "
                        f"{self.backtester.minimum_history * 2}."
                    ),

            }

        # ====================================================
        # CUSTOM WALK-FORWARD LOOP
        # ====================================================
        #
        # We need a strategy-aware backtest rather than simply
        # calling the generic engine, because this runner needs
        # to know exactly which adapter produced each signal.
        # ====================================================

        split = int(
            len(prepared) * 0.70
        )

        train = prepared.iloc[
            :split
        ].reset_index(
            drop=True
        )

        test = prepared.iloc[
            split:
        ].reset_index(
            drop=True
        )

        train_result = (
            self._simulate_period(

                train,

                strategy,

                self.backtester.starting_capital,

            )
        )

        train_equity = (
            train_result.get(
                "final_equity",
                self.backtester.starting_capital,
            )
        )

        test_result = (
            self._simulate_period(

                test,

                strategy,

                train_equity,

            )
        )

        walk_forward = (
            self._walk_forward(

                prepared,

                strategy,

            )
        )

        return {

            "success":
                True,

            "strategy":
                strategy.name,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "bars":
                len(prepared),

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
    # SIMULATE PERIOD
    # ========================================================

    def _simulate_period(
        self,
        data: pd.DataFrame,
        strategy: StrategyAdapter,
        starting_equity: float,
    ) -> Dict[str, Any]:

        equity = float(
            starting_equity
        )

        equity_curve = [
            equity
        ]

        trades = []

        position = None

        trade_id = 0

        for index in range(
            self.backtester.minimum_history,
            len(data),
        ):

            candle = data.iloc[
                index
            ]

            # ------------------------------------------------
            # Existing position
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

                if (
                    position["side"]
                    ==
                    "LONG"
                ):

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
                        if
                        position["side"]
                        ==
                        "LONG"
                        else
                        "BUY"
                    )

                    executed_exit = (
                        self.backtester.execution_price(

                            exit_price,

                            exit_side,

                        )
                    )

                    if (
                        position["side"]
                        ==
                        "LONG"
                    ):

                        gross_pnl = (

                            executed_exit
                            -
                            position["entry_price"]

                        ) * position[
                            "quantity"
                        ]

                    else:

                        gross_pnl = (

                            position["entry_price"]
                            -
                            executed_exit

                        ) * position[
                            "quantity"
                        ]

                    fees = (
                        self.backtester.commission_per_side
                        * 2.0
                    )

                    net_pnl = (
                        gross_pnl
                        - fees
                    )

                    equity += (
                        net_pnl
                    )

                    trade_id += 1

                    trades.append({

                        "trade_id":
                            trade_id,

                        "entry_index":
                            position[
                                "entry_index"
                            ],

                        "exit_index":
                            index,

                        "side":
                            position[
                                "side"
                            ],

                        "entry_price":
                            position[
                                "entry_price"
                            ],

                        "exit_price":
                            executed_exit,

                        "quantity":
                            position[
                                "quantity"
                            ],

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
            # Analyze history
            # ------------------------------------------------

            history = data.iloc[
                :index + 1
            ].copy()

            analysis = (
                self.analyze_bar(
                    history,
                    strategy,
                )
            )

            if not analysis.get(
                "success",
                False,
            ):

                equity_curve.append(
                    equity
                )

                continue

            signal = analysis[
                "signal"
            ]

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

            entry = float(
                entry
            )

            stop = float(
                stop
            )

            target = float(
                target
            )

            risk = (
                self.backtester.risk_engine.evaluate_trade(

                    account_equity=
                        equity,

                    entry_price=
                        entry,

                    stop_price=
                        stop,

                    target_price=
                        target,

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
                self.backtester.execution_price(

                    entry,

                    entry_side,

                )
            )

            equity -= (
                self.backtester.commission_per_side
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
                if
                position["side"]
                ==
                "LONG"
                else
                "BUY"
            )

            executed_exit = (
                self.backtester.execution_price(

                    raw_exit,

                    exit_side,

                )
            )

            if (
                position["side"]
                ==
                "LONG"
            ):

                gross_pnl = (

                    executed_exit
                    -
                    position["entry_price"]

                ) * position[
                    "quantity"
                ]

            else:

                gross_pnl = (

                    position["entry_price"]
                    -
                    executed_exit

                ) * position[
                    "quantity"
                ]

            fees = (
                self.backtester.commission_per_side
                * 2.0
            )

            net_pnl = (
                gross_pnl
                - fees
            )

            equity += (
                net_pnl
            )

            trade_id += 1

            trades.append({

                "trade_id":
                    trade_id,

                "entry_index":
                    position[
                        "entry_index"
                    ],

                "exit_index":
                    final_index,

                "side":
                    position[
                        "side"
                    ],

                "entry_price":
                    position[
                        "entry_price"
                    ],

                "exit_price":
                    executed_exit,

                "quantity":
                    position[
                        "quantity"
                    ],

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

        performance = (
            self._performance(
                trades,
                equity_curve,
                starting_equity,
            )
        )

        return {

            "success":
                True,

            "final_equity":
                equity,

            "performance":
                performance,

            "trades":
                trades,

            "equity_curve":
                equity_curve,

        }

    # ========================================================
    # PERFORMANCE
    # ========================================================

    def _performance(
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

        total_trades = len(
            pnls
        )

        if total_trades > 0:

            win_rate = (
                len(wins)
                /
                total_trades
                * 100.0
            )

            average_trade = (
                sum(pnls)
                /
                total_trades
            )

        else:

            win_rate = 0.0

            average_trade = 0.0

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
            /
            starting_equity
            * 100.0

            if starting_equity > 0
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
                    /
                    starting_equity
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
                average_trade,

            "gross_profit":
                gross_profit,

            "gross_loss":
                gross_loss,

            "max_drawdown_percent":
                max_drawdown_percent,

            "max_drawdown":
                max_drawdown,

        }

    # ========================================================
    # WALK-FORWARD
    # ========================================================

    def _walk_forward(
        self,
        data: pd.DataFrame,
        strategy: StrategyAdapter,
        windows: int = 3,
    ) -> Dict[str, Any]:

        if len(data) < (
            self.backtester.minimum_history
            * 2
        ):

            return {

                "windows":
                    [],

            }

        segment_size = (
            len(data)
            //
            windows
        )

        results = []

        for window in range(
            windows
        ):

            start = (
                window
                *
                segment_size
            )

            end = (

                len(data)

                if
                window
                ==
                windows - 1

                else

                (window + 1)
                *
                segment_size

            )

            segment = data.iloc[
                start:end
            ].reset_index(
                drop=True
            )

            if len(segment) < (
                self.backtester.minimum_history
                * 2
            ):

                continue

            split = int(
                len(segment)
                * 0.50
            )

            train = segment.iloc[
                :split
            ]

            test = segment.iloc[
                split:
            ]

            if len(test) < (
                self.backtester.minimum_history
            ):

                continue

            train_result = (
                self._simulate_period(

                    train,

                    strategy,

                    self.backtester.starting_capital,

                )
            )

            test_starting_equity = (
                train_result.get(
                    "final_equity",
                    self.backtester.starting_capital,
                )
            )

            test_result = (
                self._simulate_period(

                    test,

                    strategy,

                    test_starting_equity,

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

            "windows":
                results,

        }

    # ========================================================
    # SAVE EDGE
    # ========================================================

    def research_and_store(
        self,
        symbol: str,
        market: str,
        timeframe: str,
        bars: int = 1000,
        strategy_name: str = "REGIME_AWARE_BASELINE",
    ) -> Dict[str, Any]:

        strategy = self.strategies.get(
            strategy_name
        )

        if strategy is None:

            return {

                "success":
                    False,

                "message":
                    (
                        f"Strategy not registered: "
                        f"{strategy_name}"
                    ),

            }

        print(
            "JARVIS RESEARCH > "
            f"Loading {symbol} {timeframe} data..."
        )

        market_data = (
            self.load_data(

                symbol=symbol,

                market=market,

                timeframe=timeframe,

                bars=bars,

            )
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

        data = market_data.get(
            "data"
        )

        print(
            "JARVIS RESEARCH > "
            f"Loaded {len(data):,} bars."
        )

        print(
            "JARVIS RESEARCH > "
            f"Running {strategy.name}..."
        )

        backtest_result = (
            self.run_strategy(

                data=data,

                strategy=strategy,

                symbol=symbol,

                market=market,

                timeframe=timeframe,

            )
        )

        if not backtest_result.get(
            "success",
            False,
        ):

            return backtest_result

        print(
            "JARVIS RESEARCH > "
            "Evaluating research edge..."
        )

        evaluation = (
            research_edge_engine.evaluate(

                strategy=
                    strategy.name,

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

            return evaluation

        store_result = (
            research_edge_engine.store(
                evaluation
            )
        )

        return {

            "success":
                True,

            "strategy":
                strategy.name,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "backtest":
                backtest_result,

            "evaluation":
                evaluation,

            "store":
                store_result,

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
                "STRATEGY RESEARCH FAILED\n"
                "--------------------------------------------------\n"
                +
                str(
                    result.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        evaluation = result.get(
            "evaluation",
            {}
        )

        out_of_sample = (
            evaluation.get(
                "out_of_sample",
                {},
            )
        )

        walk_forward = (
            evaluation.get(
                "walk_forward",
                {},
            )
        )

        lines = []

        lines.append(
            "JARVIS STRATEGY RESEARCH"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Strategy: "
            f"{result.get('strategy')}"
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
            f"Timeframe: "
            f"{result.get('timeframe')}"
        )

        lines.append("")

        lines.append(
            "OUT-OF-SAMPLE"
        )

        lines.append(
            f"Return: "
            f"{out_of_sample.get('return_percent', 0):.2f}%"
        )

        lines.append(
            f"Profit Factor: "
            f"{out_of_sample.get('profit_factor')}"
        )

        lines.append(
            f"Win Rate: "
            f"{out_of_sample.get('win_rate', 0):.2f}%"
        )

        lines.append(
            f"Trades: "
            f"{out_of_sample.get('trades', 0)}"
        )

        lines.append(
            f"Drawdown: "
            f"{out_of_sample.get('drawdown_percent', 0):.2f}%"
        )

        lines.append("")

        lines.append(
            "WALK-FORWARD"
        )

        lines.append(
            f"Profitable Windows: "
            f"{walk_forward.get('profitable_windows', 0)}/"
            f"{walk_forward.get('total_windows', 0)}"
        )

        lines.append(
            f"Average PF: "
            f"{walk_forward.get('average_profit_factor', 0):.2f}"
        )

        lines.append(
            f"Stable: "
            f"{walk_forward.get('stable')}"
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
            "This is historical research only. "
            "It does not guarantee future performance "
            "and does not place an order."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

strategy_research_runner = (
    StrategyResearchRunner()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def research_strategy(
    symbol: str,
    market: str,
    timeframe: str,
    bars: int = 1000,
    strategy_name: str = "REGIME_AWARE_BASELINE",
):

    return (
        strategy_research_runner.research_and_store(

            symbol=symbol,

            market=market,

            timeframe=timeframe,

            bars=bars,

            strategy_name=strategy_name,

        )
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS STRATEGY RESEARCH RUNNER"
    )

    print(
        "=" * 60
    )

    result = research_strategy(

        symbol="NIFTY",

        market="india",

        timeframe="1d",

        bars=1000,

        strategy_name=
            "REGIME_AWARE_BASELINE",

    )

    print()

    print(
        strategy_research_runner.format_result(
            result
        )
    )

    print()

    print(
        "Strategy Research Runner loaded successfully."
    )