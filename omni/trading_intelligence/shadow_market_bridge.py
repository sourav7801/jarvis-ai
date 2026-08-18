from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.shadow_schema import (
    QuoteSnapshot,
    parse_timestamp,
)


def _first(
    mapping,
    names,
    default=None,
):

    normalized = {
        str(key).lower():
            value

        for key, value
        in mapping.items()
    }


    for name in names:

        if name in normalized:

            return normalized[
                name
            ]


    return default


def quote_snapshot_from_payload(
    payload,
    *,
    symbol,
    source="provider",
    received_at=None,
):

    if not isinstance(
        payload,
        dict,
    ):

        raise ValueError(
            "Quote payload must be a dictionary."
        )


    if payload.get(
        "success"
    ) is False:

        raise RuntimeError(
            str(
                payload.get(
                    "message"
                )
                or payload.get(
                    "error"
                )
                or "Market quote unavailable."
            )
        )


    candidate = payload


    for key in (
        "data",
        "quote",
        "result",
    ):

        inner = payload.get(
            key
        )

        if isinstance(
            inner,
            dict,
        ):

            candidate = {
                **payload,
                **inner,
            }

            break


    ltp = _first(
        candidate,
        (
            "ltp",
            "last_price",
            "last",
            "price",
            "lp",
        ),
    )


    if ltp is None:

        raise ValueError(
            "Quote payload does not contain LTP."
        )


    bid = _first(
        candidate,
        (
            "bid",
            "bid_price",
            "best_bid",
        ),
    )


    ask = _first(
        candidate,
        (
            "ask",
            "ask_price",
            "best_ask",
        ),
    )


    timestamp_value = _first(
        candidate,
        (
            "timestamp",
            "exchange_timestamp",
            "exch_feed_time",
            "feed_time",
            "ts",
        ),
    )


    if received_at is None:

        received_at = datetime.now(
            timezone.utc
        )


    if timestamp_value is None:

        timestamp = parse_timestamp(
            received_at
        )

        timestamp_origin = (
            "received_at"
        )


    else:

        timestamp = parse_timestamp(
            timestamp_value
        )

        timestamp_origin = (
            "provider"
        )


    return QuoteSnapshot(
        symbol=
            str(
                symbol
            ),

        timestamp=
            timestamp,

        ltp=
            float(
                ltp
            ),

        bid=
            (
                float(
                    bid
                )
                if bid
                not in (
                    None,
                    "",
                )
                else None
            ),

        ask=
            (
                float(
                    ask
                )
                if ask
                not in (
                    None,
                    "",
                )
                else None
            ),

        source=
            str(
                source
            ),

        timestamp_origin=
            timestamp_origin,

        metadata={
            "provider_success":
                payload.get(
                    "success"
                ),

            "broker_write":
                False,
        },
    )


class FyersShadowMarketBridge:

    def __init__(
        self,
        adapter=None,
    ):

        self.adapter = (
            adapter
            or FyersReadOnlyAdapter()
        )


    def read_quote(
        self,
        symbol,
    ):

        payload = self.adapter.quote(
            symbol
        )


        return quote_snapshot_from_payload(
            payload,
            symbol=symbol,
            source="fyers_readonly",
        )


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        forbidden = (
            "order",
            "trade",
            "execute",
            "place",
            "modify",
            "cancel",
            "buy",
            "sell",
        )


        if any(
            token in lower

            for token in forbidden
        ):

            raise PermissionError(
                "Shadow market bridge is market-data-only."
            )


        raise AttributeError(
            name
        )


fyers_shadow_market_bridge = (
    FyersShadowMarketBridge()
)
