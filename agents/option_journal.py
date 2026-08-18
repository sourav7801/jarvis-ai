# ============================================================
# JARVIS OPTION JOURNAL
# V1
# ============================================================
#
# Dedicated journal for multi-leg option trades.
#
# IMPORTANT:
#   P&L is supplied by the option execution engine.
#   This journal does NOT recalculate spread P&L.
#
# Supports:
#   LONG_CALL
#   LONG_PUT
#   BULL_CALL_SPREAD
#   BEAR_PUT_SPREAD
#
# PAPER / RESEARCH ONLY.
# ============================================================

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import math


# ============================================================
# PATH
# ============================================================

BASE_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
)

OPTION_JOURNAL_FILE = (
    BASE_PATH
    / "option_trades.json"
)


# ============================================================
# JOURNAL
# ============================================================

class OptionJournal:

    def __init__(
        self,
        path: Optional[str] = None,
    ):

        self.path = Path(
            path
            if path
            else OPTION_JOURNAL_FILE
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.records: List[
            Dict[str, Any]
        ] = []

        self.load()

    # ========================================================
    # SAFE NUMBER
    # ========================================================

    @staticmethod
    def number(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if value is None:
                return default

            result = float(value)

            if math.isnan(result):
                return default

            if math.isinf(result):
                return default

            return result

        except Exception:

            return default

    # ========================================================
    # NOW
    # ========================================================

    @staticmethod
    def now() -> str:

        return datetime.now().isoformat(
            timespec="seconds"
        )

    # ========================================================
    # LOAD
    # ========================================================

    def load(self) -> None:

        if not self.path.exists():

            self.records = []

            return

        try:

            data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(
                data,
                list,
            ):

                self.records = data

            else:

                self.records = []

        except Exception:

            self.records = []

    # ========================================================
    # SAVE
    # ========================================================

    def save(self) -> None:

        self.path.write_text(

            json.dumps(
                self.records,
                indent=2,
                default=str,
            ),

            encoding="utf-8",

        )

    # ========================================================
    # FIND
    # ========================================================

    def get_trade(
        self,
        trade_id: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        for record in self.records:

            if (
                record.get(
                    "trade_id"
                )
                ==
                trade_id
            ):

                return record

        return None

    # ========================================================
    # OPEN
    # ========================================================

    def record_open(
        self,
        trade: Dict[str, Any],
    ) -> Dict[str, Any]:

        trade_id = str(
            trade.get(
                "trade_id"
            )
            or
            trade.get(
                "position_id"
            )
            or
            ""
        )

        if not trade_id:

            return {

                "success":
                    False,

                "message":
                    "Option trade ID is required.",

            }

        existing = self.get_trade(
            trade_id
        )

        if existing:

            return {

                "success":
                    True,

                "action":
                    "EXISTS",

                "trade_id":
                    trade_id,

                "record":
                    existing,

            }

        now = self.now()

        record = {

            "trade_id":
                trade_id,

            "status":
                "OPEN",

            "created_at":
                now,

            "updated_at":
                now,

            "symbol":
                str(
                    trade.get(
                        "symbol",
                        "",
                    )
                ).upper(),

            "market":
                str(
                    trade.get(
                        "market",
                        "INDIA",
                    )
                ).upper(),

            "asset_type":
                "OPTION",

            "strategy":
                trade.get(
                    "strategy"
                ),

            "direction":
                trade.get(
                    "direction"
                ),

            "expiry":
                trade.get(
                    "expiry"
                ),

            "expiry_days":
                trade.get(
                    "expiry_days"
                ),

            "long_strike":
                trade.get(
                    "long_strike"
                ),

            "short_strike":
                trade.get(
                    "short_strike"
                ),

            "lot_size":
                trade.get(
                    "lot_size"
                ),

            "lots":
                trade.get(
                    "lots"
                ),

            "quantity":
                trade.get(
                    "quantity"
                ),

            "entry_debit":
                self.number(
                    trade.get(
                        "entry_debit"
                    )
                ),

            "stop_debit":
                self.number(
                    trade.get(
                        "stop_debit"
                    )
                ),

            "target_1_debit":
                self.number(
                    trade.get(
                        "target_1_debit"
                    )
                ),

            "target_2_debit":
                self.number(
                    trade.get(
                        "target_2_debit"
                    )
                ),

            "planned_risk":
                self.number(
                    trade.get(
                        "planned_risk"
                    )
                ),

            "risk_reward":
                self.number(
                    trade.get(
                        "risk_reward"
                    )
                ),

            "setup_strength":
                self.number(
                    trade.get(
                        "setup_strength"
                    )
                ),

            "quality":
                trade.get(
                    "quality"
                ),

            "agreement":
                self.number(
                    trade.get(
                        "agreement"
                    )
                ),

            "market_regime":
                trade.get(
                    "market_regime"
                ),

            "entry_legs":
                trade.get(
                    "entry_legs",
                    []
                ),

            "paper_or_live":
                "PAPER",

            "metadata":
                {

                    "execution_model":
                        "BID_ASK_PAPER",

                    "mission_id":
                        trade.get(
                            "mission_id"
                        ),

                    "reasoning":
                        trade.get(
                            "reasoning",
                            []
                        ),

                },

        }

        self.records.append(
            record
        )

        self.save()

        return {

            "success":
                True,

            "action":
                "OPEN",

            "trade_id":
                trade_id,

            "record":
                record,

        }

    # ========================================================
    # CLOSE
    # ========================================================

    def record_close(
        self,
        trade: Dict[str, Any],
    ) -> Dict[str, Any]:

        trade_id = str(
            trade.get(
                "trade_id"
            )
            or
            ""
        )

        if not trade_id:

            return {

                "success":
                    False,

                "message":
                    "Trade ID is required.",

            }

        record = self.get_trade(
            trade_id
        )

        if record is None:

            # Safe fallback: create the opening record
            # from the completed trade itself.
            opened = self.record_open(
                trade
            )

            if not opened.get(
                "success",
                False,
            ):

                return opened

            record = self.get_trade(
                trade_id
            )

        if record is None:

            return {

                "success":
                    False,

                "message":
                    "Could not create option journal record.",

            }

        now = self.now()

        # ----------------------------------------------------
        # AUTHORITATIVE EXECUTION VALUES
        # ----------------------------------------------------

        gross_pnl = self.number(
            trade.get(
                "gross_pnl"
            )
        )

        fees = self.number(
            trade.get(
                "fees"
            )
        )

        slippage = self.number(
            trade.get(
                "slippage"
            )
        )

        net_pnl = self.number(
            trade.get(
                "net_pnl"
            )
        )

        exit_debit = self.number(
            trade.get(
                "exit_debit"
            )
        )

        # IMPORTANT:
        # Do NOT calculate gross/net P&L here.
        # The option execution engine is authoritative.

        record.update({

            "status":
                "CLOSED",

            "updated_at":
                now,

            "closed_at":
                now,

            "exit_debit":
                exit_debit,

            "actual_exit_debit":
                self.number(
                    trade.get(
                        "actual_exit_debit",
                        exit_debit,
                    )
                ),

            "trigger_level":
                trade.get(
                    "trigger_level"
                ),

            "exit_reason":
                trade.get(
                    "reason"
                ),

            "exit_legs":
                trade.get(
                    "exit_legs",
                    []
                ),

            "gross_pnl":
                gross_pnl,

            "fees":
                fees,

            "slippage":
                slippage,

            "net_pnl":
                net_pnl,

            "paper_or_live":
                "PAPER",

        })

        # ----------------------------------------------------
        # Preserve execution-engine accounting.
        # ----------------------------------------------------

        record[
            "authoritative_pnl_source"
        ] = (
            "OPTION_PAPER_EXECUTION_ENGINE"
        )

        self.save()

        return {

            "success":
                True,

            "action":
                "CLOSE",

            "trade_id":
                trade_id,

            "gross_pnl":
                gross_pnl,

            "fees":
                fees,

            "slippage":
                slippage,

            "net_pnl":
                net_pnl,

            "record":
                record,

        }

    # ========================================================
    # COMPLETE TRADE
    # ========================================================

    def record_complete_trade(
        self,
        trade: Dict[str, Any],
    ) -> Dict[str, Any]:

        opened = self.record_open(
            trade
        )

        if not opened.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "stage":
                    "OPEN",

                "open_result":
                    opened,

            }

        closed = self.record_close(
            trade
        )

        return {

            "success":
                bool(
                    closed.get(
                        "success",
                        False,
                    )
                ),

            "stage":
                "CLOSE",

            "trade_id":
                trade.get(
                    "trade_id"
                ),

            "open_result":
                opened,

            "close_result":
                closed,

        }

    # ========================================================
    # ALL
    # ========================================================

    def all_trades(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        return list(
            self.records
        )

    # ========================================================
    # CLOSED
    # ========================================================

    def closed_trades(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        return [

            record
            for record
            in self.records

            if record.get(
                "status"
            )
            ==
            "CLOSED"

        ]

    # ========================================================
    # PERFORMANCE
    # ========================================================

    def performance(
        self,
    ) -> Dict[str, Any]:

        closed = (
            self.closed_trades()
        )

        pnl_values = [

            self.number(
                trade.get(
                    "net_pnl"
                )
            )

            for trade
            in closed

        ]

        wins = [
            value
            for value
            in pnl_values
            if value > 0
        ]

        losses = [
            value
            for value
            in pnl_values
            if value < 0
        ]

        gross_profit = sum(
            wins
        )

        gross_loss = abs(
            sum(
                losses
            )
        )

        total_net = sum(
            pnl_values
        )

        if gross_loss > 0:

            profit_factor = (
                gross_profit
                /
                gross_loss
            )

        else:

            profit_factor = None

        if closed:

            win_rate = (
                len(wins)
                /
                len(closed)
                *
                100.0
            )

            average_trade = (
                total_net
                /
                len(closed)
            )

        else:

            win_rate = 0.0
            average_trade = 0.0

        return {

            "total_trades":
                len(closed),

            "winning_trades":
                len(wins),

            "losing_trades":
                len(losses),

            "win_rate":
                win_rate,

            "gross_profit":
                gross_profit,

            "gross_loss":
                gross_loss,

            "fees":
                sum(

                    self.number(
                        trade.get(
                            "fees"
                        )
                    )

                    for trade
                    in closed

                ),

            "slippage":
                sum(

                    self.number(
                        trade.get(
                            "slippage"
                        )
                    )

                    for trade
                    in closed

                ),

            "net_pnl":
                total_net,

            "average_trade":
                average_trade,

            "profit_factor":
                profit_factor,

        }

    # ========================================================
    # STRATEGY PERFORMANCE
    # ========================================================

    def strategy_performance(
        self,
    ) -> Dict[str, Any]:

        output: Dict[
            str,
            Dict[str, Any]
        ] = {}

        for trade in (
            self.closed_trades()
        ):

            strategy = str(
                trade.get(
                    "strategy",
                    "UNKNOWN",
                )
            )

            bucket = output.setdefault(

                strategy,

                {

                    "trades":
                        0,

                    "wins":
                        0,

                    "losses":
                        0,

                    "net_pnl":
                        0.0,

                    "win_rate":
                        0.0,

                },

            )

            bucket[
                "trades"
            ] += 1

            pnl = self.number(
                trade.get(
                    "net_pnl"
                )
            )

            bucket[
                "net_pnl"
            ] += pnl

            if pnl > 0:

                bucket[
                    "wins"
                ] += 1

            elif pnl < 0:

                bucket[
                    "losses"
                ] += 1

        for strategy, bucket in (
            output.items()
        ):

            trades = bucket[
                "trades"
            ]

            if trades > 0:

                bucket[
                    "win_rate"
                ] = (
                    bucket[
                        "wins"
                    ]
                    /
                    trades
                    *
                    100.0
                )

        return output

    # ========================================================
    # RESET TEST DATA
    # ========================================================

    def reset(
        self,
    ) -> Dict[str, Any]:

        self.records = []

        self.save()

        return {

            "success":
                True,

            "message":
                "Option journal reset.",

            "path":
                str(
                    self.path
                ),

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_performance(
        self,
    ) -> str:

        performance = (
            self.performance()
        )

        lines = []

        lines.append(
            "JARVIS OPTION JOURNAL"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Total Trades: "
            f"{performance['total_trades']}"
        )

        lines.append(
            f"Winners: "
            f"{performance['winning_trades']}"
        )

        lines.append(
            f"Losers: "
            f"{performance['losing_trades']}"
        )

        lines.append(
            f"Win Rate: "
            f"{performance['win_rate']:.2f}%"
        )

        lines.append(
            f"Gross Profit: "
            f"{performance['gross_profit']:.2f}"
        )

        lines.append(
            f"Gross Loss: "
            f"{performance['gross_loss']:.2f}"
        )

        lines.append(
            f"Fees: "
            f"{performance['fees']:.2f}"
        )

        lines.append(
            f"Slippage: "
            f"{performance['slippage']:.2f}"
        )

        lines.append(
            f"Net P&L: "
            f"{performance['net_pnl']:.2f}"
        )

        pf = performance[
            "profit_factor"
        ]

        lines.append(
            "Profit Factor: "
            +
            (
                f"{pf:.2f}"
                if pf is not None
                else "None"
            )
        )

        lines.append("")

        lines.append(
            "STRATEGY PERFORMANCE"
        )

        for strategy, stats in (
            self.strategy_performance()
            .items()
        ):

            lines.append(

                f"{strategy} | "
                f"Trades={stats['trades']} | "
                f"WinRate={stats['win_rate']:.2f}% | "
                f"NetPnL={stats['net_pnl']:.2f}"

            )

        lines.append("")

        lines.append(
            f"Journal: {self.path}"
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

option_journal = (
    OptionJournal()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION JOURNAL V1"
    )

    print(
        "=" * 60
    )

    # Clean unit-test state.
    option_journal.reset()

    test_trade = {

        "trade_id":
            "TEST-OPTION-JOURNAL-001",

        "symbol":
            "NIFTY",

        "market":
            "INDIA",

        "strategy":
            "BULL_CALL_SPREAD",

        "direction":
            "BULLISH",

        "expiry":
            "TEST",

        "expiry_days":
            20,

        "long_strike":
            24200,

        "short_strike":
            24400,

        "lot_size":
            25,

        "lots":
            2,

        "quantity":
            50,

        "entry_debit":
            33.0,

        "stop_debit":
            15.3,

        "target_1_debit":
            84.7,

        "target_2_debit":
            135.52,

        "planned_risk":
            841.5,

        "risk_reward":
            3.54,

        "setup_strength":
            86.0,

        "quality":
            "A",

        "agreement":
            100.0,

        # AUTHORITATIVE RESULTS
        "exit_debit":
            99.0,

        "actual_exit_debit":
            99.0,

        "trigger_level":
            84.7,

        "reason":
            "TARGET_1",

        "gross_pnl":
            3300.0,

        "fees":
            80.0,

        "slippage":
            0.0,

        "net_pnl":
            3220.0,

        "entry_legs":
            [

                {
                    "strike":
                        24200,

                    "side":
                        "BUY",

                    "entry_price":
                        331.0,

                },

                {
                    "strike":
                        24400,

                    "side":
                        "SELL",

                    "entry_price":
                        298.0,

                },

            ],

        "exit_legs":
            [

                {
                    "strike":
                        24200,

                    "side":
                        "BUY",

                    "exit_price":
                        380.0,

                },

                {
                    "strike":
                        24400,

                    "side":
                        "SELL",

                    "exit_price":
                        281.0,

                },

            ],

    }

    result = (
        option_journal
        .record_complete_trade(
            test_trade
        )
    )

    print()

    print(
        result
    )

    print()

    print(
        option_journal
        .format_performance()
    )

    print()

    print(
        "Option Journal V1 "
        "loaded successfully."
    )