# ============================================================
# JARVIS OPTION PAPER MONITOR
# V8
# ============================================================
#
# PURPOSE
#   - Monitor NIFTY and BANKNIFTY
#   - Use 15m as context
#   - Use 5m as trigger
#   - Use LIVE_INTRADAY_ROUTER during market hours
#   - Require a fresh live WebSocket tick
#   - Never treat historical candles as live
#   - Use option mission only after a qualified underlying setup
#   - Require confirmation
#   - Never place live orders
#
# MODES
#
#   HISTORICAL_PAPER_SCAN
#       Market closed.
#       Historical data may be displayed for research.
#       Setup generation disabled.
#
#   LIVE_SESSION_SCAN
#       Market open.
#       Live WebSocket connected.
#       Recent tick available.
#       Fresh 5m + 15m candles available.
#       Setup engine allowed.
#
#   LIVE_SESSION_BLOCKED
#       Market open but live data is unavailable/stale.
#
# PAPER ONLY.
# ============================================================

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import math
import time


# ============================================================
# CONFIGURATION
# ============================================================

WATCHLIST = [
    {
        "symbol": "NIFTY",
        "market": "india",
    },
    {
        "symbol": "BANKNIFTY",
        "market": "india",
    },
]

BARS = 500

MIN_SETUP_SCORE = 70.0
MIN_RISK_REWARD = 1.5

MAX_TRADES_PER_DAY = 3
MAX_DAILY_LOSS_PERCENT = 2.0

STARTING_CAPITAL = 1_000_000.0

PAPER_ONLY = True
CONFIRMATION_REQUIRED = True
AUTO_EXECUTION = False

SCAN_INTERVAL_SECONDS = 60

# When the monitor is running continuously, don't print the
# same WAIT result over and over.
PRINT_REPEATED_WAIT = False


# ============================================================
# MONITOR
# ============================================================

class OptionPaperMonitor:

    def __init__(
        self,
        capital: float = STARTING_CAPITAL,
    ) -> None:

        self.capital = float(
            capital
        )

        self.trade_count_today = 0

        self.daily_realized_pnl = 0.0

        self.last_scan: Dict[
            str,
            Dict[str, Any]
        ] = {}

        self._last_signature: Optional[
            str
        ] = None

    # ========================================================
    # BASIC HELPERS
    # ========================================================

    @staticmethod
    def now() -> str:

        return (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        )

    @staticmethod
    def number(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if value is None:

                return default

            result = float(
                value
            )

            if (
                math.isnan(result)
                or
                math.isinf(result)
            ):

                return default

            return result

        except Exception:

            return default

    # ========================================================
    # LOAD COMPONENTS
    # ========================================================

    @staticmethod
    def load_components() -> Dict[str, Any]:

        from agents.live_intraday_router import (
            live_intraday_router,
        )

        from agents.market_session_gate import (
            market_session_gate,
        )

        from agents.intraday_setup_engine import (
            intraday_setup_engine,
        )

        from agents.option_mission_engine import (
            option_mission_engine,
        )

        return {

            "router":
                live_intraday_router,

            "session":
                market_session_gate,

            "setup":
                intraday_setup_engine,

            "option_mission":
                option_mission_engine,

        }

    # ========================================================
    # RISK GATE
    # ========================================================

    def risk_gate(self) -> Dict[str, Any]:

        max_daily_loss = (
            self.capital
            *
            MAX_DAILY_LOSS_PERCENT
            /
            100.0
        )

        reasons = []

        if (
            self.trade_count_today
            >=
            MAX_TRADES_PER_DAY
        ):

            reasons.append(
                "Maximum daily trade count reached."
            )

        if (
            self.daily_realized_pnl
            <=
            -max_daily_loss
        ):

            reasons.append(
                "Maximum daily loss reached."
            )

        return {

            "approved":
                not reasons,

            "trade_count":
                self.trade_count_today,

            "daily_realized_pnl":
                self.daily_realized_pnl,

            "max_daily_loss":
                max_daily_loss,

            "reasons":
                reasons,

        }

    # ========================================================
    # MARKET STATUS
    # ========================================================

    def session(
        self,
        components: Dict[str, Any],
    ) -> Dict[str, Any]:

        gate = components[
            "session"
        ]

        try:

            return gate.get_session()

        except Exception as exc:

            return {

                "status":
                    "UNKNOWN",

                "is_open":
                    False,

                "is_trading_day":
                    False,

                "reason":
                    str(exc),

            }

    # ========================================================
    # HISTORICAL / LIVE DATA
    # ========================================================

    def get_data(
        self,
        components: Dict[str, Any],
        symbol: str,
        market: str,
    ) -> Dict[str, Any]:

        router = components[
            "router"
        ]

        try:

            result = (
                router.get_required_timeframes(

                    symbol=
                        symbol,

                    market=
                        market,

                    bars=
                        BARS,

                )
            )

        except Exception as exc:

            return {

                "success":
                    False,

                "mode":
                    "LIVE_SESSION_BLOCKED",

                "status":
                    "ROUTER_ERROR",

                "message":
                    str(exc),

            }

        if not isinstance(
            result,
            dict,
        ):

            return {

                "success":
                    False,

                "mode":
                    "LIVE_SESSION_BLOCKED",

                "status":
                    "INVALID_ROUTER_RESULT",

                "message":
                    (
                        "Live router returned "
                        "invalid data."
                    ),

            }

        return result

    # ========================================================
    # OPTION MISSION
    # ========================================================

    def build_option_mission(
        self,
        components: Dict[str, Any],
        setup: Dict[str, Any],
        symbol: str,
        market: str,
    ) -> Dict[str, Any]:

        if not setup.get(
            "success"
        ):

            return {

                "success":
                    False,

                "status":
                    "BLOCKED_SETUP",

                "reason":
                    setup.get(
                        "message",
                        "Setup engine failed.",
                    ),

            }

        if setup.get(
            "status"
        ) != "CANDIDATE":

            return {

                "success":
                    True,

                "status":
                    "WAIT",

                "reason":
                    setup.get(
                        "reason",
                        "Underlying setup is not a candidate.",
                    ),

            }

        setup_score = self.number(
            setup.get(
                "setup_score"
            )
        )

        risk_reward = self.number(
            setup.get(
                "risk_reward"
            )
        )

        if setup_score < MIN_SETUP_SCORE:

            return {

                "success":
                    True,

                "status":
                    "WAIT",

                "reason":
                    (
                        f"Setup score "
                        f"{setup_score:.2f} "
                        f"is below "
                        f"{MIN_SETUP_SCORE:.2f}."
                    ),

            }

        if risk_reward < MIN_RISK_REWARD:

            return {

                "success":
                    True,

                "status":
                    "WAIT",

                "reason":
                    (
                        f"Risk/reward "
                        f"{risk_reward:.2f} "
                        f"is below "
                        f"{MIN_RISK_REWARD:.2f}."
                    ),

            }

        risk = (
            self.risk_gate()
        )

        if not risk.get(
            "approved"
        ):

            return {

                "success":
                    True,

                "status":
                    "BLOCKED_RISK",

                "reason":
                    risk.get(
                        "reasons",
                        [],
                    ),

            }

        decision = str(
            setup.get(
                "decision",
                "",
            )
        ).upper()

        if decision == "LONG":

            direction = "BULLISH"

        elif decision == "SHORT":

            direction = "BEARISH"

        else:

            return {

                "success":
                    True,

                "status":
                    "WAIT",

                "reason":
                    "Underlying direction is undefined.",

            }

        underlying = {

            "symbol":
                symbol,

            "market":
                market,

            "direction":
                direction,

            "setup_strength":
                setup_score,

            "confidence":
                setup_score,

            "agreement":
                100.0,

            "quality":
                (
                    "A+"
                    if setup_score >= 90.0
                    else
                    "A"
                    if setup_score >= 80.0
                    else
                    "B"
                ),

            "entry":
                setup.get(
                    "entry"
                ),

            "stop_loss":
                setup.get(
                    "stop_loss"
                ),

            "target":
                setup.get(
                    "target"
                ),

            "risk_reward":
                risk_reward,

            "execution_ready":
                True,

            "paper_only":
                True,

            "confirmation_required":
                True,

        }

        engine = components[
            "option_mission"
        ]

        try:

            if hasattr(
                engine,
                "create_mission",
            ):

                result = (
                    engine.create_mission(

                        underlying_setup=
                            underlying,

                        symbol=
                            symbol,

                        market=
                            market,

                        capital=
                            self.capital,

                    )
                )

            elif hasattr(
                engine,
                "build_mission",
            ):

                result = (
                    engine.build_mission(
                        underlying
                    )
                )

            elif hasattr(
                engine,
                "run",
            ):

                result = (
                    engine.run(
                        underlying
                    )
                )

            else:

                return {

                    "success":
                        False,

                    "status":
                        "OPTION_ENGINE_API_MISSING",

                    "reason":
                        (
                            "No supported public "
                            "option mission API was found."
                        ),

                }

            if not isinstance(
                result,
                dict,
            ):

                return {

                    "success":
                        False,

                    "status":
                        "OPTION_MISSION_INVALID",

                    "reason":
                        (
                            "Option mission engine "
                            "returned a non-dict result."
                        ),

                }

            return result

        except Exception as exc:

            return {

                "success":
                    False,

                "status":
                    "OPTION_MISSION_ERROR",

                "message":
                    str(exc),

            }

    # ========================================================
    # HISTORICAL RESULT
    # ========================================================

    def historical_result(
        self,
        symbol: str,
        market: str,
        session: Dict[str, Any],
        router_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {

            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "scan_mode":
                "HISTORICAL_PAPER_SCAN",

            "status":
                "MARKET_CLOSED",

            "decision":
                "WAIT",

            "direction":
                "NEUTRAL",

            "setup_score":
                0.0,

            "risk_reward":
                0.0,

            "entry":
                None,

            "stop_loss":
                None,

            "target":
                None,

            "session":
                session,

            "router":
                router_result,

            "message":
                (
                    "Historical data is available "
                    "for research only. No live "
                    "setup was evaluated."
                ),

            "timestamp":
                self.now(),

        }

    # ========================================================
    # BLOCKED LIVE RESULT
    # ========================================================

    def blocked_live_result(
        self,
        symbol: str,
        market: str,
        session: Dict[str, Any],
        router_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {

            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "scan_mode":
                "LIVE_SESSION_BLOCKED",

            "status":
                router_result.get(
                    "status",
                    "LIVE_DATA_BLOCKED",
                ),

            "decision":
                "WAIT",

            "direction":
                "NEUTRAL",

            "setup_score":
                0.0,

            "risk_reward":
                0.0,

            "entry":
                None,

            "stop_loss":
                None,

            "target":
                None,

            "session":
                session,

            "router":
                router_result,

            "message":
                router_result.get(
                    "message",
                    (
                        "Live setup blocked "
                        "because current market "
                        "data is not trustworthy."
                    ),
                ),

            "timestamp":
                self.now(),

        }

    # ========================================================
    # LIVE ANALYSIS
    # ========================================================

    def analyze_live(
        self,
        components: Dict[str, Any],
        router_result: Dict[str, Any],
        symbol: str,
        market: str,
        session: Dict[str, Any],
    ) -> Dict[str, Any]:

        timeframe_data = (
            router_result.get(
                "timeframes",
                {}
            )
        )

        data_5m_item = (
            timeframe_data.get(
                "5m",
                {}
            )
        )

        data_15m_item = (
            timeframe_data.get(
                "15m",
                {}
            )
        )

        if not isinstance(
            data_5m_item,
            dict,
        ):

            return self.blocked_live_result(

                symbol,
                market,
                session,

                {

                    "status":
                        "MISSING_5M_DATA",

                    "message":
                        "Live 5m data missing.",

                },

            )

        if not isinstance(
            data_15m_item,
            dict,
        ):

            return self.blocked_live_result(

                symbol,
                market,
                session,

                {

                    "status":
                        "MISSING_15M_DATA",

                    "message":
                        "Live 15m data missing.",

                },

            )

        data_5m = (
            data_5m_item.get(
                "data"
            )
        )

        data_15m = (
            data_15m_item.get(
                "data"
            )
        )

        if data_5m is None:

            return self.blocked_live_result(

                symbol,
                market,
                session,

                {

                    "status":
                        "MISSING_5M_DATA",

                    "message":
                        "Live 5m dataframe missing.",

                },

            )

        if data_15m is None:

            return self.blocked_live_result(

                symbol,
                market,
                session,

                {

                    "status":
                        "MISSING_15M_DATA",

                    "message":
                        "Live 15m dataframe missing.",

                },

            )

        setup_engine = components[
            "setup"
        ]

        try:

            setup = (
                setup_engine.analyze(

                    data_15m=
                        data_15m,

                    data_5m=
                        data_5m,

                    symbol=
                        symbol,

                    market=
                        market.upper(),

                )
            )

        except Exception as exc:

            return {

                "success":
                    False,

                "symbol":
                    symbol,

                "market":
                    market,

                "scan_mode":
                    "LIVE_SESSION_SCAN",

                "status":
                    "SETUP_ENGINE_ERROR",

                "decision":
                    "WAIT",

                "direction":
                    "NEUTRAL",

                "setup_score":
                    0.0,

                "risk_reward":
                    0.0,

                "session":
                    session,

                "router":
                    router_result,

                "message":
                    str(exc),

                "timestamp":
                    self.now(),

            }

        # ----------------------------------------------------
        # No candidate.
        # ----------------------------------------------------

        if (
            not setup.get(
                "success"
            )
            or
            setup.get(
                "status"
            )
            !=
            "CANDIDATE"
        ):

            reason = setup.get(
                "reason"
            )

            if not reason:

                reason = (
                    "No qualified live setup."
                )

            return {

                "success":
                    bool(
                        setup.get(
                            "success",
                            False,
                        )
                    ),

                "symbol":
                    symbol,

                "market":
                    market,

                "scan_mode":
                    "LIVE_SESSION_SCAN",

                "status":
                    setup.get(
                        "status",
                        "WAIT",
                    ),

                "decision":
                    setup.get(
                        "decision",
                        "WAIT",
                    ),

                "direction":
                    setup.get(
                        "direction",
                        "NEUTRAL",
                    ),

                "setup_score":
                    self.number(
                        setup.get(
                            "setup_score"
                        )
                    ),

                "risk_reward":
                    self.number(
                        setup.get(
                            "risk_reward"
                        )
                    ),

                "entry":
                    setup.get(
                        "entry"
                    ),

                "stop_loss":
                    setup.get(
                        "stop_loss"
                    ),

                "target":
                    setup.get(
                        "target"
                    ),

                "session":
                    session,

                "router":
                    router_result,

                "setup":
                    setup,

                "reason":
                    reason,

                "timestamp":
                    self.now(),

            }

        # ----------------------------------------------------
        # Candidate → option mission.
        # ----------------------------------------------------

        mission = (
            self.build_option_mission(

                components,

                setup,

                symbol,

                market,

            )
        )

        return {

            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "scan_mode":
                "LIVE_SESSION_SCAN",

            "status":
                mission.get(
                    "status",
                    "WAIT",
                ),

            "decision":
                setup.get(
                    "decision",
                    "WAIT",
                ),

            "direction":
                setup.get(
                    "direction",
                    "NEUTRAL",
                ),

            "setup_score":
                self.number(
                    setup.get(
                        "setup_score"
                    )
                ),

            "risk_reward":
                self.number(
                    setup.get(
                        "risk_reward"
                    )
                ),

            "entry":
                setup.get(
                    "entry"
                ),

            "stop_loss":
                setup.get(
                    "stop_loss"
                ),

            "target":
                setup.get(
                    "target"
                ),

            "session":
                session,

            "router":
                router_result,

            "setup":
                setup,

            "mission":
                mission,

            "timestamp":
                self.now(),

        }

    # ========================================================
    # SCAN ONE SYMBOL
    # ========================================================

    def scan_symbol(
        self,
        components: Dict[str, Any],
        symbol: str,
        market: str,
    ) -> Dict[str, Any]:

        session = (
            self.session(
                components
            )
        )

        router_result = (
            self.get_data(

                components,

                symbol,

                market,

            )
        )

        if not router_result.get(
            "success"
        ):

            result = {

                "success":
                    False,

                "symbol":
                    symbol,

                "market":
                    market,

                "scan_mode":
                    (
                        "HISTORICAL_PAPER_SCAN"
                        if
                        not session.get(
                            "is_open"
                        )
                        else
                        "LIVE_SESSION_BLOCKED"
                    ),

                "status":
                    router_result.get(
                        "status",
                        "DATA_ERROR",
                    ),

                "decision":
                    "WAIT",

                "direction":
                    "NEUTRAL",

                "setup_score":
                    0.0,

                "risk_reward":
                    0.0,

                "session":
                    session,

                "router":
                    router_result,

                "message":
                    router_result.get(
                        "message",
                        "Data unavailable.",
                    ),

                "timestamp":
                    self.now(),

            }

            self.last_scan[
                symbol
            ] = result

            return result

        scan_mode = (
            router_result.get(
                "mode"
            )
        )

        # ----------------------------------------------------
        # Historical mode.
        # ----------------------------------------------------

        if scan_mode == (
            "HISTORICAL_PAPER_SCAN"
        ):

            result = (
                self.historical_result(

                    symbol,

                    market,

                    session,

                    router_result,

                )
            )

            self.last_scan[
                symbol
            ] = result

            return result

        # ----------------------------------------------------
        # Live mode must be explicit.
        # ----------------------------------------------------

        if scan_mode != (
            "LIVE_SESSION_SCAN"
        ):

            result = (
                self.blocked_live_result(

                    symbol,

                    market,

                    session,

                    router_result,

                )
            )

            self.last_scan[
                symbol
            ] = result

            return result

        # ----------------------------------------------------
        # Live setup evaluation.
        # ----------------------------------------------------

        result = (
            self.analyze_live(

                components,

                router_result,

                symbol,

                market,

                session,

            )
        )

        self.last_scan[
            symbol
        ] = result

        return result

    # ========================================================
    # FULL SCAN
    # ========================================================

    def scan(
        self,
    ) -> Dict[str, Any]:

        components = (
            self.load_components()
        )

        results = []

        for item in WATCHLIST:

            result = (
                self.scan_symbol(

                    components,

                    item[
                        "symbol"
                    ],

                    item[
                        "market"
                    ],

                )
            )

            results.append(
                result
            )

        candidates = [

            item

            for item
            in results

            if item.get(
                "status"
            )
            in {
                "CANDIDATE",
                "CONFIRMATION_READY",
            }

            and
            item.get(
                "scan_mode"
            )
            ==
            "LIVE_SESSION_SCAN"

        ]

        candidates.sort(

            key=lambda item:
                self.number(
                    item.get(
                        "setup_score"
                    )
                ),

            reverse=True,

        )

        confirmation_ready = [

            item

            for item
            in candidates

            if item.get(
                "status"
            )
            ==
            "CONFIRMATION_READY"

        ]

        best = (
            candidates[0]
            if candidates
            else None
        )

        scan_modes = sorted(
            set(
                item.get(
                    "scan_mode",
                    "UNKNOWN",
                )
                for item
                in results
            )
        )

        return {

            "success":
                True,

            "timestamp":
                self.now(),

            "scan_modes":
                scan_modes,

            "results":
                results,

            "candidates":
                candidates,

            "confirmation_ready":
                confirmation_ready,

            "best":
                best,

            "paper_only":
                PAPER_ONLY,

            "confirmation_required":
                CONFIRMATION_REQUIRED,

            "auto_execution":
                AUTO_EXECUTION,

        }

    # ========================================================
    # PAPER POSITIONS
    # ========================================================

    def open_positions(
        self,
    ) -> Dict[str, Any]:

        try:

            from agents.option_paper_execution_engine import (
                option_paper_execution_engine,
            )

            positions = (
                option_paper_execution_engine
                .open_positions()
            )

            if positions is None:

                positions = []

            return {

                "success":
                    True,

                "positions":
                    positions,

                "count":
                    len(
                        positions
                    ),

            }

        except Exception as exc:

            return {

                "success":
                    False,

                "positions":
                    [],

                "count":
                    0,

                "message":
                    str(exc),

            }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_scan(
        self,
        result: Dict[str, Any],
    ) -> str:

        lines = [

            "JARVIS OPTION PAPER MONITOR V8",

            "--------------------------------------------------",

            f"Timestamp: "
            f"{result.get('timestamp')}",

            "Data Router: LIVE_INTRADAY_ROUTER",

            "15m = CONTEXT | 5m = TRIGGER",

            "Paper Only: TRUE",

            "Confirmation Required: TRUE",

            "Auto Execution: FALSE",

            "",

        ]

        for item in result.get(
            "results",
            [],
        ):

            symbol = item.get(
                "symbol"
            )

            mode = item.get(
                "scan_mode",
                "UNKNOWN",
            )

            status = item.get(
                "status",
                "WAIT",
            )

            decision = item.get(
                "decision",
                "WAIT",
            )

            direction = item.get(
                "direction",
                "NEUTRAL",
            )

            score = self.number(
                item.get(
                    "setup_score"
                )
            )

            rr = self.number(
                item.get(
                    "risk_reward"
                )
            )

            lines.append(

                f"{symbol} | "
                f"Mode={mode} | "
                f"Status={status} | "
                f"Decision={decision} | "
                f"Direction={direction} | "
                f"Score={score:.1f} | "
                f"R/R={rr:.2f}"

            )

            # ------------------------------------------------
            # Historical mode.
            # ------------------------------------------------

            if mode == (
                "HISTORICAL_PAPER_SCAN"
            ):

                lines.append(
                    "  Historical research only. "
                    "No live setup evaluated."
                )

                continue

            # ------------------------------------------------
            # Blocked live mode.
            # ------------------------------------------------

            if mode == (
                "LIVE_SESSION_BLOCKED"
            ):

                lines.append(
                    "  LIVE ANALYSIS BLOCKED."
                )

                if item.get(
                    "message"
                ):

                    lines.append(
                        f"  Reason: "
                        f"{item.get('message')}"
                    )

                continue

            # ------------------------------------------------
            # Live scan.
            # ------------------------------------------------

            if item.get(
                "reason"
            ):

                reason = item.get(
                    "reason"
                )

                if isinstance(
                    reason,
                    list,
                ):

                    reason = "; ".join(
                        str(x)
                        for x
                        in reason
                    )

                lines.append(
                    f"  Reason: {reason}"
                )

            setup = item.get(
                "setup"
            )

            if not isinstance(
                setup,
                dict,
            ):

                continue

            context = setup.get(
                "context"
            )

            if isinstance(
                context,
                dict,
            ):

                lines.append(

                    f"  15m Context: "
                    f"{context.get('direction')} "
                    f"strength="
                    f"{self.number(context.get('strength')):.1f}"

                )

            trigger = setup.get(
                "trigger"
            )

            if isinstance(
                trigger,
                dict,
            ):

                lines.append(

                    f"  5m Trigger: "
                    f"{trigger.get('type', 'NONE')} "
                    f"{trigger.get('direction', 'NONE')}"

                )

        candidates = (
            result.get(
                "candidates",
                []
            )
        )

        confirmation = (
            result.get(
                "confirmation_ready",
                []
            )
        )

        lines.extend(

            [

                "",

                f"Live underlying candidates: "
                f"{len(candidates)}",

                f"Confirmation-ready option setups: "
                f"{len(confirmation)}",

            ]

        )

        best = result.get(
            "best"
        )

        if best:

            lines.extend(

                [

                    "",

                    "BEST LIVE SETUP",

                    f"Symbol: "
                    f"{best.get('symbol')}",

                    f"Direction: "
                    f"{best.get('direction')}",

                    f"Decision: "
                    f"{best.get('decision')}",

                    f"Score: "
                    f"{self.number(best.get('setup_score')):.1f}/100",

                    f"Entry: "
                    f"{self.number(best.get('entry')):.2f}",

                    f"Stop: "
                    f"{self.number(best.get('stop_loss')):.2f}",

                    f"Target: "
                    f"{self.number(best.get('target')):.2f}",

                    f"R/R: "
                    f"{self.number(best.get('risk_reward')):.2f}",

                    "Execution: "
                    "CONFIRMATION REQUIRED",

                ]

            )

        else:

            lines.append(
                "No qualified live setup."
            )

        lines.extend(

            [

                "",

                "PAPER ONLY — NO LIVE ORDER",

            ]

        )

        return "\n".join(
            lines
        )

    # ========================================================
    # RUN ONCE
    # ========================================================

    def run_once(
        self,
    ) -> Dict[str, Any]:

        result = self.scan()

        print(
            self.format_scan(
                result
            )
        )

        return result

    # ========================================================
    # SIGNATURE
    # ========================================================

    def build_signature(
        self,
        result: Dict[str, Any],
    ) -> str:

        parts = []

        for item in result.get(
            "results",
            [],
        ):

            parts.append(

                "|".join(
                    [

                        str(
                            item.get(
                                "symbol"
                            )
                        ),

                        str(
                            item.get(
                                "scan_mode"
                            )
                        ),

                        str(
                            item.get(
                                "status"
                            )
                        ),

                        str(
                            item.get(
                                "decision"
                            )
                        ),

                        f"{self.number(item.get('setup_score')):.1f}",

                    ]
                )

            )

        return "::".join(
            parts
        )

    # ========================================================
    # CONTINUOUS LOOP
    # ========================================================

    def run_loop(
        self,
        interval_seconds:
            int = SCAN_INTERVAL_SECONDS,
        iterations:
            Optional[int] = None,
    ) -> None:

        print(
            "=" * 60
        )

        print(
            "JARVIS OPTION PAPER MONITOR V8"
        )

        print(
            "=" * 60
        )

        print(
            "Data router: LIVE_INTRADAY_ROUTER"
        )

        print(
            "15m = CONTEXT"
        )

        print(
            "5m = TRIGGER"
        )

        print(
            "Paper only = TRUE"
        )

        print(
            "Confirmation required = TRUE"
        )

        print(
            "Auto execution = FALSE"
        )

        print()

        completed = 0

        previous_signature = None

        try:

            while True:

                result = (
                    self.scan()
                )

                signature = (
                    self.build_signature(
                        result
                    )
                )

                must_print = (

                    PRINT_REPEATED_WAIT

                    or

                    signature
                    !=
                    previous_signature

                    or

                    bool(
                        result.get(
                            "candidates"
                        )
                    )

                    or

                    bool(
                        result.get(
                            "confirmation_ready"
                        )
                    )

                )

                if must_print:

                    print()

                    print(
                        self.format_scan(
                            result
                        )
                    )

                    previous_signature = (
                        signature
                    )

                completed += 1

                if (
                    iterations is not None
                    and
                    completed
                    >=
                    iterations
                ):

                    break

                time.sleep(
                    max(
                        5,
                        int(
                            interval_seconds
                        ),
                    )
                )

        except KeyboardInterrupt:

            print()

            print(
                "JARVIS MONITOR > "
                "Stopped by user."
            )


# ============================================================
# GLOBAL INSTANCE
# ============================================================

option_paper_monitor = (
    OptionPaperMonitor()
)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION PAPER MONITOR V8"
    )

    print(
        "=" * 60
    )

    print(
        "Live-data watchdog: ENABLED"
    )

    print(
        "Historical/live separation: ENABLED"
    )

    print(
        "15m = CONTEXT"
    )

    print(
        "5m = TRIGGER"
    )

    print(
        "Confirmation required: TRUE"
    )

    print(
        "Auto execution: FALSE"
    )

    print()

    option_paper_monitor.run_once()

    print()

    print(
        "OPEN PAPER POSITIONS"
    )

    print(
        option_paper_monitor.open_positions()
    )

    print()

    print(
        "Option Paper Monitor V8 "
        "loaded successfully."
    )