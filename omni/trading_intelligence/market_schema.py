from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from datetime import (
    datetime,
)

from enum import (
    Enum,
)

from typing import (
    Any,
)


class AssetClass(
    str,
    Enum,
):

    EQUITY = "equity"
    INDEX = "index"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    FOREX = "forex"
    CRYPTO = "crypto"
    FIXED_INCOME = "fixed_income"
    OTHER = "other"


class InstrumentType(
    str,
    Enum,
):

    STOCK = "stock"
    INDEX = "index"
    SPOT = "spot"
    FUTURE = "future"
    OPTION = "option"
    ETF = "etf"
    FX = "fx"
    CRYPTO = "crypto"
    OTHER = "other"


class OptionType(
    str,
    Enum,
):

    CALL = "call"
    PUT = "put"
    NONE = "none"


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

        return OptionType.CALL


    if text in {
        "pe",
        "put",
        "p",
    }:

        return OptionType.PUT


    return OptionType.NONE


@dataclass(frozen=True)
class Instrument:

    symbol: str

    exchange: str

    asset_class: AssetClass

    instrument_type: InstrumentType

    underlying: str | None = None

    expiry: str | None = None

    strike: float | None = None

    option_type: OptionType = OptionType.NONE

    tick_size: float | None = None

    lot_size: float | None = None

    currency: str = "INR"

    session: str | None = None

    timezone: str = "Asia/Kolkata"

    provider_symbol: str | None = None

    metadata: dict | None = None


    def __post_init__(
        self,
    ):

        if not str(
            self.symbol
        ).strip():

            raise ValueError(
                "Instrument symbol cannot be empty."
            )


        if not str(
            self.exchange
        ).strip():

            raise ValueError(
                "Instrument exchange cannot be empty."
            )


        if (
            self.instrument_type
            == InstrumentType.OPTION
        ):

            if self.strike is None:

                raise ValueError(
                    "Option strike is required."
                )


            if not self.expiry:

                raise ValueError(
                    "Option expiry is required."
                )


            if (
                self.option_type
                == OptionType.NONE
            ):

                raise ValueError(
                    "Option type is required."
                )


        if (
            self.lot_size is not None
            and self.lot_size <= 0
        ):

            raise ValueError(
                "lot_size must be positive."
            )


        if (
            self.tick_size is not None
            and self.tick_size <= 0
        ):

            raise ValueError(
                "tick_size must be positive."
            )


    @property
    def key(
        self,
    ):

        values = [
            self.exchange,
            self.symbol,
            self.expiry or "",
            (
                str(
                    self.strike
                )
                if self.strike is not None
                else ""
            ),
            self.option_type.value,
        ]


        return "|".join(
            value.strip().upper()
            for value in values
        )


    def to_dict(
        self,
    ):

        result = asdict(
            self
        )

        result[
            "asset_class"
        ] = self.asset_class.value

        result[
            "instrument_type"
        ] = self.instrument_type.value

        result[
            "option_type"
        ] = self.option_type.value

        return result


@dataclass(frozen=True)
class Bar:

    timestamp: datetime

    open: float

    high: float

    low: float

    close: float

    volume: float = 0.0

    open_interest: float | None = None

    symbol: str | None = None


    def __post_init__(
        self,
    ):

        if self.high < self.low:

            raise ValueError(
                "Bar high cannot be below low."
            )


        if not (
            self.low
            <= self.open
            <= self.high
        ):

            raise ValueError(
                "Bar open outside high/low."
            )


        if not (
            self.low
            <= self.close
            <= self.high
        ):

            raise ValueError(
                "Bar close outside high/low."
            )


@dataclass(frozen=True)
class Quote:

    symbol: str

    timestamp: datetime

    last: float

    bid: float | None = None

    ask: float | None = None

    volume: float | None = None

    open_interest: float | None = None


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
            self.ask - self.bid,
        )


@dataclass(frozen=True)
class OptionMarketSnapshot:

    symbol: str

    underlying: str

    spot: float

    strike: float

    expiry: str

    option_type: OptionType

    last: float

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

    timestamp: datetime | None = None

    metadata: dict[str, Any] | None = None
