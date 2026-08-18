from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import uuid


def _number(
    value,
):

    if value in (
        None,
        "",
    ):

        return None


    try:

        return float(
            value
        )

    except Exception:

        return None


def _integer(
    value,
):

    number = _number(
        value
    )


    return (
        int(
            number
        )

        if number is not None

        else None
    )


def normalize_fyers_option_chain(
    worker_result,
    *,
    captured_at=None,
):

    if not isinstance(
        worker_result,
        dict,
    ):

        raise ValueError(
            "FYERS result must be a dictionary."
        )


    response = worker_result.get(
        "response"
    )


    request = dict(
        worker_result.get(
            "request",
            {}
        )
    )


    if not isinstance(
        response,
        dict,
    ):

        raise ValueError(
            "FYERS response is not a dictionary."
        )


    status = str(
        response.get(
            "s",
            "",
        )
    ).lower()


    if (
        status == "error"
        or (
            response.get(
                "code"
            )
            is not None
            and _number(
                response.get(
                    "code"
                )
            )
            is not None
            and float(
                response.get(
                    "code"
                )
            ) < 0
        )
    ):

        raise RuntimeError(
            str(
                response.get(
                    "message",
                    "FYERS option-chain request failed.",
                )
            )
        )


    data = response.get(
        "data",
        {}
    )


    if not isinstance(
        data,
        dict,
    ):

        raise ValueError(
            "FYERS response data is invalid."
        )


    chain = data.get(
        "optionsChain",
        ()
    )


    if not isinstance(
        chain,
        (
            list,
            tuple,
        ),
    ):

        raise ValueError(
            "optionsChain is invalid."
        )


    if captured_at is None:

        captured_at = datetime.now(
            timezone.utc
        )


    if captured_at.tzinfo is None:

        captured_at = (
            captured_at.replace(
                tzinfo=timezone.utc
            )
        )


    captured_at = (
        captured_at
        .astimezone(
            timezone.utc
        )
    )


    expiry_data = data.get(
        "expiryData",
        ()
    )


    if not isinstance(
        expiry_data,
        (
            list,
            tuple,
        ),
    ):

        expiry_data = ()


    selected_expiry = request.get(
        "timestamp"
    )


    if (
        selected_expiry is None
        and expiry_data
        and isinstance(
            expiry_data[
                0
            ],
            dict,
        )
    ):

        selected_expiry = (
            expiry_data[
                0
            ].get(
                "expiry"
            )
        )


    spot = None

    legs = []


    for item in chain:

        if not isinstance(
            item,
            dict,
        ):

            continue


        option_type = str(
            item.get(
                "option_type",
                "",
            )
        ).upper()


        if option_type not in {
            "CE",
            "PE",
        }:

            if spot is None:

                candidate = _number(
                    item.get(
                        "ltp"
                    )
                )


                if candidate is not None:

                    spot = candidate

            continue


        greeks = item.get(
            "greeks",
            {}
        )


        if not isinstance(
            greeks,
            dict,
        ):

            greeks = {}


        strike = _number(
            item.get(
                "strike_price"
            )
        )


        if strike is None:

            continue


        leg = {
            "symbol":
                item.get(
                    "symbol"
                ),

            "fy_token":
                item.get(
                    "fyToken"
                ),

            "option_type":
                option_type,

            "strike":
                strike,

            "ltp":
                _number(
                    item.get(
                        "ltp"
                    )
                ),

            "ltp_change":
                _number(
                    item.get(
                        "ltpch"
                    )
                ),

            "ltp_change_pct":
                _number(
                    item.get(
                        "ltpchp"
                    )
                ),

            "bid":
                _number(
                    item.get(
                        "bid"
                    )
                ),

            "ask":
                _number(
                    item.get(
                        "ask"
                    )
                ),

            "oi":
                _integer(
                    item.get(
                        "oi"
                    )
                ),

            "oi_change":
                _integer(
                    item.get(
                        "oich"
                    )
                ),

            "oi_change_pct":
                _number(
                    item.get(
                        "oichp"
                    )
                ),

            "previous_oi":
                _integer(
                    item.get(
                        "prev_oi"
                    )
                ),

            "volume":
                _integer(
                    item.get(
                        "volume"
                    )
                ),

            "delta":
                _number(
                    greeks.get(
                        "delta"
                    )
                ),

            "gamma":
                _number(
                    greeks.get(
                        "gamma"
                    )
                ),

            "theta":
                _number(
                    greeks.get(
                        "theta"
                    )
                ),

            "vega":
                _number(
                    greeks.get(
                        "vega"
                    )
                ),

            "iv":
                _number(
                    greeks.get(
                        "iv"
                    )
                ),

            "expiry":
                (
                    str(
                        selected_expiry
                    )
                    if selected_expiry
                    is not None
                    else None
                ),
        }


        legs.append(
            leg
        )


    strikes = sorted(
        {
            leg[
                "strike"
            ]

            for leg in legs
        }
    )


    atm_strike = None


    if (
        spot is not None
        and strikes
    ):

        atm_strike = min(
            strikes,
            key=lambda strike:
                abs(
                    strike
                    - spot
                ),
        )


    atm_call_iv = None

    atm_put_iv = None


    if atm_strike is not None:

        for leg in legs:

            if leg[
                "strike"
            ] != atm_strike:

                continue


            if (
                leg[
                    "option_type"
                ] == "CE"
            ):

                atm_call_iv = (
                    leg[
                        "iv"
                    ]
                )


            elif (
                leg[
                    "option_type"
                ] == "PE"
            ):

                atm_put_iv = (
                    leg[
                        "iv"
                    ]
                )


    atm_values = [
        value

        for value in (
            atm_call_iv,
            atm_put_iv,
        )

        if value is not None
    ]


    atm_iv = (
        sum(
            atm_values
        )
        / len(
            atm_values
        )

        if atm_values

        else None
    )


    atm_skew = (
        atm_put_iv
        - atm_call_iv

        if (
            atm_put_iv
            is not None
            and atm_call_iv
            is not None
        )

        else None
    )


    call_oi = _integer(
        data.get(
            "callOi"
        )
    )


    put_oi = _integer(
        data.get(
            "putOi"
        )
    )


    pcr_oi = (
        put_oi
        / call_oi

        if (
            put_oi is not None
            and call_oi not in (
                None,
                0,
            )
        )

        else None
    )


    return {
        "snapshot_id":
            (
                "chain-"
                + uuid.uuid4()
                .hex
            ),

        "provider":
            "fyers_v3_optionchain",

        "sdk_version":
            worker_result.get(
                "sdk_version"
            ),

        "symbol":
            str(
                request.get(
                    "symbol",
                    "",
                )
            ),

        "captured_at":
            captured_at.isoformat(),

        "selected_expiry":
            (
                str(
                    selected_expiry
                )
                if selected_expiry
                is not None
                else None
            ),

        "strikecount":
            request.get(
                "strikecount"
            ),

        "greeks_requested":
            (
                str(
                    request.get(
                        "greeks",
                        ""
                    )
                )
                == "1"
            ),

        "spot":
            spot,

        "call_oi":
            call_oi,

        "put_oi":
            put_oi,

        "pcr_oi":
            pcr_oi,

        "atm_strike":
            atm_strike,

        "atm_call_iv":
            atm_call_iv,

        "atm_put_iv":
            atm_put_iv,

        "atm_iv":
            atm_iv,

        "atm_skew":
            atm_skew,

        "expiry_data":
            tuple(
                expiry_data
            ),

        "legs":
            tuple(
                legs
            ),

        "raw_response":
            response,

        "read_only":
            True,

        "broker_order":
            False,

        "live_execution":
            False,
    }
