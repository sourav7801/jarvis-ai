# ============================================================
# JARVIS OPTIONS ENGINE
# V1
# ============================================================
#
# Purpose:
#   Options analytics and strategy construction.
#
# Supports:
#   - Calls / Puts
#   - Black-Scholes pricing
#   - Implied volatility
#   - Delta
#   - Gamma
#   - Theta
#   - Vega
#   - Rho
#   - Intrinsic value
#   - Extrinsic value
#   - Break-even
#   - Payoff at expiry
#   - Position payoff
#   - Multi-leg strategies
#   - Bull Call Spread
#   - Bear Put Spread
#   - Long Straddle
#   - Long Strangle
#   - Iron Condor
#   - Strategy summaries
#
# IMPORTANT:
#   This file performs ANALYSIS ONLY.
#   It does not connect to a broker.
#   It does not place live trades.
# ============================================================

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# MATH HELPERS
# ============================================================

SQRT_2PI = math.sqrt(
    2.0 * math.pi
)


def normal_pdf(x: float) -> float:

    return (
        math.exp(
            -0.5 * x * x
        )
        / SQRT_2PI
    )


def normal_cdf(x: float) -> float:

    return (
        0.5
        * (
            1.0
            + math.erf(
                x / math.sqrt(2.0)
            )
        )
    )


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class OptionContract:

    underlying: str

    option_type: str

    strike: float

    premium: float

    expiry_days: float

    volatility: float = 0.20

    risk_free_rate: float = 0.06

    dividend_yield: float = 0.0

    quantity: int = 1

    multiplier: float = 1.0

    side: str = "BUY"


@dataclass
class Greeks:

    delta: float

    gamma: float

    theta: float

    vega: float

    rho: float


@dataclass
class StrategyLeg:

    option_type: str

    strike: float

    premium: float

    quantity: int

    side: str


# ============================================================
# OPTIONS ENGINE
# ============================================================

class OptionsEngine:

    def __init__(
        self,
        default_risk_free_rate: float = 0.06,
    ):

        self.default_risk_free_rate = (
            default_risk_free_rate
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate_option_type(
        self,
        option_type: str,
    ) -> str:

        value = str(
            option_type
            or ""
        ).strip().upper()

        aliases = {

            "CALL": "C",
            "CE": "C",

            "PUT": "P",
            "PE": "P",

        }

        value = aliases.get(
            value,
            value,
        )

        if value not in {
            "C",
            "P",
        }:

            raise ValueError(
                "option_type must be "
                "C/CE/CALL or P/PE/PUT."
            )

        return value

    def validate_inputs(
        self,
        spot: float,
        strike: float,
        volatility: float,
        expiry_days: float,
    ):

        if spot <= 0:

            raise ValueError(
                "Spot price must be positive."
            )

        if strike <= 0:

            raise ValueError(
                "Strike price must be positive."
            )

        if volatility <= 0:

            raise ValueError(
                "Volatility must be positive."
            )

        if expiry_days <= 0:

            raise ValueError(
                "Expiry days must be positive."
            )

    # ========================================================
    # BLACK-SCHOLES D1 / D2
    # ========================================================

    def d1_d2(
        self,
        spot: float,
        strike: float,
        time_years: float,
        volatility: float,
        risk_free_rate: float,
        dividend_yield: float = 0.0,
    ) -> Tuple[float, float]:

        if time_years <= 0:

            raise ValueError(
                "Time to expiry must be positive."
            )

        if volatility <= 0:

            raise ValueError(
                "Volatility must be positive."
            )

        d1 = (

            math.log(
                spot / strike
            )

            +

            (
                risk_free_rate
                - dividend_yield
                + 0.5
                * volatility
                * volatility
            )
            * time_years

        ) / (

            volatility
            * math.sqrt(
                time_years
            )

        )

        d2 = (
            d1
            -
            volatility
            * math.sqrt(
                time_years
            )
        )

        return (
            d1,
            d2,
        )

    # ========================================================
    # OPTION PRICE
    # ========================================================

    def theoretical_price(
        self,
        spot: float,
        strike: float,
        expiry_days: float,
        volatility: float,
        option_type: str,
        risk_free_rate: Optional[float] = None,
        dividend_yield: float = 0.0,
    ) -> float:

        option_type = (
            self.validate_option_type(
                option_type
            )
        )

        risk_free_rate = (
            self.default_risk_free_rate
            if risk_free_rate is None
            else risk_free_rate
        )

        self.validate_inputs(
            spot,
            strike,
            volatility,
            expiry_days,
        )

        time_years = (
            expiry_days / 365.0
        )

        d1, d2 = self.d1_d2(

            spot,

            strike,

            time_years,

            volatility,

            risk_free_rate,

            dividend_yield,

        )

        discount_rate = math.exp(
            -risk_free_rate
            * time_years
        )

        dividend_discount = math.exp(
            -dividend_yield
            * time_years
        )

        if option_type == "C":

            price = (

                spot
                * dividend_discount
                * normal_cdf(d1)

                -

                strike
                * discount_rate
                * normal_cdf(d2)

            )

        else:

            price = (

                strike
                * discount_rate
                * normal_cdf(-d2)

                -

                spot
                * dividend_discount
                * normal_cdf(-d1)

            )

        return max(
            float(price),
            0.0,
        )

    # ========================================================
    # GREEKS
    # ========================================================

    def greeks(
        self,
        spot: float,
        strike: float,
        expiry_days: float,
        volatility: float,
        option_type: str,
        risk_free_rate: Optional[float] = None,
        dividend_yield: float = 0.0,
    ) -> Greeks:

        option_type = (
            self.validate_option_type(
                option_type
            )
        )

        risk_free_rate = (
            self.default_risk_free_rate
            if risk_free_rate is None
            else risk_free_rate
        )

        self.validate_inputs(
            spot,
            strike,
            volatility,
            expiry_days,
        )

        time_years = (
            expiry_days / 365.0
        )

        d1, d2 = self.d1_d2(

            spot,

            strike,

            time_years,

            volatility,

            risk_free_rate,

            dividend_yield,

        )

        sqrt_t = math.sqrt(
            time_years
        )

        dividend_discount = math.exp(
            -dividend_yield
            * time_years
        )

        discount_rate = math.exp(
            -risk_free_rate
            * time_years
        )

        pdf_d1 = normal_pdf(
            d1
        )

        if option_type == "C":

            delta = (

                dividend_discount
                * normal_cdf(d1)

            )

            theta = (

                -(
                    spot
                    * dividend_discount
                    * pdf_d1
                    * volatility
                )
                / (
                    2.0
                    * sqrt_t
                )

                -

                risk_free_rate
                * strike
                * discount_rate
                * normal_cdf(d2)

                +

                dividend_yield
                * spot
                * dividend_discount
                * normal_cdf(d1)

            )

            rho = (

                strike
                * time_years
                * discount_rate
                * normal_cdf(d2)

            )

        else:

            delta = (

                dividend_discount
                * (
                    normal_cdf(d1)
                    - 1.0
                )

            )

            theta = (

                -(
                    spot
                    * dividend_discount
                    * pdf_d1
                    * volatility
                )
                / (
                    2.0
                    * sqrt_t
                )

                +

                risk_free_rate
                * strike
                * discount_rate
                * normal_cdf(-d2)

                -

                dividend_yield
                * spot
                * dividend_discount
                * normal_cdf(-d1)

            )

            rho = (

                -strike
                * time_years
                * discount_rate
                * normal_cdf(-d2)

            )

        gamma = (

            dividend_discount
            * pdf_d1
            / (
                spot
                * volatility
                * sqrt_t
            )

        )

        vega = (

            spot
            * dividend_discount
            * pdf_d1
            * sqrt_t

        )

        # Per-year theta to per-day theta.
        theta_per_day = (
            theta / 365.0
        )

        # Vega is conventionally quoted per 1%
        # volatility move in many trading systems.
        vega_per_one_percent = (
            vega / 100.0
        )

        return Greeks(

            delta=float(
                delta
            ),

            gamma=float(
                gamma
            ),

            theta=float(
                theta_per_day
            ),

            vega=float(
                vega_per_one_percent
            ),

            rho=float(
                rho
            ),

        )

    # ========================================================
    # INTRINSIC VALUE
    # ========================================================

    def intrinsic_value(
        self,
        spot: float,
        strike: float,
        option_type: str,
    ) -> float:

        option_type = (
            self.validate_option_type(
                option_type
            )
        )

        if option_type == "C":

            return max(
                spot - strike,
                0.0,
            )

        return max(
            strike - spot,
            0.0,
        )

    # ========================================================
    # EXTRINSIC VALUE
    # ========================================================

    def extrinsic_value(
        self,
        premium: float,
        spot: float,
        strike: float,
        option_type: str,
    ) -> float:

        intrinsic = (
            self.intrinsic_value(
                spot,
                strike,
                option_type,
            )
        )

        return max(
            premium - intrinsic,
            0.0,
        )

    # ========================================================
    # IMPLIED VOLATILITY
    # ========================================================

    def implied_volatility(
        self,
        market_price: float,
        spot: float,
        strike: float,
        expiry_days: float,
        option_type: str,
        risk_free_rate: Optional[float] = None,
        dividend_yield: float = 0.0,
        tolerance: float = 1e-6,
        max_iterations: int = 200,
    ) -> Optional[float]:

        if market_price <= 0:

            return None

        option_type = (
            self.validate_option_type(
                option_type
            )
        )

        risk_free_rate = (
            self.default_risk_free_rate
            if risk_free_rate is None
            else risk_free_rate
        )

        self.validate_inputs(
            spot,
            strike,
            0.01,
            expiry_days,
        )

        low = 0.0001
        high = 5.0

        for _ in range(
            max_iterations
        ):

            mid = (
                low + high
            ) / 2.0

            price = (
                self.theoretical_price(
                    spot=spot,
                    strike=strike,
                    expiry_days=expiry_days,
                    volatility=mid,
                    option_type=option_type,
                    risk_free_rate=risk_free_rate,
                    dividend_yield=dividend_yield,
                )
            )

            error = (
                price
                - market_price
            )

            if abs(error) <= tolerance:

                return mid

            if error > 0:

                high = mid

            else:

                low = mid

        return (
            (low + high)
            / 2.0
        )

    # ========================================================
    # BREAK-EVEN
    # ========================================================

    def break_even(
        self,
        strike: float,
        premium: float,
        option_type: str,
    ) -> float:

        option_type = (
            self.validate_option_type(
                option_type
            )
        )

        if option_type == "C":

            return (
                strike + premium
            )

        return (
            strike - premium
        )

    # ========================================================
    # SINGLE LEG EXPIRY PAYOFF
    # ========================================================

    def expiry_payoff(
        self,
        spot_at_expiry: float,
        strike: float,
        premium: float,
        option_type: str,
        side: str = "BUY",
        quantity: int = 1,
        multiplier: float = 1.0,
    ) -> float:

        option_type = (
            self.validate_option_type(
                option_type
            )
        )

        side = str(
            side or "BUY"
        ).upper()

        if option_type == "C":

            intrinsic = max(
                spot_at_expiry
                - strike,
                0.0,
            )

        else:

            intrinsic = max(
                strike
                - spot_at_expiry,
                0.0,
            )

        if side == "BUY":

            pnl_per_unit = (
                intrinsic
                - premium
            )

        elif side == "SELL":

            pnl_per_unit = (
                premium
                - intrinsic
            )

        else:

            raise ValueError(
                "side must be BUY or SELL."
            )

        return (
            pnl_per_unit
            * quantity
            * multiplier
        )

    # ========================================================
    # STRATEGY PAYOFF
    # ========================================================

    def strategy_payoff(
        self,
        legs: List[StrategyLeg],
        spot_prices: List[float],
        multiplier: float = 1.0,
    ) -> List[Dict[str, float]]:

        results = []

        for spot in spot_prices:

            total = 0.0

            for leg in legs:

                total += (
                    self.expiry_payoff(
                        spot_at_expiry=spot,
                        strike=leg.strike,
                        premium=leg.premium,
                        option_type=leg.option_type,
                        side=leg.side,
                        quantity=leg.quantity,
                        multiplier=multiplier,
                    )
                )

            results.append({

                "spot":
                    float(spot),

                "pnl":
                    float(total),

            })

        return results

    # ========================================================
    # GENERATE PRICE GRID
    # ========================================================

    def price_grid(
        self,
        center_price: float,
        width_percent: float = 15.0,
        points: int = 101,
    ) -> List[float]:

        if center_price <= 0:

            raise ValueError(
                "center_price must be positive."
            )

        if points < 2:

            raise ValueError(
                "points must be at least 2."
            )

        lower = (
            center_price
            * (
                1.0
                - width_percent
                / 100.0
            )
        )

        upper = (
            center_price
            * (
                1.0
                + width_percent
                / 100.0
            )
        )

        step = (
            upper - lower
        ) / (
            points - 1
        )

        return [
            lower + (
                step * index
            )
            for index in range(
                points
            )
        ]

    # ========================================================
    # GENERIC STRATEGY SUMMARY
    # ========================================================

    def summarize_strategy(
        self,
        legs: List[StrategyLeg],
        spot: float,
        width_percent: float = 20.0,
    ) -> Dict[str, Any]:

        prices = self.price_grid(
            spot,
            width_percent,
            501,
        )

        payoff = self.strategy_payoff(
            legs,
            prices,
        )

        if not payoff:

            return {
                "success": False,
                "message":
                    "Could not calculate payoff.",
            }

        pnls = [
            item["pnl"]
            for item in payoff
        ]

        max_profit = max(
            pnls
        )

        max_loss = min(
            pnls
        )

        breakevens = []

        previous = payoff[0]

        for current in payoff[1:]:

            previous_pnl = (
                previous["pnl"]
            )

            current_pnl = (
                current["pnl"]
            )

            if (
                previous_pnl == 0.0
                or
                current_pnl == 0.0
                or
                (
                    previous_pnl
                    < 0
                    and
                    current_pnl
                    > 0
                )
                or
                (
                    previous_pnl
                    > 0
                    and
                    current_pnl
                    < 0
                )
            ):

                breakevens.append(
                    current["spot"]
                )

            previous = current

        return {

            "success":
                True,

            "max_profit":
                max_profit,

            "max_loss":
                max_loss,

            "breakevens":
                breakevens,

            "payoff":
                payoff,

        }

    # ========================================================
    # BULL CALL SPREAD
    # ========================================================

    def bull_call_spread(
        self,
        long_strike: float,
        short_strike: float,
        long_premium: float,
        short_premium: float,
        quantity: int = 1,
    ) -> Dict[str, Any]:

        if short_strike <= long_strike:

            raise ValueError(
                "Bull Call Spread requires "
                "short_strike > long_strike."
            )

        legs = [

            StrategyLeg(
                option_type="C",
                strike=long_strike,
                premium=long_premium,
                quantity=quantity,
                side="BUY",
            ),

            StrategyLeg(
                option_type="C",
                strike=short_strike,
                premium=short_premium,
                quantity=quantity,
                side="SELL",
            ),

        ]

        net_debit = (
            long_premium
            - short_premium
        )

        return {

            "strategy":
                "BULL_CALL_SPREAD",

            "legs":
                legs,

            "net_debit":
                net_debit,

            "break_even":
                long_strike
                + net_debit,

            "max_loss":
                net_debit
                * quantity,

            "max_profit":
                (
                    short_strike
                    - long_strike
                    - net_debit
                )
                * quantity,

        }

    # ========================================================
    # BEAR PUT SPREAD
    # ========================================================

    def bear_put_spread(
        self,
        long_strike: float,
        short_strike: float,
        long_premium: float,
        short_premium: float,
        quantity: int = 1,
    ) -> Dict[str, Any]:

        if short_strike >= long_strike:

            raise ValueError(
                "Bear Put Spread requires "
                "short_strike < long_strike."
            )

        legs = [

            StrategyLeg(
                option_type="P",
                strike=long_strike,
                premium=long_premium,
                quantity=quantity,
                side="BUY",
            ),

            StrategyLeg(
                option_type="P",
                strike=short_strike,
                premium=short_premium,
                quantity=quantity,
                side="SELL",
            ),

        ]

        net_debit = (
            long_premium
            - short_premium
        )

        return {

            "strategy":
                "BEAR_PUT_SPREAD",

            "legs":
                legs,

            "net_debit":
                net_debit,

            "break_even":
                long_strike
                - net_debit,

            "max_loss":
                net_debit
                * quantity,

            "max_profit":
                (
                    long_strike
                    - short_strike
                    - net_debit
                )
                * quantity,

        }

    # ========================================================
    # LONG STRADDLE
    # ========================================================

    def long_straddle(
        self,
        strike: float,
        call_premium: float,
        put_premium: float,
        quantity: int = 1,
    ) -> Dict[str, Any]:

        total_premium = (
            call_premium
            + put_premium
        )

        legs = [

            StrategyLeg(
                option_type="C",
                strike=strike,
                premium=call_premium,
                quantity=quantity,
                side="BUY",
            ),

            StrategyLeg(
                option_type="P",
                strike=strike,
                premium=put_premium,
                quantity=quantity,
                side="BUY",
            ),

        ]

        return {

            "strategy":
                "LONG_STRADDLE",

            "legs":
                legs,

            "premium":
                total_premium,

            "upper_break_even":
                strike
                + total_premium,

            "lower_break_even":
                strike
                - total_premium,

            "max_loss":
                total_premium
                * quantity,

            "max_profit":
                "UNLIMITED_ON_CALL_SIDE",

        }

    # ========================================================
    # LONG STRANGLE
    # ========================================================

    def long_strangle(
        self,
        put_strike: float,
        call_strike: float,
        put_premium: float,
        call_premium: float,
        quantity: int = 1,
    ) -> Dict[str, Any]:

        if put_strike >= call_strike:

            raise ValueError(
                "Long Strangle requires "
                "put_strike < call_strike."
            )

        total_premium = (
            put_premium
            + call_premium
        )

        legs = [

            StrategyLeg(
                option_type="P",
                strike=put_strike,
                premium=put_premium,
                quantity=quantity,
                side="BUY",
            ),

            StrategyLeg(
                option_type="C",
                strike=call_strike,
                premium=call_premium,
                quantity=quantity,
                side="BUY",
            ),

        ]

        return {

            "strategy":
                "LONG_STRANGLE",

            "legs":
                legs,

            "premium":
                total_premium,

            "lower_break_even":
                put_strike
                - total_premium,

            "upper_break_even":
                call_strike
                + total_premium,

            "max_loss":
                total_premium
                * quantity,

            "max_profit":
                "UNLIMITED",

        }

    # ========================================================
    # IRON CONDOR
    # ========================================================

    def iron_condor(
        self,
        long_put_strike: float,
        short_put_strike: float,
        short_call_strike: float,
        long_call_strike: float,
        long_put_premium: float,
        short_put_premium: float,
        short_call_premium: float,
        long_call_premium: float,
        quantity: int = 1,
    ) -> Dict[str, Any]:

        if not (
            long_put_strike
            < short_put_strike
            < short_call_strike
            < long_call_strike
        ):

            raise ValueError(
                "Iron Condor strikes must satisfy: "
                "long put < short put < "
                "short call < long call."
            )

        legs = [

            StrategyLeg(
                option_type="P",
                strike=long_put_strike,
                premium=long_put_premium,
                quantity=quantity,
                side="BUY",
            ),

            StrategyLeg(
                option_type="P",
                strike=short_put_strike,
                premium=short_put_premium,
                quantity=quantity,
                side="SELL",
            ),

            StrategyLeg(
                option_type="C",
                strike=short_call_strike,
                premium=short_call_premium,
                quantity=quantity,
                side="SELL",
            ),

            StrategyLeg(
                option_type="C",
                strike=long_call_strike,
                premium=long_call_premium,
                quantity=quantity,
                side="BUY",
            ),

        ]

        credit = (

            short_put_premium
            + short_call_premium

            -

            long_put_premium
            - long_call_premium

        )

        put_width = (
            short_put_strike
            - long_put_strike
        )

        call_width = (
            long_call_strike
            - short_call_strike
        )

        max_width = max(
            put_width,
            call_width,
        )

        max_loss = (
            max_width
            - credit
        )

        lower_break_even = (
            short_put_strike
            - credit
        )

        upper_break_even = (
            short_call_strike
            + credit
        )

        return {

            "strategy":
                "IRON_CONDOR",

            "legs":
                legs,

            "net_credit":
                credit,

            "lower_break_even":
                lower_break_even,

            "upper_break_even":
                upper_break_even,

            "max_profit":
                credit
                * quantity,

            "max_loss":
                max_loss
                * quantity,

        }

    # ========================================================
    # OPTION ANALYSIS
    # ========================================================

    def analyze_option(
        self,
        spot: float,
        strike: float,
        premium: float,
        expiry_days: float,
        volatility: float,
        option_type: str,
        risk_free_rate: Optional[float] = None,
        dividend_yield: float = 0.0,
    ) -> Dict[str, Any]:

        option_type = (
            self.validate_option_type(
                option_type
            )
        )

        theoretical = (
            self.theoretical_price(
                spot=spot,
                strike=strike,
                expiry_days=expiry_days,
                volatility=volatility,
                option_type=option_type,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
            )
        )

        greeks = (
            self.greeks(
                spot=spot,
                strike=strike,
                expiry_days=expiry_days,
                volatility=volatility,
                option_type=option_type,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
            )
        )

        intrinsic = (
            self.intrinsic_value(
                spot=spot,
                strike=strike,
                option_type=option_type,
            )
        )

        extrinsic = (
            self.extrinsic_value(
                premium=premium,
                spot=spot,
                strike=strike,
                option_type=option_type,
            )
        )

        implied_vol = (
            self.implied_volatility(
                market_price=premium,
                spot=spot,
                strike=strike,
                expiry_days=expiry_days,
                option_type=option_type,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
            )
        )

        break_even = (
            self.break_even(
                strike=strike,
                premium=premium,
                option_type=option_type,
            )
        )

        return {

            "success":
                True,

            "option_type":
                option_type,

            "spot":
                spot,

            "strike":
                strike,

            "premium":
                premium,

            "expiry_days":
                expiry_days,

            "theoretical_price":
                theoretical,

            "intrinsic_value":
                intrinsic,

            "extrinsic_value":
                extrinsic,

            "implied_volatility":
                implied_vol,

            "break_even":
                break_even,

            "greeks": {

                "delta":
                    greeks.delta,

                "gamma":
                    greeks.gamma,

                "theta_per_day":
                    greeks.theta,

                "vega_per_1pct":
                    greeks.vega,

                "rho":
                    greeks.rho,

            },

        }


# ============================================================
# GLOBAL ENGINE
# ============================================================

options_engine = OptionsEngine()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def analyze_option(
    spot,
    strike,
    premium,
    expiry_days,
    volatility,
    option_type,
    risk_free_rate=0.06,
    dividend_yield=0.0,
):

    return options_engine.analyze_option(

        spot=spot,

        strike=strike,

        premium=premium,

        expiry_days=expiry_days,

        volatility=volatility,

        option_type=option_type,

        risk_free_rate=risk_free_rate,

        dividend_yield=dividend_yield,

    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTIONS ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    # Example only.
    #
    # These are illustrative numbers for testing the engine.
    # They are NOT live market quotes.

    spot = 24_366.0

    strike = 24_400.0

    premium = 300.0

    expiry_days = 20

    volatility = 0.18

    print(
        "ILLUSTRATIVE OPTION ANALYSIS"
    )

    print(
        "Spot:",
        spot,
    )

    print(
        "Strike:",
        strike,
    )

    print(
        "Premium:",
        premium,
    )

    print(
        "Expiry days:",
        expiry_days,
    )

    print(
        "Volatility:",
        volatility,
    )

    print()

    result = analyze_option(

        spot=spot,

        strike=strike,

        premium=premium,

        expiry_days=expiry_days,

        volatility=volatility,

        option_type="C",

    )

    print(
        "Success:",
        result.get(
            "success"
        ),
    )

    print(
        "Theoretical Price:",
        result.get(
            "theoretical_price"
        ),
    )

    print(
        "Intrinsic:",
        result.get(
            "intrinsic_value"
        ),
    )

    print(
        "Extrinsic:",
        result.get(
            "extrinsic_value"
        ),
    )

    print(
        "Implied Volatility:",
        result.get(
            "implied_volatility"
        ),
    )

    print(
        "Break-even:",
        result.get(
            "break_even"
        ),
    )

    print()

    print(
        "Greeks:"
    )

    for key, value in result[
        "greeks"
    ].items():

        print(
            f"  {key}: "
            f"{value}"
        )

    # --------------------------------------------------------
    # Bull call spread
    # --------------------------------------------------------

    print()

    print(
        "BULL CALL SPREAD"
    )

    spread = (
        options_engine.bull_call_spread(

            long_strike=24_300,

            short_strike=24_600,

            long_premium=350,

            short_premium=180,

        )
    )

    for key, value in spread.items():

        if key != "legs":

            print(
                f"  {key}: "
                f"{value}"
            )

    # --------------------------------------------------------
    # Straddle
    # --------------------------------------------------------

    print()

    print(
        "LONG STRADDLE"
    )

    straddle = (
        options_engine.long_straddle(

            strike=24_400,

            call_premium=300,

            put_premium=280,

        )
    )

    for key, value in straddle.items():

        if key != "legs":

            print(
                f"  {key}: "
                f"{value}"
            )

    # --------------------------------------------------------
    # Iron Condor
    # --------------------------------------------------------

    print()

    print(
        "IRON CONDOR"
    )

    condor = (
        options_engine.iron_condor(

            long_put_strike=24_000,

            short_put_strike=24_200,

            short_call_strike=24_600,

            long_call_strike=24_800,

            long_put_premium=80,

            short_put_premium=140,

            short_call_premium=130,

            long_call_premium=70,

        )
    )

    for key, value in condor.items():

        if key != "legs":

            print(
                f"  {key}: "
                f"{value}"
            )

    print()

    print(
        "Options Engine loaded successfully."
    )