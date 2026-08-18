# ============================================================
# JARVIS OPTION PAPER EXECUTION ENGINE
# V5
# ============================================================
#
# PAPER-ONLY multi-leg option execution engine.
#
# Supported:
#   LONG_CALL
#   LONG_PUT
#   BULL_CALL_SPREAD
#   BEAR_PUT_SPREAD
#
# Execution:
#   BUY  -> ASK
#   SELL -> BID
#
# Exit:
#   LONG  -> BID
#   SHORT -> ASK
#
# P&L:
#   Calculated from actual executable leg prices.
#
# Journal:
#   Uses agents.option_journal
#   The option execution engine is the authoritative
#   source for option P&L.
#
# NO LIVE ORDERS.
# ============================================================

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import math
import uuid


# ============================================================
# FILES
# ============================================================

BASE_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
)

POSITION_FILE = (
    BASE_PATH
    / "option_paper_positions_v5.json"
)

TRADE_FILE = (
    BASE_PATH
    / "option_paper_trades_v5.json"
)


# ============================================================
# ENGINE
# ============================================================

class OptionPaperExecutionEngine:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        fee_per_lot_round_trip: float = 40.0,
    ):

        self.starting_capital = float(
            starting_capital
        )

        self.fee_per_lot_round_trip = float(
            fee_per_lot_round_trip
        )

        self.positions: List[
            Dict[str, Any]
        ] = []

        self.trades: List[
            Dict[str, Any]
        ] = []

        BASE_PATH.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.load_state()

    # ========================================================
    # HELPERS
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

    @staticmethod
    def now() -> str:

        return datetime.now().isoformat(
            timespec="seconds"
        )

    @staticmethod
    def normalize_strategy(
        value: Any,
    ) -> str:

        return (
            str(value or "")
            .strip()
            .upper()
        )

    # ========================================================
    # STATE
    # ========================================================

    def load_state(self) -> None:

        if POSITION_FILE.exists():

            try:

                data = json.loads(
                    POSITION_FILE.read_text(
                        encoding="utf-8"
                    )
                )

                if isinstance(
                    data,
                    list,
                ):

                    self.positions = data

            except Exception:

                self.positions = []

        if TRADE_FILE.exists():

            try:

                data = json.loads(
                    TRADE_FILE.read_text(
                        encoding="utf-8"
                    )
                )

                if isinstance(
                    data,
                    list,
                ):

                    self.trades = data

            except Exception:

                self.trades = []

    def save_state(self) -> None:

        POSITION_FILE.write_text(

            json.dumps(
                self.positions,
                indent=2,
                default=str,
            ),

            encoding="utf-8",

        )

        TRADE_FILE.write_text(

            json.dumps(
                self.trades,
                indent=2,
                default=str,
            ),

            encoding="utf-8",

        )

    # ========================================================
    # POSITION LOOKUPS
    # ========================================================

    def open_positions(
        self,
    ) -> List[Dict[str, Any]]:

        return [

            position

            for position
            in self.positions

            if position.get(
                "status"
            )
            ==
            "OPEN"

        ]

    def find_position(
        self,
        position_id: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        for position in self.positions:

            if (
                position.get(
                    "position_id"
                )
                ==
                position_id
            ):

                return position

        return None

    # ========================================================
    # JOURNAL
    # ========================================================

    def journal_trade(
        self,
        trade: Dict[str, Any],
    ) -> Dict[str, Any]:

        try:

            from agents.option_journal import (
                option_journal,
            )

        except Exception as exc:

            return {

                "success":
                    False,

                "message":
                    (
                        "Option journal import failed: "
                        f"{exc}"
                    ),

            }

        try:

            return (
                option_journal
                .record_complete_trade(
                    trade
                )
            )

        except Exception as exc:

            return {

                "success":
                    False,

                "message":
                    (
                        "Option journal write failed: "
                        f"{exc}"
                    ),

            }

    # ========================================================
    # STRIKE
    # ========================================================

    @staticmethod
    def extract_strike(
        position: Dict[str, Any],
        position_side: str,
    ) -> Optional[float]:

        wanted = str(
            position_side
        ).upper()

        for leg in position.get(
            "legs",
            [],
        ):

            actual = str(
                leg.get(
                    "position_side",
                    ""
                )
            ).upper()

            if actual == wanted:

                try:

                    return float(
                        leg.get(
                            "strike"
                        )
                    )

                except Exception:

                    return None

        return None

    # ========================================================
    # QUOTE NORMALIZATION
    # ========================================================

    def normalize_quote(
        self,
        quote: Optional[
            Dict[str, Any]
        ],
        fallback_bid: float = 0.0,
        fallback_ask: float = 0.0,
    ) -> Dict[str, float]:

        quote = (
            quote
            if isinstance(
                quote,
                dict,
            )
            else {}
        )

        bid = self.number(
            quote.get(
                "bid"
            ),
            fallback_bid,
        )

        ask = self.number(
            quote.get(
                "ask"
            ),
            fallback_ask,
        )

        if bid <= 0 and ask > 0:
            bid = ask

        if ask <= 0 and bid > 0:
            ask = bid

        return {

            "bid":
                bid,

            "ask":
                ask,

        }

    # ========================================================
    # OPEN FROM MISSION
    # ========================================================

    def open_from_mission(
        self,
        mission: Dict[str, Any],
        entry_quotes: Optional[
            Dict[str, Dict[str, float]]
        ] = None,
    ) -> Dict[str, Any]:

        if not mission:

            return {

                "success":
                    False,

                "action":
                    "REJECTED",

                "message":
                    "Mission is empty.",

            }

        if mission.get(
            "status"
        ) != "CONFIRMATION_READY":

            return {

                "success":
                    False,

                "action":
                    "REJECTED",

                "message":
                    (
                        "Mission must be "
                        "CONFIRMATION_READY."
                    ),

            }

        execution = mission.get(
            "execution",
            {},
        )

        if execution.get(
            "live_order",
            False,
        ):

            return {

                "success":
                    False,

                "action":
                    "REJECTED",

                "message":
                    (
                        "Live orders are disabled "
                        "in the paper engine."
                    ),

            }

        symbol = (
            str(
                mission.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        market = (
            mission.get(
                "market",
                "INDIA",
            )
        )

        decision = mission.get(
            "option_decision",
            {},
        )

        plan = mission.get(
            "option_trade_plan",
            {},
        )

        strategy = (
            self.normalize_strategy(
                decision.get(
                    "decision"
                )
            )
        )

        supported = {

            "LONG_CALL",
            "LONG_PUT",
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",

        }

        if strategy not in supported:

            return {

                "success":
                    False,

                "action":
                    "REJECTED",

                "message":
                    (
                        f"Unsupported strategy: "
                        f"{strategy}"
                    ),

            }

        lots = int(
            self.number(
                plan.get(
                    "lots",
                    0,
                )
            )
        )

        quantity = int(
            self.number(
                plan.get(
                    "quantity",
                    0,
                )
            )
        )

        lot_size = int(
            self.number(
                plan.get(
                    "lot_size",
                    1,
                )
            )
        )

        if (
            lots <= 0
            or
            quantity <= 0
            or
            lot_size <= 0
        ):

            return {

                "success":
                    False,

                "action":
                    "REJECTED",

                "message":
                    (
                        "Invalid paper position size."
                    ),

            }

        # ----------------------------------------------------
        # Duplicate protection
        # ----------------------------------------------------

        for existing in (
            self.open_positions()
        ):

            if (

                existing.get(
                    "symbol"
                )
                ==
                symbol

                and

                existing.get(
                    "strategy"
                )
                ==
                strategy

            ):

                return {

                    "success":
                        False,

                    "action":
                        "REJECTED",

                    "message":
                        (
                            "Equivalent paper "
                            "position already exists."
                        ),

                    "position":
                        existing,

                }

        if not isinstance(
            entry_quotes,
            dict,
        ):

            entry_quotes = {}

        contract = decision.get(
            "contract",
            {},
        )

        legs: List[
            Dict[str, Any]
        ] = []

        # ====================================================
        # DEBIT SPREAD
        # ====================================================

        if strategy in {

            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",

        }:

            option_type = str(

                contract.get(
                    "option_type",
                    (
                        "CALL"
                        if
                        strategy
                        ==
                        "BULL_CALL_SPREAD"
                        else
                        "PUT"
                    ),
                )

            ).upper()

            long_strike = (
                self.number(
                    contract.get(
                        "long_strike"
                    )
                )
            )

            short_strike = (
                self.number(
                    contract.get(
                        "short_strike"
                    )
                )
            )

            fallback_long = (
                self.number(
                    contract.get(
                        "long_price"
                    )
                )
            )

            fallback_short = (
                self.number(
                    contract.get(
                        "short_price"
                    )
                )
            )

            long_quote = (
                self.normalize_quote(

                    entry_quotes.get(
                        "LONG"
                    ),

                    fallback_long,

                    fallback_long,

                )
            )

            short_quote = (
                self.normalize_quote(

                    entry_quotes.get(
                        "SHORT"
                    ),

                    fallback_short,

                    fallback_short,

                )
            )

            if (
                long_quote["ask"]
                <=
                0
                or
                short_quote["bid"]
                <=
                0
            ):

                return {

                    "success":
                        False,

                    "action":
                        "REJECTED",

                    "message":
                        (
                            "Invalid executable "
                            "entry quotes."
                        ),

                }

            legs.append({

                "leg_id":
                    str(
                        uuid.uuid4()
                    ),

                "side":
                    "BUY",

                "position_side":
                    "LONG",

                "option_type":
                    option_type,

                "strike":
                    long_strike,

                "quantity":
                    quantity,

                "entry_bid":
                    long_quote[
                        "bid"
                    ],

                "entry_ask":
                    long_quote[
                        "ask"
                    ],

                "entry_price":
                    long_quote[
                        "ask"
                    ],

                "current_bid":
                    long_quote[
                        "bid"
                    ],

                "current_ask":
                    long_quote[
                        "ask"
                    ],

                "current_price":
                    long_quote[
                        "ask"
                    ],

                "unrealized_pnl":
                    0.0,

            })

            legs.append({

                "leg_id":
                    str(
                        uuid.uuid4()
                    ),

                "side":
                    "SELL",

                "position_side":
                    "SHORT",

                "option_type":
                    option_type,

                "strike":
                    short_strike,

                "quantity":
                    quantity,

                "entry_bid":
                    short_quote[
                        "bid"
                    ],

                "entry_ask":
                    short_quote[
                        "ask"
                    ],

                "entry_price":
                    short_quote[
                        "bid"
                    ],

                "current_bid":
                    short_quote[
                        "bid"
                    ],

                "current_ask":
                    short_quote[
                        "ask"
                    ],

                "current_price":
                    short_quote[
                        "bid"
                    ],

                "unrealized_pnl":
                    0.0,

            })

            entry_debit = (

                long_quote[
                    "ask"
                ]

                -

                short_quote[
                    "bid"
                ]

            )

        # ====================================================
        # SINGLE LONG OPTION
        # ====================================================

        else:

            option_type = str(

                contract.get(
                    "option_type",
                    (
                        "CALL"
                        if
                        strategy
                        ==
                        "LONG_CALL"
                        else
                        "PUT"
                    ),
                )

            ).upper()

            strike = (
                self.number(
                    contract.get(
                        "strike"
                    )
                )
            )

            fallback_price = (
                self.number(

                    contract.get(
                        "price",
                        contract.get(
                            "premium"
                        ),
                    )

                )
            )

            quote = (
                self.normalize_quote(

                    entry_quotes.get(
                        "LONG"
                    ),

                    fallback_price,

                    fallback_price,

                )
            )

            if quote["ask"] <= 0:

                return {

                    "success":
                        False,

                    "action":
                        "REJECTED",

                    "message":
                        (
                            "Invalid option ask."
                        ),

                }

            legs.append({

                "leg_id":
                    str(
                        uuid.uuid4()
                    ),

                "side":
                    "BUY",

                "position_side":
                    "LONG",

                "option_type":
                    option_type,

                "strike":
                    strike,

                "quantity":
                    quantity,

                "entry_bid":
                    quote[
                        "bid"
                    ],

                "entry_ask":
                    quote[
                        "ask"
                    ],

                "entry_price":
                    quote[
                        "ask"
                    ],

                "current_bid":
                    quote[
                        "bid"
                    ],

                "current_ask":
                    quote[
                        "ask"
                    ],

                "current_price":
                    quote[
                        "ask"
                    ],

                "unrealized_pnl":
                    0.0,

            })

            entry_debit = (
                quote[
                    "ask"
                ]
            )

        if entry_debit <= 0:

            return {

                "success":
                    False,

                "action":
                    "REJECTED",

                "message":
                    (
                        "Entry debit must be positive."
                    ),

            }

        entry_fee = (

            lots

            *

            self.fee_per_lot_round_trip

            /

            2.0

        )

        position_id = (

            "OP-"

            +

            datetime.now().strftime(
                "%Y%m%d%H%M%S"
            )

            +

            "-"

            +

            str(
                uuid.uuid4()
            )[:8]

        )

        position = {

            "position_id":
                position_id,

            "status":
                "OPEN",

            "opened_at":
                self.now(),

            "updated_at":
                self.now(),

            "symbol":
                symbol,

            "market":
                market,

            "strategy":
                strategy,

            "direction":
                mission.get(
                    "underlying",
                    {},
                ).get(
                    "direction"
                ),

            "setup_strength":
                self.number(
                    mission.get(
                        "underlying",
                        {},
                    ).get(
                        "setup_strength"
                    )
                ),

            "quality":
                mission.get(
                    "underlying",
                    {},
                ).get(
                    "quality"
                ),

            "agreement":
                self.number(
                    mission.get(
                        "underlying",
                        {},
                    ).get(
                        "agreement"
                    )
                ),

            "expiry":
                mission.get(
                    "option_chain",
                    {},
                ).get(
                    "expiry"
                ),

            "expiry_days":
                mission.get(
                    "option_chain",
                    {},
                ).get(
                    "expiry_days"
                ),

            "lot_size":
                lot_size,

            "lots":
                lots,

            "quantity":
                quantity,

            "entry_debit":
                entry_debit,

            "current_debit":
                entry_debit,

            "stop_debit":
                self.number(
                    plan.get(
                        "stop_debit",
                        plan.get(
                            "stop_premium",
                            0.0,
                        ),
                    )
                ),

            "target_1_debit":
                self.number(
                    plan.get(
                        "target_1_debit",
                        plan.get(
                            "target_1_premium",
                            0.0,
                        ),
                    )
                ),

            "target_2_debit":
                self.number(
                    plan.get(
                        "target_2_debit",
                        plan.get(
                            "target_2_premium",
                            0.0,
                        ),
                    )
                ),

            "max_loss":
                self.number(
                    plan.get(
                        "max_loss",
                        0.0,
                    )
                ),

            "max_profit":
                self.number(
                    plan.get(
                        "max_profit",
                        0.0,
                    )
                ),

            "risk_reward":
                self.number(
                    plan.get(
                        "risk_reward_target_1",
                        plan.get(
                            "risk_reward_contract",
                            0.0,
                        ),
                    )
                ),

            "planned_risk":
                self.number(
                    plan.get(
                        "planned_risk",
                        0.0,
                    )
                ),

            "entry_fees":
                entry_fee,

            "exit_fees":
                0.0,

            "total_fees":
                entry_fee,

            "unrealized_pnl":
                0.0,

            "gross_pnl":
                None,

            "realized_pnl":
                None,

            "net_pnl":
                None,

            "close_reason":
                None,

            "trigger_level":
                None,

            "exit_debit":
                None,

            "actual_exit_debit":
                None,

            "legs":
                legs,

            "mission_id":
                mission.get(
                    "candidate_id",
                    mission.get(
                        "timestamp"
                    )
                ),

        }

        self.positions.append(
            position
        )

        self.save_state()

        return {

            "success":
                True,

            "action":
                "OPEN",

            "message":
                (
                    f"Opened paper "
                    f"{strategy} on {symbol}."
                ),

            "position":
                position,

        }

    # ========================================================
    # UPDATE POSITION
    # ========================================================

    def update_position(
        self,
        position_id: str,
        leg_quotes: Dict[
            str,
            Dict[str, float]
        ],
    ) -> Dict[str, Any]:

        position = (
            self.find_position(
                position_id
            )
        )

        if position is None:

            return {

                "success":
                    False,

                "action":
                    "NOT_FOUND",

                "message":
                    "Position not found.",

            }

        if position.get(
            "status"
        ) != "OPEN":

            return {

                "success":
                    False,

                "action":
                    "CLOSED",

                "message":
                    "Position is not open.",

            }

        if not isinstance(
            leg_quotes,
            dict,
        ):

            leg_quotes = {}

        net_current_value = 0.0
        net_entry_value = 0.0

        for leg in position.get(
            "legs",
            [],
        ):

            leg_id = leg.get(
                "leg_id"
            )

            quote = (
                self.normalize_quote(

                    leg_quotes.get(
                        leg_id
                    ),

                    self.number(
                        leg.get(
                            "current_bid"
                        )
                    ),

                    self.number(
                        leg.get(
                            "current_ask"
                        )
                    ),

                )
            )

            bid = quote["bid"]
            ask = quote["ask"]

            quantity = int(
                self.number(
                    leg.get(
                        "quantity"
                    )
                )
            )

            entry_price = self.number(
                leg.get(
                    "entry_price"
                )
            )

            leg[
                "current_bid"
            ] = bid

            leg[
                "current_ask"
            ] = ask

            # ------------------------------------------------
            # Executable liquidation mark:
            #
            # LONG -> sell at bid
            # SHORT -> buy at ask
            # ------------------------------------------------

            if (
                leg.get(
                    "position_side"
                )
                ==
                "LONG"
            ):

                mark = bid

                pnl = (

                    mark
                    -
                    entry_price

                ) * quantity

                net_current_value += (
                    mark
                    *
                    quantity
                )

                net_entry_value += (
                    entry_price
                    *
                    quantity
                )

            else:

                mark = ask

                pnl = (

                    entry_price
                    -
                    mark

                ) * quantity

                net_current_value -= (
                    mark
                    *
                    quantity
                )

                net_entry_value -= (
                    entry_price
                    *
                    quantity
                )

            leg[
                "current_price"
            ] = mark

            leg[
                "unrealized_pnl"
            ] = pnl

        quantity = int(
            self.number(
                position.get(
                    "quantity"
                )
            )
        )

        if quantity <= 0:

            return {

                "success":
                    False,

                "action":
                    "REJECTED",

                "message":
                    "Invalid quantity.",

            }

        current_debit = (
            net_current_value
            /
            quantity
        )

        unrealized_pnl = (
            net_current_value
            -
            net_entry_value
        )

        position[
            "current_debit"
        ] = current_debit

        position[
            "unrealized_pnl"
        ] = unrealized_pnl

        position[
            "updated_at"
        ] = self.now()

        stop = self.number(
            position.get(
                "stop_debit"
            )
        )

        target_1 = self.number(
            position.get(
                "target_1_debit"
            )
        )

        target_2 = self.number(
            position.get(
                "target_2_debit"
            )
        )

        reason = None
        trigger_level = None

        if (
            stop > 0
            and
            current_debit <= stop
        ):

            reason = (
                "STOP_LOSS"
            )

            trigger_level = stop

        elif (
            target_2 > 0
            and
            current_debit >= target_2
        ):

            reason = (
                "TARGET_2"
            )

            trigger_level = target_2

        elif (
            target_1 > 0
            and
            current_debit >= target_1
        ):

            reason = (
                "TARGET_1"
            )

            trigger_level = target_1

        self.save_state()

        if reason:

            return self.close_position(

                position_id=
                    position_id,

                exit_quotes=
                    leg_quotes,

                reason=
                    reason,

                trigger_level=
                    trigger_level,

            )

        return {

            "success":
                True,

            "action":
                "HOLD",

            "current_debit":
                current_debit,

            "unrealized_pnl":
                unrealized_pnl,

            "position":
                position,

        }

    # ========================================================
    # CLOSE POSITION
    # ========================================================

    def close_position(
        self,
        position_id: str,
        exit_quotes: Optional[
            Dict[str, Dict[str, float]]
        ] = None,
        reason: str = "MANUAL",
        trigger_level: Optional[float] = None,
    ) -> Dict[str, Any]:

        position = (
            self.find_position(
                position_id
            )
        )

        if position is None:

            return {

                "success":
                    False,

                "action":
                    "NOT_FOUND",

                "message":
                    "Position not found.",

            }

        if position.get(
            "status"
        ) != "OPEN":

            return {

                "success":
                    False,

                "action":
                    "ALREADY_CLOSED",

                "message":
                    "Position already closed.",

            }

        if not isinstance(
            exit_quotes,
            dict,
        ):

            exit_quotes = {}

        net_exit_value = 0.0

        exit_legs: List[
            Dict[str, Any]
        ] = []

        for leg in position.get(
            "legs",
            [],
        ):

            leg_id = leg.get(
                "leg_id"
            )

            quote = (
                self.normalize_quote(

                    exit_quotes.get(
                        leg_id
                    ),

                    self.number(
                        leg.get(
                            "current_bid"
                        )
                    ),

                    self.number(
                        leg.get(
                            "current_ask"
                        )
                    ),

                )
            )

            bid = quote["bid"]
            ask = quote["ask"]

            quantity = int(
                self.number(
                    leg.get(
                        "quantity"
                    )
                )
            )

            if (
                leg.get(
                    "position_side"
                )
                ==
                "LONG"
            ):

                exit_price = bid

                net_exit_value += (
                    exit_price
                    *
                    quantity
                )

            else:

                exit_price = ask

                net_exit_value -= (
                    exit_price
                    *
                    quantity
                )

            exit_legs.append({

                "leg_id":
                    leg_id,

                "strike":
                    leg.get(
                        "strike"
                    ),

                "side":
                    leg.get(
                        "side"
                    ),

                "position_side":
                    leg.get(
                        "position_side"
                    ),

                "option_type":
                    leg.get(
                        "option_type"
                    ),

                "quantity":
                    quantity,

                "bid":
                    bid,

                "ask":
                    ask,

                "exit_price":
                    exit_price,

            })

        quantity = int(
            self.number(
                position.get(
                    "quantity"
                )
            )
        )

        if quantity <= 0:

            return {

                "success":
                    False,

                "action":
                    "REJECTED",

                "message":
                    "Invalid position quantity.",

            }

        entry_debit = (
            self.number(
                position.get(
                    "entry_debit"
                )
            )
        )

        exit_debit = (
            net_exit_value
            /
            quantity
        )

        gross_pnl = (

            exit_debit
            -
            entry_debit

        ) * quantity

        lots = int(
            self.number(
                position.get(
                    "lots"
                )
            )
        )

        entry_fees = (
            self.number(
                position.get(
                    "entry_fees"
                )
            )
        )

        exit_fees = (

            lots
            *
            self.fee_per_lot_round_trip
            /
            2.0

        )

        total_fees = (
            entry_fees
            +
            exit_fees
        )

        # Bid/ask execution is already reflected in the
        # fill prices. Do not apply a second percentage
        # slippage penalty.

        slippage = 0.0

        net_pnl = (

            gross_pnl
            -
            total_fees

        )

        now = self.now()

        position[
            "status"
        ] = "CLOSED"

        position[
            "updated_at"
        ] = now

        position[
            "closed_at"
        ] = now

        position[
            "exit_debit"
        ] = exit_debit

        position[
            "actual_exit_debit"
        ] = exit_debit

        position[
            "trigger_level"
        ] = trigger_level

        position[
            "exit_legs"
        ] = exit_legs

        position[
            "gross_pnl"
        ] = gross_pnl

        position[
            "realized_pnl"
        ] = gross_pnl

        position[
            "net_pnl"
        ] = net_pnl

        position[
            "entry_fees"
        ] = entry_fees

        position[
            "exit_fees"
        ] = exit_fees

        position[
            "total_fees"
        ] = total_fees

        position[
            "slippage"
        ] = slippage

        position[
            "unrealized_pnl"
        ] = 0.0

        position[
            "close_reason"
        ] = reason

        trade = {

            "trade_id":
                position[
                    "position_id"
                ],

            "symbol":
                position[
                    "symbol"
                ],

            "market":
                position[
                    "market"
                ],

            "strategy":
                position[
                    "strategy"
                ],

            "direction":
                position[
                    "direction"
                ],

            "setup_strength":
                position[
                    "setup_strength"
                ],

            "quality":
                position[
                    "quality"
                ],

            "agreement":
                position[
                    "agreement"
                ],

            "expiry":
                position[
                    "expiry"
                ],

            "expiry_days":
                position[
                    "expiry_days"
                ],

            "lot_size":
                position[
                    "lot_size"
                ],

            "lots":
                lots,

            "quantity":
                quantity,

            "entry_debit":
                entry_debit,

            "exit_debit":
                exit_debit,

            "actual_exit_debit":
                exit_debit,

            "trigger_level":
                trigger_level,

            "stop_debit":
                position[
                    "stop_debit"
                ],

            "target_1_debit":
                position[
                    "target_1_debit"
                ],

            "target_2_debit":
                position[
                    "target_2_debit"
                ],

            "planned_risk":
                position[
                    "planned_risk"
                ],

            "risk_reward":
                position[
                    "risk_reward"
                ],

            "gross_pnl":
                gross_pnl,

            "fees":
                total_fees,

            "slippage":
                slippage,

            "net_pnl":
                net_pnl,

            "reason":
                reason,

            "long_strike":
                self.extract_strike(
                    position,
                    "LONG",
                ),

            "short_strike":
                self.extract_strike(
                    position,
                    "SHORT",
                ),

            "legs":
                position[
                    "legs"
                ],

            "entry_legs":
                [

                    {
                        "strike":
                            leg.get(
                                "strike"
                            ),

                        "side":
                            leg.get(
                                "side"
                            ),

                        "entry_price":
                            leg.get(
                                "entry_price"
                            ),

                        "entry_bid":
                            leg.get(
                                "entry_bid"
                            ),

                        "entry_ask":
                            leg.get(
                                "entry_ask"
                            ),

                    }

                    for leg
                    in position[
                        "legs"
                    ]

                ],

            "exit_legs":
                exit_legs,

            "opened_at":
                position[
                    "opened_at"
                ],

            "closed_at":
                now,

            "paper_or_live":
                "PAPER",

            "reasoning":
                [

                    (
                        "Option spread was "
                        "executed using "
                        "leg-by-leg bid/ask fills."
                    ),

                ],

        }

        self.trades.append(
            trade
        )

        self.save_state()

        # ----------------------------------------------------
        # Dedicated option journal.
        # ----------------------------------------------------

        journal_result = (
            self.journal_trade(
                trade
            )
        )

        trade[
            "journal_result"
        ] = journal_result

        self.save_state()

        return {

            "success":
                True,

            "action":
                "CLOSE",

            "message":
                (
                    f"Closed paper "
                    f"{position['symbol']} "
                    f"{position['strategy']}."
                ),

            "position":
                position,

            "trade":
                trade,

        }

    # ========================================================
    # ACCOUNT SNAPSHOT
    # ========================================================

    def account_snapshot(
        self,
    ) -> Dict[str, Any]:

        realized = sum(

            self.number(
                trade.get(
                    "net_pnl"
                )
            )

            for trade
            in self.trades

        )

        unrealized = sum(

            self.number(
                position.get(
                    "unrealized_pnl"
                )
            )

            for position
            in self.open_positions()

        )

        total = (
            realized
            +
            unrealized
        )

        return {

            "starting_capital":
                self.starting_capital,

            "equity":
                self.starting_capital
                +
                total,

            "realized_pnl":
                realized,

            "unrealized_pnl":
                unrealized,

            "total_pnl":
                total,

            "open_positions":
                len(
                    self.open_positions()
                ),

            "closed_trades":
                len(
                    self.trades
                ),

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_position(
        self,
        position: Dict[str, Any],
    ) -> str:

        lines: List[str] = []

        lines.append(
            "JARVIS OPTION PAPER POSITION V5"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: "
            f"{position.get('symbol')}"
        )

        lines.append(
            f"Strategy: "
            f"{position.get('strategy')}"
        )

        lines.append(
            f"Status: "
            f"{position.get('status')}"
        )

        lines.append(
            f"Lots: "
            f"{position.get('lots')}"
        )

        lines.append(
            f"Quantity: "
            f"{position.get('quantity')}"
        )

        lines.append("")

        lines.append(
            "LEGS"
        )

        for leg in position.get(
            "legs",
            [],
        ):

            lines.append(

                f"{leg.get('side')} "
                f"{leg.get('quantity')} "
                f"{leg.get('option_type')} "
                f"{leg.get('strike')} "
                f"entry={leg.get('entry_price')} "
                f"bid={leg.get('current_bid')} "
                f"ask={leg.get('current_ask')} "
                f"mark={leg.get('current_price')} "
                f"PnL="
                f"{self.number(leg.get('unrealized_pnl')):.2f}"

            )

        lines.append("")

        lines.append(
            f"Entry Debit: "
            f"{self.number(position.get('entry_debit')):.2f}"
        )

        lines.append(
            f"Current Debit: "
            f"{self.number(position.get('current_debit')):.2f}"
        )

        lines.append(
            f"Stop Debit: "
            f"{self.number(position.get('stop_debit')):.2f}"
        )

        lines.append(
            f"Target 1: "
            f"{self.number(position.get('target_1_debit')):.2f}"
        )

        lines.append(
            f"Target 2: "
            f"{self.number(position.get('target_2_debit')):.2f}"
        )

        lines.append(
            f"Unrealized P&L: "
            f"{self.number(position.get('unrealized_pnl')):.2f}"
        )

        if (
            position.get(
                "status"
            )
            ==
            "CLOSED"
        ):

            lines.append("")

            lines.append(
                f"Trigger Level: "
                f"{self.number(position.get('trigger_level')):.2f}"
            )

            lines.append(
                f"Actual Exit Debit: "
                f"{self.number(position.get('actual_exit_debit')):.2f}"
            )

            lines.append(
                f"Gross P&L: "
                f"{self.number(position.get('gross_pnl')):.2f}"
            )

            lines.append(
                f"Fees: "
                f"{self.number(position.get('total_fees')):.2f}"
            )

            lines.append(
                f"Net P&L: "
                f"{self.number(position.get('net_pnl')):.2f}"
            )

            lines.append(
                f"Reason: "
                f"{position.get('close_reason')}"
            )

        lines.append("")

        lines.append(
            "PAPER ONLY — NO LIVE ORDER"
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL INSTANCE
# ============================================================

option_paper_execution_engine = (
    OptionPaperExecutionEngine()
)


# ============================================================
# CLEAN UNIT TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION PAPER EXECUTION ENGINE V5"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # Test mission
    # --------------------------------------------------------

    synthetic_mission = {

        "status":
            "CONFIRMATION_READY",

        "symbol":
            "NIFTY",

        "market":
            "INDIA",

        "candidate_id":
            "TEST-OPTION-V5",

        "timestamp":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "underlying":
            {

                "direction":
                    "BULLISH",

                "setup_strength":
                    86.0,

                "quality":
                    "A",

                "agreement":
                    100.0,

            },

        "option_chain":
            {

                "expiry":
                    "TEST",

                "expiry_days":
                    20,

            },

        "option_decision":
            {

                "decision":
                    "BULL_CALL_SPREAD",

                "contract":
                    {

                        "option_type":
                            "CALL",

                        "long_strike":
                            24200,

                        "short_strike":
                            24400,

                        "long_price":
                            330.0,

                        "short_price":
                            299.4,

                    },

            },

        "option_trade_plan":
            {

                "lot_size":
                    25,

                "lots":
                    2,

                "quantity":
                    50,

                "entry_debit":
                    30.60,

                "stop_debit":
                    15.30,

                "target_1_debit":
                    84.70,

                "target_2_debit":
                    135.52,

                "max_profit":
                    169.40,

                "max_loss":
                    30.60,

                "risk_reward_target_1":
                    3.54,

                "planned_risk":
                    841.50,

            },

        "execution":
            {

                "mode":
                    "PAPER",

                "confirmation_required":
                    True,

                "live_order":
                    False,

            },

    }

    # --------------------------------------------------------
    # Entry:
    #
    # BUY 24200 CE @ ask 331
    # SELL 24400 CE @ bid 298
    #
    # Actual entry debit = 33
    # --------------------------------------------------------

    entry_quotes = {

        "LONG":
            {

                "bid":
                    330.50,

                "ask":
                    331.00,

            },

        "SHORT":
            {

                "bid":
                    298.00,

                "ask":
                    299.00,

            },

    }

    opened = (
        option_paper_execution_engine
        .open_from_mission(

            mission=
                synthetic_mission,

            entry_quotes=
                entry_quotes,

        )
    )

    print()

    print(
        opened
    )

    if opened.get(
        "success"
    ):

        position = (
            opened[
                "position"
            ]
        )

        print()

        print(
            option_paper_execution_engine
            .format_position(
                position
            )
        )

        legs = (
            position[
                "legs"
            ]
        )

        # ----------------------------------------------------
        # Exit:
        #
        # LONG leg sells at bid = 380
        # SHORT leg buys at ask = 281
        #
        # Exit debit = 99
        #
        # Gross P&L:
        #   (99 - 33) * 50
        #   = 3300
        #
        # Fees:
        #   2 lots * 40
        #   = 80
        #
        # Net:
        #   3220
        # ----------------------------------------------------

        exit_quotes = {

            legs[0][
                "leg_id"
            ]:
                {

                    "bid":
                        380.00,

                    "ask":
                        381.00,

                },

            legs[1][
                "leg_id"
            ]:
                {

                    "bid":
                        280.00,

                    "ask":
                        281.00,

                },

        }

        update = (
            option_paper_execution_engine
            .update_position(

                position_id=
                    position[
                        "position_id"
                    ],

                leg_quotes=
                    exit_quotes,

            )
        )

        print()

        print(
            "MARKET UPDATE"
        )

        print(
            update
        )

        final_position = (
            option_paper_execution_engine
            .find_position(
                position[
                    "position_id"
                ]
            )
        )

        if final_position:

            print()

            print(
                option_paper_execution_engine
                .format_position(
                    final_position
                )
            )

    print()

    print(
        "ACCOUNT SNAPSHOT"
    )

    print(
        option_paper_execution_engine
        .account_snapshot()
    )

    print()

    print(
        f"Position file: "
        f"{POSITION_FILE}"
    )

    print(
        f"Trade file: "
        f"{TRADE_FILE}"
    )

    print()

    print(
        "Option Paper Execution Engine V5 "
        "loaded successfully."
    )