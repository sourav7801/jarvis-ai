"""
Read-only FYERS historical-data process bridge.

The main JARVIS environment intentionally does not contain
fyers_apiv3. This bridge executes the canonical
agents.fyers_data_adapter inside .venv-fyers and returns a
JSON-safe result.

No order API is imported or exposed.
"""

from __future__ import annotations

import json
import subprocess

from pathlib import Path
from typing import Any, Callable


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

FYERS_PYTHON = (
    ROOT
    / ".venv-fyers"
    / "Scripts"
    / "python.exe"
)


WORKER_CODE = r"""
import json
import sys

from agents.fyers_data_adapter import (
    get_intraday_data,
)


request = json.loads(
    sys.stdin.read()
)


result = get_intraday_data(
    request["symbol"],
    market=request.get(
        "market",
        "india",
    ),
    timeframe=request.get(
        "timeframe",
        "5m",
    ),
    bars=int(
        request.get(
            "bars",
            500,
        )
    ),
)


output = dict(
    result
)


data = output.get(
    "data"
)


if data is not None:

    if hasattr(
        data,
        "reset_index",
    ):

        try:

            frame = data.reset_index()


            # Convert pandas timestamps and numpy values
            # into JSON-compatible Python values.
            rows = []


            for record in frame.to_dict(
                orient="records"
            ):

                clean = {}


                for key, value in record.items():

                    if value is None:

                        clean[str(key)] = None

                        continue


                    if hasattr(
                        value,
                        "isoformat",
                    ):

                        clean[str(key)] = (
                            value.isoformat()
                        )

                        continue


                    if hasattr(
                        value,
                        "item",
                    ):

                        try:

                            value = value.item()

                        except Exception:

                            pass


                    if isinstance(
                        value,
                        (
                            str,
                            int,
                            float,
                            bool,
                        ),
                    ):

                        clean[str(key)] = value

                    else:

                        clean[str(key)] = str(
                            value
                        )


                rows.append(
                    clean
                )


            output["data"] = rows


        except Exception as exc:

            output = {
                "success":
                    False,

                "source":
                    "FYERS",

                "message":
                    (
                        "Failed to serialize FYERS "
                        "history frame: "
                        + str(
                            exc
                        )
                    ),

                "data":
                    None,
            }


# Security:
# never emit auth material.
for key in list(
    output
):

    lowered = str(
        key
    ).lower()


    if any(
        token in lowered

        for token in (
            "token",
            "secret",
            "password",
            "authorization",
            "cookie",
        )
    ):

        output[
            key
        ] = "<REDACTED>"


print(
    json.dumps(
        output,
        default=str,
    )
)
"""


def isolated_fyers_available() -> bool:

    return (
        FYERS_PYTHON.exists()
    )


def get_intraday_data_isolated(
    symbol: str,
    market: str = "india",
    timeframe: str = "5m",
    bars: int = 500,
    *,
    timeout: int = 30,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:

    if not FYERS_PYTHON.exists():

        return {
            "success":
                False,

            "source":
                "FYERS_ISOLATED",

            "message":
                (
                    "Isolated FYERS environment "
                    "is unavailable."
                ),

            "data":
                None,
        }


    payload = {
        "symbol":
            str(
                symbol
            ),

        "market":
            str(
                market
            ),

        "timeframe":
            str(
                timeframe
            ),

        "bars":
            int(
                bars
            ),
    }


    try:

        result = runner(
            [
                str(
                    FYERS_PYTHON
                ),
                "-c",
                WORKER_CODE,
            ],
            cwd=ROOT,
            input=json.dumps(
                payload
            ),
            capture_output=True,
            text=True,
            timeout=max(
                1,
                min(
                    int(
                        timeout
                    ),
                    60,
                ),
            ),
        )


    except subprocess.TimeoutExpired:

        return {
            "success":
                False,

            "source":
                "FYERS_ISOLATED",

            "message":
                "FYERS historical request timed out.",

            "data":
                None,
        }


    except Exception as exc:

        return {
            "success":
                False,

            "source":
                "FYERS_ISOLATED",

            "message":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),

            "data":
                None,
        }


    if result.returncode != 0:

        error = (
            result.stderr
            or result.stdout
            or (
                "FYERS isolated worker "
                "failed."
            )
        )


        return {
            "success":
                False,

            "source":
                "FYERS_ISOLATED",

            "message":
                error.strip()[
                    :2000
                ],

            "data":
                None,
        }


    stdout = (
        result.stdout
        or ""
    ).strip()


    if not stdout:

        return {
            "success":
                False,

            "source":
                "FYERS_ISOLATED",

            "message":
                (
                    "FYERS isolated worker "
                    "returned no payload."
                ),

            "data":
                None,
        }


    # Canonical adapter should print one JSON payload.
    # If a dependency emits harmless text before it,
    # parse from the final JSON-looking line.
    candidates = [
        line.strip()

        for line
        in stdout.splitlines()

        if line.strip()
    ]


    response = None


    for candidate in reversed(
        candidates
    ):

        try:

            value = json.loads(
                candidate
            )

        except Exception:

            continue


        if isinstance(
            value,
            dict,
        ):

            response = value

            break


    if response is None:

        return {
            "success":
                False,

            "source":
                "FYERS_ISOLATED",

            "message":
                (
                    "FYERS isolated worker "
                    "returned invalid JSON."
                ),

            "data":
                None,
        }


    response[
        "bridge"
    ] = (
        "isolated_fyers_history"
    )


    return response



_ANALYSIS_COMMODITIES = {
    "CRUDEOIL",
    "GOLD",
    "SILVER",
    "NATURALGAS",
}


def _resolve_analysis_symbol(
    symbol,
):

    requested = (
        str(
            symbol
            or ""
        )
        .upper()
        .strip()
        .replace(
            " ",
            "",
        )
    )


    if requested not in _ANALYSIS_COMMODITIES:
        return str(
            symbol
        ).strip()


    from workstation.paper_market_data import (
        UnifiedPaperMarketData,
    )


    def forbidden_loader(
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "Unexpected provider loader call "
            "during symbol resolution."
        )


    service = UnifiedPaperMarketData(
        fyers_quote_loader=forbidden_loader,
        fyers_history_loader=forbidden_loader,
    )


    resolved = service.provider_symbol(
        requested
    )


    provider_symbol = str(
        resolved.get(
            "provider_symbol",
            "",
        )
    ).strip()


    if not provider_symbol:
        raise RuntimeError(
            "Unable to resolve active commodity contract."
        )


    return provider_symbol


def get_intraday_data_isolated_frame(
    symbol: str,
    market: str = "india",
    timeframe: str = "5m",
    bars: int = 500,
    *,
    client=None,
    timeout: int = 30,
):

    requested_symbol = str(
        symbol
    ).strip()


    provider_symbol = (
        _resolve_analysis_symbol(
            requested_symbol
        )
    )


    result = get_intraday_data_isolated(
        provider_symbol,
        market=market,
        timeframe=timeframe,
        bars=bars,
        timeout=timeout,
    )


    if not isinstance(
        result,
        dict,
    ):
        return {
            "success":
                False,

            "source":
                "FYERS_ISOLATED",

            "data":
                None,

            "message":
                "Invalid isolated FYERS result.",
        }


    result = dict(
        result
    )


    result["symbol"] = (
        requested_symbol.upper()
    )


    result["provider_symbol"] = (
        result.get(
            "provider_symbol"
        )
        or provider_symbol
    )


    result["timeframe"] = (
        timeframe
    )


    if not result.get(
        "success"
    ):
        return result


    rows = result.get(
        "data"
    )


    if not isinstance(
        rows,
        list,
    ):
        return result


    try:
        import pandas as pd


        frame = pd.DataFrame(
            rows
        )


        rename = {}


        for column in frame.columns:

            name = str(
                column
            ).lower().strip()


            mapped = {
                "timestamp":
                    "Timestamp",

                "datetime":
                    "Timestamp",

                "date":
                    "Timestamp",

                "time":
                    "Timestamp",

                "open":
                    "Open",

                "high":
                    "High",

                "low":
                    "Low",

                "close":
                    "Close",

                "volume":
                    "Volume",
            }.get(
                name
            )


            if mapped:
                rename[
                    column
                ] = mapped


        frame = frame.rename(
            columns=rename
        )


        required = {
            "Timestamp",
            "Open",
            "High",
            "Low",
            "Close",
        }


        missing = (
            required
            - set(
                frame.columns
            )
        )


        if missing:
            raise RuntimeError(
                "Missing OHLC columns: "
                + ", ".join(
                    sorted(missing)
                )
            )


        frame["Timestamp"] = (
            pd.to_datetime(
                frame["Timestamp"],
                errors="coerce",
            )
        )


        for column in (
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ):
            if column in frame.columns:
                frame[column] = (
                    pd.to_numeric(
                        frame[column],
                        errors="coerce",
                    )
                )


        frame = (
            frame
            .dropna(
                subset=[
                    "Timestamp",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                ]
            )
            .sort_values(
                "Timestamp"
            )
            .set_index(
                "Timestamp"
            )
            .tail(
                int(bars)
            )
        )


        frame.index.name = (
            "Timestamp"
        )


        result["data"] = (
            frame
        )

        result["bars"] = (
            len(frame)
        )

        result["bridge"] = (
            "isolated_fyers_analysis"
        )


        return result


    except Exception as exc:
        return {
            **result,

            "success":
                False,

            "bars":
                0,

            "data":
                None,

            "message":
                (
                    "Failed to restore analysis DataFrame: "
                    + str(exc)
                ),
        }
