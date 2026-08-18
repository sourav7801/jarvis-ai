from __future__ import annotations

from dataclasses import (
    dataclass,
)

from datetime import (
    date,
    datetime,
    time,
)

from zoneinfo import (
    ZoneInfo,
)


@dataclass(frozen=True)
class CommodityContract:

    symbol: str

    exchange: str

    underlying: str

    expiry: str

    lot_size: float

    tick_size: float

    session_start: str

    session_end: str

    timezone: str = "Asia/Kolkata"

    currency: str = "INR"


    def __post_init__(
        self,
    ):

        if self.lot_size <= 0:

            raise ValueError(
                "lot_size must be positive."
            )


        if self.tick_size <= 0:

            raise ValueError(
                "tick_size must be positive."
            )


def _clock(
    value,
):

    hour, minute = [
        int(
            item
        )

        for item
        in str(
            value
        ).split(
            ":",
            1,
        )
    ]


    return time(
        hour,
        minute,
    )


def commodity_contract_state(
    contract,
    *,
    now=None,
    spot=None,
    future=None,
    bid=None,
    ask=None,
    volume=None,
    open_interest=None,
):

    zone = ZoneInfo(
        contract.timezone
    )


    current = (
        now
        if now is not None
        else datetime.now(
            zone
        )
    )


    if current.tzinfo is None:

        current = current.replace(
            tzinfo=zone
        )


    current = current.astimezone(
        zone
    )


    start = _clock(
        contract.session_start
    )

    end = _clock(
        contract.session_end
    )

    current_clock = current.time().replace(
        tzinfo=None
    )


    if start <= end:

        session_open = (
            start
            <= current_clock
            <= end
        )


    else:

        session_open = (
            current_clock >= start
            or current_clock <= end
        )


    expiry_date = date.fromisoformat(
        str(
            contract.expiry
        )[
            :10
        ]
    )


    days_to_expiry = (
        expiry_date
        - current.date()
    ).days


    if days_to_expiry < 0:

        roll_phase = "EXPIRED"


    elif days_to_expiry <= 3:

        roll_phase = "URGENT_ROLL"


    elif days_to_expiry <= 7:

        roll_phase = "ROLL_WINDOW"


    else:

        roll_phase = "FRONT_CONTRACT"


    basis = None

    basis_pct = None


    if (
        spot is not None
        and future is not None
    ):

        spot = float(
            spot
        )

        future = float(
            future
        )


        basis = (
            future
            - spot
        )


        basis_pct = (
            basis
            / spot
            if spot != 0
            else None
        )


    spread = None

    spread_pct = None


    if (
        bid is not None
        and ask is not None
    ):

        bid = float(
            bid
        )

        ask = float(
            ask
        )


        spread = max(
            0.0,
            ask
            - bid,
        )


        midpoint = (
            bid
            + ask
        ) / 2.0


        spread_pct = (
            spread
            / midpoint
            if midpoint > 0
            else None
        )


    liquidity = 0.0


    if spread_pct is not None:

        if spread_pct <= 0.001:
            liquidity += 40

        elif spread_pct <= 0.003:
            liquidity += 30

        elif spread_pct <= 0.01:
            liquidity += 20

        elif spread_pct <= 0.03:
            liquidity += 10


    if float(
        volume
        or 0
    ) > 0:

        liquidity += 30


    if float(
        open_interest
        or 0
    ) > 0:

        liquidity += 30


    return {
        "symbol":
            contract.symbol,

        "exchange":
            contract.exchange,

        "underlying":
            contract.underlying,

        "expiry":
            contract.expiry,

        "days_to_expiry":
            days_to_expiry,

        "roll_phase":
            roll_phase,

        "session_open":
            session_open,

        "session_start":
            contract.session_start,

        "session_end":
            contract.session_end,

        "timezone":
            contract.timezone,

        "basis":
            basis,

        "basis_pct":
            basis_pct,

        "spread":
            spread,

        "spread_pct":
            spread_pct,

        "volume":
            volume,

        "open_interest":
            open_interest,

        "liquidity_score":
            min(
                100.0,
                liquidity,
            ),

        "research_only":
            True,
    }
