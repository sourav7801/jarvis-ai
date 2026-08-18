from __future__ import annotations

import inspect

from datetime import (
    datetime,
    timedelta,
    timezone,
)


SYMBOL_MAP = {
    "NIFTY":
        "NSE:NIFTY50-INDEX",

    "BANKNIFTY":
        "NSE:NIFTYBANK-INDEX",

    "SENSEX":
        "BSE:SENSEX-INDEX",

    "CRUDEOIL":
        "MCX:CRUDEOIL",

    "GOLD":
        "MCX:GOLD",

    "SILVER":
        "MCX:SILVER",

    "NATURALGAS":
        "MCX:NATURALGAS",

    "BTC":
        "BTC",

    "ETH":
        "ETH",

    "SOL":
        "SOL",
}


RESOLUTION_MAP = {
    "1m":
        "1",

    "3m":
        "3",

    "5m":
        "5",

    "15m":
        "15",

    "30m":
        "30",

    "1h":
        "60",

    "2h":
        "120",

    "4h":
        "240",

    "1d":
        "D",
}


def canonical_symbol(
    symbol,
):

    text = str(
        symbol
    ).upper().strip()


    return SYMBOL_MAP.get(
        text,
        symbol,
    )


def _normalize_frame(
    value,
    *,
    limit=240,
):

    rows = []


    # pandas DataFrame
    if hasattr(
        value,
        "to_dict",
    ):

        try:

            records = value.to_dict(
                orient="records"
            )

        except TypeError:

            records = None


        if records is not None:

            value = records


    if isinstance(
        value,
        dict,
    ):

        for key in (
            "bars",
            "candles",
            "data",
            "history",
            "rows",
        ):

            candidate = value.get(
                key
            )


            if isinstance(
                candidate,
                (
                    list,
                    tuple,
                ),
            ):

                value = candidate

                break


    if not isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        return ()


    for item in value:

        if isinstance(
            item,
            dict,
        ):

            # Provider payloads are not guaranteed to use the
            # same field casing. FYERS/pandas transport currently
            # emits:
            #
            # Timestamp, Open, High, Low, Close, Volume
            #
            # Normalize keys once so provider casing never causes
            # otherwise valid candles to be discarded.
            normalized_item = {
                str(
                    key
                ).strip().lower():
                    value

                for key, value
                in item.items()
            }


            timestamp = (
                normalized_item.get(
                    "timestamp"
                )
                or normalized_item.get(
                    "datetime"
                )
                or normalized_item.get(
                    "date"
                )
                or normalized_item.get(
                    "time"
                )
                or normalized_item.get(
                    "ts"
                )
            )


            open_ = (
                normalized_item.get(
                    "open"
                )
                if normalized_item.get(
                    "open"
                ) is not None
                else normalized_item.get(
                    "o"
                )
            )


            high = (
                normalized_item.get(
                    "high"
                )
                if normalized_item.get(
                    "high"
                ) is not None
                else normalized_item.get(
                    "h"
                )
            )


            low = (
                normalized_item.get(
                    "low"
                )
                if normalized_item.get(
                    "low"
                ) is not None
                else normalized_item.get(
                    "l"
                )
            )


            close = (
                normalized_item.get(
                    "close"
                )
                if normalized_item.get(
                    "close"
                ) is not None
                else normalized_item.get(
                    "c"
                )
            )


            volume = (
                normalized_item.get(
                    "volume"
                )
                if normalized_item.get(
                    "volume"
                ) is not None
                else normalized_item.get(
                    "v"
                )
            )


        elif isinstance(
            item,
            (
                list,
                tuple,
            )
        ) and len(
            item
        ) >= 5:

            timestamp = item[0]
            open_ = item[1]
            high = item[2]
            low = item[3]
            close = item[4]

            volume = (
                item[5]
                if len(
                    item
                ) > 5
                else None
            )


        else:

            continue


        try:

            row = {
                "timestamp":
                    (
                        timestamp.isoformat()
                        if hasattr(
                            timestamp,
                            "isoformat"
                        )
                        else str(
                            timestamp
                        )
                    ),

                "open":
                    float(
                        open_
                    ),

                "high":
                    float(
                        high
                    ),

                "low":
                    float(
                        low
                    ),

                "close":
                    float(
                        close
                    ),

                "volume":
                    (
                        float(
                            volume
                        )
                        if volume
                        is not None
                        else None
                    ),
            }


        except Exception:

            continue


        if (
            row[
                "high"
            ]
            < row[
                "low"
            ]
        ):

            continue


        rows.append(
            row
        )


    return tuple(
        rows[
            -max(
                1,
                min(
                    int(
                        limit
                    ),
                    500,
                ),
            ):
        ]
    )



_COMMODITY_SYMBOLS = {
    "CRUDEOIL",
    "GOLD",
    "SILVER",
    "NATURALGAS",
}


def resolved_history_symbol(
    symbol,
):
    """
    Resolve friendly JARVIS commodity names to the canonical
    active FYERS futures contract.

    Index symbols continue to use the existing static mapping.
    """

    friendly = (
        str(
            symbol
        )
        .upper()
        .strip()
    )


    if friendly not in _COMMODITY_SYMBOLS:

        return canonical_symbol(
            friendly
        )


    # Reuse JARVIS's existing canonical front-month resolver.
    # Loader injection prevents provider_symbol() from using
    # quote/history loaders while resolving the contract.
    from workstation.paper_market_data import (
        UnifiedPaperMarketData,
    )


    def forbidden_loader(
        *args,
        **kwargs,
    ):

        raise RuntimeError(
            "Quote/history loader was invoked during "
            "resolver-only operation."
        )


    service = UnifiedPaperMarketData(
        fyers_quote_loader=
            forbidden_loader,

        fyers_history_loader=
            forbidden_loader,
    )


    resolved = service.provider_symbol(
        friendly
    )


    if not isinstance(
        resolved,
        dict,
    ):

        raise RuntimeError(
            "Canonical market-data resolver returned "
            "an invalid contract payload."
        )


    provider_symbol = str(
        resolved.get(
            "provider_symbol",
            "",
        )
    ).strip()


    if not provider_symbol:

        raise RuntimeError(
            "Canonical market-data resolver did not "
            "return provider_symbol for "
            + friendly
        )


    if (
        friendly in _COMMODITY_SYMBOLS
        and provider_symbol
        in {
            "MCX:CRUDEOIL",
            "MCX:GOLD",
            "MCX:SILVER",
            "MCX:NATURALGAS",
        }
    ):

        raise RuntimeError(
            "Commodity resolver returned a generic "
            "non-tradable FYERS symbol."
        )


    return provider_symbol


def _invoke_intraday(
    function,
    *,
    symbol,
    timeframe,
    limit,
):

    signature = inspect.signature(
        function
    )


    params = signature.parameters


    kwargs = {}


    for name, parameter in params.items():

        lowered = name.lower()


        if lowered in {
            "symbol",
            "ticker",
            "instrument",
        }:

            kwargs[
                name
            ] = resolved_history_symbol(
                symbol
            )


        elif lowered == "timeframe":

            # Provider-level timeframe contracts such as
            # agents.fyers_data_adapter.get_intraday_data()
            # expect canonical JARVIS labels:
            #
            #     5m, 15m, 1h, 1d
            #
            # That adapter performs its own FYERS resolution
            # conversion internally.
            kwargs[
                name
            ] = timeframe


        elif lowered in {
            "resolution",
            "interval",
        }:

            # Lower-level provider functions which explicitly
            # request a resolution/interval receive the mapped
            # provider representation:
            #
            #     5m -> 5
            #     1h -> 60
            #     1d -> D
            kwargs[
                name
            ] = RESOLUTION_MAP.get(
                timeframe,
                timeframe,
            )


        elif lowered in {
            "limit",
            "count",
            "bars",
        }:

            kwargs[
                name
            ] = int(
                limit
            )


        elif lowered in {
            "days",
            "lookback_days",
        }:

            kwargs[
                name
            ] = 10


        elif lowered in {
            "period",
        }:

            kwargs[
                name
            ] = "10d"


    missing = []


    for name, parameter in params.items():

        if (
            parameter.default
            is inspect._empty
            and parameter.kind
            not in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }
            and name not in kwargs
        ):

            missing.append(
                name
            )


    if missing:

        raise RuntimeError(
            "Unable to safely call get_intraday_data; "
            "unresolved required parameters: "
            + ", ".join(
                missing
            )
        )


    return function(
        **kwargs
    )



def _provider_payload(
    raw,
):

    """
    Return the actual candle payload from a provider result.

    FYERS get_intraday_data() returns:

        {
            "success": True,
            "data": <pandas.DataFrame>,
            ...
        }

    Older V3 chart code attempted to normalize the outer
    dictionary instead of the DataFrame.
    """

    if not isinstance(
        raw,
        dict,
    ):

        return raw


    if raw.get(
        "success"
    ) is False:

        return None


    for key in (
        "data",
        "candles",
        "bars",
        "history",
        "rows",
    ):

        if key not in raw:

            continue


        value = raw.get(
            key
        )


        if value is not None:

            return value


    return raw


def _provider_error(
    raw,
):

    if not isinstance(
        raw,
        dict,
    ):

        return None


    return (
        raw.get(
            "message"
        )
        or raw.get(
            "error"
        )
        or raw.get(
            "reason"
        )
    )


def get_chart(
    symbol,
    timeframe="15m",
    *,
    limit=180,
):

    symbol = str(
        symbol
    ).upper().strip()

    timeframe = str(
        timeframe
    ).lower().strip()


    if timeframe not in RESOLUTION_MAP:

        timeframe = "15m"


    result = {
        "success":
            False,

        "symbol":
            symbol,

        "provider_symbol":
            canonical_symbol(
                symbol
            ),

        "timeframe":
            timeframe,

        "bars":
            (),

        "verified":
            False,

        "synthetic":
            False,

        "provider":
            None,

        "error":
            None,
    }


    try:

        from workstation.fyers_isolated_history_bridge import (
            get_intraday_data_isolated,
        )


        raw = _invoke_intraday(
            get_intraday_data_isolated,
            symbol=
                symbol,
            timeframe=
                timeframe,
            limit=
                limit,
        )


        payload = _provider_payload(
            raw
        )


        bars = _normalize_frame(
            payload,
            limit=limit,
        )


        if bars:

            result.update(
                {
                    "success":
                        True,

                    "bars":
                        bars,

                    "verified":
                        True,

                    "provider":
                        "fyers_isolated_history",

                    "provider_symbol":
                        (
                            raw.get(
                                "provider_symbol"
                            )
                            if isinstance(
                                raw,
                                dict,
                            )
                            and raw.get(
                                "provider_symbol"
                            )
                            else resolved_history_symbol(
                                symbol
                            )
                        ),
                }
            )


            return result


        provider_error = _provider_error(
            raw
        )


        result[
            "error"
        ] = (
            str(
                provider_error
            )
            if provider_error
            else (
                "FYERS returned no "
                "normalizable candles."
            )
        )


    except Exception as exc:

        result[
            "error"
        ] = (
            type(
                exc
            ).__name__
            + ": "
            + str(
                exc
            )
        )


    return result
