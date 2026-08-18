# ============================================================
# JARVIS TRADING MISSION AGENT
# V3
# ============================================================
#
# High-level trading mission controller.
#
# Example:
#
#   Jarvis scan NIFTY and BANKNIFTY
#   on 5 minute and 15 minute
#
#   Jarvis watch NIFTY and BANKNIFTY all day
#
#   Jarvis find the best trade
#
#   Jarvis execute
#
# Pipeline:
#
#   MARKET DATA
#       ↓
#   TIMEFRAME DATA GATE
#       ↓
#   TECHNICAL / PATTERN / REGIME
#       ↓
#   MULTI-TIMEFRAME SETUP SCORE
#       ↓
#   RESEARCH EDGE
#       ↓
#   TRADE PLAN
#       ↓
#   VERIFIER
#       ↓
#   VERIFIED SETUP
#       ↓
#   PAPER / CONFIRMATION
#
# IMPORTANT
# ----------
# This module does not place live broker orders.
#
# AUTO EXECUTION remains disabled by default.
#
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import threading


# ============================================================
# PATHS
# ============================================================

BASE_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
)

MISSION_FILE = (
    BASE_PATH
    / "trading_mission_v3.json"
)

MISSION_LOG_FILE = (
    BASE_PATH
    / "trading_mission_v3_log.json"
)


# ============================================================
# DEFAULTS
# ============================================================

DEFAULT_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
]

DEFAULT_TIMEFRAMES = [
    "5m",
    "15m",
]

DEFAULT_BARS = {
    "5m": 500,
    "15m": 500,
    "1h": 500,
    "4h": 500,
    "1d": 500,
}

DEFAULT_MAX_TRADES_PER_DAY = 3

DEFAULT_MAX_DAILY_LOSS_PERCENT = 2.0

DEFAULT_MIN_SETUP_SCORE = 75.0

DEFAULT_MIN_SETUP_STRENGTH = 70.0

DEFAULT_MIN_AGREEMENT = 70.0

DEFAULT_MIN_RISK_REWARD = 1.5

AUTO_EXECUTION = False


# ============================================================
# SYMBOL REGISTRY
# ============================================================

@dataclass
class SymbolConfig:

    symbol: str
    market: str
    asset_type: str = "INDEX"


# ============================================================
# MISSION CONFIG
# ============================================================

@dataclass
class MissionConfig:

    symbols: List[str]

    timeframes: List[str]

    all_day: bool = False

    auto_execution: bool = False

    max_trades_per_day: int = 3

    max_daily_loss_percent: float = 2.0

    min_setup_score: float = 75.0

    min_setup_strength: float = 70.0

    min_agreement: float = 70.0

    min_risk_reward: float = 1.5


# ============================================================
# AGENT
# ============================================================

class TradingMissionAgent:

    def __init__(
        self,
        auto_execution: bool = AUTO_EXECUTION,
    ):

        self.symbol_registry = {

            "NIFTY":
                SymbolConfig(
                    symbol="NIFTY",
                    market="india",
                    asset_type="INDEX",
                ),

            "BANKNIFTY":
                SymbolConfig(
                    symbol="BANKNIFTY",
                    market="india",
                    asset_type="INDEX",
                ),

            "SENSEX":
                SymbolConfig(
                    symbol="SENSEX",
                    market="india",
                    asset_type="INDEX",
                ),

        }

        self.config = MissionConfig(

            symbols=list(
                DEFAULT_SYMBOLS
            ),

            timeframes=list(
                DEFAULT_TIMEFRAMES
            ),

            auto_execution=bool(
                auto_execution
            ),

            max_trades_per_day=
                DEFAULT_MAX_TRADES_PER_DAY,

            max_daily_loss_percent=
                DEFAULT_MAX_DAILY_LOSS_PERCENT,

            min_setup_score=
                DEFAULT_MIN_SETUP_SCORE,

            min_setup_strength=
                DEFAULT_MIN_SETUP_STRENGTH,

            min_agreement=
                DEFAULT_MIN_AGREEMENT,

            min_risk_reward=
                DEFAULT_MIN_RISK_REWARD,

        )

        self.running = False

        self.pending_setups: List[
            Dict[str, Any]
        ] = []

        self.last_results: List[
            Dict[str, Any]
        ] = []

        self.trades_today = 0

        self.realized_pnl_today = 0.0

        self.last_scan_time: Optional[str] = None

        self._stop_event = (
            threading.Event()
        )

        BASE_PATH.mkdir(
            parents=True,
            exist_ok=True,
        )

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

            value = float(value)

            if value != value:
                return default

            return value

        except Exception:

            return default

    # ========================================================
    # SAVE
    # ========================================================

    def save_state(
        self,
    ):

        payload = {

            "saved_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "running":
                self.running,

            "config":
                asdict(
                    self.config
                ),

            "pending_setups":
                self.pending_setups,

            "last_results":
                self.last_results[-100:],

            "trades_today":
                self.trades_today,

            "realized_pnl_today":
                self.realized_pnl_today,

            "last_scan_time":
                self.last_scan_time,

        }

        try:

            MISSION_FILE.write_text(

                json.dumps(
                    payload,
                    indent=2,
                    default=str,
                ),

                encoding="utf-8",

            )

        except Exception as exc:

            print(
                "JARVIS MISSION DEBUG > "
                f"Could not save state: {exc}"
            )

    # ========================================================
    # LOAD
    # ========================================================

    def load_state(
        self,
    ):

        if not MISSION_FILE.exists():
            return

        try:

            payload = json.loads(

                MISSION_FILE.read_text(
                    encoding="utf-8"
                )

            )

            config = payload.get(
                "config",
                {}
            )

            self.config = MissionConfig(

                symbols=list(
                    config.get(
                        "symbols",
                        DEFAULT_SYMBOLS,
                    )
                ),

                timeframes=list(
                    config.get(
                        "timeframes",
                        DEFAULT_TIMEFRAMES,
                    )
                ),

                all_day=bool(
                    config.get(
                        "all_day",
                        False,
                    )
                ),

                auto_execution=bool(
                    config.get(
                        "auto_execution",
                        False,
                    )
                ),

                max_trades_per_day=int(
                    config.get(
                        "max_trades_per_day",
                        DEFAULT_MAX_TRADES_PER_DAY,
                    )
                ),

                max_daily_loss_percent=float(
                    config.get(
                        "max_daily_loss_percent",
                        DEFAULT_MAX_DAILY_LOSS_PERCENT,
                    )
                ),

                min_setup_score=float(
                    config.get(
                        "min_setup_score",
                        DEFAULT_MIN_SETUP_SCORE,
                    )
                ),

                min_setup_strength=float(
                    config.get(
                        "min_setup_strength",
                        DEFAULT_MIN_SETUP_STRENGTH,
                    )
                ),

                min_agreement=float(
                    config.get(
                        "min_agreement",
                        DEFAULT_MIN_AGREEMENT,
                    )
                ),

                min_risk_reward=float(
                    config.get(
                        "min_risk_reward",
                        DEFAULT_MIN_RISK_REWARD,
                    )
                ),

            )

            self.pending_setups = list(
                payload.get(
                    "pending_setups",
                    [],
                )
            )

            self.last_results = list(
                payload.get(
                    "last_results",
                    [],
                )
            )

            self.trades_today = int(
                payload.get(
                    "trades_today",
                    0,
                )
            )

            self.realized_pnl_today = float(
                payload.get(
                    "realized_pnl_today",
                    0.0,
                )
            )

            self.last_scan_time = (
                payload.get(
                    "last_scan_time"
                )
            )

        except Exception as exc:

            print(
                "JARVIS MISSION DEBUG > "
                f"Could not load state: {exc}"
            )

    # ========================================================
    # LOG
    # ========================================================

    def log(
        self,
        event: str,
        payload: Dict[str, Any],
    ):

        records = []

        if MISSION_LOG_FILE.exists():

            try:

                records = json.loads(

                    MISSION_LOG_FILE.read_text(
                        encoding="utf-8"
                    )

                )

                if not isinstance(
                    records,
                    list,
                ):

                    records = []

            except Exception:

                records = []

        records.append({

            "timestamp":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "event":
                event,

            "payload":
                payload,

        })

        records = records[-5000:]

        try:

            MISSION_LOG_FILE.write_text(

                json.dumps(
                    records,
                    indent=2,
                    default=str,
                ),

                encoding="utf-8",

            )

        except Exception:
            pass

    # ========================================================
    # COMMAND PARSER
    # ========================================================

    def parse_command(
        self,
        command: str,
    ) -> Dict[str, Any]:

        text = (
            str(command)
            .strip()
            .lower()
        )

        # ----------------------------------------------------
        # SYMBOLS
        # ----------------------------------------------------

        symbols = []

        if "nifty" in text:

            symbols.append(
                "NIFTY"
            )

        if (
            "banknifty" in text
            or
            "bank nifty" in text
        ):

            symbols.append(
                "BANKNIFTY"
            )

        if "sensex" in text:

            symbols.append(
                "SENSEX"
            )

        # ----------------------------------------------------
        # TIMEFRAMES
        # ----------------------------------------------------

        aliases = {

            "5m": [
                "5m",
                "5 min",
                "5 mins",
                "5 minute",
                "5 minutes",
            ],

            "15m": [
                "15m",
                "15 min",
                "15 mins",
                "15 minute",
                "15 minutes",
            ],

            "1h": [
                "1h",
                "1 hour",
                "1hour",
            ],

            "4h": [
                "4h",
                "4 hour",
                "4hour",
            ],

            "1d": [
                "1d",
                "daily",
                "day chart",
                "daily chart",
            ],

        }

        timeframes = []

        for timeframe, words in (
            aliases.items()
        ):

            if any(
                word in text
                for word in words
            ):

                timeframes.append(
                    timeframe
                )

        if not symbols:

            symbols = list(
                DEFAULT_SYMBOLS
            )

        if not timeframes:

            timeframes = list(
                DEFAULT_TIMEFRAMES
            )

        # ----------------------------------------------------
        # INTENT
        # ----------------------------------------------------

        scan = any(

            phrase in text

            for phrase in [

                "scan",
                "find trade",
                "find a trade",
                "find setup",
                "find a setup",
                "trade setup",
                "look for trade",
                "look for setup",
                "watch",
                "monitor",

            ]

        )

        execute = any(

            phrase in text

            for phrase in [

                "execute",
                "place trade",
                "enter trade",
                "take trade",

            ]

        )

        all_day = any(

            phrase in text

            for phrase in [

                "all day",
                "whole day",
                "entire day",
                "for the day",
                "today",

            ]

        )

        autonomous = any(

            phrase in text

            for phrase in [

                "auto trade",
                "trade automatically",
                "trade by yourself",
                "automatically",

            ]

        )

        return {

            "symbols":
                symbols,

            "timeframes":
                timeframes,

            "scan":
                scan,

            "execute":
                execute,

            "all_day":
                all_day,

            "autonomous":
                autonomous,

            "original_command":
                command,

        }

    # ========================================================
    # HANDLE COMMAND
    # ========================================================

    def handle_command(
        self,
        command: str,
    ) -> Dict[str, Any]:

        parsed = (
            self.parse_command(
                command
            )
        )

        if parsed["autonomous"]:

            return {

                "success":
                    True,

                "action":
                    "AUTO_BLOCKED",

                "message":
                    (
                        "Autonomous execution is disabled "
                        "in the current policy."
                    ),

            }

        if parsed["execute"]:

            return (
                self.confirm_best_setup()
            )

        if parsed["scan"]:

            self.config.symbols = list(
                parsed["symbols"]
            )

            self.config.timeframes = list(
                parsed["timeframes"]
            )

            self.config.all_day = bool(
                parsed["all_day"]
            )

            self.running = True

            self.save_state()

            self.log(
                "MISSION_STARTED",
                asdict(
                    self.config
                )
            )

            return {

                "success":
                    True,

                "action":
                    "MISSION_STARTED",

                "message":
                    "Trading mission started.",

                "config":
                    asdict(
                        self.config
                    ),

            }

        return {

            "success":
                False,

            "action":
                "NO_TRADING_INTENT",

            "message":
                "No trading mission detected.",

        }

    # ========================================================
    # FETCH MARKET DATA
    # ========================================================

    def fetch_data(
        self,
        symbol: str,
        timeframe: str,
    ) -> Dict[str, Any]:

        registry = (
            self.symbol_registry.get(
                symbol
            )
        )

        if registry is None:

            return {

                "success":
                    False,

                "message":
                    f"Unsupported symbol: {symbol}",

            }

        from agents.market_data_agent import (
            get_market_data,
        )

        try:

            result = get_market_data(

                symbol=symbol,

                market=registry.market,

                timeframe=timeframe,

                bars=int(
                    DEFAULT_BARS.get(
                        timeframe,
                        500,
                    )
                ),

            )

        except Exception as exc:

            return {

                "success":
                    False,

                "message":
                    str(exc),

            }

        if not result.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    result.get(
                        "message",
                        "Market data unavailable.",
                    ),

            }

        data = result.get(
            "data"
        )

        if data is None or data.empty:

            return {

                "success":
                    False,

                "message":
                    "Empty market data.",

            }

        return {

            "success":
                True,

            "symbol":
                symbol,

            "timeframe":
                timeframe,

            "data":
                data,

            "source":
                result.get(
                    "source",
                    "unknown",
                ),

        }

    # ========================================================
    # ANALYZE TIMEFRAME
    # ========================================================

    def analyze_timeframe(
        self,
        symbol: str,
        timeframe: str,
    ) -> Dict[str, Any]:

        data_result = (
            self.fetch_data(

                symbol=symbol,

                timeframe=timeframe,

            )
        )

        if not data_result.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "symbol":
                    symbol,

                "timeframe":
                    timeframe,

                "message":
                    data_result.get(
                        "message",
                        "Market data failed.",
                    ),

            }

        data = (
            data_result[
                "data"
            ]
        )

        # ----------------------------------------------------
        # Technical
        # ----------------------------------------------------

        try:

            from agents.technical_engine import (
                technical_engine,
            )

            technical = (
                technical_engine.analyze(
                    data
                )
            )

        except Exception as exc:

            technical = {

                "success":
                    False,

                "message":
                    str(exc),

            }

        # ----------------------------------------------------
        # Patterns
        # ----------------------------------------------------

        try:

            from agents.pattern_engine import (
                pattern_engine,
            )

            patterns = (
                pattern_engine.analyze(
                    data
                )
            )

        except Exception as exc:

            patterns = {

                "success":
                    False,

                "message":
                    str(exc),

            }

        # ----------------------------------------------------
        # Regime
        # ----------------------------------------------------

        try:

            from agents.regime_detector import (
                regime_detector,
            )

            regime = (
                regime_detector.analyze(
                    data
                )
            )

        except Exception as exc:

            regime = {

                "success":
                    False,

                "message":
                    str(exc),

            }

        try:

            current_price = float(
                data.iloc[-1][
                    "close"
                ]
            )

        except Exception:

            return {

                "success":
                    False,

                "symbol":
                    symbol,

                "timeframe":
                    timeframe,

                "message":
                    "Current price unavailable.",

            }

        return {

            "success":
                True,

            "symbol":
                symbol,

            "timeframe":
                timeframe,

            "price":
                current_price,

            "source":
                data_result.get(
                    "source",
                    "unknown",
                ),

            "bars":
                len(data),

            "technical":
                technical,

            "patterns":
                patterns,

            "regime":
                regime,

            "data":
                data,

        }

    # ========================================================
    # ANALYZE SYMBOL
    # ========================================================

    def analyze_symbol(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        analyses = []

        for timeframe in (
            self.config.timeframes
        ):

            result = (
                self.analyze_timeframe(

                    symbol=symbol,

                    timeframe=timeframe,

                )
            )

            analyses.append(
                result
            )

        required = {
            str(tf).lower()
            for tf
            in self.config.timeframes
        }

        available = {

            str(
                item.get(
                    "timeframe",
                    ""
                )
            ).lower()

            for item
            in analyses

            if item.get(
                "success",
                False,
            )

        }

        missing = sorted(
            required - available
        )

        if missing:

            return {

                "success":
                    True,

                "status":
                    "BLOCKED_DATA",

                "symbol":
                    symbol,

                "analyses":
                    analyses,

                "missing_timeframes":
                    missing,

            }

        return {

            "success":
                True,

            "status":
                "DATA_COMPLETE",

            "symbol":
                symbol,

            "analyses":
                analyses,

            "missing_timeframes":
                [],

        }

    # ========================================================
    # SCORE SETUP
    # ========================================================

    def score_setup(
        self,
        analyzed: Dict[str, Any],
    ) -> Dict[str, Any]:

        symbol = analyzed[
            "symbol"
        ]

        if (
            analyzed.get(
                "status"
            )
            !=
            "DATA_COMPLETE"
        ):

            return {

                "success":
                    False,

                "status":
                    "BLOCKED_DATA",

                "message":
                    "Cannot score incomplete data.",

            }

        analyses = analyzed[
            "analyses"
        ]

        bullish = []
        bearish = []

        timeframe_directions = []

        evidence = []

        for analysis in analyses:

            technical = (
                analysis.get(
                    "technical",
                    {}
                )
            )

            regime = (
                analysis.get(
                    "regime",
                    {}
                )
            )

            patterns = (
                analysis.get(
                    "patterns",
                    {}
                )
            )

            timeframe = (
                analysis[
                    "timeframe"
                ]
            )

            bull = 0.0
            bear = 0.0

            # ------------------------------------------------
            # Trend
            # ------------------------------------------------

            trend = str(

                technical.get(
                    "trend",
                    technical.get(
                        "trend_direction",
                        "",
                    )
                )

            ).upper()

            if (
                "BULL" in trend
                or
                trend in {
                    "UP",
                    "UPTREND",
                }
            ):

                bull += 25

            if (
                "BEAR" in trend
                or
                trend in {
                    "DOWN",
                    "DOWNTREND",
                }
            ):

                bear += 25

            # ------------------------------------------------
            # Regime
            # ------------------------------------------------

            bias = str(

                regime.get(
                    "bias",
                    "",
                )

            ).upper()

            if "BULL" in bias:

                bull += 20

            if "BEAR" in bias:

                bear += 20

            # ------------------------------------------------
            # RSI
            # ------------------------------------------------

            rsi = self.number(

                technical.get(
                    "rsi",
                    50.0,
                ),

                50.0,

            )

            if rsi >= 55:

                bull += 10

            elif rsi <= 45:

                bear += 10

            # ------------------------------------------------
            # Patterns
            # ------------------------------------------------

            pattern_items = []

            if isinstance(
                patterns,
                dict,
            ):

                pattern_items = (
                    patterns.get(
                        "recent_patterns",
                        patterns.get(
                            "patterns",
                            []
                        )
                    )
                )

            if isinstance(
                pattern_items,
                list,
            ):

                for pattern in pattern_items:

                    if not isinstance(
                        pattern,
                        dict,
                    ):

                        continue

                    direction = str(
                        pattern.get(
                            "direction",
                            ""
                        )
                    ).upper()

                    strength = self.number(

                        pattern.get(
                            "strength",
                            1,
                        ),

                        1.0,

                    )

                    points = min(

                        10.0,

                        max(
                            1.0,
                            strength * 5.0,
                        ),

                    )

                    if "BULL" in direction:

                        bull += points

                    elif "BEAR" in direction:

                        bear += points

            if bull > bear:

                direction = "BULLISH"

            elif bear > bull:

                direction = "BEARISH"

            else:

                direction = "NEUTRAL"

            bullish.append(
                bull
            )

            bearish.append(
                bear
            )

            timeframe_directions.append(
                direction
            )

            evidence.append({

                "timeframe":
                    timeframe,

                "bullish":
                    round(
                        bull,
                        2,
                    ),

                "bearish":
                    round(
                        bear,
                        2,
                    ),

                "direction":
                    direction,

                "rsi":
                    rsi,

            })

        bullish_total = sum(
            bullish
        )

        bearish_total = sum(
            bearish
        )

        if bullish_total > bearish_total:

            direction = "BULLISH"

        elif bearish_total > bullish_total:

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        total = (
            bullish_total
            +
            bearish_total
        )

        directional_score = (

            max(
                bullish_total,
                bearish_total,
            )
            /
            total
            *
            100.0

            if total > 0
            else
            0.0

        )

        agreement = (

            sum(

                1

                for item
                in timeframe_directions

                if item == direction

            )

            /
            len(
                timeframe_directions
            )

            *
            100.0

            if timeframe_directions

            else
            0.0

        )

        setup_score = (

            directional_score
            * 0.65

            +

            agreement
            * 0.35

        )

        # ----------------------------------------------------
        # IMPORTANT:
        # "setup_strength" is not probability of profit.
        # ----------------------------------------------------

        setup_strength = setup_score

        if (
            setup_score >= 85
            and
            agreement >= 80
        ):

            quality = "A+"

        elif (
            setup_score >= 78
            and
            agreement >= 75
        ):

            quality = "A"

        elif (
            setup_score >= 70
            and
            agreement >= 65
        ):

            quality = "B"

        else:

            quality = "C"

        return {

            "success":
                True,

            "status":
                "SCORED",

            "symbol":
                symbol,

            "direction":
                direction,

            "setup_score":
                round(
                    setup_score,
                    2,
                ),

            "setup_strength":
                round(
                    setup_strength,
                    2,
                ),

            "agreement":
                round(
                    agreement,
                    2,
                ),

            "quality":
                quality,

            "timeframe_directions":
                timeframe_directions,

            "evidence":
                evidence,

        }

    # ========================================================
    # RESEARCH EDGE
    # ========================================================

    def get_research_edge(
        self,
        strategy: str = "MEAN_REVERSION",
    ) -> Optional[
        Dict[str, Any]
    ]:

        try:

            from agents.edge_validation_engine import (
                edge_validation_engine,
            )

            loaded = (
                edge_validation_engine
                .load_matrix_file()
            )

            if not loaded.get(
                "success",
                False,
            ):

                return None

            report = (
                edge_validation_engine
                .validate_matrix(
                    loaded[
                        "data"
                    ]
                )
            )

            return (

                report
                .get(
                    "evaluations",
                    {}
                )
                .get(
                    str(
                        strategy
                    ).upper()
                )

            )

        except Exception:

            return None

    # ========================================================
    # TRADE PLAN
    # ========================================================

    def build_trade_plan(
        self,
        symbol: str,
        direction: str,
        analyses: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        from agents.trade_plan_engine import (
            trade_plan_engine,
        )

        return (
            trade_plan_engine.create_plan(

                symbol=symbol,

                direction=direction,

                analyses=analyses,

            )
        )

    # ========================================================
    # VERIFICATION
    # ========================================================

    def verify(
        self,
        symbol: str,
        analyzed: Dict[str, Any],
        score: Dict[str, Any],
        plan_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        from agents.trade_setup_verifier import (
            trade_setup_verifier,
        )

        research = (
            self.get_research_edge(
                "MEAN_REVERSION"
            )
        )

        plan = plan_result.get(
            "plan",
            {}
        )

        candidate = {

            "direction":
                score.get(
                    "direction",
                    "NEUTRAL",
                ),

            "setup_score":
                score.get(
                    "setup_score",
                    0.0,
                ),

            "confidence":
                score.get(
                    "setup_strength",
                    0.0,
                ),

            "agreement":
                score.get(
                    "agreement",
                    0.0,
                ),

            "risk_reward":
                plan.get(
                    "risk_reward_target_1",
                    0.0,
                ),

        }

        return (
            trade_setup_verifier.verify(

                symbol=symbol,

                analyses=analyzed.get(
                    "analyses",
                    []
                ),

                candidate=candidate,

                research=research,

                strategy_name=
                    "MEAN_REVERSION",

            )
        )

    # ========================================================
    # SCAN ONE SYMBOL
    # ========================================================

    def scan_symbol(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        analyzed = (
            self.analyze_symbol(
                symbol
            )
        )

        if not analyzed.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "symbol":
                    symbol,

                "status":
                    "DATA_ERROR",

                "message":
                    analyzed.get(
                        "message",
                        "Analysis failed.",
                    ),

            }

        # ----------------------------------------------------
        # HARD DATA GATE
        # ----------------------------------------------------

        if (
            analyzed.get(
                "status"
            )
            !=
            "DATA_COMPLETE"
        ):

            missing = (
                analyzed.get(
                    "missing_timeframes",
                    []
                )
            )

            return {

                "success":
                    True,

                "symbol":
                    symbol,

                "status":
                    "BLOCKED_DATA",

                "candidate":
                    None,

                "verification":
                    {

                        "approved":
                            False,

                        "execution_permission":
                            "BLOCKED",

                        "reasons": [

                            (
                                "Missing required "
                                "timeframes: "
                                +
                                ", ".join(
                                    missing
                                )
                            )

                        ],

                    },

                "analyses":
                    analyzed.get(
                        "analyses",
                        []
                    ),

            }

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        score = (
            self.score_setup(
                analyzed
            )
        )

        if not score.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "symbol":
                    symbol,

                "status":
                    "SCORING_FAILED",

                "message":
                    score.get(
                        "message",
                        "Scoring failed.",
                    ),

            }

        # ----------------------------------------------------
        # Require direction
        # ----------------------------------------------------

        if score.get(
            "direction"
        ) not in {
            "BULLISH",
            "BEARISH",
        }:

            return {

                "success":
                    True,

                "symbol":
                    symbol,

                "status":
                    "BLOCKED_DIRECTION",

                "candidate":
                    None,

                "score":
                    score,

            }

        # ----------------------------------------------------
        # BUILD REAL TRADE PLAN
        # ----------------------------------------------------

        plan_result = (
            self.build_trade_plan(

                symbol=symbol,

                direction=
                    score[
                        "direction"
                    ],

                analyses=
                    analyzed[
                        "analyses"
                    ],

            )
        )

        if not plan_result.get(
            "success",
            False,
        ):

            return {

                "success":
                    True,

                "symbol":
                    symbol,

                "status":
                    "BLOCKED_TRADE_PLAN",

                "candidate":
                    None,

                "score":
                    score,

                "trade_plan":
                    plan_result,

            }

        plan = (
            plan_result.get(
                "plan",
                {}
            )
        )

        # ----------------------------------------------------
        # VERIFICATION
        # ----------------------------------------------------

        verification = (
            self.verify(

                symbol=symbol,

                analyzed=analyzed,

                score=score,

                plan_result=plan_result,

            )
        )

        approved = bool(
            verification.get(
                "approved",
                False,
            )
        )

        # ----------------------------------------------------
        # Candidate
        # ----------------------------------------------------

        candidate = {

            "candidate_id":
                (
                    "SETUP-"
                    +
                    datetime.now().strftime(
                        "%Y%m%d%H%M%S"
                    )
                    +
                    "-"
                    +
                    symbol
                ),

            "created_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "symbol":
                symbol,

            "direction":
                score.get(
                    "direction"
                ),

            "quality":
                score.get(
                    "quality"
                ),

            "setup_score":
                score.get(
                    "setup_score"
                ),

            "setup_strength":
                score.get(
                    "setup_strength"
                ),

            "agreement":
                score.get(
                    "agreement"
                ),

            "timeframes":
                list(
                    self.config.timeframes
                ),

            "timeframe_directions":
                score.get(
                    "timeframe_directions",
                    []
                ),

            "entry":
                plan.get(
                    "entry"
                ),

            "stop_loss":
                plan.get(
                    "stop_loss"
                ),

            "target_1":
                plan.get(
                    "target_1"
                ),

            "target_2":
                plan.get(
                    "target_2"
                ),

            "risk_distance":
                plan.get(
                    "risk_distance"
                ),

            "risk_reward":
                plan.get(
                    "risk_reward_target_1"
                ),

            "invalidation":
                plan.get(
                    "invalidation"
                ),

            "execution_ready":
                approved,

            "paper_only":
                True,

            "verification":
                verification,

        }

        status = (

            "VERIFIED_SETUP"

            if approved

            else
            "BLOCKED_QUALITY"

        )

        return {

            "success":
                True,

            "symbol":
                symbol,

            "status":
                status,

            "candidate":
                candidate,

            "score":
                score,

            "trade_plan":
                plan_result,

            "verification":
                verification,

            "analyses":
                analyzed.get(
                    "analyses",
                    []
                ),

        }

    # ========================================================
    # SCAN ALL
    # ========================================================

    def scan_all(
        self,
    ) -> Dict[str, Any]:

        started_at = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

        results = []

        verified = []

        blocked = []

        self.last_scan_time = (
            started_at
        )

        for symbol in (
            self.config.symbols
        ):

            try:

                result = (
                    self.scan_symbol(
                        symbol
                    )
                )

            except Exception as exc:

                result = {

                    "success":
                        False,

                    "symbol":
                        symbol,

                    "status":
                        "ERROR",

                    "message":
                        str(exc),

                    "candidate":
                        None,

                }

            results.append(
                result
            )

            candidate = (
                result.get(
                    "candidate"
                )
            )

            if (
                candidate is not None
                and
                candidate.get(
                    "execution_ready",
                    False,
                )
            ):

                verified.append(
                    candidate
                )

            else:

                blocked.append(
                    result
                )

        # ----------------------------------------------------
        # Rank VERIFIED ONLY
        # ----------------------------------------------------

        verified.sort(

            key=lambda item:
                (
                    self.number(
                        item.get(
                            "setup_score"
                        )
                    ),

                    self.number(
                        item.get(
                            "risk_reward"
                        )
                    ),

                    self.number(
                        item.get(
                            "agreement"
                        )
                    ),

                ),

            reverse=True,

        )

        self.pending_setups = (
            verified
        )

        payload = {

            "success":
                True,

            "timestamp":
                self.last_scan_time,

            "results":
                results,

            "verified_setups":
                verified,

            "blocked_setups":
                blocked,

            "best_setup":
                (
                    verified[0]
                    if verified
                    else
                    None
                ),

        }

        self.last_results.append(
            payload
        )

        self.log(
            "SCAN_COMPLETE",
            payload,
        )

        self.save_state()

        return payload

    # ========================================================
    # CONFIRM
    # ========================================================

    def confirm_best_setup(
        self,
    ) -> Dict[str, Any]:

        if not self.pending_setups:

            return {

                "success":
                    True,

                "action":
                    "NO_VERIFIED_SETUP",

                "message":
                    (
                        "No verified setup is currently "
                        "ready for confirmation."
                    ),

            }

        if (
            self.trades_today
            >=
            self.config.max_trades_per_day
        ):

            return {

                "success":
                    False,

                "action":
                    "DAILY_TRADE_LIMIT",

                "message":
                    (
                        "Daily trade limit has been reached."
                    ),

            }

        best = (
            self.pending_setups[0]
        )

        # ----------------------------------------------------
        # PAPER-FIRST
        # ----------------------------------------------------

        return {

            "success":
                True,

            "action":
                "CONFIRMATION_READY",

            "message":
                (
                    "Verified setup is ready "
                    "for explicit confirmation."
                ),

            "setup":
                best,

            "execution_mode":
                (
                    "PAPER"
                    if not self.config.auto_execution
                    else
                    "BROKER_GATE"
                ),

            "live_order":
                False,

        }

    # ========================================================
    # STOP
    # ========================================================

    def stop(
        self,
    ) -> Dict[str, Any]:

        self.running = False

        self._stop_event.set()

        self.save_state()

        self.log(
            "MISSION_STOPPED",
            {}
        )

        return {

            "success":
                True,

            "action":
                "MISSION_STOPPED",

            "message":
                "Trading mission stopped.",

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_scan(
        self,
        payload: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS TRADING MISSION"
        )

        lines.append(
            "--------------------------------------------------"
        )

        results = payload.get(
            "results",
            []
        )

        if not results:

            lines.append(
                "No symbols analyzed."
            )

        for result in results:

            symbol = result.get(
                "symbol",
                "UNKNOWN",
            )

            status = result.get(
                "status",
                "UNKNOWN",
            )

            candidate = result.get(
                "candidate"
            )

            if candidate is None:

                lines.append(

                    f"{symbol} | "
                    f"{status}"

                )

                verification = (
                    result.get(
                        "verification",
                        {}
                    )
                )

                for reason in verification.get(
                    "reasons",
                    []
                ):

                    lines.append(
                        f"  BLOCKED: {reason}"
                    )

                continue

            execution_ready = bool(
                candidate.get(
                    "execution_ready",
                    False,
                )
            )

            final_status = (
                "VERIFIED"
                if execution_ready
                else
                "BLOCKED"
            )

            lines.append(

                f"{symbol} | "
                f"{candidate.get('direction')} | "
                f"{candidate.get('quality')} | "
                f"Strength={candidate.get('setup_strength')}/100 | "
                f"Agreement={candidate.get('agreement')}% | "
                f"R/R={candidate.get('risk_reward')} | "
                f"{final_status}"

            )

            if execution_ready:

                lines.append(

                    f"  Entry={candidate.get('entry')} | "
                    f"SL={candidate.get('stop_loss')} | "
                    f"T1={candidate.get('target_1')} | "
                    f"T2={candidate.get('target_2')}"

                )

            verification = (
                candidate.get(
                    "verification",
                    {}
                )
            )

            for reason in verification.get(
                "reasons",
                []
            ):

                lines.append(
                    f"  {reason}"
                )

        verified = payload.get(
            "verified_setups",
            []
        )

        lines.append("")

        lines.append(
            f"Verified setups: "
            f"{len(verified)}"
        )

        if verified:

            best = verified[0]

            lines.append("")

            lines.append(
                "BEST VERIFIED SETUP"
            )

            lines.append(
                f"Symbol: "
                f"{best.get('symbol')}"
            )

            lines.append(
                f"Direction: "
                f"{best.get('direction')}"
            )

            lines.append(
                f"Quality: "
                f"{best.get('quality')}"
            )

            lines.append(
                f"Setup Strength: "
                f"{best.get('setup_strength')}/100"
            )

            lines.append(
                f"Agreement: "
                f"{best.get('agreement')}%"
            )

            lines.append(
                f"Entry: "
                f"{best.get('entry')}"
            )

            lines.append(
                f"Stop: "
                f"{best.get('stop_loss')}"
            )

            lines.append(
                f"Target 1: "
                f"{best.get('target_1')}"
            )

            lines.append(
                f"Target 2: "
                f"{best.get('target_2')}"
            )

            lines.append(
                f"R/R: "
                f"{best.get('risk_reward')}"
            )

            lines.append(
                "Execution: "
                "CONFIRMATION REQUIRED"
            )

        else:

            lines.append("")

            lines.append(
                "NO VERIFIED TRADE"
            )

            lines.append(
                "JARVIS will continue watching."
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Setup strength is not probability of profit. "
            "Paper/research only."
        )

        return "\n".join(
            lines
        )

    # ========================================================
    # SINGLE SCAN
    # ========================================================

    def scan_once(
        self,
    ) -> Dict[str, Any]:

        return (
            self.scan_all()
        )

    # ========================================================
    # FULL DAY
    # ========================================================

    def run_day(
        self,
        interval_seconds: int = 60,
    ):

        self.running = True

        self.config.all_day = True

        self._stop_event.clear()

        self.save_state()

        print(
            "=" * 60
        )

        print(
            "JARVIS FULL-DAY TRADING MISSION"
        )

        print(
            "=" * 60
        )

        print(
            "Paper-first monitoring."
        )

        print(
            "Press Ctrl+C to stop."
        )

        print()

        try:

            while (
                self.running
                and
                not self._stop_event.is_set()
            ):

                # ------------------------------------------------
                # DAILY LOSS LIMIT
                # ------------------------------------------------

                if (
                    self.realized_pnl_today
                    < 0
                ):

                    loss_percent = (

                        abs(
                            self.realized_pnl_today
                        )
                        /
                        1_000_000.0
                        *
                        100.0

                    )

                    if (
                        loss_percent
                        >=
                        self.config.max_daily_loss_percent
                    ):

                        print(
                            "JARVIS > "
                            "Daily loss limit reached."
                        )

                        self.stop()

                        break

                result = (
                    self.scan_once()
                )

                print()

                print(
                    self.format_scan(
                        result
                    )
                )

                print()

                print(
                    f"Next scan in "
                    f"{interval_seconds} seconds."
                )

                print()

                self._stop_event.wait(
                    interval_seconds
                )

        except KeyboardInterrupt:

            self.stop()

    # ========================================================
    # TEST
    # ========================================================

    def test_once(
        self,
    ) -> Dict[str, Any]:

        result = (
            self.scan_once()
        )

        print()

        print(
            self.format_scan(
                result
            )
        )

        return result


# ============================================================
# GLOBAL
# ============================================================

trading_mission_agent = (
    TradingMissionAgent()
)


# ============================================================
# HELPER
# ============================================================

def handle_trading_command(
    command: str,
) -> Dict[str, Any]:

    return (
        trading_mission_agent
        .handle_command(
            command
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
        "JARVIS TRADING MISSION AGENT V3"
    )

    print(
        "=" * 60
    )

    command = (
        "Jarvis scan NIFTY and BANKNIFTY "
        "using 5 minute and 15 minute"
    )

    command_result = (
        trading_mission_agent
        .handle_command(
            command
        )
    )

    print()

    print(
        command_result
    )

    if (
        command_result.get(
            "action"
        )
        ==
        "MISSION_STARTED"
    ):

        result = (
            trading_mission_agent
            .test_once()
        )

        print()

        print(
            "FINAL RESULT"
        )

        print(
            trading_mission_agent
            .format_scan(
                result
            )
        )

    print()

    print(
        "Trading Mission Agent V3 loaded successfully."
    )