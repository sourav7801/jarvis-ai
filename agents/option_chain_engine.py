# ============================================================
# JARVIS OPTION CHAIN ENGINE
# V1
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


class OptionChainEngine:

    """
    Normalizes and analyzes option-chain data.

    Expected columns can include:

        strike
        call_ltp
        put_ltp
        call_iv
        put_iv
        call_delta
        put_delta
        call_oi
        put_oi
        call_oi_change
        put_oi_change
        call_volume
        put_volume

    The engine intentionally accepts flexible input
    so different brokers/exchanges can be adapted
    later without changing the analysis layer.
    """

    def normalize_columns(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        if df is None or df.empty:
            return pd.DataFrame()

        data = df.copy()

        normalized = {}

        aliases = {

            "strike_price": "strike",
            "strikeprice": "strike",

            "call_ltp": "call_ltp",
            "ce_ltp": "call_ltp",
            "call_price": "call_ltp",
            "ce_price": "call_ltp",

            "put_ltp": "put_ltp",
            "pe_ltp": "put_ltp",
            "put_price": "put_ltp",
            "pe_price": "put_ltp",

            "call_iv": "call_iv",
            "ce_iv": "call_iv",

            "put_iv": "put_iv",
            "pe_iv": "put_iv",

            "call_oi": "call_oi",
            "ce_oi": "call_oi",

            "put_oi": "put_oi",
            "pe_oi": "put_oi",

            "call_oi_change": "call_oi_change",
            "ce_oi_change": "call_oi_change",

            "put_oi_change": "put_oi_change",
            "pe_oi_change": "put_oi_change",

            "call_volume": "call_volume",
            "ce_volume": "call_volume",

            "put_volume": "put_volume",
            "pe_volume": "put_volume",
        }

        for column in data.columns:

            key = (
                str(column)
                .strip()
                .lower()
                .replace(" ", "_")
                .replace("-", "_")
            )

            normalized[
                column
            ] = aliases.get(
                key,
                key,
            )

        data = data.rename(
            columns=normalized
        )

        if "strike" not in data.columns:

            return pd.DataFrame()

        for column in data.columns:

            if column != "strike":

                data[column] = pd.to_numeric(
                    data[column],
                    errors="coerce",
                )

        data["strike"] = pd.to_numeric(
            data["strike"],
            errors="coerce",
        )

        data = data.dropna(
            subset=["strike"]
        )

        return data.sort_values(
            "strike"
        ).reset_index(
            drop=True
        )

    # ========================================================
    # ATM
    # ========================================================

    def find_atm(
        self,
        df: pd.DataFrame,
        spot: float,
    ) -> Optional[float]:

        if df.empty:
            return None

        distances = (
            (df["strike"] - spot)
            .abs()
        )

        index = distances.idxmin()

        return float(
            df.loc[index, "strike"]
        )

    # ========================================================
    # OI LEVELS
    # ========================================================

    def open_interest_levels(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        result = {

            "highest_call_oi":
                None,

            "highest_put_oi":
                None,

            "call_oi_resistance":
                None,

            "put_oi_support":
                None,

        }

        if "call_oi" in df.columns:

            call = df[
                "call_oi"
            ].fillna(0)

            if not call.empty:

                index = call.idxmax()

                result[
                    "highest_call_oi"
                ] = {

                    "strike":
                        float(
                            df.loc[index, "strike"]
                        ),

                    "oi":
                        float(
                            call.loc[index]
                        ),

                }

                result[
                    "call_oi_resistance"
                ] = float(
                    df.loc[index, "strike"]
                )

        if "put_oi" in df.columns:

            put = df[
                "put_oi"
            ].fillna(0)

            if not put.empty:

                index = put.idxmax()

                result[
                    "highest_put_oi"
                ] = {

                    "strike":
                        float(
                            df.loc[index, "strike"]
                        ),

                    "oi":
                        float(
                            put.loc[index]
                        ),

                }

                result[
                    "put_oi_support"
                ] = float(
                    df.loc[index, "strike"]
                )

        return result

    # ========================================================
    # OI CHANGE
    # ========================================================

    def oi_change_analysis(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        result = {}

        if "call_oi_change" in df.columns:

            call = df[
                "call_oi_change"
            ].fillna(0)

            if not call.empty:

                index = call.abs().idxmax()

                result[
                    "largest_call_oi_change"
                ] = {

                    "strike":
                        float(
                            df.loc[index, "strike"]
                        ),

                    "change":
                        float(
                            call.loc[index]
                        ),

                }

        if "put_oi_change" in df.columns:

            put = df[
                "put_oi_change"
            ].fillna(0)

            if not put.empty:

                index = put.abs().idxmax()

                result[
                    "largest_put_oi_change"
                ] = {

                    "strike":
                        float(
                            df.loc[index, "strike"]
                        ),

                    "change":
                        float(
                            put.loc[index]
                        ),

                }

        return result

    # ========================================================
    # MAX PAIN
    # ========================================================

    def max_pain(
        self,
        df: pd.DataFrame,
    ) -> Optional[float]:

        required = {
            "strike",
            "call_oi",
            "put_oi",
        }

        if not required.issubset(
            df.columns
        ):

            return None

        strikes = (
            df["strike"]
            .dropna()
            .tolist()
        )

        if not strikes:
            return None

        best_strike = None
        minimum_pain = None

        for settlement in strikes:

            call_pain = (
                (
                    settlement
                    - df["strike"]
                )
                .clip(
                    lower=0
                )
                * df["call_oi"].fillna(0)
            ).sum()

            put_pain = (
                (
                    df["strike"]
                    - settlement
                )
                .clip(
                    lower=0
                )
                * df["put_oi"].fillna(0)
            ).sum()

            total_pain = (
                call_pain
                + put_pain
            )

            if (
                minimum_pain is None
                or total_pain
                < minimum_pain
            ):

                minimum_pain = (
                    total_pain
                )

                best_strike = (
                    settlement
                )

        return (
            float(best_strike)
            if best_strike is not None
            else None
        )

    # ========================================================
    # PUT/CALL RATIO
    # ========================================================

    def put_call_ratio(
        self,
        df: pd.DataFrame,
    ) -> Optional[float]:

        if (
            "put_oi"
            not in df.columns
            or
            "call_oi"
            not in df.columns
        ):

            return None

        put_oi = (
            df["put_oi"]
            .fillna(0)
            .sum()
        )

        call_oi = (
            df["call_oi"]
            .fillna(0)
            .sum()
        )

        if call_oi == 0:
            return None

        return float(
            put_oi / call_oi
        )

    # ========================================================
    # IV SUMMARY
    # ========================================================

    def volatility_summary(
        self,
        df: pd.DataFrame,
        spot: float,
    ) -> Dict[str, Any]:

        atm = self.find_atm(
            df,
            spot,
        )

        result = {

            "atm_strike":
                atm,

            "atm_call_iv":
                None,

            "atm_put_iv":
                None,

            "atm_iv":
                None,

            "iv_skew":
                None,

        }

        if atm is None:
            return result

        row = df[
            df["strike"] == atm
        ]

        if row.empty:
            return result

        row = row.iloc[0]

        call_iv = None
        put_iv = None

        if "call_iv" in df.columns:

            value = row.get(
                "call_iv"
            )

            if pd.notna(value):
                call_iv = float(
                    value
                )

        if "put_iv" in df.columns:

            value = row.get(
                "put_iv"
            )

            if pd.notna(value):
                put_iv = float(
                    value
                )

        result[
            "atm_call_iv"
        ] = call_iv

        result[
            "atm_put_iv"
        ] = put_iv

        values = [
            value
            for value in [
                call_iv,
                put_iv,
            ]
            if value is not None
        ]

        if values:

            result[
                "atm_iv"
            ] = sum(values) / len(values)

        if (
            call_iv is not None
            and put_iv is not None
        ):

            result[
                "iv_skew"
            ] = (
                put_iv - call_iv
            )

        return result

    # ========================================================
    # NEAREST STRIKES
    # ========================================================

    def nearest_strikes(
        self,
        df: pd.DataFrame,
        spot: float,
        count: int = 5,
    ) -> pd.DataFrame:

        if df.empty:
            return df

        data = df.copy()

        data[
            "_distance"
        ] = (
            data["strike"]
            - spot
        ).abs()

        result = (
            data.sort_values(
                "_distance"
            )
            .head(count)
            .drop(
                columns=[
                    "_distance"
                ]
            )
            .sort_values(
                "strike"
            )
            .reset_index(
                drop=True
            )
        )

        return result

    # ========================================================
    # MARKET BIAS
    # ========================================================

    def market_bias(
        self,
        df: pd.DataFrame,
        spot: float,
    ) -> str:

        levels = (
            self.open_interest_levels(
                df
            )
        )

        resistance = (
            levels.get(
                "call_oi_resistance"
            )
        )

        support = (
            levels.get(
                "put_oi_support"
            )
        )

        if (
            support is not None
            and
            resistance is not None
        ):

            if (
                spot > resistance
            ):

                return "BULLISH"

            if (
                spot < support
            ):

                return "BEARISH"

        pcr = (
            self.put_call_ratio(
                df
            )
        )

        if pcr is None:

            return "NEUTRAL"

        if pcr > 1.2:
            return "BULLISH"

        if pcr < 0.8:
            return "BEARISH"

        return "NEUTRAL"

    # ========================================================
    # FULL ANALYSIS
    # ========================================================

    def analyze(
        self,
        df: pd.DataFrame,
        spot: float,
    ) -> Dict[str, Any]:

        data = (
            self.normalize_columns(
                df
            )
        )

        if data.empty:

            return {

                "success":
                    False,

                "message":
                    (
                        "Option-chain data "
                        "could not be normalized."
                    ),

            }

        atm = self.find_atm(
            data,
            spot,
        )

        levels = (
            self.open_interest_levels(
                data
            )
        )

        oi_change = (
            self.oi_change_analysis(
                data
            )
        )

        max_pain = (
            self.max_pain(
                data
            )
        )

        pcr = (
            self.put_call_ratio(
                data
            )
        )

        volatility = (
            self.volatility_summary(
                data,
                spot,
            )
        )

        bias = (
            self.market_bias(
                data,
                spot,
            )
        )

        nearest = (
            self.nearest_strikes(
                data,
                spot,
                count=7,
            )
        )

        return {

            "success":
                True,

            "spot":
                float(spot),

            "atm":
                atm,

            "bias":
                bias,

            "levels":
                levels,

            "oi_change":
                oi_change,

            "max_pain":
                max_pain,

            "put_call_ratio":
                pcr,

            "volatility":
                volatility,

            "nearest_strikes":
                nearest.to_dict(
                    orient="records"
                ),

            "chain":
                data,

        }


# ============================================================
# GLOBAL ENGINE
# ============================================================

option_chain_engine = (
    OptionChainEngine()
)


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

def analyze_option_chain(
    df: pd.DataFrame,
    spot: float,
):

    return (
        option_chain_engine.analyze(
            df,
            spot,
        )
    )


# ============================================================
# TEST DATA
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION CHAIN ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    spot = 24_366.0

    strikes = [
        23_900,
        24_000,
        24_100,
        24_200,
        24_300,
        24_400,
        24_500,
        24_600,
        24_700,
        24_800,
    ]

    data = []

    for strike in strikes:

        distance = abs(
            strike - spot
        )

        call_oi = int(
            100_000
            + distance * 20
        )

        put_oi = int(
            90_000
            + distance * 18
        )

        data.append({

            "strike":
                strike,

            "call_ltp":
                max(
                    50,
                    spot
                    - strike
                    + 300,
                ),

            "put_ltp":
                max(
                    50,
                    strike
                    - spot
                    + 280,
                ),

            "call_iv":
                18.0
                + distance / 1000,

            "put_iv":
                19.0
                + distance / 1000,

            "call_oi":
                call_oi,

            "put_oi":
                put_oi,

            "call_oi_change":
                10_000,

            "put_oi_change":
                8_000,

            "call_volume":
                25_000,

            "put_volume":
                27_000,

        })

    df = pd.DataFrame(
        data
    )

    result = (
        analyze_option_chain(
            df,
            spot,
        )
    )

    print(
        "Success:",
        result.get(
            "success"
        ),
    )

    print(
        "Spot:",
        result.get(
            "spot"
        ),
    )

    print(
        "ATM:",
        result.get(
            "atm"
        ),
    )

    print(
        "Bias:",
        result.get(
            "bias"
        ),
    )

    print(
        "Max Pain:",
        result.get(
            "max_pain"
        ),
    )

    print(
        "Put/Call Ratio:",
        result.get(
            "put_call_ratio"
        ),
    )

    print(
        "Levels:"
    )

    print(
        result.get(
            "levels"
        )
    )

    print(
        "Volatility:"
    )

    print(
        result.get(
            "volatility"
        )
    )

    print()

    print(
        "Nearest strikes:"
    )

    for row in result.get(
        "nearest_strikes",
        [],
    ):

        print(
            row
        )

    print()

    print(
        "Option Chain Engine loaded successfully."
    )