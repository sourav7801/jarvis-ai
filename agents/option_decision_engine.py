# ============================================================
# JARVIS OPTION DECISION ENGINE
# V2
# ============================================================
#
# Converts a VERIFIED underlying setup into an option
# strategy candidate.
#
# IMPORTANT:
#   No broker orders.
#   Invalid option structures are rejected.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import math


class OptionDecisionEngine:

    def __init__(
        self,
        min_setup_strength: float = 75.0,
        min_liquidity_score: float = 60.0,
        max_iv: float = 45.0,
        max_spread_percent: float = 2.5,
        min_dte: int = 2,
        max_dte: int = 45,
        min_option_volume: int = 1000,
        min_oi: int = 5000,
        min_spread_rr: float = 1.5,
    ):

        self.min_setup_strength = float(
            min_setup_strength
        )

        self.min_liquidity_score = float(
            min_liquidity_score
        )

        self.max_iv = float(
            max_iv
        )

        self.max_spread_percent = float(
            max_spread_percent
        )

        self.min_dte = int(
            min_dte
        )

        self.max_dte = int(
            max_dte
        )

        self.min_option_volume = int(
            min_option_volume
        )

        self.min_oi = int(
            min_oi
        )

        self.min_spread_rr = float(
            min_spread_rr
        )

    # ========================================================
    # SAFE NUMBER
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
    # BIAS
    # ========================================================

    @staticmethod
    def normalize_bias(
        bias: str,
    ) -> str:

        value = (
            str(bias)
            .upper()
            .strip()
        )

        if value in {
            "BULL",
            "BULLISH",
            "LONG",
        }:
            return "BULLISH"

        if value in {
            "BEAR",
            "BEARISH",
            "SHORT",
        }:
            return "BEARISH"

        return "RANGE"

    # ========================================================
    # OPTION TYPE
    # ========================================================

    @staticmethod
    def option_type(
        value: Any,
    ) -> str:

        value = (
            str(value or "")
            .upper()
            .strip()
        )

        if value in {
            "CALL",
            "CE",
            "C",
        }:
            return "CALL"

        if value in {
            "PUT",
            "PE",
            "P",
        }:
            return "PUT"

        return value

    # ========================================================
    # SPREAD %
    # ========================================================

    def spread_percent(
        self,
        row: Dict[str, Any],
    ) -> float:

        bid = self.number(
            row.get("bid")
        )

        ask = self.number(
            row.get("ask")
        )

        if (
            bid <= 0
            or ask <= 0
            or ask < bid
        ):
            return 999.0

        mid = (
            bid + ask
        ) / 2.0

        if mid <= 0:
            return 999.0

        return (
            (ask - bid)
            / mid
            * 100.0
        )

    # ========================================================
    # LIQUIDITY
    # ========================================================

    def liquidity_score(
        self,
        volume: float,
        oi: float,
        spread_percent: float,
    ) -> float:

        score = 0.0

        if volume >= self.min_option_volume:
            score += 30

        elif volume >= self.min_option_volume * 0.5:
            score += 20

        elif volume >= self.min_option_volume * 0.2:
            score += 10

        if oi >= self.min_oi:
            score += 30

        elif oi >= self.min_oi * 0.5:
            score += 20

        elif oi >= self.min_oi * 0.2:
            score += 10

        if spread_percent <= 0.5:
            score += 40

        elif spread_percent <= 1.0:
            score += 30

        elif spread_percent <= 2.0:
            score += 15

        return min(
            100.0,
            score,
        )

    # ========================================================
    # CONTRACT QUALITY
    # ========================================================

    def contract_quality(
        self,
        row: Dict[str, Any],
        option_type: str,
    ) -> Dict[str, Any]:

        option_type = self.option_type(
            option_type
        )

        if option_type == "CALL":

            ltp = self.number(
                row.get(
                    "call_ltp",
                    row.get("ltp")
                )
            )

            iv = self.number(
                row.get(
                    "call_iv",
                    row.get("iv")
                )
            )

            volume = self.number(
                row.get(
                    "call_volume",
                    row.get("volume")
                )
            )

            oi = self.number(
                row.get(
                    "call_oi",
                    row.get("oi")
                )
            )

            oi_change = self.number(
                row.get(
                    "call_oi_change"
                )
            )

            delta = self.number(
                row.get(
                    "call_delta",
                    row.get("delta")
                )
            )

        else:

            ltp = self.number(
                row.get(
                    "put_ltp",
                    row.get("ltp")
                )
            )

            iv = self.number(
                row.get(
                    "put_iv",
                    row.get("iv")
                )
            )

            volume = self.number(
                row.get(
                    "put_volume",
                    row.get("volume")
                )
            )

            oi = self.number(
                row.get(
                    "put_oi",
                    row.get("oi")
                )
            )

            oi_change = self.number(
                row.get(
                    "put_oi_change"
                )
            )

            delta = self.number(
                row.get(
                    "put_delta",
                    row.get("delta")
                )
            )

        spread = self.spread_percent(
            row
        )

        liquidity = self.liquidity_score(
            volume,
            oi,
            spread,
        )

        return {

            "ltp":
                ltp,

            "iv":
                iv,

            "volume":
                volume,

            "oi":
                oi,

            "oi_change":
                oi_change,

            "delta":
                delta,

            "spread_percent":
                spread,

            "liquidity_score":
                liquidity,

        }

    # ========================================================
    # ATM
    # ========================================================

    def find_atm(
        self,
        spot: float,
        rows: List[Dict[str, Any]],
    ) -> Optional[
        Dict[str, Any]
    ]:

        best = None
        distance = float("inf")

        for row in rows:

            strike = self.number(
                row.get("strike")
            )

            if strike <= 0:
                continue

            d = abs(
                strike - spot
            )

            if d < distance:

                distance = d
                best = row

        return best

    # ========================================================
    # STRIKE
    # ========================================================

    def find_strike(
        self,
        rows: List[Dict[str, Any]],
        strike: float,
    ) -> Optional[
        Dict[str, Any]
    ]:

        best = None
        distance = float("inf")

        for row in rows:

            current = self.number(
                row.get("strike")
            )

            if current <= 0:
                continue

            d = abs(
                current - strike
            )

            if d < distance:

                distance = d
                best = row

        return best

    # ========================================================
    # LONG OPTION
    # ========================================================

    def choose_long_option(
        self,
        rows: List[Dict[str, Any]],
        option_type: str,
        spot: float,
    ) -> Optional[
        Dict[str, Any]
    ]:

        best = None
        best_score = -1.0

        for row in rows:

            strike = self.number(
                row.get("strike")
            )

            if strike <= 0:
                continue

            quality = self.contract_quality(
                row,
                option_type,
            )

            if quality[
                "ltp"
            ] <= 0:
                continue

            if (
                quality[
                    "liquidity_score"
                ]
                <
                self.min_liquidity_score
            ):
                continue

            if (
                quality[
                    "iv"
                ] > self.max_iv
                and
                quality[
                    "iv"
                ] > 0
            ):
                continue

            # Prefer near-ATM, liquid contracts.
            moneyness_penalty = (
                abs(
                    strike - spot
                )
                /
                max(
                    spot,
                    1.0,
                )
                *
                1000.0
            )

            score = (

                quality[
                    "liquidity_score"
                ]
                * 0.60

                +
                max(
                    0.0,
                    40.0
                    -
                    moneyness_penalty,
                )
                * 0.40

            )

            if score > best_score:

                best_score = score

                best = {

                    "strike":
                        strike,

                    "option_type":
                        self.option_type(
                            option_type
                        ),

                    "price":
                        quality[
                            "ltp"
                        ],

                    "quality":
                        quality,

                    "selection_score":
                        round(
                            score,
                            2,
                        ),

                }

        return best

    # ========================================================
    # SPREAD CANDIDATE
    # ========================================================

    def spread_candidates(
        self,
        rows: List[Dict[str, Any]],
        option_type: str,
        direction: str,
        spot: float,
    ) -> List[
        Dict[str, Any]
    ]:

        valid = []

        for row in rows:

            strike = self.number(
                row.get("strike")
            )

            if strike <= 0:
                continue

            quality = self.contract_quality(
                row,
                option_type,
            )

            if quality["ltp"] <= 0:
                continue

            if (
                quality[
                    "liquidity_score"
                ]
                <
                self.min_liquidity_score
            ):
                continue

            valid.append({

                "row":
                    row,

                "strike":
                    strike,

                "quality":
                    quality,

            })

        if len(valid) < 2:
            return []

        valid.sort(
            key=lambda x:
                x["strike"]
        )

        candidates = []

        # ----------------------------------------------------
        # Try EVERY available strike pair.
        # This avoids forcing a bad 200-point spread.
        # ----------------------------------------------------

        for long_item in valid:

            for short_item in valid:

                long_strike = (
                    long_item[
                        "strike"
                    ]
                )

                short_strike = (
                    short_item[
                        "strike"
                    ]
                )

                if direction == "BULLISH":

                    if (
                        option_type == "CALL"
                        and
                        short_strike
                        <=
                        long_strike
                    ):
                        continue

                    if (
                        option_type == "PUT"
                        and
                        short_strike
                        >=
                        long_strike
                    ):
                        continue

                else:

                    if (
                        option_type == "PUT"
                        and
                        short_strike
                        >=
                        long_strike
                    ):
                        continue

                    if (
                        option_type == "CALL"
                        and
                        short_strike
                        <=
                        long_strike
                    ):
                        continue

                long_price = (
                    long_item[
                        "quality"
                    ][
                        "ltp"
                    ]
                )

                short_price = (
                    short_item[
                        "quality"
                    ][
                        "ltp"
                    ]
                )

                width = abs(
                    short_strike
                    -
                    long_strike
                )

                # ------------------------------------------------
                # Debit spread
                # ------------------------------------------------

                net_debit = (
                    long_price
                    -
                    short_price
                )

                if net_debit <= 0:
                    continue

                # CRITICAL SAFETY CHECK
                if net_debit >= width:
                    continue

                max_profit = (
                    width
                    -
                    net_debit
                )

                max_loss = (
                    net_debit
                )

                if max_profit <= 0:
                    continue

                if max_loss <= 0:
                    continue

                rr = (
                    max_profit
                    /
                    max_loss
                )

                if rr < self.min_spread_rr:
                    continue

                liquidity = min(

                    long_item[
                        "quality"
                    ][
                        "liquidity_score"
                    ],

                    short_item[
                        "quality"
                    ][
                        "liquidity_score"
                    ],

                )

                score = (

                    min(
                        100.0,
                        rr * 40.0,
                    )
                    * 0.50

                    +
                    liquidity
                    * 0.30

                    +
                    max(
                        0.0,
                        20.0
                        -
                        abs(
                            long_strike
                            -
                            spot
                        )
                        /
                        max(
                            spot,
                            1.0,
                        )
                        *
                        1000.0,
                    )
                    * 0.20

                )

                candidates.append({

                    "long_strike":
                        long_strike,

                    "short_strike":
                        short_strike,

                    "long_price":
                        long_price,

                    "short_price":
                        short_price,

                    "width":
                        width,

                    "net_debit":
                        net_debit,

                    "max_profit":
                        max_profit,

                    "max_loss":
                        max_loss,

                    "risk_reward":
                        rr,

                    "liquidity_score":
                        liquidity,

                    "selection_score":
                        score,

                })

        candidates.sort(

            key=lambda x:
                (
                    x["selection_score"],
                    x["risk_reward"],
                ),

            reverse=True,

        )

        return candidates

    # ========================================================
    # STRATEGIES
    # ========================================================

    def build_candidates(
        self,
        spot: float,
        bias: str,
        setup_strength: float,
        chain: Dict[str, Any],
    ) -> List[
        Dict[str, Any]
    ]:

        rows = chain.get(
            "rows",
            chain.get(
                "nearest_strikes",
                []
            )
        )

        calls = chain.get(
            "calls",
            rows,
        )

        puts = chain.get(
            "puts",
            rows,
        )

        candidates = []

        # ====================================================
        # BULLISH
        # ====================================================

        if bias == "BULLISH":

            # ------------------------------------------------
            # Long Call
            # ------------------------------------------------

            long_call = (
                self.choose_long_option(

                    rows=calls,

                    option_type="CALL",

                    spot=spot,

                )
            )

            if long_call:

                q = long_call[
                    "quality"
                ]

                score = (

                    setup_strength
                    * 0.55

                    +
                    q[
                        "liquidity_score"
                    ]
                    * 0.35

                    +
                    max(
                        0.0,
                        10.0
                        -
                        q[
                            "iv"
                        ] / 5.0,
                    )

                )

                candidates.append({

                    "strategy":
                        "LONG_CALL",

                    "direction":
                        "BULLISH",

                    "selection_score":
                        score,

                    "contract":
                        long_call,

                })

            # ------------------------------------------------
            # Bull Call Spreads
            # ------------------------------------------------

            spreads = (
                self.spread_candidates(

                    rows=calls,

                    option_type="CALL",

                    direction="BULLISH",

                    spot=spot,

                )
            )

            for spread in spreads[:5]:

                score = (

                    setup_strength
                    * 0.50

                    +
                    min(
                        100.0,
                        spread[
                            "risk_reward"
                        ] * 40.0,
                    )
                    * 0.30

                    +
                    spread[
                        "liquidity_score"
                    ]
                    * 0.20

                )

                candidates.append({

                    "strategy":
                        "BULL_CALL_SPREAD",

                    "direction":
                        "BULLISH",

                    "selection_score":
                        score,

                    "contract":
                        spread,

                })

        # ====================================================
        # BEARISH
        # ====================================================

        if bias == "BEARISH":

            # ------------------------------------------------
            # Long Put
            # ------------------------------------------------

            long_put = (
                self.choose_long_option(

                    rows=puts,

                    option_type="PUT",

                    spot=spot,

                )
            )

            if long_put:

                q = long_put[
                    "quality"
                ]

                score = (

                    setup_strength
                    * 0.55

                    +
                    q[
                        "liquidity_score"
                    ]
                    * 0.35

                    +
                    max(
                        0.0,
                        10.0
                        -
                        q[
                            "iv"
                        ] / 5.0,
                    )

                )

                candidates.append({

                    "strategy":
                        "LONG_PUT",

                    "direction":
                        "BEARISH",

                    "selection_score":
                        score,

                    "contract":
                        long_put,

                })

            # ------------------------------------------------
            # Bear Put Spreads
            # ------------------------------------------------

            spreads = (
                self.spread_candidates(

                    rows=puts,

                    option_type="PUT",

                    direction="BEARISH",

                    spot=spot,

                )
            )

            for spread in spreads[:5]:

                score = (

                    setup_strength
                    * 0.50

                    +
                    min(
                        100.0,
                        spread[
                            "risk_reward"
                        ] * 40.0,
                    )
                    * 0.30

                    +
                    spread[
                        "liquidity_score"
                    ]
                    * 0.20

                )

                candidates.append({

                    "strategy":
                        "BEAR_PUT_SPREAD",

                    "direction":
                        "BEARISH",

                    "selection_score":
                        score,

                    "contract":
                        spread,

                })

        # ====================================================
        # RANGE
        # ====================================================

        if bias == "RANGE":

            atm = self.find_atm(
                spot,
                rows,
            )

            if atm:

                call = self.contract_quality(
                    atm,
                    "CALL",
                )

                put = self.contract_quality(
                    atm,
                    "PUT",
                )

                liquidity = min(

                    call[
                        "liquidity_score"
                    ],

                    put[
                        "liquidity_score"
                    ],

                )

                premium = (

                    call[
                        "ltp"
                    ]
                    +
                    put[
                        "ltp"
                    ]

                )

                if (
                    liquidity
                    >=
                    self.min_liquidity_score
                    and
                    premium > 0
                ):

                    candidates.append({

                        "strategy":
                            "LONG_STRADDLE",

                        "direction":
                            "RANGE_BREAKOUT",

                        "selection_score":
                            (
                                setup_strength
                                * 0.60
                                +
                                liquidity
                                * 0.40
                            ),

                        "contract": {

                            "strike":
                                self.number(
                                    atm.get(
                                        "strike"
                                    )
                                ),

                            "call_price":
                                call[
                                    "ltp"
                                ],

                            "put_price":
                                put[
                                    "ltp"
                                ],

                            "premium":
                                premium,

                        },

                    })

        return candidates

    # ========================================================
    # DECIDE
    # ========================================================

    def decide(
        self,
        spot: float,
        bias: str,
        setup_strength: float,
        chain: Dict[str, Any],
        expiry_days: Optional[int] = None,
    ) -> Dict[str, Any]:

        spot = self.number(
            spot
        )

        setup_strength = self.number(
            setup_strength
        )

        normalized_bias = (
            self.normalize_bias(
                bias
            )
        )

        if spot <= 0:

            return {

                "success":
                    False,

                "decision":
                    "WAIT",

                "message":
                    "Invalid spot price.",

            }

        if (
            setup_strength
            <
            self.min_setup_strength
        ):

            return {

                "success":
                    True,

                "decision":
                    "WAIT",

                "message":
                    (
                        "Underlying setup strength "
                        "is below option threshold."
                    ),

            }

        if expiry_days is not None:

            expiry_days = int(
                expiry_days
            )

            if not (
                self.min_dte
                <= expiry_days
                <= self.max_dte
            ):

                return {

                    "success":
                        True,

                    "decision":
                        "WAIT",

                    "message":
                        "Expiry outside configured DTE range.",

                }

        candidates = (
            self.build_candidates(

                spot=spot,

                bias=normalized_bias,

                setup_strength=
                    setup_strength,

                chain=chain,

            )
        )

        # ----------------------------------------------------
        # Critical final validation
        # ----------------------------------------------------

        valid_candidates = []

        for candidate in candidates:

            contract = candidate.get(
                "contract",
                {}
            )

            if (
                candidate[
                    "strategy"
                ]
                in {
                    "BULL_CALL_SPREAD",
                    "BEAR_PUT_SPREAD",
                }
            ):

                rr = self.number(
                    contract.get(
                        "risk_reward"
                    )
                )

                max_profit = self.number(
                    contract.get(
                        "max_profit"
                    )
                )

                max_loss = self.number(
                    contract.get(
                        "max_loss"
                    )
                )

                net_debit = self.number(
                    contract.get(
                        "net_debit"
                    )
                )

                width = self.number(
                    contract.get(
                        "width"
                    )
                )

                if (
                    rr < self.min_spread_rr
                    or
                    max_profit <= 0
                    or
                    max_loss <= 0
                    or
                    net_debit <= 0
                    or
                    net_debit >= width
                ):

                    continue

            valid_candidates.append(
                candidate
            )

        if not valid_candidates:

            return {

                "success":
                    True,

                "decision":
                    "WAIT",

                "direction":
                    normalized_bias,

                "setup_strength":
                    setup_strength,

                "message":
                    (
                        "No option structure passed "
                        "the final payoff and liquidity checks."
                    ),

                "rejected_candidates":
                    candidates,

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

            }

        valid_candidates.sort(

            key=lambda x:
                self.number(
                    x.get(
                        "selection_score",
                        0.0,
                    )
                ),

            reverse=True,

        )

        best = valid_candidates[
            0
        ]

        return {

            "success":
                True,

            "decision":
                best[
                    "strategy"
                ],

            "direction":
                best[
                    "direction"
                ],

            "setup_strength":
                setup_strength,

            "selection_score":
                round(
                    self.number(
                        best.get(
                            "selection_score"
                        )
                    ),
                    2,
                ),

            "contract":
                best.get(
                    "contract"
                ),

            "alternatives":
                valid_candidates[
                    1:
                ],

            "rejected_candidates":
                [
                    item
                    for item
                    in candidates
                    if item
                    not in
                    valid_candidates
                ],

            "reasoning": [

                "Underlying setup passed "
                "the option threshold.",

                "Liquidity and payoff structure "
                "passed validation.",

                "Invalid spreads with zero or "
                "insufficient profit were rejected.",

            ],

            "timestamp":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS OPTION DECISION ENGINE V2"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Decision: "
            f"{result.get('decision')}"
        )

        lines.append(
            f"Direction: "
            f"{result.get('direction')}"
        )

        lines.append(
            f"Setup Strength: "
            f"{result.get('setup_strength', 0)}/100"
        )

        if result.get(
            "selection_score"
        ) is not None:

            lines.append(
                f"Selection Score: "
                f"{result.get('selection_score')}"
            )

        contract = result.get(
            "contract"
        )

        if contract:

            lines.append("")

            lines.append(
                "CONTRACT"
            )

            for key, value in (
                contract.items()
            ):

                lines.append(
                    f"{key}: {value}"
                )

        alternatives = result.get(
            "alternatives",
            []
        )

        if alternatives:

            lines.append("")

            lines.append(
                "VALID ALTERNATIVES"
            )

            for item in alternatives:

                lines.append(

                    f"- "
                    f"{item.get('strategy')} | "
                    f"score="
                    f"{self.number(item.get('selection_score')):.2f}"

                )

        rejected = result.get(
            "rejected_candidates",
            []
        )

        if rejected:

            lines.append("")

            lines.append(
                "REJECTED STRUCTURES"
            )

            for item in rejected:

                strategy = item.get(
                    "strategy"
                )

                contract = item.get(
                    "contract",
                    {}
                )

                lines.append(

                    f"- "
                    f"{strategy}: "
                    f"invalid payoff/risk structure"

                )

        reasoning = result.get(
            "reasoning",
            []
        )

        if reasoning:

            lines.append("")

            lines.append(
                "REASONING"
            )

            for item in reasoning:

                lines.append(
                    f"- {item}"
                )

        if result.get(
            "message"
        ):

            lines.append("")

            lines.append(
                f"Message: "
                f"{result.get('message')}"
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Analytical option selection only. "
            "No order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

option_decision_engine = (
    OptionDecisionEngine()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION DECISION ENGINE V2"
    )

    print(
        "=" * 60
    )

    spot = 24366.0

    rows = []

    strikes = [
        24200,
        24300,
        24400,
        24500,
        24600,
        24700,
        24800,
    ]

    for strike in strikes:

        distance = (
            strike - spot
        )

        rows.append({

            "strike":
                strike,

            # Deliberately realistic enough to test
            # payoff validation.

            "call_ltp":
                max(
                    25.0,
                    330.0
                    -
                    max(
                        0.0,
                        distance,
                    )
                    * 0.90,
                ),

            "put_ltp":
                max(
                    25.0,
                    330.0
                    +
                    min(
                        0.0,
                        distance,
                    )
                    * 0.90,
                ),

            "call_iv":
                18.0,

            "put_iv":
                19.0,

            "call_oi":
                100000,

            "put_oi":
                95000,

            "call_volume":
                25000,

            "put_volume":
                27000,

            "call_oi_change":
                10000,

            "put_oi_change":
                8000,

        })

    chain = {

        "spot":
            spot,

        "rows":
            rows,

    }

    result = (
        option_decision_engine.decide(

            spot=spot,

            bias="BULLISH",

            setup_strength=86.0,

            chain=chain,

            expiry_days=20,

        )
    )

    print()

    print(
        option_decision_engine.format_result(
            result
        )
    )

    print()

    print(
        "Option Decision Engine V2 loaded successfully."
    )