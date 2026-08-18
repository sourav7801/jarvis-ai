# ============================================================
# JARVIS PAPER MONITOR
# V1
# ============================================================
#
# Purpose:
#   Continuously monitor paper signals and paper positions.
#
# Architecture:
#
#   Market Data
#        ↓
#   Paper Signal Engine
#        ↓
#   Paper Position Engine
#        ↓
#   Monitoring / P&L
#
# IMPORTANT:
#   PAPER TRADING ONLY.
#   NO LIVE ORDERS.
#
# Supports:
#   NIFTY
#   BANKNIFTY
#   SENSEX
#   Stocks
#
# Timeframes:
#   15m
#   1h
#   4h
#   1d
#
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import time
import json
import threading

from agents.market_data_agent import get_market_data
from agents.paper_signal_engine import (
    paper_signal_engine,
)
from agents.paper_position_engine import (
    paper_position_engine,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_WATCHLIST = [

    {
        "symbol": "NIFTY",
        "market": "india",
        "timeframe": "1d",
        "strategy": "MEAN_REVERSION",
        "bars": 500,
    },

    {
        "symbol": "BANKNIFTY",
        "market": "india",
        "timeframe": "1d",
        "strategy": "MEAN_REVERSION",
        "bars": 500,
    },

    {
        "symbol": "SENSEX",
        "market": "india",
        "timeframe": "1d",
        "strategy": "MEAN_REVERSION",
        "bars": 500,
    },

]


# ============================================================
# FILES
# ============================================================

BASE_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
)

MONITOR_LOG_PATH = (
    BASE_PATH
    / "paper_monitor_log.json"
)


# ============================================================
# MONITOR
# ============================================================

class PaperMonitor:

    def __init__(
        self,
        watchlist: Optional[
            List[Dict[str, Any]]
        ] = None,
        interval_seconds: int = 60,
    ):

        self.watchlist = (
            watchlist
            if watchlist is not None
            else list(
                DEFAULT_WATCHLIST
            )
        )

        self.interval_seconds = int(
            interval_seconds
        )

        self.running = False

        self._stop_event = (
            threading.Event()
        )

        BASE_PATH.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ========================================================
    # LOAD LOG
    # ========================================================

    def load_log(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        if not MONITOR_LOG_PATH.exists():

            return []

        try:

            content = (
                MONITOR_LOG_PATH.read_text(
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

        except Exception:

            return []

    # ========================================================
    # SAVE LOG
    # ========================================================

    def save_log(
        self,
        records: List[
            Dict[str, Any]
        ],
    ) -> bool:

        try:

            MONITOR_LOG_PATH.write_text(

                json.dumps(
                    records,
                    indent=2,
                    default=str,
                ),

                encoding="utf-8",

            )

            return True

        except Exception as exc:

            print(
                "JARVIS MONITOR DEBUG > "
                f"Could not save log: {exc}"
            )

            return False

    # ========================================================
    # LOG EVENT
    # ========================================================

    def log_event(
        self,
        event: Dict[str, Any],
    ):

        records = (
            self.load_log()
        )

        records.append(
            event
        )

        # Keep the file manageable.

        if len(records) > 5000:

            records = (
                records[-5000:]
            )

        self.save_log(
            records
        )

    # ========================================================
    # GET MARKET PRICE
    # ========================================================

    def get_current_price(
        self,
        symbol: str,
        market: str,
        timeframe: str,
        bars: int,
    ) -> Optional[
        float
    ]:

        result = (
            get_market_data(

                symbol=symbol,

                market=market,

                timeframe=timeframe,

                bars=bars,

            )
        )

        if not result.get(
            "success",
            False,
        ):

            print(
                "JARVIS MONITOR > "
                f"Data unavailable for {symbol}."
            )

            return None

        data = result.get(
            "data"
        )

        if data is None or data.empty:

            return None

        try:

            return float(
                data.iloc[-1]["close"]
            )

        except Exception:

            return None

    # ========================================================
    # MONITOR OPEN POSITIONS
    # ========================================================

    def update_open_positions(
        self,
        price_map: Dict[
            str,
            float
        ],
    ) -> Dict[str, Any]:

        if not price_map:

            return {

                "success":
                    True,

                "actions":
                    [],

            }

        result = (
            paper_position_engine.update_all(
                price_map
            )
        )

        self.log_event({

            "timestamp":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "type":
                "POSITION_UPDATE",

            "prices":
                price_map,

            "result":
                result,

        })

        return result

    # ========================================================
    # FIND EXISTING POSITION
    # ========================================================

    def has_open_position(
        self,
        symbol: str,
        strategy: str,
        timeframe: str,
    ) -> bool:

        positions = (
            paper_position_engine
            .open_positions()
        )

        for position in positions:

            if (
                str(
                    position.get(
                        "symbol",
                        "",
                    )
                )
                .upper()
                ==
                str(
                    symbol
                )
                .upper()
                and
                str(
                    position.get(
                        "strategy",
                        "",
                    )
                )
                .upper()
                ==
                str(
                    strategy
                )
                .upper()
                and
                str(
                    position.get(
                        "timeframe",
                        "",
                    )
                )
                .lower()
                ==
                str(
                    timeframe
                )
                .lower()
            ):

                return True

        return False

    # ========================================================
    # SCAN ONE
    # ========================================================

    def scan_one(
        self,
        item: Dict[str, Any],
    ) -> Dict[str, Any]:

        symbol = str(
            item.get(
                "symbol",
                "",
            )
        ).upper()

        market = str(
            item.get(
                "market",
                "india",
            )
        ).lower()

        timeframe = str(
            item.get(
                "timeframe",
                "1d",
            )
        ).lower()

        strategy = str(
            item.get(
                "strategy",
                "MEAN_REVERSION",
            )
        ).upper()

        bars = int(
            item.get(
                "bars",
                500,
            )
        )

        print(
            f"JARVIS MONITOR > "
            f"Scanning {strategy} | "
            f"{symbol} | "
            f"{timeframe}"
        )

        # ----------------------------------------------------
        # Market data
        # ----------------------------------------------------

        market_data = (
            get_market_data(

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

            result = {

                "success":
                    False,

                "action":
                    "ERROR",

                "symbol":
                    symbol,

                "message":
                    market_data.get(
                        "message",
                        "Market data failed.",
                    ),

            }

            self.log_event({

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

                "type":
                    "SCAN_ERROR",

                "result":
                    result,

            })

            return result

        data = market_data.get(
            "data"
        )

        if data is None or data.empty:

            return {

                "success":
                    False,

                "action":
                    "ERROR",

                "symbol":
                    symbol,

                "message":
                    "No market data returned.",

            }

        try:

            current_price = float(
                data.iloc[-1]["close"]
            )

        except Exception:

            return {

                "success":
                    False,

                "action":
                    "ERROR",

                "symbol":
                    symbol,

                "message":
                    "Current price unavailable.",

            }

        # ----------------------------------------------------
        # Existing position?
        # ----------------------------------------------------

        if self.has_open_position(

            symbol=symbol,

            strategy=strategy,

            timeframe=timeframe,

        ):

            result = {

                "success":
                    True,

                "action":
                    "HOLD_POSITION",

                "symbol":
                    symbol,

                "price":
                    current_price,

                "message":
                    (
                        "Open paper position already exists."
                    ),

            }

            self.log_event({

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

                "type":
                    "HOLD_EXISTING_POSITION",

                "result":
                    result,

            })

            return result

        # ----------------------------------------------------
        # Create paper signal
        # ----------------------------------------------------

        signal = (
            paper_signal_engine.create_signal(

                df=data,

                strategy=strategy,

                symbol=symbol,

                market=market,

                timeframe=timeframe,

                capital=(
                    paper_position_engine
                    .account_snapshot()
                    .get(
                        "equity",
                        1_000_000.0,
                    )
                ),

                metadata={

                    "monitor":
                        "PAPER_MONITOR",

                    "scan_time":
                        datetime.now().isoformat(
                            timespec="seconds"
                        ),

                },

            )
        )

        if not signal.get(
            "success",
            False,
        ):

            self.log_event({

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

                "type":
                    "SIGNAL_ERROR",

                "symbol":
                    symbol,

                "result":
                    signal,

            })

            return signal

        # ----------------------------------------------------
        # WAIT
        # ----------------------------------------------------

        if signal.get(
            "action"
        ) != "BUY" and signal.get(
            "action"
        ) != "SELL":

            result = {

                "success":
                    True,

                "action":
                    "WAIT",

                "symbol":
                    symbol,

                "price":
                    current_price,

                "signal":
                    signal,

            }

            print(
                f"JARVIS MONITOR > "
                f"{symbol}: WAIT"
            )

            self.log_event({

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

                "type":
                    "SIGNAL_WAIT",

                "result":
                    result,

            })

            return result

        # ----------------------------------------------------
        # OPEN PAPER POSITION
        # ----------------------------------------------------

        opened = (
            paper_position_engine.open_position(

                signal=signal,

                current_price=
                    current_price,

            )
        )

        result = {

            "success":
                opened.get(
                    "success",
                    False,
                ),

            "action":
                (
                    "PAPER_OPENED"
                    if opened.get(
                        "success",
                        False,
                    )
                    else
                    "OPEN_REJECTED"
                ),

            "symbol":
                symbol,

            "price":
                current_price,

            "signal":
                signal,

            "position":
                opened.get(
                    "position"
                ),

            "message":
                opened.get(
                    "message"
                ),

        }

        self.log_event({

            "timestamp":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "type":
                "PAPER_POSITION_OPEN",

            "result":
                result,

        })

        return result

    # ========================================================
    # RUN ONE CYCLE
    # ========================================================

    def run_cycle(
        self,
    ) -> Dict[str, Any]:

        started_at = (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        )

        price_map: Dict[
            str,
            float
        ] = {}

        scan_results = []

        # ----------------------------------------------------
        # First get prices for existing positions.
        # ----------------------------------------------------

        open_positions = (
            paper_position_engine
            .open_positions()
        )

        for position in open_positions:

            symbol = str(
                position.get(
                    "symbol",
                    "",
                )
            ).upper()

            if not symbol:

                continue

            # Find a matching watchlist item.

            matching_item = None

            for item in self.watchlist:

                if (
                    str(
                        item.get(
                            "symbol",
                            "",
                        )
                    ).upper()
                    ==
                    symbol
                ):

                    matching_item = item

                    break

            if matching_item is None:

                continue

            current_price = (
                self.get_current_price(

                    symbol=symbol,

                    market=str(
                        matching_item.get(
                            "market",
                            "india",
                        )
                    ),

                    timeframe=str(
                        matching_item.get(
                            "timeframe",
                            "1d",
                        )
                    ),

                    bars=int(
                        matching_item.get(
                            "bars",
                            500,
                        )
                    ),

                )
            )

            if current_price is not None:

                price_map[
                    symbol
                ] = current_price

        # ----------------------------------------------------
        # Update positions.
        # ----------------------------------------------------

        position_update = (
            self.update_open_positions(
                price_map
            )
        )

        # ----------------------------------------------------
        # Scan watchlist.
        # ----------------------------------------------------

        for item in self.watchlist:

            try:

                result = (
                    self.scan_one(
                        item
                    )
                )

            except Exception as exc:

                result = {

                    "success":
                        False,

                    "action":
                        "ERROR",

                    "message":
                        str(exc),

                    "item":
                        item,

                }

            scan_results.append(
                result
            )

        snapshot = (
            paper_position_engine
            .account_snapshot()
        )

        cycle = {

            "success":
                True,

            "started_at":
                started_at,

            "finished_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "position_update":
                position_update,

            "scans":
                scan_results,

            "account":
                snapshot,

        }

        self.log_event({

            "timestamp":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "type":
                "MONITOR_CYCLE",

            "cycle":
                cycle,

        })

        return cycle

    # ========================================================
    # FORMAT CYCLE
    # ========================================================

    def format_cycle(
        self,
        cycle: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS PAPER MONITOR"
        )

        lines.append(
            "--------------------------------------------------"
        )

        scans = cycle.get(
            "scans",
            []
        )

        for result in scans:

            symbol = result.get(
                "symbol",
                "UNKNOWN",
            )

            action = result.get(
                "action",
                "UNKNOWN",
            )

            price = result.get(
                "price"
            )

            if price is None:

                lines.append(
                    f"{symbol}: {action}"
                )

            else:

                lines.append(

                    f"{symbol}: "
                    f"{action} | "
                    f"Price={price}"

                )

            message = result.get(
                "message"
            )

            if message:

                lines.append(
                    f"  {message}"
                )

        account = cycle.get(
            "account",
            {}
        )

        lines.append("")

        lines.append(
            f"Equity: "
            f"{account.get('equity', 0):,.2f}"
        )

        lines.append(
            f"Realized P&L: "
            f"{account.get('realized_pnl', 0):,.2f}"
        )

        lines.append(
            f"Unrealized P&L: "
            f"{account.get('unrealized_pnl', 0):,.2f}"
        )

        lines.append(
            f"Open Positions: "
            f"{account.get('open_positions', 0)}"
        )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Paper monitoring only. "
            "No live orders."
        )

        return "\n".join(
            lines
        )

    # ========================================================
    # START CONTINUOUS MONITOR
    # ========================================================

    def start(
        self,
    ):

        if self.running:

            print(
                "JARVIS MONITOR > "
                "Already running."
            )

            return

        self.running = True

        self._stop_event.clear()

        print(
            "=" * 60
        )

        print(
            "JARVIS PAPER MONITOR STARTED"
        )

        print(
            "=" * 60
        )

        print(
            "Press Ctrl+C to stop."
        )

        print()

        try:

            while not (
                self._stop_event.is_set()
            ):

                cycle = (
                    self.run_cycle()
                )

                print()

                print(
                    self.format_cycle(
                        cycle
                    )
                )

                print()

                print(
                    f"Next scan in "
                    f"{self.interval_seconds} seconds..."
                )

                print()

                self._stop_event.wait(
                    self.interval_seconds
                )

        except KeyboardInterrupt:

            print()

            print(
                "JARVIS MONITOR > "
                "Stopping..."
            )

        finally:

            self.running = False

            print(
                "JARVIS MONITOR > "
                "Stopped."
            )

    # ========================================================
    # STOP
    # ========================================================

    def stop(
        self,
    ):

        self._stop_event.set()

        self.running = False


# ============================================================
# GLOBAL
# ============================================================

paper_monitor = (
    PaperMonitor()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS PAPER MONITOR"
    )

    print(
        "=" * 60
    )

    print()

    cycle = (
        paper_monitor.run_cycle()
    )

    print()

    print(
        paper_monitor.format_cycle(
            cycle
        )
    )

    print()

    print(
        f"Monitor log: "
        f"{MONITOR_LOG_PATH}"
    )

    print()

    print(
        "Paper Monitor loaded successfully."
    )