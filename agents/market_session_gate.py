# ============================================================
# JARVIS MARKET SESSION GATE
# V1
# ============================================================
#
# Purpose:
#   Prevent JARVIS from treating stale/historical candles as
#   live intraday opportunities.
#
# Rules:
#   - Saturday/Sunday -> CLOSED
#   - Before 09:15 IST -> PRE_MARKET
#   - 09:15 through 15:30 IST -> OPEN
#   - After 15:30 IST -> CLOSED
#
# This is a session gate, not a holiday calendar.
# A future holiday calendar integration can be added later.
#
# PAPER / RESEARCH SAFE.
# ============================================================

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN = time(
    9,
    15,
)

MARKET_CLOSE = time(
    15,
    30,
)


class MarketSessionGate:

    def __init__(self) -> None:
        self.timezone = IST

    # ========================================================
    # NOW
    # ========================================================

    def now(self) -> datetime:

        return datetime.now(
            self.timezone
        )

    # ========================================================
    # SESSION
    # ========================================================

    def get_session(
        self,
        current_time: datetime | None = None,
    ) -> Dict[str, Any]:

        now = (
            current_time
            if current_time is not None
            else self.now()
        )

        if now.tzinfo is None:

            now = now.replace(
                tzinfo=IST
            )

        weekday = now.weekday()

        # Saturday / Sunday
        if weekday >= 5:

            return {
                "status": "CLOSED",
                "is_open": False,
                "is_trading_day": False,
                "reason": "Weekend.",
            }

        current = now.time()

        if current < MARKET_OPEN:

            return {
                "status": "PRE_MARKET",
                "is_open": False,
                "is_trading_day": True,
                "reason": (
                    "Before normal market open."
                ),
            }

        if current > MARKET_CLOSE:

            return {
                "status": "CLOSED",
                "is_open": False,
                "is_trading_day": True,
                "reason": (
                    "Normal market session has ended."
                ),
            }

        return {
            "status": "OPEN",
            "is_open": True,
            "is_trading_day": True,
            "reason": (
                "Normal market session is open."
            ),
        }

    # ========================================================
    # CANDLE FRESHNESS
    # ========================================================

    def candle_age_minutes(
        self,
        candle_timestamp: Any,
    ) -> float | None:

        if candle_timestamp is None:
            return None

        try:

            if isinstance(
                candle_timestamp,
                str,
            ):

                timestamp = (
                    datetime.fromisoformat(
                        candle_timestamp
                    )
                )

            else:

                timestamp = candle_timestamp

            if timestamp.tzinfo is None:

                timestamp = timestamp.replace(
                    tzinfo=IST
                )

            timestamp = timestamp.astimezone(
                IST
            )

            current = self.now()

            age = (
                current - timestamp
            ).total_seconds() / 60.0

            return max(
                0.0,
                age,
            )

        except Exception:

            return None

    # ========================================================
    # FRESHNESS LIMIT
    # ========================================================

    @staticmethod
    def freshness_limit(
        timeframe: str,
    ) -> float:

        timeframe = (
            str(timeframe)
            .strip()
            .lower()
        )

        if timeframe == "5m":
            return 8.0

        if timeframe == "15m":
            return 20.0

        if timeframe == "1m":
            return 3.0

        return 30.0

    # ========================================================
    # DATA STATUS
    # ========================================================

    def validate_intraday_data(
        self,
        timeframe_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        session = self.get_session()

        results = {}

        for timeframe in (
            "5m",
            "15m",
        ):

            item = timeframe_data.get(
                timeframe
            )

            if not isinstance(
                item,
                dict,
            ):

                results[timeframe] = {
                    "valid": False,
                    "reason": (
                        "Timeframe result missing."
                    ),
                }

                continue

            if not item.get(
                "success"
            ):

                results[timeframe] = {
                    "valid": False,
                    "reason": (
                        item.get(
                            "message",
                            "Data unavailable.",
                        )
                    ),
                }

                continue

            data = item.get(
                "data"
            )

            if data is None:

                results[timeframe] = {
                    "valid": False,
                    "reason": (
                        "No candle data."
                    ),
                }

                continue

            try:

                if len(data) == 0:

                    results[timeframe] = {
                        "valid": False,
                        "reason": (
                            "Empty candle data."
                        ),
                    }

                    continue

                last_timestamp = (
                    data.index[-1]
                )

                age = (
                    self.candle_age_minutes(
                        last_timestamp
                    )
                )

            except Exception as exc:

                results[timeframe] = {
                    "valid": False,
                    "reason": (
                        f"Unable to determine "
                        f"last candle: {exc}"
                    ),
                }

                continue

            if age is None:

                results[timeframe] = {
                    "valid": False,
                    "reason": (
                        "Candle timestamp invalid."
                    ),
                }

                continue

            limit = (
                self.freshness_limit(
                    timeframe
                )
            )

            fresh = (
                age <= limit
            )

            # Outside market hours, historical candles are
            # allowed for research, but NEVER for live setup.
            if session["status"] != "OPEN":

                results[timeframe] = {

                    "valid":
                        True,

                    "fresh":
                        False,

                    "age_minutes":
                        age,

                    "limit_minutes":
                        limit,

                    "reason":
                        (
                            "Market is not open; "
                            "candle freshness is "
                            "research-only."
                        ),

                }

            else:

                results[timeframe] = {

                    "valid":
                        fresh,

                    "fresh":
                        fresh,

                    "age_minutes":
                        age,

                    "limit_minutes":
                        limit,

                    "reason":
                        (
                            "Fresh intraday candle."
                            if fresh
                            else
                            (
                                f"Stale candle: "
                                f"{age:.1f} min old."
                            )
                        ),

                }

        all_fresh = all(
            results.get(
                tf,
                {}
            ).get(
                "fresh",
                False,
            )
            for tf in (
                "5m",
                "15m",
            )
        )

        live_allowed = (
            session["is_open"]
            and
            all_fresh
        )

        return {

            "success":
                True,

            "session":
                session,

            "timeframes":
                results,

            "all_fresh":
                all_fresh,

            "live_allowed":
                live_allowed,

            "reason":
                (
                    "Live intraday analysis allowed."
                    if live_allowed
                    else
                    (
                        "Live intraday analysis "
                        "blocked."
                    )
                ),

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_status(
        self,
        result: Dict[str, Any],
    ) -> str:

        session = result.get(
            "session",
            {}
        )

        lines = [

            "JARVIS MARKET SESSION",

            "--------------------------------------------------",

            f"Time IST: "
            f"{self.now().strftime('%Y-%m-%d %H:%M:%S')}",

            f"Session: "
            f"{session.get('status')}",

            f"Trading Day: "
            f"{session.get('is_trading_day')}",

            f"Market Open: "
            f"{session.get('is_open')}",

        ]

        for timeframe in (
            "5m",
            "15m",
        ):

            item = (
                result.get(
                    "timeframes",
                    {}
                )
                .get(
                    timeframe,
                    {}
                )
            )

            lines.append(

                f"{timeframe}: "
                f"valid={item.get('valid')} | "
                f"fresh={item.get('fresh')} | "
                f"age="
                f"{item.get('age_minutes')} min"

            )

        lines.extend(

            [

                "",

                f"Live Analysis Allowed: "
                f"{result.get('live_allowed')}",

                f"Reason: "
                f"{result.get('reason')}",

            ]

        )

        return "\n".join(
            lines
        )


market_session_gate = (
    MarketSessionGate()
)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS MARKET SESSION GATE V1"
    )

    print(
        "=" * 60
    )

    print()

    session = (
        market_session_gate
        .get_session()
    )

    print(
        "CURRENT SESSION"
    )

    print(
        session
    )

    print()

    print(
        "NOTE:"
    )

    print(
        "This gate blocks live intraday analysis "
        "outside the normal session."
    )

    print()

    print(
        "Market Session Gate V1 "
        "loaded successfully."
    )