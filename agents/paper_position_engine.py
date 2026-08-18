# ============================================================
# JARVIS PAPER POSITION ENGINE
# V1
# ============================================================
#
# Purpose:
#   Manage paper-trading positions created by the
#   Paper Signal Engine.
#
# Handles:
#   - Opening paper positions
#   - Updating market prices
#   - Stop loss
#   - Take profit
#   - Manual close
#   - P&L
#   - Fees
#   - Position persistence
#   - Trade history
#
# IMPORTANT:
#   PAPER ONLY.
#   NO LIVE ORDERS.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json
import uuid


# ============================================================
# PATHS
# ============================================================

BASE_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
)

POSITION_PATH = (
    BASE_PATH
    / "paper_positions.json"
)

PAPER_TRADE_PATH = (
    BASE_PATH
    / "paper_trades.json"
)


# ============================================================
# ENGINE
# ============================================================

class PaperPositionEngine:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        fee_per_side: float = 20.0,
    ):

        self.starting_capital = float(
            starting_capital
        )

        self.fee_per_side = float(
            fee_per_side
        )

        BASE_PATH.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ========================================================
    # LOAD POSITIONS
    # ========================================================

    def load_positions(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        if not POSITION_PATH.exists():

            return []

        try:

            content = (
                POSITION_PATH.read_text(
                    encoding="utf-8"
                )
            )

            if not content.strip():

                return []

            data = json.loads(
                content
            )

            if isinstance(
                data,
                list,
            ):

                return data

            return []

        except Exception as exc:

            print(
                "JARVIS PAPER POSITION DEBUG > "
                f"Could not load positions: {exc}"
            )

            return []

    # ========================================================
    # SAVE POSITIONS
    # ========================================================

    def save_positions(
        self,
        positions: List[
            Dict[str, Any]
        ],
    ) -> bool:

        try:

            POSITION_PATH.write_text(

                json.dumps(
                    positions,
                    indent=2,
                    default=str,
                ),

                encoding="utf-8",

            )

            return True

        except Exception as exc:

            print(
                "JARVIS PAPER POSITION DEBUG > "
                f"Could not save positions: {exc}"
            )

            return False

    # ========================================================
    # LOAD TRADES
    # ========================================================

    def load_trades(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        if not PAPER_TRADE_PATH.exists():

            return []

        try:

            content = (
                PAPER_TRADE_PATH.read_text(
                    encoding="utf-8"
                )
            )

            if not content.strip():

                return []

            data = json.loads(
                content
            )

            if isinstance(
                data,
                list,
            ):

                return data

            return []

        except Exception as exc:

            print(
                "JARVIS PAPER POSITION DEBUG > "
                f"Could not load trades: {exc}"
            )

            return []

    # ========================================================
    # SAVE TRADES
    # ========================================================

    def save_trades(
        self,
        trades: List[
            Dict[str, Any]
        ],
    ) -> bool:

        try:

            PAPER_TRADE_PATH.write_text(

                json.dumps(
                    trades,
                    indent=2,
                    default=str,
                ),

                encoding="utf-8",

            )

            return True

        except Exception as exc:

            print(
                "JARVIS PAPER POSITION DEBUG > "
                f"Could not save trades: {exc}"
            )

            return False

    # ========================================================
    # OPEN POSITION
    # ========================================================

    def open_position(
        self,
        signal: Dict[str, Any],
        current_price: Optional[
            float
        ] = None,
    ) -> Dict[str, Any]:

        if not signal:

            return {

                "success":
                    False,

                "message":
                    "No paper signal supplied.",

            }

        if signal.get(
            "action"
        ) not in {
            "BUY",
            "SELL",
        }:

            return {

                "success":
                    False,

                "message":
                    "Signal is not executable.",

            }

        record = signal.get(
            "record"
        )

        if not record:

            return {

                "success":
                    False,

                "message":
                    "Paper signal record is missing.",

            }

        positions = (
            self.load_positions()
        )

        # ----------------------------------------------------
        # Prevent duplicate position for same strategy/symbol
        # ----------------------------------------------------

        for existing in positions:

            if (
                existing.get(
                    "status"
                )
                ==
                "OPEN"
                and
                existing.get(
                    "symbol"
                )
                ==
                record.get(
                    "symbol"
                )
                and
                existing.get(
                    "strategy"
                )
                ==
                record.get(
                    "strategy"
                )
                and
                existing.get(
                    "timeframe"
                )
                ==
                record.get(
                    "timeframe"
                )
            ):

                return {

                    "success":
                        False,

                    "message":
                        (
                            "An open paper position already "
                            "exists for this strategy/symbol/timeframe."
                        ),

                    "position":
                        existing,

                }

        action = (
            record.get(
                "action"
            )
        )

        side = (
            "LONG"
            if action == "BUY"
            else "SHORT"
        )

        entry_price = float(
            record.get(
                "entry"
            )
        )

        quantity = float(
            record.get(
                "quantity",
                0.0,
            )
        )

        stop_loss = float(
            record.get(
                "stop_loss"
            )
        )

        target = float(
            record.get(
                "target"
            )
        )

        market_price = (
            entry_price
            if current_price is None
            else float(current_price)
        )

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        position_id = (
            "PP-"
            +
            datetime.now().strftime(
                "%Y%m%d%H%M%S"
            )
            +
            "-"
            +
            uuid.uuid4().hex[:8]
        )

        position = {

            "position_id":
                position_id,

            "status":
                "OPEN",

            "opened_at":
                now,

            "updated_at":
                now,

            "strategy":
                record.get(
                    "strategy"
                ),

            "symbol":
                record.get(
                    "symbol"
                ),

            "market":
                record.get(
                    "market"
                ),

            "timeframe":
                record.get(
                    "timeframe"
                ),

            "side":
                side,

            "entry_price":
                entry_price,

            "current_price":
                market_price,

            "quantity":
                quantity,

            "stop_loss":
                stop_loss,

            "target":
                target,

            "risk_reward":
                record.get(
                    "risk_reward"
                ),

            "initial_risk":
                (
                    abs(
                        entry_price
                        -
                        stop_loss
                    )
                    *
                    quantity
                ),

            "unrealized_pnl":
                0.0,

            "realized_pnl":
                None,

            "fees":
                self.fee_per_side,

            "paper_or_live":
                "PAPER",

            "source_signal_id":
                record.get(
                    "signal_id"
                ),

            "metadata":
                record.get(
                    "metadata",
                    {},
                ),

        }

        positions.append(
            position
        )

        saved = (
            self.save_positions(
                positions
            )
        )

        if not saved:

            return {

                "success":
                    False,

                "message":
                    "Could not persist paper position.",

            }

        return {

            "success":
                True,

            "action":
                "OPEN",

            "message":
                (
                    f"Opened paper {side} "
                    f"{quantity} "
                    f"{record.get('symbol')} "
                    f"at {entry_price:.2f}."
                ),

            "position":
                position,

        }

    # ========================================================
    # UPDATE ONE POSITION
    # ========================================================

    def update_position(
        self,
        position: Dict[str, Any],
        market_price: float,
    ) -> Dict[str, Any]:

        price = float(
            market_price
        )

        entry = float(
            position[
                "entry_price"
            ]
        )

        quantity = float(
            position[
                "quantity"
            ]
        )

        stop_loss = float(
            position[
                "stop_loss"
            ]
        )

        target = float(
            position[
                "target"
            ]
        )

        side = (
            position[
                "side"
            ]
        )

        if side == "LONG":

            unrealized = (
                price
                -
                entry
            ) * quantity

            stop_hit = (
                price
                <=
                stop_loss
            )

            target_hit = (
                price
                >=
                target
            )

        else:

            unrealized = (
                entry
                -
                price
            ) * quantity

            stop_hit = (
                price
                >=
                stop_loss
            )

            target_hit = (
                price
                <=
                target
            )

        position[
            "current_price"
        ] = price

        position[
            "updated_at"
        ] = datetime.now().isoformat(
            timespec="seconds"
        )

        position[
            "unrealized_pnl"
        ] = unrealized

        if stop_hit:

            return {

                "action":
                    "CLOSE",

                "reason":
                    "STOP_LOSS",

                "price":
                    price,

                "position":
                    position,

            }

        if target_hit:

            return {

                "action":
                    "CLOSE",

                "reason":
                    "TAKE_PROFIT",

                "price":
                    price,

                "position":
                    position,

            }

        return {

            "action":
                "HOLD",

            "reason":
                "POSITION_ACTIVE",

            "price":
                price,

            "position":
                position,

        }

    # ========================================================
    # CLOSE POSITION
    # ========================================================

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "MANUAL",
    ) -> Dict[str, Any]:

        positions = (
            self.load_positions()
        )

        position = None

        position_index = None

        for index, item in enumerate(
            positions
        ):

            if (
                item.get(
                    "position_id"
                )
                ==
                position_id
            ):

                position = item

                position_index = index

                break

        if position is None:

            return {

                "success":
                    False,

                "message":
                    (
                        f"Position not found: "
                        f"{position_id}"
                    ),

            }

        if (
            position.get(
                "status"
            )
            !=
            "OPEN"
        ):

            return {

                "success":
                    False,

                "message":
                    "Position is already closed.",

            }

        exit_price = float(
            exit_price
        )

        entry_price = float(
            position[
                "entry_price"
            ]
        )

        quantity = float(
            position[
                "quantity"
            ]
        )

        side = (
            position[
                "side"
            ]
        )

        if side == "LONG":

            gross_pnl = (
                exit_price
                -
                entry_price
            ) * quantity

        else:

            gross_pnl = (
                entry_price
                -
                exit_price
            ) * quantity

        entry_fee = float(
            position.get(
                "fees",
                self.fee_per_side,
            )
        )

        exit_fee = float(
            self.fee_per_side
        )

        total_fees = (
            entry_fee
            +
            exit_fee
        )

        net_pnl = (
            gross_pnl
            -
            total_fees
        )

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        position[
            "status"
        ] = "CLOSED"

        position[
            "closed_at"
        ] = now

        position[
            "updated_at"
        ] = now

        position[
            "exit_price"
        ] = exit_price

        position[
            "current_price"
        ] = exit_price

        position[
            "gross_pnl"
        ] = gross_pnl

        position[
            "realized_pnl"
        ] = gross_pnl

        position[
            "fees"
        ] = total_fees

        position[
            "net_pnl"
        ] = net_pnl

        position[
            "close_reason"
        ] = reason

        position[
            "unrealized_pnl"
        ] = 0.0

        if (
            position_index
            is not None
        ):

            positions[
                position_index
            ] = position

        saved_positions = (
            self.save_positions(
                positions
            )
        )

        if not saved_positions:

            return {

                "success":
                    False,

                "message":
                    "Could not update position storage.",

            }

        trades = (
            self.load_trades()
        )

        trades.append({

            "trade_id":
                "PT-"
                +
                uuid.uuid4().hex[:12],

            "position_id":
                position[
                    "position_id"
                ],

            "strategy":
                position[
                    "strategy"
                ],

            "symbol":
                position[
                    "symbol"
                ],

            "market":
                position[
                    "market"
                ],

            "timeframe":
                position[
                    "timeframe"
                ],

            "side":
                side,

            "entry_price":
                entry_price,

            "exit_price":
                exit_price,

            "quantity":
                quantity,

            "gross_pnl":
                gross_pnl,

            "fees":
                total_fees,

            "net_pnl":
                net_pnl,

            "reason":
                reason,

            "opened_at":
                position[
                    "opened_at"
                ],

            "closed_at":
                now,

            "paper_or_live":
                "PAPER",

        })

        saved_trades = (
            self.save_trades(
                trades
            )
        )

        if not saved_trades:

            return {

                "success":
                    False,

                "message":
                    "Position closed but trade journal save failed.",

                "position":
                    position,

            }

        return {

            "success":
                True,

            "action":
                "CLOSE",

            "message":
                (
                    f"Closed paper "
                    f"{position['symbol']}. "
                    f"Net P&L: "
                    f"{net_pnl:.2f}"
                ),

            "position":
                position,

        }

    # ========================================================
    # UPDATE ALL POSITIONS
    # ========================================================

    def update_all(
        self,
        prices: Dict[
            str,
            float
        ],
    ) -> Dict[str, Any]:

        positions = (
            self.load_positions()
        )

        actions = []

        for position in positions:

            if (
                position.get(
                    "status"
                )
                !=
                "OPEN"
            ):

                continue

            symbol = (
                str(
                    position.get(
                        "symbol",
                        "",
                    )
                )
                .upper()
            )

            if symbol not in prices:

                continue

            market_price = float(
                prices[
                    symbol
                ]
            )

            result = (
                self.update_position(

                    position=position,

                    market_price=
                        market_price,

                )
            )

            if (
                result.get(
                    "action"
                )
                ==
                "CLOSE"
            ):

                close_result = (
                    self.close_position(

                        position_id=
                            position[
                                "position_id"
                            ],

                        exit_price=
                            result[
                                "price"
                            ],

                        reason=
                            result[
                                "reason"
                            ],

                    )
                )

                actions.append(
                    close_result
                )

            else:

                actions.append(
                    result
                )

        # Persist updated current prices.

        latest_positions = (
            self.load_positions()
        )

        for position in latest_positions:

            if (
                position.get(
                    "status"
                )
                !=
                "OPEN"
            ):

                continue

            symbol = (
                str(
                    position.get(
                        "symbol",
                        "",
                    )
                )
                .upper()
            )

            if symbol not in prices:

                continue

            price = float(
                prices[
                    symbol
                ]
            )

            side = position[
                "side"
            ]

            entry = float(
                position[
                    "entry_price"
                ]
            )

            quantity = float(
                position[
                    "quantity"
                ]
            )

            if side == "LONG":

                pnl = (
                    price
                    -
                    entry
                ) * quantity

            else:

                pnl = (
                    entry
                    -
                    price
                ) * quantity

            position[
                "current_price"
            ] = price

            position[
                "unrealized_pnl"
            ] = pnl

            position[
                "updated_at"
            ] = datetime.now().isoformat(
                timespec="seconds"
            )

        self.save_positions(
            latest_positions
        )

        return {

            "success":
                True,

            "actions":
                actions,

        }

    # ========================================================
    # OPEN POSITIONS
    # ========================================================

    def open_positions(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        positions = (
            self.load_positions()
        )

        return [

            item

            for item
            in positions

            if item.get(
                "status"
            )
            ==
            "OPEN"

        ]

    # ========================================================
    # ACCOUNT SNAPSHOT
    # ========================================================

    def account_snapshot(
        self,
    ) -> Dict[str, Any]:

        positions = (
            self.open_positions()
        )

        trades = (
            self.load_trades()
        )

        unrealized = sum(

            float(
                item.get(
                    "unrealized_pnl",
                    0.0,
                )
            )

            for item
            in positions

        )

        realized = sum(

            float(
                item.get(
                    "net_pnl",
                    0.0,
                )
            )

            for item
            in trades

        )

        equity = (
            self.starting_capital
            +
            realized
            +
            unrealized
        )

        return {

            "starting_capital":
                self.starting_capital,

            "equity":
                equity,

            "realized_pnl":
                realized,

            "unrealized_pnl":
                unrealized,

            "total_pnl":
                realized
                +
                unrealized,

            "open_positions":
                len(
                    positions
                ),

            "closed_trades":
                len(
                    trades
                ),

        }

    # ========================================================
    # FORMAT SNAPSHOT
    # ========================================================

    def format_snapshot(
        self,
        snapshot: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS PAPER POSITION ENGINE"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Starting Capital: "
            f"{snapshot.get('starting_capital', 0):,.2f}"
        )

        lines.append(
            f"Equity: "
            f"{snapshot.get('equity', 0):,.2f}"
        )

        lines.append(
            f"Realized P&L: "
            f"{snapshot.get('realized_pnl', 0):,.2f}"
        )

        lines.append(
            f"Unrealized P&L: "
            f"{snapshot.get('unrealized_pnl', 0):,.2f}"
        )

        lines.append(
            f"Total P&L: "
            f"{snapshot.get('total_pnl', 0):,.2f}"
        )

        lines.append(
            f"Open Positions: "
            f"{snapshot.get('open_positions', 0)}"
        )

        lines.append(
            f"Closed Trades: "
            f"{snapshot.get('closed_trades', 0)}"
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

paper_position_engine = (
    PaperPositionEngine()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS PAPER POSITION ENGINE"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # Standalone paper-position test.
    #
    # This test DOES NOT use real market data and DOES NOT
    # submit anything to a broker.
    # --------------------------------------------------------

    test_signal = {

        "action":
            "BUY",

        "record": {

            "signal_id":
                "TEST-SIGNAL",

            "strategy":
                "MEAN_REVERSION",

            "symbol":
                "TEST",

            "market":
                "TEST",

            "timeframe":
                "1d",

            "action":
                "BUY",

            "entry":
                100.0,

            "stop_loss":
                95.0,

            "target":
                110.0,

            "risk_reward":
                2.0,

            "quantity":
                10.0,

            "metadata":
                {},

        },

    }

    opened = (
        paper_position_engine.open_position(
            test_signal,
            current_price=100.0,
        )
    )

    print()

    print(
        "OPEN"
    )

    print(
        opened
    )

    if opened.get(
        "success",
        False,
    ):

        position_id = (
            opened[
                "position"
            ][
                "position_id"
            ]
        )

        updated = (
            paper_position_engine.update_position(

                opened[
                    "position"
                ],

                107.0,

            )
        )

        print()

        print(
            "PRICE UPDATE"
        )

        print(
            updated
        )

        closed = (
            paper_position_engine.close_position(

                position_id=
                    position_id,

                exit_price=
                    110.0,

                reason=
                    "TAKE_PROFIT",

            )
        )

        print()

        print(
            "CLOSE"
        )

        print(
            closed
        )

    print()

    print(
        paper_position_engine.format_snapshot(

            paper_position_engine.account_snapshot()

        )
    )

    print()

    print(
        "Positions:"
    )

    print(
        paper_position_engine.open_positions()
    )

    print()

    print(
        f"Position file: {POSITION_PATH}"
    )

    print(
        f"Trade file: {PAPER_TRADE_PATH}"
    )

    print()

    print(
        "Paper Position Engine loaded successfully."
    )