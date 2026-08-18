# ============================================================
# JARVIS TRADING INTELLIGENCE AGENT
# V2
# ============================================================
#
# Unified research/paper-trading intelligence layer.
#
# Adds:
#   - Technical analysis
#   - Pattern analysis
#   - Regime detection
#   - Regime-aware signal
#   - Multi-timeframe confluence
#   - Strategy Lab
#   - Research Edge validation
#
# IMPORTANT:
#   No live orders are placed by this module.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from agents.technical_engine import technical_engine
from agents.pattern_engine import pattern_engine
from agents.regime_detector import regime_detector
from agents.regime_aware_signal_engine import (
    regime_aware_signal_engine,
)
from agents.mtf_confluence_engine import (
    mtf_confluence_engine,
)
from agents.strategy_lab import strategy_lab
from agents.research_edge_engine import (
    research_edge_engine,
)


# ============================================================
# AGENT
# ============================================================

class TradingIntelligenceAgent:

    # ========================================================
    # SINGLE TIMEFRAME
    # ========================================================

    def analyze_dataframe(
        self,
        df: pd.DataFrame,
        timeframe: str = "1d",
        symbol: str = "UNKNOWN",
        market: str = "INDIA",
        option_context: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        if df is None or df.empty:

            return {
                "success": False,
                "message": "No market data supplied.",
            }

        technical = technical_engine.analyze(
            df
        )

        if not technical.get(
            "success",
            False,
        ):

            return {
                "success": False,
                "message": "Technical analysis failed.",
                "technical": technical,
            }

        patterns = pattern_engine.analyze(
            df
        )

        if not patterns.get(
            "success",
            False,
        ):

            return {
                "success": False,
                "message": "Pattern analysis failed.",
                "technical": technical,
                "patterns": patterns,
            }

        regime = regime_detector.analyze(
            df
        )

        if not regime.get(
            "success",
            False,
        ):

            return {
                "success": False,
                "message": "Regime detection failed.",
            }

        signal = (
            regime_aware_signal_engine.generate_signal(
                technical=technical,
                patterns=patterns,
                regime=regime,
            )
        )

        preliminary_confluence = {

            "confluence_score":
                float(
                    signal.get(
                        "confidence",
                        0,
                    )
                ),

            "agreement":
                100.0,

            "quality":
                (
                    "A"
                    if signal.get(
                        "confidence",
                        0,
                    ) >= 75
                    else "WATCH"
                ),

            "permission":
                (
                    "CANDIDATE"
                    if signal.get(
                        "action"
                    ) in {
                        "BUY",
                        "SELL",
                    }
                    else "WAIT"
                ),

        }

        strategy_result = (
            strategy_lab.rank(

                technical=technical,

                regime=regime,

                confluence=preliminary_confluence,

                option_context=(
                    option_context or {}
                ),

            )
        )

        rankings = strategy_result.get(
            "rankings",
            [],
        )

        # ----------------------------------------------------
        # Research Edge validation for every ranked strategy.
        # ----------------------------------------------------

        research_rankings = []

        for item in rankings:

            strategy_name = item.get(
                "strategy"
            )

            edge = (
                research_edge_engine.get_edge(

                    strategy=strategy_name,

                    symbol=symbol,

                    market=market,

                    timeframe=timeframe,

                )
            )

            if edge is None:

                research_rankings.append({

                    "strategy":
                        strategy_name,

                    "fit_score":
                        item.get(
                            "score",
                            0,
                        ),

                    "research_score":
                        0.0,

                    "validated":
                        False,

                    "research_quality":
                        "UNVALIDATED",

                })

            else:

                research_rankings.append({

                    "strategy":
                        strategy_name,

                    "fit_score":
                        item.get(
                            "score",
                            0,
                        ),

                    "research_score":
                        edge.get(
                            "research_score",
                            0,
                        ),

                    "validated":
                        bool(
                            edge.get(
                                "validated",
                                False,
                            )
                        ),

                    "research_quality":
                        edge.get(
                            "quality",
                            "UNVALIDATED",
                        ),

                })

        # ----------------------------------------------------
        # Final candidate selection
        # ----------------------------------------------------

        candidate = None

        for item in research_rankings:

            if (
                item["validated"]
                and
                item["fit_score"] >= 70
                and
                item["research_score"] >= 70
            ):

                if candidate is None:

                    candidate = item

                elif (
                    item["research_score"]
                    >
                    candidate["research_score"]
                ):

                    candidate = item

        if candidate is not None:

            final_decision = "CANDIDATE"

            final_strategy = (
                candidate["strategy"]
            )

            final_reason = (
                "Strategy fit and validated "
                "research edge both pass."
            )

        else:

            final_decision = "WAIT"

            final_strategy = "NONE"

            final_reason = (
                "No strategy has both sufficient "
                "current setup fit and validated research edge."
            )

        # ----------------------------------------------------
        # Risk adjustment
        # ----------------------------------------------------

        risk_adjustment = signal.get(
            "risk_adjustment",
            1.0,
        )

        # If the regime-aware signal itself says WAIT,
        # do not allow the research layer to resurrect a trade.

        if signal.get(
            "action"
        ) not in {
            "BUY",
            "SELL",
        }:

            final_decision = "WAIT"

            final_strategy = "NONE"

            final_reason = (
                "The regime-aware signal does not "
                "permit a directional trade."
            )

        return {

            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "technical":
                technical,

            "patterns":
                patterns,

            "regime":
                regime,

            "signal":
                signal,

            "strategy_lab":
                strategy_result,

            "research_rankings":
                research_rankings,

            "final_decision":
                final_decision,

            "final_strategy":
                final_strategy,

            "final_reason":
                final_reason,

            "risk_adjustment":
                risk_adjustment,

            "option_context":
                option_context or {},

        }

    # ========================================================
    # MULTI-TIMEFRAME
    # ========================================================

    def analyze_multitimeframe(
        self,
        timeframe_data: Dict[
            str,
            pd.DataFrame,
        ],
        symbol: str = "UNKNOWN",
        market: str = "INDIA",
        option_context: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        if not timeframe_data:

            return {
                "success": False,
                "message":
                    "No timeframe data supplied.",
            }

        analyses = {}

        raw_analyses = {}

        for timeframe, df in (
            timeframe_data.items()
        ):

            result = (
                self.analyze_dataframe(

                    df=df,

                    timeframe=timeframe,

                    symbol=symbol,

                    market=market,

                    option_context=option_context,

                )
            )

            if not result.get(
                "success",
                False,
            ):

                continue

            raw_analyses[
                timeframe
            ] = result

            signal = result[
                "signal"
            ]

            regime = result[
                "regime"
            ]

            if signal.get(
                "action"
            ) == "BUY":

                bias = "BULLISH"

            elif signal.get(
                "action"
            ) == "SELL":

                bias = "BEARISH"

            else:

                bias = (
                    regime.get(
                        "bias",
                        "NEUTRAL",
                    )
                    or "NEUTRAL"
                )

            analyses[
                timeframe
            ] = {

                "bias":
                    bias,

                "regime":
                    regime.get(
                        "regime",
                        "TRANSITION",
                    ),

                "confidence":
                    signal.get(
                        "confidence",
                        0,
                    ),

                "trend_strength":
                    regime.get(
                        "trend_strength",
                        "WEAK",
                    ),

                "volatility_regime":
                    regime.get(
                        "volatility_regime",
                        "NORMAL_VOLATILITY",
                    ),

            }

        if not analyses:

            return {
                "success": False,
                "message":
                    "No timeframe analysis succeeded.",
            }

        confluence = (
            mtf_confluence_engine.analyze(
                analyses
            )
        )

        if not confluence.get(
            "success",
            False,
        ):

            return {
                "success": False,
                "message":
                    "Multi-timeframe confluence failed.",
            }

        # ----------------------------------------------------
        # Strategy Lab using representative timeframe.
        # ----------------------------------------------------

        representative_timeframe = None

        for preferred in [
            "1d",
            "4h",
            "1h",
            "15m",
            "5m",
        ]:

            if preferred in raw_analyses:

                representative_timeframe = (
                    preferred
                )

                break

        if (
            representative_timeframe
            is None
        ):

            representative_timeframe = next(
                iter(
                    raw_analyses
                )
            )

        representative = raw_analyses[
            representative_timeframe
        ]

        strategy_result = (
            strategy_lab.rank(

                technical=
                    representative[
                        "technical"
                    ],

                regime=
                    representative[
                        "regime"
                    ],

                confluence=
                    confluence,

                option_context=
                    option_context or {},

            )
        )

        # ----------------------------------------------------
        # Research validation against every timeframe
        # ----------------------------------------------------

        research_candidates = []

        for item in strategy_result.get(
            "rankings",
            [],
        ):

            strategy_name = item.get(
                "strategy"
            )

            for timeframe in raw_analyses:

                edge = (
                    research_edge_engine.get_edge(

                        strategy=strategy_name,

                        symbol=symbol,

                        market=market,

                        timeframe=timeframe,

                    )
                )

                if edge is None:
                    continue

                if not edge.get(
                    "validated",
                    False,
                ):
                    continue

                if (
                    item.get(
                        "score",
                        0,
                    )
                    <
                    70
                ):
                    continue

                if (
                    edge.get(
                        "research_score",
                        0,
                    )
                    <
                    70
                ):
                    continue

                research_candidates.append({

                    "strategy":
                        strategy_name,

                    "timeframe":
                        timeframe,

                    "fit_score":
                        item.get(
                            "score",
                            0,
                        ),

                    "research_score":
                        edge.get(
                            "research_score",
                            0,
                        ),

                })

        research_candidates.sort(

            key=lambda item:
                (
                    item["research_score"],
                    item["fit_score"],
                ),

            reverse=True,

        )

        # ----------------------------------------------------
        # Final permission
        # ----------------------------------------------------

        if (
            confluence.get(
                "permission"
            )
            == "CANDIDATE"
            and
            research_candidates
        ):

            final_decision = (
                "CANDIDATE"
            )

            final_strategy = (
                research_candidates[0][
                    "strategy"
                ]
            )

            final_reason = (
                "Multi-timeframe confluence passes "
                "and a validated strategy edge exists."
            )

        else:

            final_decision = "WAIT"

            final_strategy = "NONE"

            if confluence.get(
                "permission"
            ) != "CANDIDATE":

                final_reason = (
                    "Multi-timeframe confluence "
                    "does not permit a trade."
                )

            else:

                final_reason = (
                    "No validated research edge "
                    "matches the current setup."
                )

        return {

            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "timeframes":
                analyses,

            "raw_analyses":
                raw_analyses,

            "confluence":
                confluence,

            "strategy_lab":
                strategy_result,

            "research_candidates":
                research_candidates,

            "final_decision":
                final_decision,

            "final_strategy":
                final_strategy,

            "final_reason":
                final_reason,

            "option_context":
                option_context or {},

        }

    # ========================================================
    # FORMAT SINGLE
    # ========================================================

    def format_single(
        self,
        result: Dict[str, Any],
    ) -> str:

        if not result.get(
            "success",
            False,
        ):

            return (
                "TRADING INTELLIGENCE FAILED\n"
                "--------------------------------------------------\n"
                +
                str(
                    result.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        signal = result[
            "signal"
        ]

        regime = result[
            "regime"
        ]

        lines = []

        lines.append(
            "JARVIS TRADING INTELLIGENCE V2"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: "
            f"{result.get('symbol')}"
        )

        lines.append(
            f"Timeframe: "
            f"{result.get('timeframe')}"
        )

        lines.append(
            f"Regime: "
            f"{regime.get('regime')}"
        )

        lines.append(
            f"Bias: "
            f"{regime.get('bias')}"
        )

        lines.append(
            f"Volatility: "
            f"{regime.get('volatility_regime')}"
        )

        lines.append(
            f"Signal: "
            f"{signal.get('action')}"
        )

        lines.append(
            f"Confidence: "
            f"{signal.get('confidence')}%"
        )

        lines.append("")

        lines.append(
            "STRATEGY LAB"
        )

        for index, item in enumerate(
            result.get(
                "strategy_lab",
                {}
            ).get(
                "rankings",
                [],
            )[:5],
            1,
        ):

            lines.append(

                f"{index}. "
                f"{item.get('strategy')} "
                f"{item.get('score')}/100"

            )

        lines.append("")

        lines.append(
            "RESEARCH EDGE"
        )

        research_rankings = result.get(
            "research_rankings",
            [],
        )

        for item in research_rankings[:5]:

            lines.append(

                f"- "
                f"{item.get('strategy')}: "
                f"fit={item.get('fit_score')}, "
                f"research={item.get('research_score')}, "
                f"validated={item.get('validated')}"

            )

        lines.append("")

        lines.append(
            "FINAL DECISION"
        )

        lines.append(
            f"Decision: "
            f"{result.get('final_decision')}"
        )

        lines.append(
            f"Strategy: "
            f"{result.get('final_strategy')}"
        )

        lines.append(
            f"Reason: "
            f"{result.get('final_reason')}"
        )

        lines.append("")

        lines.append(
            "TRADE SETUP"
        )

        lines.append(
            f"Entry: "
            f"{signal.get('entry')}"
        )

        lines.append(
            f"Stop: "
            f"{signal.get('stop_loss')}"
        )

        lines.append(
            f"Target: "
            f"{signal.get('target')}"
        )

        lines.append(
            f"Risk/Reward: "
            f"{signal.get('risk_reward')}"
        )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Analytical/paper-trading output only. "
            "No live order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

trading_intelligence_agent = (
    TradingIntelligenceAgent()
)


# ============================================================
# HELPERS
# ============================================================

def analyze_market(
    df: pd.DataFrame,
    timeframe: str = "1d",
    symbol: str = "UNKNOWN",
    market: str = "INDIA",
    option_context=None,
):

    return (
        trading_intelligence_agent.analyze_dataframe(

            df=df,

            timeframe=timeframe,

            symbol=symbol,

            market=market,

            option_context=option_context,

        )
    )


def analyze_multitimeframe(
    timeframe_data,
    symbol="UNKNOWN",
    market="INDIA",
    option_context=None,
):

    return (
        trading_intelligence_agent.analyze_multitimeframe(

            timeframe_data=timeframe_data,

            symbol=symbol,

            market=market,

            option_context=option_context,

        )
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    from agents.market_data_agent import (
        get_market_data,
    )

    print(
        "=" * 60
    )

    print(
        "JARVIS TRADING INTELLIGENCE AGENT V2"
    )

    print(
        "=" * 60
    )

    result = get_market_data(

        "NIFTY",

        market="india",

        timeframe="1d",

        bars=500,

    )

    if not result.get(
        "success",
        False,
    ):

        print(
            "Market data failed:"
        )

        print(
            result.get(
                "message"
            )
        )

    else:

        analysis = (
            analyze_market(

                df=result["data"],

                timeframe="1d",

                symbol="NIFTY",

                market="INDIA",

            )
        )

        print(
            trading_intelligence_agent.format_single(
                analysis
            )
        )

    print()

    print(
        "Trading Intelligence Agent V2 loaded successfully."
    )