from __future__ import annotations

from statistics import (
    fmean,
    pstdev,
)


from omni.trading_intelligence.iv_analytics import (
    strike_iv_skew,
)


def _sum(
    contracts,
    field,
):

    return sum(
        float(
            getattr(
                contract,
                field
            )
            or 0.0
        )

        for contract
        in contracts
    )


def _ratio(
    numerator,
    denominator,
):

    if denominator == 0:

        return None


    return (
        numerator
        / denominator
    )


def _max_contract(
    contracts,
    field,
):

    candidates = [
        contract

        for contract
        in contracts

        if getattr(
            contract,
            field
        )
        is not None
    ]


    if not candidates:

        return None


    contract = max(
        candidates,
        key=lambda item:
            float(
                getattr(
                    item,
                    field
                )
                or 0.0
            ),
    )


    return contract.to_dict()


def _liquidity_score(
    contract,
    max_volume,
    max_oi,
):

    spread_score = 0.0


    spread_pct = (
        contract.spread_pct
    )


    if spread_pct is not None:

        if spread_pct <= 0.002:
            spread_score = 40.0

        elif spread_pct <= 0.005:
            spread_score = 35.0

        elif spread_pct <= 0.01:
            spread_score = 30.0

        elif spread_pct <= 0.02:
            spread_score = 20.0

        elif spread_pct <= 0.05:
            spread_score = 10.0


    volume = float(
        contract.volume
        or 0.0
    )


    oi = float(
        contract.open_interest
        or 0.0
    )


    volume_score = (
        min(
            30.0,
            30.0
            * volume
            / max_volume,
        )
        if max_volume > 0
        else 0.0
    )


    oi_score = (
        min(
            30.0,
            30.0
            * oi
            / max_oi,
        )
        if max_oi > 0
        else 0.0
    )


    return (
        spread_score
        + volume_score
        + oi_score
    )


def _cross_sectional_zscores(
    contracts,
    field,
):

    values = [
        float(
            getattr(
                contract,
                field
            )
            or 0.0
        )

        for contract
        in contracts
    ]


    if len(
        values
    ) < 2:

        return [
            0.0

            for _ in values
        ]


    mean = fmean(
        values
    )

    sigma = pstdev(
        values
    )


    if sigma == 0:

        return [
            0.0

            for _ in values
        ]


    return [
        (
            value
            - mean
        )
        / sigma

        for value in values
    ]


def max_pain_research(
    snapshot,
):

    strikes = list(
        snapshot.strikes
    )


    payouts = []


    for settlement in strikes:

        total = 0.0


        for contract in snapshot.contracts:

            oi = float(
                contract.open_interest
                or 0.0
            )


            if contract.option_type == "call":

                intrinsic = max(
                    0.0,
                    settlement
                    - contract.strike,
                )


            else:

                intrinsic = max(
                    0.0,
                    contract.strike
                    - settlement,
                )


            total += (
                intrinsic
                * oi
            )


        payouts.append(
            {
                "settlement":
                    settlement,

                "writer_intrinsic_payout":
                    total,
            }
        )


    best = min(
        payouts,
        key=lambda item:
            item[
                "writer_intrinsic_payout"
            ],
    )


    return {
        "strike":
            best[
                "settlement"
            ],

        "payout":
            best[
                "writer_intrinsic_payout"
            ],

        "surface":
            tuple(
                payouts
            ),

        "predictive_claim":
            False,

        "research_only":
            True,
    }


class OptionChainIntelligence:

    def analyze(
        self,
        snapshot,
    ):

        calls = [
            contract

            for contract
            in snapshot.contracts

            if contract.option_type
            == "call"
        ]


        puts = [
            contract

            for contract
            in snapshot.contracts

            if contract.option_type
            == "put"
        ]


        if (
            not calls
            or not puts
        ):

            raise ValueError(
                "Chain requires both calls and puts."
            )


        atm_strike = min(
            snapshot.strikes,
            key=lambda strike:
                abs(
                    strike
                    - snapshot.spot
                ),
        )


        atm_call = min(
            calls,
            key=lambda contract:
                abs(
                    contract.strike
                    - atm_strike
                ),
        )


        atm_put = min(
            puts,
            key=lambda contract:
                abs(
                    contract.strike
                    - atm_strike
                ),
        )


        call_oi = _sum(
            calls,
            "open_interest",
        )

        put_oi = _sum(
            puts,
            "open_interest",
        )


        call_volume = _sum(
            calls,
            "volume",
        )

        put_volume = _sum(
            puts,
            "volume",
        )


        call_doi = _sum(
            calls,
            "change_in_oi",
        )

        put_doi = _sum(
            puts,
            "change_in_oi",
        )


        max_volume = max(
            (
                float(
                    contract.volume
                    or 0.0
                )

                for contract
                in snapshot.contracts
            ),
            default=0.0,
        )


        max_oi = max(
            (
                float(
                    contract.open_interest
                    or 0.0
                )

                for contract
                in snapshot.contracts
            ),
            default=0.0,
        )


        liquidity_rows = []


        for contract in snapshot.contracts:

            liquidity_rows.append(
                {
                    "symbol":
                        contract.symbol,

                    "strike":
                        contract.strike,

                    "option_type":
                        contract.option_type,

                    "score":
                        _liquidity_score(
                            contract,
                            max_volume,
                            max_oi,
                        ),

                    "spread_pct":
                        contract.spread_pct,

                    "volume":
                        contract.volume,

                    "open_interest":
                        contract.open_interest,
                }
            )


        near_atm = sorted(
            liquidity_rows,
            key=lambda item:
                abs(
                    item[
                        "strike"
                    ]
                    - snapshot.spot
                ),
        )[
            :min(
                6,
                len(
                    liquidity_rows
                ),
            )
        ]


        chain_liquidity = (
            fmean(
                item[
                    "score"
                ]

                for item in near_atm
            )
            if near_atm
            else 0.0
        )


        volume_z = (
            _cross_sectional_zscores(
                snapshot.contracts,
                "volume",
            )
        )


        oi_z = (
            _cross_sectional_zscores(
                snapshot.contracts,
                "open_interest",
            )
        )


        unusual = []


        for contract, vz, oz in zip(
            snapshot.contracts,
            volume_z,
            oi_z,
        ):

            if (
                vz >= 2.0
                or oz >= 2.0
            ):

                unusual.append(
                    {
                        "symbol":
                            contract.symbol,

                        "strike":
                            contract.strike,

                        "option_type":
                            contract.option_type,

                        "volume_z":
                            vz,

                        "oi_z":
                            oz,
                    }
                )


        call_ivs = [
            contract.implied_volatility

            for contract in calls

            if contract.implied_volatility
            is not None
        ]


        put_ivs = [
            contract.implied_volatility

            for contract in puts

            if contract.implied_volatility
            is not None
        ]


        average_call_iv = (
            fmean(
                call_ivs
            )
            if call_ivs
            else None
        )


        average_put_iv = (
            fmean(
                put_ivs
            )
            if put_ivs
            else None
        )


        return {
            "success":
                True,

            "underlying":
                snapshot.underlying,

            "spot":
                snapshot.spot,

            "timestamp":
                snapshot.timestamp,

            "expiries":
                snapshot.expiries,

            "atm_strike":
                atm_strike,

            "atm_call":
                atm_call.to_dict(),

            "atm_put":
                atm_put.to_dict(),

            "call_oi":
                call_oi,

            "put_oi":
                put_oi,

            "pcr_oi":
                _ratio(
                    put_oi,
                    call_oi,
                ),

            "call_volume":
                call_volume,

            "put_volume":
                put_volume,

            "pcr_volume":
                _ratio(
                    put_volume,
                    call_volume,
                ),

            "call_change_in_oi":
                call_doi,

            "put_change_in_oi":
                put_doi,

            "pcr_change_in_oi":
                _ratio(
                    put_doi,
                    call_doi,
                ),

            "call_oi_wall":
                _max_contract(
                    calls,
                    "open_interest",
                ),

            "put_oi_wall":
                _max_contract(
                    puts,
                    "open_interest",
                ),

            "call_volume_leader":
                _max_contract(
                    calls,
                    "volume",
                ),

            "put_volume_leader":
                _max_contract(
                    puts,
                    "volume",
                ),

            "average_call_iv":
                average_call_iv,

            "average_put_iv":
                average_put_iv,

            "put_minus_call_iv":
                (
                    average_put_iv
                    - average_call_iv

                    if (
                        average_put_iv
                        is not None
                        and average_call_iv
                        is not None
                    )

                    else None
                ),

            "strike_iv_skew":
                strike_iv_skew(
                    snapshot
                ),

            "liquidity":
                tuple(
                    liquidity_rows
                ),

            "chain_liquidity_score":
                chain_liquidity,

            "unusual_contracts":
                tuple(
                    unusual
                ),

            "max_pain_research":
                max_pain_research(
                    snapshot
                ),

            "predictive_claim":
                False,

            "research_only":
                True,
        }


option_chain_intelligence = (
    OptionChainIntelligence()
)
