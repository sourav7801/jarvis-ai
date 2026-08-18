# ============================================================
# JARVIS INTRADAY DATA ROUTER
# V1
# ============================================================
#
# Purpose:
#   Provide ONE stable interface for intraday market data.
#
# Priority:
#   1. Configured broker/provider adapter
#   2. Existing market_data_agent fallback
#   3. Otherwise BLOCK
#
# IMPORTANT:
#   This router never fabricates candles.
#   Missing/invalid intraday data = failure.
#
# PAPER/RESEARCH SAFE.
# ============================================================

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import os


# ============================================================
# CONFIG
# ============================================================

SUPPORTED_TIMEFRAMES = {
    "1m",
    "5m",
    "15m",
    "30m",
    "1h",
}

INTRADAY_TIMEFRAMES = {
    "1m",
    "5m",
    "15m",
    "30m",
    "1h",
}


# ============================================================
# SYMBOL MAP
# ============================================================

SYMBOL_MAP = {
    "NIFTY": {
        "india": {
            "yfinance": "^NSEI",
            "broker": "NIFTY",
        }
    },
    "BANKNIFTY": {
        "india": {
            "yfinance": "^NSEBANK",
            "broker": "BANKNIFTY",
        }
    },
    "SENSEX": {
        "india": {
            "yfinance": "^BSESN",
            "broker": "SENSEX",
        }
    },
}


# ============================================================
# ROUTER
# ============================================================

class IntradayDataRouter:

    def __init__(self):

        self.provider_name = (
            os.getenv(
                "JARVIS_INTRADAY_PROVIDER",
                "AUTO",
            )
            .strip()
            .upper()
        )

        self.last_result: Optional[
            Dict[str, Any]
        ] = None

    # ========================================================
    # TIME
    # ========================================================

    @staticmethod
    def now() -> str:

        return datetime.now().isoformat(
            timespec="seconds"
        )

    # ========================================================
    # SYMBOL
    # ========================================================

    @staticmethod
    def resolve_symbol(
        symbol: str,
        market: str,
    ) -> Dict[str, str]:

        normalized_symbol = (
            str(symbol or "")
            .strip()
            .upper()
        )

        normalized_market = (
            str(market or "india")
            .strip()
            .lower()
        )

        info = SYMBOL_MAP.get(
            normalized_symbol,
            {}
        ).get(
            normalized_market,
            {}
        )

        return {

            "canonical":
                normalized_symbol,

            "market":
                normalized_market,

            "yfinance":
                info.get(
                    "yfinance",
                    normalized_symbol,
                ),

            "broker":
                info.get(
                    "broker",
                    normalized_symbol,
                ),

        }

    # ========================================================
    # VALIDATE TIMEFRAME
    # ========================================================

    @staticmethod
    def validate_timeframe(
        timeframe: str,
    ) -> Dict[str, Any]:

        tf = str(
            timeframe or ""
        ).strip().lower()

        if tf not in SUPPORTED_TIMEFRAMES:

            return {

                "success":
                    False,

                "timeframe":
                    tf,

                "message":
                    (
                        f"Unsupported timeframe: {tf}"
                    ),

            }

        return {

            "success":
                True,

            "timeframe":
                tf,

        }

    # ========================================================
    # VALIDATE DATA
    # ========================================================

    @staticmethod
    def validate_data(
        data: Any,
        timeframe: str,
        minimum_bars: int,
    ) -> Dict[str, Any]:

        if data is None:

            return {

                "valid":
                    False,

                "bars":
                    0,

                "message":
                    "No candle data returned.",

            }

        bars = 0

        try:

            if hasattr(
                data,
                "__len__",
            ):

                bars = len(data)

        except Exception:

            bars = 0

        if bars < minimum_bars:

            return {

                "valid":
                    False,

                "bars":
                    bars,

                "message":
                    (
                        f"Only {bars} bars returned; "
                        f"minimum required is "
                        f"{minimum_bars}."
                    ),

            }

        # ----------------------------------------------------
        # DataFrame validation.
        # ----------------------------------------------------

        if hasattr(
            data,
            "columns",
        ):

            required = {

                "Open",
                "High",
                "Low",
                "Close",

            }

            columns = set(
                str(x)
                for x
                in data.columns
            )

            missing = (
                required
                -
                columns
            )

            if missing:

                return {

                    "valid":
                        False,

                    "bars":
                        bars,

                    "message":
                        (
                            "Missing OHLC columns: "
                            +
                            ", ".join(
                                sorted(
                                    missing
                                )
                            )
                        ),

                }

            try:

                last_close = (
                    data[
                        "Close"
                    ].iloc[-1]
                )

                if last_close is None:

                    return {

                        "valid":
                            False,

                        "bars":
                            bars,

                        "message":
                            "Last close is empty.",

                    }

            except Exception:

                return {

                    "valid":
                        False,

                    "bars":
                        bars,

                    "message":
                        "Unable to validate last close.",

                }

        return {

            "valid":
                True,

            "bars":
                bars,

            "message":
                "Data validation passed.",

        }

    # ========================================================
    # BROKER ADAPTER HOOK
    # ========================================================

    def broker_fetch(
        self,
        symbol: str,
        market: str,
        timeframe: str,
        bars: int,
    ) -> Optional[
        Dict[str, Any]
    ]:

        # ----------------------------------------------------
        # This is intentionally a hook.
        #
        # When your broker connector exists, implement:
        #
        #   agents/broker_intraday_adapter.py
        #
        # with:
        #
        #   get_intraday_data(...)
        #
        # The router will automatically use it.
        # ----------------------------------------------------

        try:

            from agents.broker_intraday_adapter import (
                get_intraday_data,
            )

        except Exception:

            return None

        try:

            result = get_intraday_data(

                symbol=symbol,

                market=market,

                timeframe=timeframe,

                bars=bars,

            )

        except Exception as exc:

            return {

                "success":
                    False,

                "source":
                    "BROKER",

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

                "source":
                    "BROKER",

                "message":
                    (
                        "Broker adapter returned "
                        "invalid result."
                    ),

            }

        result.setdefault(
            "source",
            "BROKER",
        )

        return result

    # ========================================================
    # EXISTING MARKET DATA FALLBACK
    # ========================================================

    def market_data_fallback(
        self,
        symbol: str,
        market: str,
        timeframe: str,
        bars: int,
    ) -> Optional[
        Dict[str, Any]
    ]:

        try:

            from agents.market_data_agent import (
                get_market_data,
            )

        except Exception as exc:

            return {

                "success":
                    False,

                "source":
                    "MARKET_DATA_AGENT",

                "message":
                    (
                        "market_data_agent import failed: "
                        f"{exc}"
                    ),

            }

        try:

            result = get_market_data(

                symbol,

                market=market,

                timeframe=timeframe,

                bars=bars,

            )

        except Exception as exc:

            return {

                "success":
                    False,

                "source":
                    "MARKET_DATA_AGENT",

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

                "source":
                    "MARKET_DATA_AGENT",

                "message":
                    (
                        "market_data_agent returned "
                        "invalid result."
                    ),

            }

        result.setdefault(
            "source",
            "MARKET_DATA_AGENT",
        )

        return result

    # ========================================================
    # MAIN GET
    # ========================================================

    def get_intraday_data(
        self,
        symbol: str,
        market: str = "india",
        timeframe: str = "5m",
        bars: int = 500,
    ) -> Dict[str, Any]:

        validation = (
            self.validate_timeframe(
                timeframe
            )
        )

        if not validation[
            "success"
        ]:

            result = {

                "success":
                    False,

                "symbol":
                    symbol,

                "market":
                    market,

                "timeframe":
                    timeframe,

                "source":
                    "NONE",

                "data_quality":
                    "INVALID",

                "message":
                    validation[
                        "message"
                    ],

                "timestamp":
                    self.now(),

            }

            self.last_result = result

            return result

        # ----------------------------------------------------
        # Only intraday timeframes go through this router.
        # ----------------------------------------------------

        if timeframe not in (
            INTRADAY_TIMEFRAMES
        ):

            result = {

                "success":
                    False,

                "symbol":
                    symbol,

                "market":
                    market,

                "timeframe":
                    timeframe,

                "source":
                    "NONE",

                "data_quality":
                    "BLOCKED",

                "message":
                    (
                        "This router handles intraday "
                        "timeframes only."
                    ),

                "timestamp":
                    self.now(),

            }

            self.last_result = result

            return result

        resolved = (
            self.resolve_symbol(
                symbol,
                market,
            )
        )

        minimum_bars = min(
            max(
                50,
                int(bars * 0.50),
            ),
            bars,
        )

        # ====================================================
        # PROVIDER ORDER
        # ====================================================

        providers = []

        if self.provider_name in {
            "AUTO",
            "BROKER",
        }:

            providers.append(
                "BROKER"
            )

        if self.provider_name in {
            "AUTO",
            "MARKET_DATA",
            "YFINANCE",
        }:

            providers.append(
                "MARKET_DATA_AGENT"
            )

        attempts = []

        # ====================================================
        # TRY PROVIDERS
        # ====================================================

        for provider in providers:

            if provider == "BROKER":

                result = (
                    self.broker_fetch(

                        symbol=
                            resolved[
                                "broker"
                            ],

                        market=
                            market,

                        timeframe=
                            timeframe,

                        bars=
                            bars,

                    )
                )

            else:

                result = (
                    self.market_data_fallback(

                        symbol=
                            symbol,

                        market=
                            market,

                        timeframe=
                            timeframe,

                        bars=
                            bars,

                    )
                )

            if result is None:

                attempts.append({

                    "provider":
                        provider,

                    "success":
                        False,

                    "message":
                        "Provider unavailable.",

                })

                continue

            validation_result = (
                self.validate_data(

                    result.get(
                        "data"
                    ),

                    timeframe,

                    minimum_bars,

                )
            )

            if (
                result.get(
                    "success"
                )
                and
                validation_result[
                    "valid"
                ]
            ):

                source = str(
                    result.get(
                        "source",
                        provider,
                    )
                )

                final = {

                    "success":
                        True,

                    "symbol":
                        symbol,

                    "market":
                        market,

                    "provider_symbol":
                        resolved[
                            "broker"
                            if
                            provider
                            ==
                            "BROKER"
                            else
                            "yfinance"
                        ],

                    "timeframe":
                        timeframe,

                    "bars":
                        validation_result[
                            "bars"
                        ],

                    "source":
                        source,

                    "data_quality":
                        (
                            "LIVE"
                            if
                            provider
                            ==
                            "BROKER"
                            else
                            "FALLBACK"
                        ),

                    "data":
                        result.get(
                            "data"
                        ),

                    "message":
                        (
                            "Intraday data "
                            "validated."
                        ),

                    "attempts":
                        attempts,

                    "timestamp":
                        self.now(),

                }

                self.last_result = final

                return final

            attempts.append({

                "provider":
                    provider,

                "success":
                    bool(
                        result.get(
                            "success"
                        )
                    ),

                "message":
                    result.get(
                        "message",
                        validation_result[
                            "message"
                        ],
                    ),

                "bars":
                    validation_result[
                        "bars"
                    ],

            })

        # ====================================================
        # COMPLETE FAILURE
        # ====================================================

        result = {

            "success":
                False,

            "symbol":
                symbol,

            "market":
                market,

            "provider_symbol":
                resolved[
                    "broker"
                ],

            "timeframe":
                timeframe,

            "bars":
                0,

            "source":
                "NONE",

            "data_quality":
                "UNAVAILABLE",

            "data":
                None,

            "message":
                (
                    "No reliable intraday provider "
                    "returned valid data."
                ),

            "attempts":
                attempts,

            "timestamp":
                self.now(),

        }

        self.last_result = result

        return result

    # ========================================================
    # REQUIRED TIMEFRAME SET
    # ========================================================

    def get_required_timeframes(
        self,
        symbol: str,
        market: str = "india",
        bars: int = 500,
    ) -> Dict[str, Any]:

        output = {}

        for timeframe in (
            "5m",
            "15m",
        ):

            output[
                timeframe
            ] = self.get_intraday_data(

                symbol=
                    symbol,

                market=
                    market,

                timeframe=
                    timeframe,

                bars=
                    bars,

            )

        complete = all(

            output[
                timeframe
            ].get(
                "success"
            )

            for timeframe
            in (
                "5m",
                "15m",
            )

        )

        return {

            "success":
                complete,

            "symbol":
                symbol,

            "market":
                market,

            "timeframes":
                output,

            "missing":
                [

                    timeframe

                    for timeframe
                    in (
                        "5m",
                        "15m",
                    )

                    if not output[
                        timeframe
                    ].get(
                        "success"
                    )

                ],

            "timestamp":
                self.now(),

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS INTRADAY DATA ROUTER"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: "
            f"{result.get('symbol')}"
        )

        lines.append(
            f"Timeframe: "
            f"{result.get('timeframe')}"
        )

        lines.append(
            f"Success: "
            f"{result.get('success')}"
        )

        lines.append(
            f"Source: "
            f"{result.get('source')}"
        )

        lines.append(
            f"Quality: "
            f"{result.get('data_quality')}"
        )

        lines.append(
            f"Bars: "
            f"{result.get('bars')}"
        )

        lines.append(
            f"Message: "
            f"{result.get('message')}"
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

intraday_data_router = (
    IntradayDataRouter()
)


# ============================================================
# MAIN TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS INTRADAY DATA ROUTER"
    )

    print(
        "=" * 60
    )

    print()

    for symbol in (
        "NIFTY",
        "BANKNIFTY",
    ):

        print(
            f"SCAN: {symbol}"
        )

        result = (
            intraday_data_router
            .get_required_timeframes(

                symbol=
                    symbol,

                market=
                    "india",

                bars=
                    500,

            )
        )

        for timeframe, item in (
            result[
                "timeframes"
            ].items()
        ):

            print()

            print(
                intraday_data_router
                .format_result(
                    item
                )
            )

        print()

        print(
            f"COMPLETE: "
            f"{result.get('success')}"
        )

        print(
            f"MISSING: "
            f"{result.get('missing')}"
        )

        print()

    print(
        "Intraday Data Router V1 "
        "loaded successfully."
    )