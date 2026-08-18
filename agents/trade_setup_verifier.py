# ============================================================
# JARVIS TRADE SETUP VERIFIER
# V2
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime


class TradeSetupVerifier:

    def __init__(
        self,
        required_timeframes: Optional[List[str]] = None,
        min_setup_score: float = 75.0,
        min_confidence: float = 70.0,
        min_agreement: float = 70.0,
        min_risk_reward: float = 1.5,
        require_research_edge: bool = True,
    ):

        self.required_timeframes = (
            list(required_timeframes)
            if required_timeframes is not None
            else ["5m", "15m"]
        )

        self.min_setup_score = float(
            min_setup_score
        )

        self.min_confidence = float(
            min_confidence
        )

        self.min_agreement = float(
            min_agreement
        )

        self.min_risk_reward = float(
            min_risk_reward
        )

        self.require_research_edge = bool(
            require_research_edge
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

            if value != value:
                return default

            return value

        except Exception:

            return default

    # ========================================================
    # VERIFY
    # ========================================================

    def verify(
        self,
        symbol: str,
        analyses: List[Dict[str, Any]],
        candidate: Dict[str, Any],
        research: Optional[Dict[str, Any]] = None,
        strategy_name: Optional[str] = None,
    ) -> Dict[str, Any]:

        checks: Dict[str, bool] = {}
        reasons: List[str] = []

        required = {
            str(tf).lower()
            for tf in self.required_timeframes
        }

        available = set()
        failed = set()

        # ====================================================
        # TIMEFRAME DATA
        # ====================================================

        for analysis in analyses:

            timeframe = str(
                analysis.get(
                    "timeframe",
                    "",
                )
            ).lower()

            if analysis.get(
                "success",
                False,
            ):

                available.add(
                    timeframe
                )

            else:

                failed.add(
                    timeframe
                )

        missing = sorted(
            required - available
        )

        checks[
            "timeframe_data_complete"
        ] = (
            len(missing) == 0
        )

        checks[
            "all_required_timeframes_present"
        ] = (
            required.issubset(
                available
            )
        )

        checks[
            "enough_timeframes"
        ] = (
            len(available & required)
            ==
            len(required)
        )

        if missing:

            reasons.append(
                "Missing required timeframe data: "
                + ", ".join(missing)
            )

        # ====================================================
        # SETUP METRICS
        # ====================================================

        setup_score = self.number(
            candidate.get(
                "setup_score",
                0.0,
            )
        )

        confidence = self.number(
            candidate.get(
                "confidence",
                0.0,
            )
        )

        agreement = self.number(
            candidate.get(
                "agreement",
                0.0,
            )
        )

        risk_reward = self.number(
            candidate.get(
                "risk_reward",
                0.0,
            )
        )

        checks[
            "setup_score"
        ] = (
            setup_score
            >=
            self.min_setup_score
        )

        checks[
            "confidence"
        ] = (
            confidence
            >=
            self.min_confidence
        )

        checks[
            "timeframe_agreement"
        ] = (
            agreement
            >=
            self.min_agreement
        )

        checks[
            "risk_reward"
        ] = (
            risk_reward
            >=
            self.min_risk_reward
        )

        if not checks["setup_score"]:

            reasons.append(
                "Setup score is below threshold."
            )

        if not checks["confidence"]:

            reasons.append(
                "Setup confidence is below threshold."
            )

        if not checks["timeframe_agreement"]:

            reasons.append(
                "Timeframe agreement is below threshold."
            )

        if not checks["risk_reward"]:

            reasons.append(
                (
                    f"Risk/reward "
                    f"{risk_reward:.2f} "
                    f"is below required "
                    f"{self.min_risk_reward:.2f}."
                )
            )

        # ====================================================
        # DIRECTION
        # ====================================================

        direction = str(
            candidate.get(
                "direction",
                "NEUTRAL",
            )
        ).upper()

        checks[
            "direction_defined"
        ] = (
            direction
            in {
                "BULLISH",
                "BEARISH",
            }
        )

        if not checks[
            "direction_defined"
        ]:

            reasons.append(
                "No valid trade direction."
            )

        # ====================================================
        # RESEARCH EDGE
        # ====================================================

        if self.require_research_edge:

            if research is None:

                checks[
                    "research_edge"
                ] = False

                reasons.append(
                    "No validated aggregate research edge available."
                )

            else:

                validated = bool(
                    research.get(
                        "validated",
                        False,
                    )
                )

                aggregate_score = self.number(
                    research.get(
                        "aggregate_score",
                        0.0,
                    )
                )

                checks[
                    "research_edge"
                ] = (
                    validated
                    and
                    aggregate_score >= 70.0
                )

                if not validated:

                    reasons.append(
                        "Strategy research edge is not validated."
                    )

                if aggregate_score < 70.0:

                    reasons.append(
                        "Aggregate research score is below 70."
                    )

        else:

            checks[
                "research_edge"
            ] = True

        # ====================================================
        # FINAL HARD GATE
        # ====================================================
        #
        # EVERY check below must pass.
        #
        # No warnings that secretly allow execution.
        # ====================================================

        hard_gate_names = [

            "timeframe_data_complete",

            "all_required_timeframes_present",

            "enough_timeframes",

            "setup_score",

            "confidence",

            "timeframe_agreement",

            "risk_reward",

            "direction_defined",

            "research_edge",

        ]

        approved = all(

            checks.get(
                name,
                False,
            )

            for name
            in hard_gate_names

        )

        if approved:

            permission = (
                "CONFIRMATION_READY"
            )

        else:

            permission = (
                "BLOCKED"
            )

        return {

            "success":
                True,

            "approved":
                approved,

            "execution_permission":
                permission,

            "symbol":
                symbol,

            "strategy":
                strategy_name,

            "timestamp":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "required_timeframes":
                sorted(required),

            "available_timeframes":
                sorted(available),

            "missing_timeframes":
                missing,

            "failed_timeframes":
                sorted(failed),

            "checks":
                checks,

            "setup_score":
                setup_score,

            "confidence":
                confidence,

            "agreement":
                agreement,

            "risk_reward":
                risk_reward,

            "direction":
                direction,

            "reasons":
                reasons,

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
            "JARVIS TRADE SETUP VERIFIER V2"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: "
            f"{result.get('symbol')}"
        )

        lines.append(
            f"Decision: "
            f"{result.get('execution_permission')}"
        )

        lines.append(
            f"Approved: "
            f"{result.get('approved')}"
        )

        lines.append(
            f"Direction: "
            f"{result.get('direction')}"
        )

        lines.append(
            f"Setup Score: "
            f"{result.get('setup_score')}/100"
        )

        lines.append(
            f"Confidence: "
            f"{result.get('confidence')}%"
        )

        lines.append(
            f"Agreement: "
            f"{result.get('agreement')}%"
        )

        lines.append(
            f"Risk/Reward: "
            f"{result.get('risk_reward'):.2f}"
        )

        lines.append("")

        lines.append(
            "TIMEFRAME VALIDATION"
        )

        lines.append(
            "Required: "
            +
            ", ".join(
                result.get(
                    "required_timeframes",
                    [],
                )
            )
        )

        lines.append(
            "Available: "
            +
            ", ".join(
                result.get(
                    "available_timeframes",
                    [],
                )
            )
        )

        missing = result.get(
            "missing_timeframes",
            []
        )

        if missing:

            lines.append(
                "Missing: "
                +
                ", ".join(
                    missing
                )
            )

        lines.append("")

        lines.append(
            "HARD GATE CHECKS"
        )

        for name, value in (
            result.get(
                "checks",
                {}
            ).items()
        ):

            lines.append(
                f"- {name}: "
                f"{'PASS' if value else 'FAIL'}"
            )

        reasons = result.get(
            "reasons",
            []
        )

        if reasons:

            lines.append("")

            lines.append(
                "BLOCK REASONS"
            )

            for reason in reasons:

                lines.append(
                    f"- {reason}"
                )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "A setup is executable only when every "
            "hard gate passes."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

trade_setup_verifier = (
    TradeSetupVerifier()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS TRADE SETUP VERIFIER V2"
    )

    print(
        "=" * 60
    )

    fake_candidate = {

        "direction":
            "BULLISH",

        "setup_score":
            100.0,

        "confidence":
            100.0,

        "agreement":
            100.0,

        "risk_reward":
            0.0,

    }

    fake_analyses = [

        {
            "success":
                True,

            "timeframe":
                "5m",

        },

        {
            "success":
                True,

            "timeframe":
                "15m",

        },

    ]

    result = (
        trade_setup_verifier.verify(

            symbol="NIFTY",

            analyses=fake_analyses,

            candidate=fake_candidate,

            research={

                "validated":
                    True,

                "aggregate_score":
                    74.41,

            },

            strategy_name=
                "MEAN_REVERSION",

        )
    )

    print()

    print(
        trade_setup_verifier.format_result(
            result
        )
    )

    print()

    print(
        "Trade Setup Verifier V2 loaded successfully."
    )