from __future__ import annotations

from agents.intraday_data_router import intraday_data_router


def inspect(symbol: str):
    print("=" * 70)
    print(f"DEBUG 5M DATA: {symbol}")
    print("=" * 70)

    result = intraday_data_router.get_intraday_data(
        symbol=symbol,
        market="india",
        timeframe="5m",
        bars=100,
    )

    print()
    print("ROUTER RESULT")
    print("success:", result.get("success"))
    print("source:", result.get("source"))
    print("quality:", result.get("data_quality"))
    print("bars:", result.get("bars"))
    print("message:", result.get("message"))

    data = result.get("data")

    print()
    print("TYPE")
    print(type(data))

    if data is None:
        print("DATA IS NONE")
        return

    print()
    print("SHAPE")
    print(getattr(data, "shape", None))

    print()
    print("COLUMNS")
    print(getattr(data, "columns", None))

    print()
    print("DTYPES")
    print(getattr(data, "dtypes", None))

    print()
    print("TAIL")
    try:
        print(data.tail(10))
    except Exception as exc:
        print("TAIL ERROR:", exc)

    print()
    print("NUMERIC CONVERSION TEST")

    try:
        for column in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:

            if column in data.columns:

                series = data[column]

                numeric = (
                    series
                    .astype(str)
                    .str.replace(",", "", regex=False)
                )

                numeric = (
                    __import__("pandas")
                    .to_numeric(
                        numeric,
                        errors="coerce",
                    )
                )

                print(
                    column,
                    "count=",
                    numeric.count(),
                    "nan=",
                    numeric.isna().sum(),
                    "last=",
                    numeric.iloc[-1],
                )

    except Exception as exc:

        print(
            "NUMERIC TEST ERROR:",
            exc,
        )

    print()
    print("DONE")


if __name__ == "__main__":

    inspect("NIFTY")

    print()

    inspect("BANKNIFTY")