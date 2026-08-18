# ============================================================
# JARVIS MARKET DATA AGENT
# V2
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

import os
import time
import pandas as pd


@dataclass
class MarketDataRequest:

    symbol: str

    market: str = "india"

    timeframe: str = "1d"

    bars: int = 500


@dataclass
class MarketDataResult:

    success: bool

    symbol: str

    market: str

    timeframe: str

    bars: int

    data: Optional[pd.DataFrame] = None

    source: str = "unavailable"

    message: str = ""


class MarketDataAgent:

    """
    Unified market-data interface.

    V2 improvements:

        - provider retries
        - smaller Yahoo requests
        - automatic fallback periods
        - chunked daily downloads
        - clean OHLCV normalization
        - no dependency on one giant Yahoo request
    """

    def __init__(self):

        self.providers = [
            "yfinance",
        ]

    # ========================================================
    # SYMBOL NORMALIZATION
    # ========================================================

    def normalize_symbol(
        self,
        symbol: str,
        market: str = "india",
    ) -> str:

        symbol = str(
            symbol or ""
        ).strip().upper()

        market = str(
            market or ""
        ).strip().lower()

        aliases = {

            "NIFTY": "^NSEI",
            "NIFTY50": "^NSEI",
            "NIFTY 50": "^NSEI",

            "BANKNIFTY": "^NSEBANK",
            "BANK NIFTY": "^NSEBANK",

            "SENSEX": "^BSESN",

        }

        if market in {
            "india",
            "indian",
            "nse",
            "bse",
        }:

            return aliases.get(
                symbol,
                symbol,
            )

        return symbol

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate_request(
        self,
        request: MarketDataRequest,
    ) -> Optional[str]:

        if not request.symbol:

            return "Symbol is required."

        if request.bars <= 0:

            return "bars must be greater than zero."

        allowed = {

            "1m",
            "2m",
            "5m",
            "15m",
            "30m",
            "1h",
            "4h",
            "1d",
            "1wk",
            "1mo",

        }

        if request.timeframe not in allowed:

            return (
                f"Unsupported timeframe: "
                f"{request.timeframe}"
            )

        return None

    # ========================================================
    # PERIOD SELECTION
    # ========================================================

    def _period_options(
        self,
        bars: int,
        timeframe: str,
    ):

        if timeframe == "1d":

            if bars <= 100:
                return [
                    "1y",
                    "2y",
                    "5y",
                ]

            if bars <= 250:
                return [
                    "2y",
                    "5y",
                ]

            if bars <= 500:
                return [
                    "5y",
                    "10y",
                ]

            return [
                "5y",
                "10y",
                "max",
            ]

        if timeframe in {
            "1wk",
            "1mo",
        }:

            return [
                "10y",
                "max",
            ]

        if timeframe in {
            "1h",
            "4h",
        }:

            return [
                "2y",
                "5y",
            ]

        return [
            "60d",
        ]

    # ========================================================
    # SAFE YFINANCE REQUEST
    # ========================================================

    def _yf_history(
        self,
        symbol: str,
        period: str,
        interval: str,
    ):

        try:

            import yfinance as yf

        except Exception as e:

            return (
                pd.DataFrame(),
                f"yfinance unavailable: {e}",
            )

        last_error = ""

        for attempt in range(
            3
        ):

            try:

                ticker = yf.Ticker(
                    symbol
                )

                data = ticker.history(

                    period=period,

                    interval=interval,

                    auto_adjust=False,

                    actions=False,

                )

                if (
                    data is not None
                    and
                    not data.empty
                ):

                    return (
                        data,
                        "",
                    )

                last_error = (
                    "Provider returned no rows."
                )

            except Exception as e:

                last_error = str(
                    e
                )

            if attempt < 2:

                time.sleep(
                    1.0 * (
                        attempt + 1
                    )
                )

        return (
            pd.DataFrame(),
            last_error,
        )

    # ========================================================
    # NORMALIZE OHLCV
    # ========================================================

    def normalize_ohlcv(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        if data is None or data.empty:

            return pd.DataFrame()

        result = data.copy()

        if isinstance(
            result.columns,
            pd.MultiIndex,
        ):

            result.columns = [

                "_".join(
                    str(part)
                    for part in column
                    if str(part)
                    != ""
                )

                for column
                in result.columns

            ]

        renamed = {}

        for column in result.columns:

            normalized = (
                str(column)
                .strip()
                .lower()
                .replace(
                    " ",
                    "_",
                )
            )

            if normalized.startswith(
                "open"
            ):

                renamed[column] = "open"

            elif normalized.startswith(
                "high"
            ):

                renamed[column] = "high"

            elif normalized.startswith(
                "low"
            ):

                renamed[column] = "low"

            elif normalized.startswith(
                "close"
            ):

                renamed[column] = "close"

            elif normalized.startswith(
                "volume"
            ):

                renamed[column] = "volume"

            elif normalized.startswith(
                "adj_close"
            ):

                renamed[column] = "adj_close"

        result = result.rename(
            columns=renamed
        )

        required = {
            "open",
            "high",
            "low",
            "close",
        }

        if not required.issubset(
            result.columns
        ):

            return pd.DataFrame()

        if "volume" not in result.columns:

            result[
                "volume"
            ] = 0.0

        for column in [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]:

            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

        result = result.dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
            ]
        )

        return result

    # ========================================================
    # FETCH
    # ========================================================

    def get_market_data(
        self,
        symbol: str,
        market: str = "india",
        timeframe: str = "1d",
        bars: int = 500,
    ) -> Dict[str, Any]:

        request = MarketDataRequest(

            symbol=symbol,

            market=market,

            timeframe=timeframe,

            bars=bars,

        )

        validation = (
            self.validate_request(
                request
            )
        )

        if validation:

            return {

                "success":
                    False,

                "message":
                    validation,

                "source":
                    "unavailable",

                "bars":
                    0,

            }

        errors = []

        # Prefer authenticated broker data when FYERS is configured.  AUTO
        # falls back to Yahoo if login has not been completed or the token has
        # expired, preserving the existing research workflow.
        preferred = os.getenv(
            "JARVIS_MARKET_DATA_PROVIDER",
            "AUTO",
        ).strip().upper()

        if (
            str(market).strip().lower()
            in {"india", "indian", "nse", "bse"}
            and preferred in {"", "AUTO", "FYERS", "FYERS_ONLY"}
        ):
            try:
                from workstation.fyers_isolated_history_bridge import get_intraday_data_isolated_frame as get_intraday_data

                fyers_result = get_intraday_data(
                    symbol=symbol,
                    market=market,
                    timeframe=timeframe,
                    bars=bars,
                )
                if fyers_result.get("success"):
                    fyers_frame = fyers_result["data"].rename(
                        columns={
                            "Open": "open",
                            "High": "high",
                            "Low": "low",
                            "Close": "close",
                            "Volume": "volume",
                        }
                    ).reset_index(drop=False)
                    return {
                        **fyers_result,
                        "market": market,
                        "data": fyers_frame,
                    }
                errors.append(
                    "FYERS: "
                    + str(fyers_result.get("message", "provider unavailable"))
                )
                if preferred == "FYERS_ONLY":
                    return fyers_result
            except Exception as e:
                errors.append(f"FYERS: {e}")
                if preferred == "FYERS_ONLY":
                    return {
                        "success": False,
                        "source": "FYERS",
                        "bars": 0,
                        "message": str(e),
                    }

        provider_symbol = (
            self.normalize_symbol(
                symbol,
                market,
            )
        )

        print(
            f"JARVIS MARKET DATA > "
            f"Request: {provider_symbol} "
            f"{timeframe} "
            f"{bars} bars"
        )

        periods = (
            self._period_options(
                bars,
                timeframe,
            )
        )

        # ----------------------------------------------------
        # First try ordinary period requests.
        # ----------------------------------------------------

        for period in periods:

            print(
                f"JARVIS MARKET DATA > "
                f"Trying period {period}"
            )

            data, error = (
                self._yf_history(
                    provider_symbol,
                    period,
                    timeframe,
                )
            )

            if (
                not data.empty
            ):

                normalized = (
                    self.normalize_ohlcv(
                        data
                    )
                )

                if not normalized.empty:

                    normalized = (
                        normalized
                        .tail(
                            bars
                        )
                        .reset_index(
                            drop=False
                        )
                    )

                    return {

                        "success":
                            True,

                        "symbol":
                            symbol,

                        "provider_symbol":
                            provider_symbol,

                        "market":
                            market,

                        "timeframe":
                            timeframe,

                        "bars":
                            len(
                                normalized
                            ),

                        "source":
                            "yfinance",

                        "message":
                            "Market data loaded successfully.",

                        "data":
                            normalized,

                    }

            if error:

                errors.append(
                    f"{period}: {error}"
                )

        # ----------------------------------------------------
        # Chunked daily fallback.
        #
        # If Yahoo rejects the large request, try several
        # smaller date windows and combine them.
        # ----------------------------------------------------

        if timeframe == "1d":

            chunks = [
                "5y",
                "5y",
            ]

            combined = []

            for chunk in chunks:

                data, error = (
                    self._yf_history(
                        provider_symbol,
                        chunk,
                        timeframe,
                    )
                )

                if not data.empty:

                    normalized = (
                        self.normalize_ohlcv(
                            data
                        )
                    )

                    if not normalized.empty:

                        combined.append(
                            normalized
                        )

                elif error:

                    errors.append(
                        f"chunk: {error}"
                    )

            if combined:

                result = pd.concat(
                    combined,
                    ignore_index=False,
                )

                result = (
                    result[
                        ~result.index.duplicated(
                            keep="last"
                        )
                    ]
                    .sort_index()
                    .tail(
                        bars
                    )
                    .reset_index(
                        drop=False
                    )
                )

                if not result.empty:

                    return {

                        "success":
                            True,

                        "symbol":
                            symbol,

                        "provider_symbol":
                            provider_symbol,

                        "market":
                            market,

                        "timeframe":
                            timeframe,

                        "bars":
                            len(result),

                        "source":
                            "yfinance",

                        "message":
                            "Market data loaded through fallback retrieval.",

                        "data":
                            result,

                    }

        return {

            "success":
                False,

            "symbol":
                symbol,

            "provider_symbol":
                provider_symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "bars":
                0,

            "source":
                "unavailable",

            "message":
                (
                    "Market-data provider could not "
                    "return the requested history. "
                    "Tried multiple retrieval modes. "
                    +
                    (
                        errors[-1]
                        if errors
                        else
                        "No provider details available."
                    )
                ),

        }

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def get_latest_snapshot(
        self,
        symbol: str,
        market: str = "india",
        timeframe: str = "1d",
    ) -> Dict[str, Any]:

        result = self.get_market_data(
            symbol=symbol,
            market=market,
            timeframe=timeframe,
            bars=5,
        )

        if not result.get(
            "success",
            False,
        ):

            return result

        data = result.get(
            "data"
        )

        if data is None or data.empty:

            return {

                "success":
                    False,

                "message":
                    "No snapshot data available.",

            }

        latest = data.iloc[-1]

        return {

            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "source":
                result.get(
                    "source"
                ),

            "open":
                float(
                    latest["open"]
                ),

            "high":
                float(
                    latest["high"]
                ),

            "low":
                float(
                    latest["low"]
                ),

            "close":
                float(
                    latest["close"]
                ),

            "volume":
                float(
                    latest["volume"]
                ),

            "timestamp":
                str(
                    latest.get(
                        "Date",
                        latest.get(
                            "Datetime",
                            latest.get(
                                "Timestamp",
                                "",
                            ),
                        ),
                    )
                ),

        }


# ============================================================
# GLOBAL AGENT
# ============================================================

market_data_agent = MarketDataAgent()


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

def get_market_data(
    symbol: str,
    market: str = "india",
    timeframe: str = "1d",
    bars: int = 500,
):

    return market_data_agent.get_market_data(
        symbol=symbol,
        market=market,
        timeframe=timeframe,
        bars=bars,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS MARKET DATA AGENT V2"
    )

    print(
        "=" * 60
    )

    print()

    result = get_market_data(
        "NIFTY",
        market="india",
        timeframe="1d",
        bars=500,
    )

    print()

    print(
        "SUCCESS:",
        result.get(
            "success"
        ),
    )

    print(
        "SOURCE:",
        result.get(
            "source"
        ),
    )

    print(
        "BARS:",
        result.get(
            "bars"
        ),
    )

    print(
        "MESSAGE:",
        result.get(
            "message"
        ),
    )

    if result.get(
        "success"
    ):

        data = result.get(
            "data"
        )

        print()

        print(
            data.tail()
        )

    print()

    print(
        "Market Data Agent V2 loaded successfully."
    )
