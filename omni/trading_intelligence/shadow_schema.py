from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)


def parse_timestamp(
    value,
):

    if isinstance(
        value,
        datetime,
    ):

        result = value


    elif isinstance(
        value,
        (
            int,
            float,
        ),
    ):

        numeric = float(
            value
        )

        if numeric > 100000000000:
            numeric /= 1000.0

        result = datetime.fromtimestamp(
            numeric,
            tz=timezone.utc,
        )


    else:

        text = str(
            value
        ).strip()

        if text.isdigit():

            return parse_timestamp(
                int(text)
            )

        if text.endswith("Z"):

            text = (
                text[:-1]
                + "+00:00"
            )

        result = datetime.fromisoformat(
            text
        )


    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )


    return result


@dataclass(frozen=True)
class QuoteSnapshot:

    symbol: str

    timestamp: datetime

    ltp: float

    bid: float | None = None

    ask: float | None = None

    source: str = "unknown"

    timestamp_origin: str = "provider"

    metadata: dict = field(
        default_factory=dict
    )


    def __post_init__(
        self,
    ):

        object.__setattr__(
            self,
            "timestamp",
            parse_timestamp(
                self.timestamp
            ),
        )


        if not self.symbol:

            raise ValueError(
                "symbol is required."
            )


        if float(
            self.ltp
        ) <= 0:

            raise ValueError(
                "ltp must be positive."
            )


        if (
            self.bid is not None
            and float(
                self.bid
            ) < 0
        ):

            raise ValueError(
                "bid cannot be negative."
            )


        if (
            self.ask is not None
            and float(
                self.ask
            ) < 0
        ):

            raise ValueError(
                "ask cannot be negative."
            )


        if (
            self.bid is not None
            and self.ask is not None
            and float(
                self.ask
            ) < float(
                self.bid
            )
        ):

            raise ValueError(
                "ask cannot be below bid."
            )


    def to_dict(
        self,
    ):

        return {
            "symbol":
                self.symbol,

            "timestamp":
                self.timestamp.isoformat(),

            "ltp":
                float(
                    self.ltp
                ),

            "bid":
                (
                    float(
                        self.bid
                    )
                    if self.bid
                    is not None
                    else None
                ),

            "ask":
                (
                    float(
                        self.ask
                    )
                    if self.ask
                    is not None
                    else None
                ),

            "source":
                self.source,

            "timestamp_origin":
                self.timestamp_origin,

            "metadata":
                dict(
                    self.metadata
                ),
        }


VALID_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
    "FLAT",
}


@dataclass(frozen=True)
class PaperSignal:

    strategy_id: str

    symbol: str

    signal: str

    timestamp: datetime

    confidence: float = 1.0

    metadata: dict = field(
        default_factory=dict
    )


    def __post_init__(
        self,
    ):

        signal = str(
            self.signal
        ).strip().upper()


        if signal not in VALID_SIGNALS:

            raise ValueError(
                "Unsupported paper signal."
            )


        object.__setattr__(
            self,
            "signal",
            signal,
        )


        object.__setattr__(
            self,
            "timestamp",
            parse_timestamp(
                self.timestamp
            ),
        )


        if not self.strategy_id:

            raise ValueError(
                "strategy_id is required."
            )


        if not self.symbol:

            raise ValueError(
                "symbol is required."
            )


        confidence = float(
            self.confidence
        )


        if not 0 <= confidence <= 1:

            raise ValueError(
                "confidence must be between 0 and 1."
            )


@dataclass(frozen=True)
class ShadowSessionConfig:

    initial_capital: float = 100000.0

    quantity: float = 1.0

    multiplier: float = 1.0

    allow_short: bool = True

    max_quote_age_seconds: float = 15.0

    max_future_skew_seconds: float = 5.0

    slippage_bps: float = 0.0

    fixed_fee: float = 0.0


    def __post_init__(
        self,
    ):

        if self.initial_capital <= 0:
            raise ValueError(
                "initial_capital must be positive."
            )


        if self.quantity <= 0:
            raise ValueError(
                "quantity must be positive."
            )


        if self.multiplier <= 0:
            raise ValueError(
                "multiplier must be positive."
            )


        if self.max_quote_age_seconds <= 0:
            raise ValueError(
                "max_quote_age_seconds must be positive."
            )


        if self.max_future_skew_seconds < 0:
            raise ValueError(
                "max_future_skew_seconds cannot be negative."
            )


        if self.slippage_bps < 0:
            raise ValueError(
                "slippage_bps cannot be negative."
            )


        if self.fixed_fee < 0:
            raise ValueError(
                "fixed_fee cannot be negative."
            )
