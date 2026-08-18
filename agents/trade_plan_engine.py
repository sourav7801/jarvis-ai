# ============================================================
# JARVIS TRADE PLAN ENGINE
# V1
# ============================================================
#
# Creates an actual trade plan from completed timeframe
# analysis.
#
# Outputs:
#   - entry
#   - stop loss
#   - target 1
#   - target 2
#   - risk/reward
#   - invalidation
#   - risk distance
#
# PAPER/RESEARCH ONLY.
# No broker orders.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

import math


class TradePlanEngine:

    def __init__(
        self,
        atr_stop_multiple: float = 1.5,
        target_1_multiple: float = 1.5,
        target_2_multiple: float = 3.0,
        minimum_risk_reward: float = 1.5,
        pivot_lookback: int = 20,
    ):

        self.atr_stop_multiple = float(
            atr_stop_multiple
        )

        self.target_1_multiple = float(
            target_1_multiple
        )

        self.target_2_multiple = float(
            target_2_multiple
        )

        self.minimum_risk_reward = float(
            minimum_risk_reward
        )

        self.pivot_lookback = int(
            pivot_lookback
        )

    # ========================================================
    # NUMBER
    # ========================================================

    @staticmethod
    def number(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if value is None:
                return default

            value = float(value)

            if math.isnan(value):
                return default

            if math.isinf(value):
                return default

            return value

        except Exception:

            return default

    # ========================================================
    # EXTRACT ATR
    # ========================================================

    def extract_atr(
        self,
        analysis: Dict[str, Any],
    ) -> float:

        technical = (
            analysis.get(
                "technical",
                {}
            )
        )

        regime = (
            analysis.get(
                "regime",
                {}
            )
        )

        candidates = [

            technical.get(
                "atr"
            ),

            regime.get(
                "atr"
            ),

            analysis.get(
                "atr"
            ),

        ]

        for value in candidates:

            number = self.number(
                value,
                0.0,
            )

            if number > 0:

                return number

        return 0.0

    # ========================================================
    # EXTRACT OHLC DATA
    # ========================================================

    def extract_levels(
        self,
        analysis: Dict[str, Any],
    ) -> Dict[str, float]:

        data = analysis.get(
            "data"
        )

        if data is None or data.empty:

            return {

                "recent_high":
                    0.0,

                "recent_low":
                    0.0,

                "previous_close":
                    0.0,

            }

        window = min(
            self.pivot_lookback,
            len(data),
        )

        recent = (
            data.iloc[-window:]
        )

        return {

            "recent_high":
                self.number(
                    recent["high"].max()
                ),

            "recent_low":
                self.number(
                    recent["low"].min()
                ),

            "previous_close":
                self.number(
                    data.iloc[-1]["close"]
                ),

        }

    # ========================================================
    # CHOOSE PRIMARY TIMEFRAME
    # ========================================================

    def choose_primary_analysis(
        self,
        analyses: List[
            Dict[str, Any]
        ],
    ) -> Optional[
        Dict[str, Any]
    ]:

        priority = [
            "15m",
            "5m",
            "1h",
            "4h",
            "1d",
        ]

        for timeframe in priority:

            for analysis in analyses:

                if (
                    str(
                        analysis.get(
                            "timeframe",
                            "",
                        )
                    ).lower()
                    ==
                    timeframe
                ):

                    if analysis.get(
                        "success",
                        False,
                    ):

                        return analysis

        return None

    # ========================================================
    # CREATE PLAN
    # ========================================================

    def create_plan(
        self,
        symbol: str,
        direction: str,
        analyses: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        direction = (
            str(
                direction
            )
            .upper()
            .strip()
        )

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:

            return {

                "success":
                    False,

                "approved":
                    False,

                "message":
                    "Direction must be BULLISH or BEARISH.",

            }

        primary = (
            self.choose_primary_analysis(
                analyses
            )
        )

        if primary is None:

            return {

                "success":
                    False,

                "approved":
                    False,

                "message":
                    "No valid primary timeframe analysis.",

            }

        price = self.number(
            primary.get(
                "price"
            )
        )

        atr = self.extract_atr(
            primary
        )

        if price <= 0:

            return {

                "success":
                    False,

                "approved":
                    False,

                "message":
                    "Invalid market price.",

            }

        if atr <= 0:

            return {

                "success":
                    False,

                "approved":
                    False,

                "message":
                    "ATR is unavailable.",

            }

        levels = (
            self.extract_levels(
                primary
            )
        )

        recent_high = levels[
            "recent_high"
        ]

        recent_low = levels[
            "recent_low"
        ]

        # ====================================================
        # LONG
        # ====================================================

        if direction == "BULLISH":

            entry = price

            atr_stop = (
                entry
                -
                atr
                *
                self.atr_stop_multiple
            )

            structure_stop = (
                recent_low
                -
                atr * 0.25
                if recent_low > 0
                else atr_stop
            )

            # Use the tighter but still structurally sensible
            # stop. We do not place the stop inside the recent
            # structure by accident.
            stop_loss = max(
                structure_stop,
                atr_stop,
            )

            risk_distance = (
                entry
                -
                stop_loss
            )

            if risk_distance <= 0:

                return {

                    "success":
                        False,

                    "approved":
                        False,

                    "message":
                        "Invalid bullish risk distance.",

                }

            target_1 = (
                entry
                +
                risk_distance
                *
                self.target_1_multiple
            )

            target_2 = (
                entry
                +
                risk_distance
                *
                self.target_2_multiple
            )

            # If recent resistance is materially higher than
            # the entry, prefer it as a validation level.
            resistance = recent_high

            invalidation = (
                "Price closes below the structural stop."
            )

            side = "LONG"

        # ====================================================
        # SHORT
        # ====================================================

        else:

            entry = price

            atr_stop = (
                entry
                +
                atr
                *
                self.atr_stop_multiple
            )

            structure_stop = (
                recent_high
                +
                atr * 0.25
                if recent_high > 0
                else atr_stop
            )

            stop_loss = min(
                structure_stop,
                atr_stop,
            )

            risk_distance = (
                stop_loss
                -
                entry
            )

            if risk_distance <= 0:

                return {

                    "success":
                        False,

                    "approved":
                        False,

                    "message":
                        "Invalid bearish risk distance.",

                }

            target_1 = (
                entry
                -
                risk_distance
                *
                self.target_1_multiple
            )

            target_2 = (
                entry
                -
                risk_distance
                *
                self.target_2_multiple
            )

            support = recent_low

            invalidation = (
                "Price closes above the structural stop."
            )

            side = "SHORT"

        # ====================================================
        # REWARD / RISK
        # ====================================================

        rr_1 = (
            abs(
                target_1
                -
                entry
            )
            /
            risk_distance
            if risk_distance > 0
            else
            0.0
        )

        rr_2 = (
            abs(
                target_2
                -
                entry
            )
            /
            risk_distance
            if risk_distance > 0
            else
            0.0
        )

        approved = (
            rr_1
            >=
            self.minimum_risk_reward
        )

        reasons = []

        if not approved:

            reasons.append(
                (
                    f"Target 1 R/R "
                    f"{rr_1:.2f} is below "
                    f"minimum "
                    f"{self.minimum_risk_reward:.2f}."
                )
            )

        # ====================================================
        # PLAN
        # ====================================================

        plan = {

            "plan_id":
                (
                    "PLAN-"
                    +
                    datetime.now().strftime(
                        "%Y%m%d%H%M%S"
                    )
                    +
                    "-"
                    +
                    str(symbol).upper()
                ),

            "created_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "symbol":
                str(symbol).upper(),

            "side":
                side,

            "direction":
                direction,

            "primary_timeframe":
                primary.get(
                    "timeframe"
                ),

            "entry":
                entry,

            "stop_loss":
                stop_loss,

            "target_1":
                target_1,

            "target_2":
                target_2,

            "risk_distance":
                risk_distance,

            "risk_reward_target_1":
                rr_1,

            "risk_reward_target_2":
                rr_2,

            "atr":
                atr,

            "atr_stop_multiple":
                self.atr_stop_multiple,

            "structural_low":
                recent_low,

            "structural_high":
                recent_high,

            "invalidation":
                invalidation,

            "approved":
                approved,

            "reasons":
                reasons,

        }

        return {

            "success":
                True,

            "approved":
                approved,

            "plan":
                plan,

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        if not result.get(
            "success",
            False,
        ):

            return (
                "TRADE PLAN FAILED\n"
                "--------------------------------------------------\n"
                +
                str(
                    result.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        plan = result.get(
            "plan",
            {}
        )

        lines = []

        lines.append(
            "JARVIS TRADE PLAN"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: "
            f"{plan.get('symbol')}"
        )

        lines.append(
            f"Direction: "
            f"{plan.get('direction')}"
        )

        lines.append(
            f"Side: "
            f"{plan.get('side')}"
        )

        lines.append(
            f"Primary Timeframe: "
            f"{plan.get('primary_timeframe')}"
        )

        lines.append("")

        lines.append(
            "PRICE PLAN"
        )

        lines.append(
            f"Entry: "
            f"{plan.get('entry'):.2f}"
        )

        lines.append(
            f"Stop Loss: "
            f"{plan.get('stop_loss'):.2f}"
        )

        lines.append(
            f"Target 1: "
            f"{plan.get('target_1'):.2f}"
        )

        lines.append(
            f"Target 2: "
            f"{plan.get('target_2'):.2f}"
        )

        lines.append("")

        lines.append(
            "RISK"
        )

        lines.append(
            f"Risk Distance: "
            f"{plan.get('risk_distance'):.2f}"
        )

        lines.append(
            f"Target 1 R/R: "
            f"{plan.get('risk_reward_target_1'):.2f}"
        )

        lines.append(
            f"Target 2 R/R: "
            f"{plan.get('risk_reward_target_2'):.2f}"
        )

        lines.append(
            f"ATR: "
            f"{plan.get('atr'):.2f}"
        )

        lines.append("")

        lines.append(
            f"Approved: "
            f"{plan.get('approved')}"
        )

        for reason in plan.get(
            "reasons",
            [],
        ):

            lines.append(
                f"- {reason}"
            )

        lines.append("")

        lines.append(
            f"Invalidation: "
            f"{plan.get('invalidation')}"
        )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Research/paper trading only. "
            "No order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

trade_plan_engine = (
    TradePlanEngine()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS TRADE PLAN ENGINE"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # Synthetic test only.
    # --------------------------------------------------------

    import pandas as pd

    dates = pd.date_range(
        end=pd.Timestamp.now(),
        periods=100,
        freq="15min",
    )

    prices = [
        24000 + i * 4
        for i in range(100)
    ]

    data = pd.DataFrame({

        "open":
            prices,

        "high":
            [
                price + 30
                for price in prices
            ],

        "low":
            [
                price - 30
                for price in prices
            ],

        "close":
            prices,

        "volume":
            [100000] * 100,

    }, index=dates)

    fake_analysis = {

        "success":
            True,

        "symbol":
            "NIFTY",

        "timeframe":
            "15m",

        "price":
            float(
                prices[-1]
            ),

        "technical":
            {
                "atr":
                    80.0,
            },

        "regime":
            {},

        "data":
            data,

    }

    result = (
        trade_plan_engine.create_plan(

            symbol="NIFTY",

            direction="BULLISH",

            analyses=[
                fake_analysis
            ],

        )
    )

    print()

    print(
        trade_plan_engine.format_result(
            result
        )
    )

    print()

    print(
        "Trade Plan Engine loaded successfully."
    )