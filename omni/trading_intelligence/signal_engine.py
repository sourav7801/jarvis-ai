from __future__ import annotations

from omni.trading_intelligence.strategy_schema import (
    Condition,
    StrategySpec,
)


class SignalEngine:

    @staticmethod
    def _resolve(
        row,
        value,
    ):

        if isinstance(
            value,
            (
                int,
                float,
            ),
        ):

            return float(
                value
            )


        if value not in row:

            raise KeyError(
                "Required feature missing: "
                + str(
                    value
                )
            )


        result = row[
            value
        ]


        if result is None:

            raise ValueError(
                "Required feature is None: "
                + str(
                    value
                )
            )


        return float(
            result
        )


    @classmethod
    def condition(
        cls,
        condition,
        current,
        previous=None,
    ):

        if not isinstance(
            condition,
            Condition,
        ):

            raise TypeError(
                "condition must be Condition."
            )


        left = cls._resolve(
            current,
            condition.left,
        )


        right = cls._resolve(
            current,
            condition.right,
        )


        operator = condition.operator


        if operator == "gt":
            return left > right


        if operator == "gte":
            return left >= right


        if operator == "lt":
            return left < right


        if operator == "lte":
            return left <= right


        if operator == "eq":
            return left == right


        if operator in {
            "cross_above",
            "cross_below",
        }:

            if previous is None:

                return False


            previous_left = cls._resolve(
                previous,
                condition.left,
            )


            previous_right = cls._resolve(
                previous,
                condition.right,
            )


            if operator == "cross_above":

                return (
                    previous_left
                    <= previous_right
                    and left
                    > right
                )


            return (
                previous_left
                >= previous_right
                and left
                < right
            )


        raise ValueError(
            "Unsupported operator."
        )


    @classmethod
    def all_conditions(
        cls,
        conditions,
        current,
        previous=None,
    ):

        conditions = tuple(
            conditions
        )


        if not conditions:

            return False


        return all(
            cls.condition(
                condition,
                current,
                previous,
            )

            for condition
            in conditions
        )


    @classmethod
    def evaluate(
        cls,
        strategy,
        current,
        previous=None,
    ):

        if not isinstance(
            strategy,
            StrategySpec,
        ):

            raise TypeError(
                "strategy must be StrategySpec."
            )


        if cls.all_conditions(
            strategy.exit_conditions,
            current,
            previous,
        ):

            signal = "EXIT"


        elif cls.all_conditions(
            strategy.long_entry,
            current,
            previous,
        ):

            signal = "LONG"


        elif cls.all_conditions(
            strategy.short_entry,
            current,
            previous,
        ):

            signal = "SHORT"


        else:

            signal = "FLAT"


        return {
            "success":
                True,

            "strategy_id":
                strategy.strategy_id,

            "signal":
                signal,

            "research_only":
                True,

            "execution_allowed":
                False,
        }


signal_engine = SignalEngine()
