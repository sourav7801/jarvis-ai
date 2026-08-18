from __future__ import annotations

import csv
import json

from pathlib import (
    Path,
)


from omni.trading_intelligence.market_schema import (
    AssetClass,
    Instrument,
    InstrumentType,
    normalize_option_type,
)


class InstrumentMaster:

    def __init__(
        self,
    ):

        self._items = {}


    @staticmethod
    def from_mapping(
        data,
    ):

        data = dict(
            data
        )


        return Instrument(
            symbol=
                str(
                    data[
                        "symbol"
                    ]
                ),

            exchange=
                str(
                    data[
                        "exchange"
                    ]
                ),

            asset_class=
                AssetClass(
                    str(
                        data.get(
                            "asset_class",
                            "other",
                        )
                    ).lower()
                ),

            instrument_type=
                InstrumentType(
                    str(
                        data.get(
                            "instrument_type",
                            "other",
                        )
                    ).lower()
                ),

            underlying=
                data.get(
                    "underlying"
                ),

            expiry=
                data.get(
                    "expiry"
                ),

            strike=
                (
                    float(
                        data[
                            "strike"
                        ]
                    )
                    if data.get(
                        "strike"
                    )
                    not in (
                        None,
                        "",
                    )
                    else None
                ),

            option_type=
                normalize_option_type(
                    data.get(
                        "option_type"
                    )
                ),

            tick_size=
                (
                    float(
                        data[
                            "tick_size"
                        ]
                    )
                    if data.get(
                        "tick_size"
                    )
                    not in (
                        None,
                        "",
                    )
                    else None
                ),

            lot_size=
                (
                    float(
                        data[
                            "lot_size"
                        ]
                    )
                    if data.get(
                        "lot_size"
                    )
                    not in (
                        None,
                        "",
                    )
                    else None
                ),

            currency=
                str(
                    data.get(
                        "currency",
                        "INR",
                    )
                ),

            session=
                data.get(
                    "session"
                ),

            timezone=
                str(
                    data.get(
                        "timezone",
                        "Asia/Kolkata",
                    )
                ),

            provider_symbol=
                data.get(
                    "provider_symbol"
                ),

            metadata=
                data.get(
                    "metadata"
                ),
        )


    def register(
        self,
        instrument,
    ):

        if not isinstance(
            instrument,
            Instrument,
        ):

            instrument = self.from_mapping(
                instrument
            )


        self._items[
            instrument.key
        ] = instrument


        return instrument


    def get(
        self,
        key,
    ):

        return self._items.get(
            str(
                key
            ).upper()
        )


    def all(
        self,
    ):

        return tuple(
            self._items.values()
        )


    def search(
        self,
        query="",
        *,
        exchange=None,
        asset_class=None,
        instrument_type=None,
        underlying=None,
    ):

        query = str(
            query
            or ""
        ).strip().lower()


        output = []


        for item in self._items.values():

            if (
                exchange
                and item.exchange.lower()
                != str(
                    exchange
                ).lower()
            ):

                continue


            if (
                asset_class
                and item.asset_class.value
                != str(
                    asset_class
                ).lower()
            ):

                continue


            if (
                instrument_type
                and item.instrument_type.value
                != str(
                    instrument_type
                ).lower()
            ):

                continue


            if (
                underlying
                and str(
                    item.underlying
                    or ""
                ).lower()
                != str(
                    underlying
                ).lower()
            ):

                continue


            haystack = " ".join(
                [
                    item.symbol,
                    item.exchange,
                    item.underlying or "",
                    item.expiry or "",
                    item.option_type.value,
                ]
            ).lower()


            if (
                query
                and query not in haystack
            ):

                continue


            output.append(
                item
            )


        return tuple(
            output
        )


    def load_json(
        self,
        path,
    ):

        data = json.loads(
            Path(
                path
            ).read_text(
                encoding="utf-8"
            )
        )


        if isinstance(
            data,
            dict,
        ):

            data = data.get(
                "instruments",
                (),
            )


        for row in data:

            self.register(
                row
            )


        return len(
            self._items
        )


    def load_csv(
        self,
        path,
    ):

        with Path(
            path
        ).open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:

            reader = csv.DictReader(
                handle
            )


            for row in reader:

                self.register(
                    row
                )


        return len(
            self._items
        )


instrument_master = InstrumentMaster()
