# ============================================================
# JARVIS OPTION TRADE JOURNAL ADAPTER
# V2
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional


class OptionTradeJournalAdapter:

    def __init__(self):
        self.journal = None
        self.load_error: Optional[str] = None

        try:
            from agents.trading_journal import trading_journal

            self.journal = trading_journal

        except Exception as exc:
            self.load_error = str(exc)

    # ========================================================
    # STATUS
    # ========================================================

    def available(self) -> bool:
        return self.journal is not None

    # ========================================================
    # NUMBER
    # ========================================================

    @staticmethod
    def number(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:
            if value is None:
                return default

            return float(value)

        except Exception:
            return default

    # ========================================================
    # RECORD OPEN
    # ========================================================

    def record_open(
        self,
        trade: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not self.available():

            return {
                "success": False,
                "message": (
                    "Trading journal unavailable."
                ),
            }

        add_trade = getattr(
            self.journal,
            "add_trade",
            None,
        )

        if not callable(add_trade):

            return {
                "success": False,
                "message": (
                    "Trading journal does not expose "
                    "add_trade()."
                ),
            }

        metadata = {

            "position_id":
                trade.get(
                    "trade_id"
                ),

            "execution_model":
                "BID_ASK_PAPER",

            "long_strike":
                trade.get(
                    "long_strike"
                ),

            "short_strike":
                trade.get(
                    "short_strike"
                ),

            "expiry":
                trade.get(
                    "expiry"
                ),

            "expiry_days":
                trade.get(
                    "expiry_days"
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
                trade.get(
                    "entry_debit"
                ),

            "target_1_debit":
                trade.get(
                    "target_1_debit"
                ),

            "target_2_debit":
                trade.get(
                    "target_2_debit"
                ),

            "stop_debit":
                trade.get(
                    "stop_debit"
                ),

            "entry_legs":
                trade.get(
                    "entry_legs",
                    [],
                ),

            "paper_or_live":
                "PAPER",

        }

        reasoning = trade.get(
            "reasoning",
            [
                (
                    "Option setup passed "
                    "paper execution gates."
                ),
                (
                    "Paper execution used "
                    "bid/ask fills."
                ),
            ],
        )

        try:

            result = add_trade(

                symbol=
                    str(
                        trade.get(
                            "symbol",
                            "",
                        )
                    ).upper(),

                market=
                    str(
                        trade.get(
                            "market",
                            "INDIA",
                        )
                    ).upper(),

                asset_type=
                    "OPTION",

                strategy=
                    trade.get(
                        "strategy",
                        "OPTION",
                    ),

                side=
                    trade.get(
                        "direction",
                        "LONG",
                    ),

                entry_price=
                    self.number(
                        trade.get(
                            "entry_debit"
                        )
                    ),

                quantity=
                    self.number(
                        trade.get(
                            "quantity"
                        )
                    ),

                stop_loss=
                    self.number(
                        trade.get(
                            "stop_debit"
                        )
                    ),

                target=
                    self.number(
                        trade.get(
                            "target_1_debit"
                        )
                    ),

                signal_score=
                    self.number(
                        trade.get(
                            "setup_strength"
                        )
                    ),

                confidence=
                    self.number(
                        trade.get(
                            "setup_strength"
                        )
                    ),

                risk_reward=
                    self.number(
                        trade.get(
                            "risk_reward"
                        )
                    ),

                market_regime=
                    trade.get(
                        "market_regime",
                        "OPTION_SETUP",
                    ),

                reasoning=
                    reasoning,

                risk_amount=
                    self.number(
                        trade.get(
                            "planned_risk"
                        )
                    ),

                paper_or_live=
                    "PAPER",

                metadata=
                    metadata,

            )

        except Exception as exc:

            return {
                "success": False,
                "message": (
                    "Trading journal add_trade() "
                    f"failed: {exc}"
                ),
            }

        if not isinstance(
            result,
            dict,
        ):

            return {
                "success": False,
                "message": (
                    "Trading journal returned "
                    "an unexpected result."
                ),
                "raw": result,
            }

        return {
            "success":
                bool(
                    result.get(
                        "success",
                        False,
                    )
                ),

            "trade_id":
                result.get(
                    "trade_id"
                ),

            "record":
                result.get(
                    "record"
                ),

            "raw":
                result,
        }

    # ========================================================
    # CLOSE
    # ========================================================

    def record_close(
        self,
        journal_trade_id: str,
        trade: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not self.available():

            return {
                "success": False,
                "message":
                    "Trading journal unavailable.",
            }

        close_trade = getattr(
            self.journal,
            "close_trade",
            None,
        )

        if not callable(close_trade):

            return {
                "success": False,
                "message": (
                    "Trading journal does not expose "
                    "close_trade()."
                ),
            }

        try:

            result = close_trade(

                trade_id=
                    journal_trade_id,

                exit_price=
                    self.number(
                        trade.get(
                            "exit_debit"
                        )
                    ),

                fees=
                    self.number(
                        trade.get(
                            "fees"
                        )
                    ),

                reason=
                    trade.get(
                        "reason",
                        "",
                    ),

            )

        except Exception as exc:

            return {
                "success": False,
                "message": (
                    "Trading journal close_trade() "
                    f"failed: {exc}"
                ),
            }

        if not isinstance(
            result,
            dict,
        ):

            return {
                "success": False,
                "message": (
                    "Trading journal returned "
                    "an unexpected close result."
                ),
                "raw": result,
            }

        return {

            "success":
                bool(
                    result.get(
                        "success",
                        False,
                    )
                ),

            "trade_id":
                journal_trade_id,

            "gross_pnl":
                result.get(
                    "gross_pnl"
                ),

            "net_pnl":
                result.get(
                    "net_pnl"
                ),

            "record":
                result.get(
                    "record"
                ),

            "raw":
                result,

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
                "success": False,
                "stage": "OPEN",
                "open_result": opened,
            }

        journal_trade_id = opened.get(
            "trade_id"
        )

        if not journal_trade_id:

            return {
                "success": False,
                "stage": "OPEN",
                "message": (
                    "Journal trade was created "
                    "without a trade_id."
                ),
                "open_result": opened,
            }

        closed = self.record_close(

            journal_trade_id=
                journal_trade_id,

            trade=
                trade,

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
                journal_trade_id,

            "open_result":
                opened,

            "close_result":
                closed,

        }


# ============================================================
# GLOBAL
# ============================================================

option_trade_journal_adapter = (
    OptionTradeJournalAdapter()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION TRADE JOURNAL ADAPTER V2"
    )

    print(
        "=" * 60
    )

    adapter = (
        option_trade_journal_adapter
    )

    print()

    print(
        "Journal available:",
        adapter.available(),
    )

    if adapter.load_error:

        print(
            "Load error:",
            adapter.load_error,
        )

    print()

    print(
        "Methods detected:"
    )

    if adapter.journal:

        print(
            [
                name
                for name
                in dir(
                    adapter.journal
                )
                if not name.startswith("_")
            ]
        )

    print()

    print(
        "Option Trade Journal Adapter V2 "
        "loaded successfully."
    )