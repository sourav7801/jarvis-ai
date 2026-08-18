from __future__ import annotations

from math import (
    erf,
    exp,
    log,
    pi,
    sqrt,
)


def _normal_cdf(
    value,
):

    return (
        0.5
        * (
            1.0
            + erf(
                value
                / sqrt(
                    2.0
                )
            )
        )
    )


def _normal_pdf(
    value,
):

    return (
        exp(
            -0.5
            * value
            * value
        )
        / sqrt(
            2.0
            * pi
        )
    )


def _option_type(
    value,
):

    text = str(
        value
    ).strip().lower()


    if text in {
        "call",
        "ce",
        "c",
    }:

        return "call"


    if text in {
        "put",
        "pe",
        "p",
    }:

        return "put"


    raise ValueError(
        "option_type must be call/put or CE/PE."
    )


def intrinsic_value(
    spot,
    strike,
    option_type,
):

    option_type = _option_type(
        option_type
    )


    spot = float(
        spot
    )

    strike = float(
        strike
    )


    if option_type == "call":

        return max(
            0.0,
            spot - strike,
        )


    return max(
        0.0,
        strike - spot,
    )


def moneyness(
    spot,
    strike,
    option_type,
    *,
    atm_tolerance=0.0025,
):

    option_type = _option_type(
        option_type
    )


    spot = float(
        spot
    )

    strike = float(
        strike
    )


    if spot <= 0:

        raise ValueError(
            "spot must be positive."
        )


    distance = (
        strike
        / spot
        - 1.0
    )


    if abs(
        distance
    ) <= float(
        atm_tolerance
    ):

        return "ATM"


    if option_type == "call":

        return (
            "ITM"
            if strike < spot
            else "OTM"
        )


    return (
        "ITM"
        if strike > spot
        else "OTM"
    )


def black_scholes_greeks(
    spot,
    strike,
    time_to_expiry_years,
    risk_free_rate,
    volatility,
    option_type,
    *,
    dividend_yield=0.0,
):

    option_type = _option_type(
        option_type
    )


    spot = float(
        spot
    )

    strike = float(
        strike
    )

    t = float(
        time_to_expiry_years
    )

    rate = float(
        risk_free_rate
    )

    volatility = float(
        volatility
    )

    q = float(
        dividend_yield
    )


    if (
        spot <= 0
        or strike <= 0
    ):

        raise ValueError(
            "spot and strike must be positive."
        )


    if (
        t <= 0
        or volatility <= 0
    ):

        return {
            "model":
                "black_scholes_european",

            "price":
                intrinsic_value(
                    spot,
                    strike,
                    option_type,
                ),

            "delta":
                (
                    1.0
                    if (
                        option_type == "call"
                        and spot > strike
                    )
                    else (
                        -1.0
                        if (
                            option_type == "put"
                            and spot < strike
                        )
                        else 0.0
                    )
                ),

            "gamma":
                0.0,

            "theta":
                0.0,

            "vega":
                0.0,
        }


    sigma_sqrt_t = (
        volatility
        * sqrt(
            t
        )
    )


    d1 = (
        (
            log(
                spot
                / strike
            )
            + (
                rate
                - q
                + 0.5
                * volatility
                * volatility
            )
            * t
        )
        / sigma_sqrt_t
    )


    d2 = (
        d1
        - sigma_sqrt_t
    )


    discount_r = exp(
        -rate
        * t
    )

    discount_q = exp(
        -q
        * t
    )


    if option_type == "call":

        price = (
            spot
            * discount_q
            * _normal_cdf(
                d1
            )
            - strike
            * discount_r
            * _normal_cdf(
                d2
            )
        )


        delta = (
            discount_q
            * _normal_cdf(
                d1
            )
        )


        theta = (
            -spot
            * discount_q
            * _normal_pdf(
                d1
            )
            * volatility
            / (
                2.0
                * sqrt(
                    t
                )
            )
            - rate
            * strike
            * discount_r
            * _normal_cdf(
                d2
            )
            + q
            * spot
            * discount_q
            * _normal_cdf(
                d1
            )
        )


    else:

        price = (
            strike
            * discount_r
            * _normal_cdf(
                -d2
            )
            - spot
            * discount_q
            * _normal_cdf(
                -d1
            )
        )


        delta = (
            discount_q
            * (
                _normal_cdf(
                    d1
                )
                - 1.0
            )
        )


        theta = (
            -spot
            * discount_q
            * _normal_pdf(
                d1
            )
            * volatility
            / (
                2.0
                * sqrt(
                    t
                )
            )
            + rate
            * strike
            * discount_r
            * _normal_cdf(
                -d2
            )
            - q
            * spot
            * discount_q
            * _normal_cdf(
                -d1
            )
        )


    gamma = (
        discount_q
        * _normal_pdf(
            d1
        )
        / (
            spot
            * volatility
            * sqrt(
                t
            )
        )
    )


    vega = (
        spot
        * discount_q
        * _normal_pdf(
            d1
        )
        * sqrt(
            t
        )
    )


    return {
        "model":
            "black_scholes_european",

        "price":
            price,

        "delta":
            delta,

        "gamma":
            gamma,

        "theta":
            (
                theta
                / 365.0
            ),

        "vega":
            (
                vega
                / 100.0
            ),
    }


def option_feature_snapshot(
    *,
    spot,
    strike,
    option_type,
    premium,
    bid=None,
    ask=None,
    open_interest=None,
    change_in_oi=None,
    volume=None,
    implied_volatility=None,
    time_to_expiry_years=None,
    risk_free_rate=0.0,
    dividend_yield=0.0,
):

    spot = float(
        spot
    )

    strike = float(
        strike
    )

    premium = float(
        premium
    )


    intrinsic = intrinsic_value(
        spot,
        strike,
        option_type,
    )


    midpoint = None

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
            ask - bid,
        )

        midpoint = (
            bid
            + ask
        ) / 2.0


        if midpoint > 0:

            spread_pct = (
                spread
                / midpoint
            )


    greeks = None


    if (
        implied_volatility is not None
        and time_to_expiry_years is not None
    ):

        iv = float(
            implied_volatility
        )


        if iv > 3.0:

            iv = (
                iv
                / 100.0
            )


        greeks = black_scholes_greeks(
            spot,
            strike,
            time_to_expiry_years,
            risk_free_rate,
            iv,
            option_type,
            dividend_yield=
                dividend_yield,
        )


    return {
        "spot":
            spot,

        "strike":
            strike,

        "option_type":
            _option_type(
                option_type
            ),

        "premium":
            premium,

        "intrinsic_value":
            intrinsic,

        "extrinsic_value":
            max(
                0.0,
                premium
                - intrinsic,
            ),

        "moneyness":
            moneyness(
                spot,
                strike,
                option_type,
            ),

        "bid":
            bid,

        "ask":
            ask,

        "mid":
            midpoint,

        "spread":
            spread,

        "spread_pct":
            spread_pct,

        "open_interest":
            open_interest,

        "change_in_oi":
            change_in_oi,

        "volume":
            volume,

        "implied_volatility":
            implied_volatility,

        "greeks":
            greeks,
    }
