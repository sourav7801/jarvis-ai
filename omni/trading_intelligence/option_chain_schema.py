from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from statistics import (
    fmean,
)


def normalize_option_type(
    value,
):

    text = str(
        value
        or ""
    ).strip().lower()


    if text in {
        "ce",
        "call",
        "c",
    }:

        return "call"


    if text in {
        "pe",
        "put",
        "p",
    }:

        return "put"


    raise ValueError(
        "Option type must be CE/PE or call/put."
    )


def _optional_float(
    value,
):

    if value in (
        None,
        "",
    ):

        return None


    return float(
        value
    )


@dataclass(frozen=True)
class OptionContractQuote:

    underlying: str

    expiry: str

    strike: float

    option_type: str

    ltp: float

    symbol: str | None = None

    bid: float | None = None

    ask: float | None = None

    volume: float | None = None

    open_interest: float | None = None

    change_in_oi: float | None = None

    implied_volatility: float | None = None

    delta: float | None = None

    gamma: float | None = None

    theta: float | None = None

    vega: float | None = None


    def __post_init__(
        self,
    ):

        object.__setattr__(
            self,
            "option_type",
            normalize_option_type(
                self.option_type
            ),
        )


        if self.strike <= 0:

            raise ValueError(
                "Option strike must be positive."
            )


        if not self.expiry:

            raise ValueError(
                "Option expiry is required."
            )


        if self.ltp < 0:

            raise ValueError(
                "Option LTP cannot be negative."
            )


    @property
    def mid(
        self,
    ):

        if (
            self.bid is None
            or self.ask is None
        ):

            return None


        return (
            self.bid
            + self.ask
        ) / 2.0


    @property
    def spread(
        self,
    ):

        if (
            self.bid is None
            or self.ask is None
        ):

            return None


        return max(
            0.0,
            self.ask
            - self.bid,
        )


    @property
    def spread_pct(
        self,
    ):

        if (
            self.mid is None
            or self.mid <= 0
        ):

            return None


        return (
            self.spread
            / self.mid
        )


    def to_dict(
        self,
    ):

        result = asdict(
            self
        )

        result[
            "mid"
        ] = self.mid

        result[
            "spread"
        ] = self.spread

        result[
            "spread_pct"
        ] = self.spread_pct

        return result


@dataclass(frozen=True)
class OptionChainSnapshot:

    underlying: str

    spot: float

    timestamp: str

    contracts: tuple[OptionContractQuote, ...]


    def __post_init__(
        self,
    ):

        if self.spot <= 0:

            raise ValueError(
                "Spot price must be positive."
            )


        if not self.contracts:

            raise ValueError(
                "Option chain requires contracts."
            )


    @property
    def expiries(
        self,
    ):

        return tuple(
            sorted(
                {
                    contract.expiry

                    for contract
                    in self.contracts
                }
            )
        )


    @property
    def strikes(
        self,
    ):

        return tuple(
            sorted(
                {
                    contract.strike

                    for contract
                    in self.contracts
                }
            )
        )


    def to_dict(
        self,
    ):

        return {
            "underlying":
                self.underlying,

            "spot":
                self.spot,

            "timestamp":
                self.timestamp,

            "expiries":
                self.expiries,

            "strikes":
                self.strikes,

            "contracts":
                tuple(
                    contract.to_dict()

                    for contract
                    in self.contracts
                ),
        }


FIELD_ALIASES = {
    "symbol": (
        "symbol",
        "tradingsymbol",
        "trading_symbol",
    ),

    "strike": (
        "strike",
        "strike_price",
        "strikeprice",
    ),

    "option_type": (
        "option_type",
        "type",
        "right",
        "cp_type",
        "optiontype",
    ),

    "expiry": (
        "expiry",
        "expiry_date",
        "expirydate",
    ),

    "ltp": (
        "ltp",
        "last",
        "last_price",
        "lastprice",
        "price",
    ),

    "bid": (
        "bid",
        "bid_price",
        "best_bid",
    ),

    "ask": (
        "ask",
        "ask_price",
        "best_ask",
    ),

    "volume": (
        "volume",
        "vol",
        "traded_volume",
    ),

    "open_interest": (
        "open_interest",
        "oi",
    ),

    "change_in_oi": (
        "change_in_oi",
        "change_oi",
        "oi_change",
        "changeinoi",
        "doi",
    ),

    "implied_volatility": (
        "implied_volatility",
        "iv",
    ),

    "delta": (
        "delta",
    ),

    "gamma": (
        "gamma",
    ),

    "theta": (
        "theta",
    ),

    "vega": (
        "vega",
    ),
}


def _value(
    row,
    field,
    default=None,
):

    normalized = {
        str(
            key
        ).strip().lower():
            value

        for key, value
        in dict(
            row
        ).items()
    }


    for alias in FIELD_ALIASES[
        field
    ]:

        if alias in normalized:

            return normalized[
                alias
            ]


    return default


def normalize_option_chain(
    rows,
    *,
    underlying,
    spot,
    timestamp,
    expiry=None,
):

    contracts = []


    for row in rows:

        row_expiry = (
            _value(
                row,
                "expiry",
                expiry,
            )
        )


        if not row_expiry:

            raise ValueError(
                "Every option contract requires expiry."
            )


        contract = OptionContractQuote(
            underlying=
                str(
                    underlying
                ),

            expiry=
                str(
                    row_expiry
                ),

            strike=
                float(
                    _value(
                        row,
                        "strike",
                    )
                ),

            option_type=
                _value(
                    row,
                    "option_type",
                ),

            ltp=
                float(
                    _value(
                        row,
                        "ltp",
                        0.0,
                    )
                    or 0.0
                ),

            symbol=
                (
                    str(
                        _value(
                            row,
                            "symbol",
                        )
                    )
                    if _value(
                        row,
                        "symbol",
                    )
                    is not None
                    else None
                ),

            bid=
                _optional_float(
                    _value(
                        row,
                        "bid",
                    )
                ),

            ask=
                _optional_float(
                    _value(
                        row,
                        "ask",
                    )
                ),

            volume=
                _optional_float(
                    _value(
                        row,
                        "volume",
                    )
                ),

            open_interest=
                _optional_float(
                    _value(
                        row,
                        "open_interest",
                    )
                ),

            change_in_oi=
                _optional_float(
                    _value(
                        row,
                        "change_in_oi",
                    )
                ),

            implied_volatility=
                _optional_float(
                    _value(
                        row,
                        "implied_volatility",
                    )
                ),

            delta=
                _optional_float(
                    _value(
                        row,
                        "delta",
                    )
                ),

            gamma=
                _optional_float(
                    _value(
                        row,
                        "gamma",
                    )
                ),

            theta=
                _optional_float(
                    _value(
                        row,
                        "theta",
                    )
                ),

            vega=
                _optional_float(
                    _value(
                        row,
                        "vega",
                    )
                ),
        )


        contracts.append(
            contract
        )


    return OptionChainSnapshot(
        underlying=
            str(
                underlying
            ),

        spot=
            float(
                spot
            ),

        timestamp=
            str(
                timestamp
            ),

        contracts=
            tuple(
                contracts
            ),
    )
