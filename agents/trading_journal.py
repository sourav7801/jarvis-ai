# ============================================================
# JARVIS TRADING JOURNAL
# V1
# ============================================================

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional


# ============================================================
# CONFIG
# ============================================================

DEFAULT_JOURNAL_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
    / "trading_journal.json"
)


# ============================================================
# JOURNAL
# ============================================================

class TradingJournal:

    def __init__(
        self,
        path: Optional[str] = None,
    ):

        self.path = Path(
            path
            if path
            else DEFAULT_JOURNAL_PATH
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
    # TIME
    # ========================================================

    def _now(self) -> str:

        return datetime.now().isoformat(
            timespec="seconds"
        )

    # ========================================================
    # LOAD
    # ========================================================

    def load(self):

        if not self.path.exists():

            self.records = []

            return

        try:

            content = self.path.read_text(
                encoding="utf-8"
            )

            if not content.strip():

                self.records = []

                return

            data = json.loads(
                content
            )

            if isinstance(
                data,
                list,
            ):

                self.records = data

            else:

                self.records = []

        except Exception as e:

            print(
                f"JARVIS JOURNAL DEBUG > "
                f"Load failed: {e}"
            )

            self.records = []

    # ========================================================
    # SAVE
    # ========================================================

    def save(self):

        try:

            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.path.write_text(
                json.dumps(
                    self.records,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )

            return True

        except Exception as e:

            print(
                f"JARVIS JOURNAL DEBUG > "
                f"Save failed: {e}"
            )

            return False

    # ========================================================
    # ADD TRADE
    # ========================================================

    def add_trade(
        self,
        symbol: str,
        market: str,
        asset_type: str,
        strategy: str,
        side: str,
        entry_price: float,
        quantity: float,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        signal_score: Optional[float] = None,
        confidence: Optional[float] = None,
        risk_reward: Optional[float] = None,
        market_regime: Optional[str] = None,
        reasoning: Optional[List[str]] = None,
        risk_amount: Optional[float] = None,
        paper_or_live: str = "PAPER",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        trade_id = (
            f"JARVIS-"
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}-"
            f"{len(self.records) + 1}"
        )

        record = {

            "trade_id":
                trade_id,

            "status":
                "OPEN",

            "created_at":
                self._now(),

            "updated_at":
                self._now(),

            "symbol":
                str(symbol).upper(),

            "market":
                market,

            "asset_type":
                asset_type,

            "strategy":
                strategy,

            "side":
                side,

            "entry_price":
                float(entry_price),

            "quantity":
                float(quantity),

            "stop_loss":
                stop_loss,

            "target":
                target,

            "exit_price":
                None,

            "gross_pnl":
                None,

            "fees":
                0.0,

            "net_pnl":
                None,

            "signal_score":
                signal_score,

            "confidence":
                confidence,

            "risk_reward":
                risk_reward,

            "risk_amount":
                risk_amount,

            "market_regime":
                market_regime,

            "reasoning":
                reasoning or [],

            "paper_or_live":
                str(
                    paper_or_live
                    or "PAPER"
                ).upper(),

            "metadata":
                metadata or {},

        }

        self.records.append(
            record
        )

        saved = self.save()

        return {

            "success":
                saved,

            "trade_id":
                trade_id,

            "message":
                (
                    "Trade journal entry created."
                    if saved
                    else
                    "Trade created but could not be saved."
                ),

            "record":
                record,

        }

    # ========================================================
    # CLOSE TRADE
    # ========================================================

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        fees: float = 0.0,
        reason: str = "",
    ) -> Dict[str, Any]:

        record = self.get_trade(
            trade_id
        )

        if record is None:

            return {

                "success":
                    False,

                "message":
                    (
                        f"Trade not found: "
                        f"{trade_id}"
                    ),

            }

        if record.get(
            "status"
        ) == "CLOSED":

            return {

                "success":
                    False,

                "message":
                    "Trade is already closed.",

            }

        entry = float(
            record.get(
                "entry_price",
                0,
            )
        )

        quantity = float(
            record.get(
                "quantity",
                0,
            )
        )

        side = str(
            record.get(
                "side",
                "LONG",
            )
        ).upper()

        exit_price = float(
            exit_price
        )

        fees = float(
            fees
        )

        if side in {
            "BUY",
            "LONG",
        }:

            gross_pnl = (
                exit_price
                - entry
            ) * quantity

        else:

            gross_pnl = (
                entry
                - exit_price
            ) * quantity

        net_pnl = (
            gross_pnl
            - fees
        )

        record[
            "status"
        ] = "CLOSED"

        record[
            "updated_at"
        ] = self._now()

        record[
            "exit_price"
        ] = exit_price

        record[
            "gross_pnl"
        ] = gross_pnl

        record[
            "fees"
        ] = fees

        record[
            "net_pnl"
        ] = net_pnl

        record[
            "exit_reason"
        ] = reason

        saved = self.save()

        return {

            "success":
                saved,

            "trade_id":
                trade_id,

            "gross_pnl":
                gross_pnl,

            "net_pnl":
                net_pnl,

            "message":
                (
                    "Trade closed and journal updated."
                    if saved
                    else
                    "Trade closed but journal could not be saved."
                ),

        }

    # ========================================================
    # GET TRADE
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
    # ALL TRADES
    # ========================================================

    def all_trades(
        self,
    ) -> List[Dict[str, Any]]:

        return list(
            self.records
        )

    # ========================================================
    # OPEN TRADES
    # ========================================================

    def open_trades(
        self,
    ) -> List[Dict[str, Any]]:

        return [

            record

            for record
            in self.records

            if record.get(
                "status"
            ) == "OPEN"

        ]

    # ========================================================
    # CLOSED TRADES
    # ========================================================

    def closed_trades(
        self,
    ) -> List[Dict[str, Any]]:

        return [

            record

            for record
            in self.records

            if record.get(
                "status"
            ) == "CLOSED"

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

        if not closed:

            return {

                "total_trades":
                    0,

                "winning_trades":
                    0,

                "losing_trades":
                    0,

                "win_rate":
                    0.0,

                "gross_pnl":
                    0.0,

                "fees":
                    0.0,

                "net_pnl":
                    0.0,

                "average_trade":
                    0.0,

                "profit_factor":
                    None,

            }

        winners = []

        losers = []

        gross_profit = 0.0

        gross_loss = 0.0

        total_fees = 0.0

        net_pnl = 0.0

        for trade in closed:

            pnl = float(
                trade.get(
                    "net_pnl",
                    0.0,
                )
                or
                0.0
            )

            fees = float(
                trade.get(
                    "fees",
                    0.0,
                )
                or
                0.0
            )

            total_fees += fees

            net_pnl += pnl

            if pnl > 0:

                winners.append(
                    pnl
                )

                gross_profit += pnl

            elif pnl < 0:

                losers.append(
                    pnl
                )

                gross_loss += abs(
                    pnl
                )

        total_trades = len(
            closed
        )

        winning_trades = len(
            winners
        )

        losing_trades = len(
            losers
        )

        win_rate = (
            winning_trades
            / total_trades
            * 100.0
        )

        average_trade = (
            net_pnl
            / total_trades
        )

        if gross_loss > 0:

            profit_factor = (
                gross_profit
                / gross_loss
            )

        else:

            profit_factor = None

        return {

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

            "fees":
                total_fees,

            "net_pnl":
                net_pnl,

            "average_trade":
                average_trade,

            "profit_factor":
                profit_factor,

        }

    # ========================================================
    # FILTER BY SYMBOL
    # ========================================================

    def trades_by_symbol(
        self,
        symbol: str,
    ) -> List[Dict[str, Any]]:

        symbol = str(
            symbol
        ).upper()

        return [

            trade

            for trade
            in self.records

            if str(
                trade.get(
                    "symbol",
                    "",
                )
            ).upper()
            ==
            symbol

        ]

    # ========================================================
    # FILTER BY STRATEGY
    # ========================================================

    def trades_by_strategy(
        self,
        strategy: str,
    ) -> List[Dict[str, Any]]:

        target = str(
            strategy
        ).upper()

        return [

            trade

            for trade
            in self.records

            if str(
                trade.get(
                    "strategy",
                    "",
                )
            ).upper()
            ==
            target

        ]

    # ========================================================
    # STRATEGY PERFORMANCE
    # ========================================================

    def strategy_performance(
        self,
    ) -> Dict[str, Any]:

        strategies = {}

        for trade in (
            self.closed_trades()
        ):

            strategy = str(
                trade.get(
                    "strategy",
                    "UNKNOWN",
                )
            )

            strategies.setdefault(
                strategy,
                {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "net_pnl": 0.0,
                },
            )

            item = strategies[
                strategy
            ]

            item[
                "trades"
            ] += 1

            pnl = float(
                trade.get(
                    "net_pnl",
                    0.0,
                )
                or
                0.0
            )

            item[
                "net_pnl"
            ] += pnl

            if pnl > 0:

                item[
                    "wins"
                ] += 1

            elif pnl < 0:

                item[
                    "losses"
                ] += 1

        for strategy, item in (
            strategies.items()
        ):

            if item[
                "trades"
            ] > 0:

                item[
                    "win_rate"
                ] = round(

                    item[
                        "wins"
                    ]
                    /
                    item[
                        "trades"
                    ]
                    * 100.0,

                    2,

                )

            else:

                item[
                    "win_rate"
                ] = 0.0

        return strategies

    # ========================================================
    # EXPORT
    # ========================================================

    def export_json(
        self,
        path: str,
    ) -> Dict[str, Any]:

        export_path = Path(
            path
        )

        export_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:

            export_path.write_text(
                json.dumps(
                    self.records,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )

            return {

                "success":
                    True,

                "path":
                    str(
                        export_path
                    ),

            }

        except Exception as e:

            return {

                "success":
                    False,

                "message":
                    str(e),

            }


# ============================================================
# GLOBAL JOURNAL
# ============================================================

trading_journal = TradingJournal()


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS TRADING JOURNAL"
    )

    print(
        "=" * 60
    )

    # Use a temporary test journal so the
    # real journal is not polluted.

    test_path = (
        Path.home()
        / "Documents"
        / "JARVIS_Trading"
        / "journal_test.json"
    )

    journal = TradingJournal(
        path=str(
            test_path
        )
    )

    journal.records = []

    # --------------------------------------------------------
    # Create trade
    # --------------------------------------------------------

    result = journal.add_trade(

        symbol="NIFTY",

        market="INDIA",

        asset_type="INDEX",

        strategy="BULL_CALL_SPREAD",

        side="LONG",

        entry_price=24300.0,

        quantity=10,

        stop_loss=24100.0,

        target=24700.0,

        signal_score=82,

        confidence=74,

        risk_reward=2.0,

        market_regime="BULLISH",

        reasoning=[

            "Bullish trend.",

            "Positive momentum.",

            "Breakout confirmation.",

            "Defined-risk option structure.",

        ],

        risk_amount=2000.0,

        paper_or_live="PAPER",

    )

    print()

    print(
        "TRADE CREATED"
    )

    print(
        result
    )

    trade_id = result[
        "trade_id"
    ]

    # --------------------------------------------------------
    # Close trade
    # --------------------------------------------------------

    close_result = (
        journal.close_trade(

            trade_id=trade_id,

            exit_price=24700.0,

            fees=25.0,

            reason="TAKE_PROFIT",

        )
    )

    print()

    print(
        "TRADE CLOSED"
    )

    print(
        close_result
    )

    # --------------------------------------------------------
    # Performance
    # --------------------------------------------------------

    print()

    print(
        "PERFORMANCE"
    )

    print(
        journal.performance()
    )

    # --------------------------------------------------------
    # Strategy performance
    # --------------------------------------------------------

    print()

    print(
        "STRATEGY PERFORMANCE"
    )

    print(
        journal.strategy_performance()
    )

    print()

    print(
        "Journal path:"
    )

    print(
        journal.path
    )

    print()

    print(
        "Trading Journal loaded successfully."
    )