from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)


SUPPORTED_OPERATORS = {
    "gt",
    "gte",
    "lt",
    "lte",
    "eq",
    "cross_above",
    "cross_below",
}


SUPPORTED_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
}


@dataclass(frozen=True)
class Condition:

    left: str

    operator: str

    right: str | float | int


    def __post_init__(
        self,
    ):

        if (
            self.operator
            not in SUPPORTED_OPERATORS
        ):

            raise ValueError(
                "Unsupported strategy operator: "
                + str(
                    self.operator
                )
            )


@dataclass(frozen=True)
class StrategySpec:

    strategy_id: str

    name: str

    family: str

    supported_asset_classes: tuple[str, ...]

    supported_instrument_types: tuple[str, ...]

    supported_timeframes: tuple[str, ...]

    required_features: tuple[str, ...]

    long_entry: tuple[Condition, ...] = ()

    short_entry: tuple[Condition, ...] = ()

    exit_conditions: tuple[Condition, ...] = ()

    parameters: dict = field(
        default_factory=dict
    )

    metadata: dict = field(
        default_factory=dict
    )


    def __post_init__(
        self,
    ):

        if not self.strategy_id:

            raise ValueError(
                "strategy_id is required."
            )


        if not self.name:

            raise ValueError(
                "strategy name is required."
            )


    def to_dict(
        self,
    ):

        return asdict(
            self
        )


def _condition(
    value,
):

    if isinstance(
        value,
        Condition,
    ):

        return value


    value = dict(
        value
    )


    return Condition(
        left=
            str(
                value[
                    "left"
                ]
            ),

        operator=
            str(
                value[
                    "operator"
                ]
            ),

        right=
            value[
                "right"
            ],
    )


def strategy_from_dict(
    data,
):

    data = dict(
        data
    )


    return StrategySpec(
        strategy_id=
            str(
                data[
                    "strategy_id"
                ]
            ),

        name=
            str(
                data[
                    "name"
                ]
            ),

        family=
            str(
                data.get(
                    "family",
                    "custom",
                )
            ),

        supported_asset_classes=
            tuple(
                map(
                    str,
                    data.get(
                        "supported_asset_classes",
                        (),
                    ),
                )
            ),

        supported_instrument_types=
            tuple(
                map(
                    str,
                    data.get(
                        "supported_instrument_types",
                        (),
                    ),
                )
            ),

        supported_timeframes=
            tuple(
                map(
                    str,
                    data.get(
                        "supported_timeframes",
                        (),
                    ),
                )
            ),

        required_features=
            tuple(
                map(
                    str,
                    data.get(
                        "required_features",
                        (),
                    ),
                )
            ),

        long_entry=
            tuple(
                _condition(
                    item
                )

                for item
                in data.get(
                    "long_entry",
                    (),
                )
            ),

        short_entry=
            tuple(
                _condition(
                    item
                )

                for item
                in data.get(
                    "short_entry",
                    (),
                )
            ),

        exit_conditions=
            tuple(
                _condition(
                    item
                )

                for item
                in data.get(
                    "exit_conditions",
                    (),
                )
            ),

        parameters=
            dict(
                data.get(
                    "parameters",
                    {},
                )
            ),

        metadata=
            dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
    )
