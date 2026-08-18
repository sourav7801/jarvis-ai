from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)


SUPPORTED_INSTRUMENT_KINDS = {
    "spot",
    "future",
    "option_long",
    "commodity_future",
    "currency_future",
}


SUPPORTED_AMBIGUOUS_POLICIES = {
    "stop_first",
    "target_first",
}


@dataclass(frozen=True)
class ExecutionCostConfig:

    brokerage_bps: float = 0.0

    exchange_bps: float = 0.0

    other_bps: float = 0.0

    tax_bps_buy: float = 0.0

    tax_bps_sell: float = 0.0

    fixed_per_order: float = 0.0

    per_contract: float = 0.0

    slippage_bps: float = 0.0

    spread_bps: float = 0.0


    def __post_init__(
        self,
    ):

        for name, value in asdict(
            self
        ).items():

            if float(
                value
            ) < 0:

                raise ValueError(
                    name
                    + " cannot be negative."
                )


@dataclass(frozen=True)
class BacktestConfig:

    initial_capital: float = 100000.0

    quantity: float = 1.0

    contract_multiplier: float = 1.0

    instrument_kind: str = "spot"

    allow_long: bool = True

    allow_short: bool = True

    warmup_bars: int = 50

    stop_loss_pct: float | None = None

    target_pct: float | None = None

    trailing_stop_pct: float | None = None

    max_bars_in_trade: int | None = None

    exit_on_opposite_signal: bool = True

    ambiguous_bar_policy: str = "stop_first"

    base_timeframe_minutes: int = 1

    higher_timeframes: tuple[int, ...] = ()

    capital_requirement_per_unit: float | None = None

    cost: ExecutionCostConfig = field(
        default_factory=ExecutionCostConfig
    )


    def __post_init__(
        self,
    ):

        if (
            self.initial_capital
            <= 0
        ):

            raise ValueError(
                "initial_capital must be positive."
            )


        if self.quantity <= 0:

            raise ValueError(
                "quantity must be positive."
            )


        if (
            self.contract_multiplier
            <= 0
        ):

            raise ValueError(
                "contract_multiplier must be positive."
            )


        if (
            self.instrument_kind
            not in SUPPORTED_INSTRUMENT_KINDS
        ):

            raise ValueError(
                "Unsupported instrument_kind."
            )


        if (
            self.instrument_kind
            == "option_long"
            and self.allow_short
        ):

            raise ValueError(
                "option_long cannot enable naked premium shorting."
            )


        if self.warmup_bars < 21:

            raise ValueError(
                "warmup_bars must be at least 21."
            )


        for name in (
            "stop_loss_pct",
            "target_pct",
            "trailing_stop_pct",
        ):

            value = getattr(
                self,
                name,
            )

            if (
                value is not None
                and float(
                    value
                ) <= 0
            ):

                raise ValueError(
                    name
                    + " must be positive."
                )


        if (
            self.max_bars_in_trade
            is not None
            and int(
                self.max_bars_in_trade
            ) <= 0
        ):

            raise ValueError(
                "max_bars_in_trade must be positive."
            )


        if (
            self.ambiguous_bar_policy
            not in SUPPORTED_AMBIGUOUS_POLICIES
        ):

            raise ValueError(
                "Unsupported ambiguous-bar policy."
            )


        if (
            self.base_timeframe_minutes
            <= 0
        ):

            raise ValueError(
                "base_timeframe_minutes must be positive."
            )


        for timeframe in self.higher_timeframes:

            if int(
                timeframe
            ) <= self.base_timeframe_minutes:

                raise ValueError(
                    "Higher timeframe must exceed base timeframe."
                )


        if (
            self.capital_requirement_per_unit
            is not None
            and self.capital_requirement_per_unit
            < 0
        ):

            raise ValueError(
                "capital_requirement_per_unit cannot be negative."
            )


    def to_dict(
        self,
    ):

        return asdict(
            self
        )


def option_premium_config(
    *,
    initial_capital=100000.0,
    quantity=1.0,
    lot_size=1.0,
    **kwargs,
):

    return BacktestConfig(
        initial_capital=
            initial_capital,

        quantity=
            quantity,

        contract_multiplier=
            lot_size,

        instrument_kind=
            "option_long",

        allow_long=
            True,

        allow_short=
            False,

        **kwargs,
    )


def commodity_future_config(
    *,
    initial_capital=100000.0,
    contracts=1.0,
    lot_size=1.0,
    **kwargs,
):

    return BacktestConfig(
        initial_capital=
            initial_capital,

        quantity=
            contracts,

        contract_multiplier=
            lot_size,

        instrument_kind=
            "commodity_future",

        allow_long=
            True,

        allow_short=
            True,

        **kwargs,
    )
