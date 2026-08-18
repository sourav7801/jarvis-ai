# ============================================================
# JARVIS RESEARCH EDGE ENGINE
# V1
# ============================================================
#
# Purpose:
#   Store and evaluate validated strategy performance.
#
# Core idea:
#
#   STRATEGY FIT != STRATEGY EDGE
#
#   Strategy Lab answers:
#       "Does this strategy fit the current market?"
#
#   Research Edge Engine answers:
#       "Has this strategy demonstrated a historical edge?"
#
# Inputs:
#   strategy
#   symbol
#   market
#   timeframe
#   out-of-sample metrics
#   walk-forward metrics
#
# Outputs:
#   validated / unvalidated
#   research score
#   edge quality
#   stability
#   warnings
#
# IMPORTANT:
#   This engine does not place trades.
# ============================================================

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_DATABASE_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
    / "research_edge_database.json"
)


# ============================================================
# ENGINE
# ============================================================

class ResearchEdgeEngine:

    def __init__(
        self,
        database_path: Optional[str] = None,
    ):

        self.database_path = Path(
            database_path
            if database_path
            else DEFAULT_DATABASE_PATH
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.records: List[
            Dict[str, Any]
        ] = []

        self.load()

    # ========================================================
    # LOAD
    # ========================================================

    def load(self):

        if not self.database_path.exists():

            self.records = []

            return

        try:

            raw = self.database_path.read_text(
                encoding="utf-8"
            )

            if not raw.strip():

                self.records = []

                return

            data = json.loads(
                raw
            )

            if isinstance(
                data,
                list,
            ):

                self.records = data

            else:

                self.records = []

        except Exception as e:

            print(
                "JARVIS EDGE DEBUG > "
                f"Could not load database: {e}"
            )

            self.records = []

    # ========================================================
    # SAVE
    # ========================================================

    def save(self) -> bool:

        try:

            self.database_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.database_path.write_text(
                json.dumps(
                    self.records,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )

            return True

        except Exception as e:

            print(
                "JARVIS EDGE DEBUG > "
                f"Could not save database: {e}"
            )

            return False

    # ========================================================
    # SAFE NUMBER
    # ========================================================

    def number(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if value is None:

                return default

            value = float(
                value
            )

            if math.isnan(value):
                return default

            if math.isinf(value):
                return default

            return value

        except Exception:

            return default

    # ========================================================
    # NORMALIZE PROFIT FACTOR
    # ========================================================

    def profit_factor_score(
        self,
        profit_factor: Any,
    ) -> float:

        pf = self.number(
            profit_factor,
            0.0,
        )

        if pf <= 0:

            return 0.0

        if pf < 1.0:

            return 0.0

        if pf >= 2.0:

            return 100.0

        if pf >= 1.5:

            return 85.0

        if pf >= 1.25:

            return 70.0

        if pf >= 1.10:

            return 55.0

        if pf >= 1.0:

            return 35.0

        return 0.0

    # ========================================================
    # RETURN SCORE
    # ========================================================

    def return_score(
        self,
        return_percent: Any,
    ) -> float:

        value = self.number(
            return_percent,
            0.0,
        )

        if value <= 0:

            return 0.0

        if value >= 20:

            return 100.0

        if value >= 10:

            return 85.0

        if value >= 5:

            return 70.0

        if value >= 2:

            return 55.0

        return 35.0

    # ========================================================
    # DRAWdown SCORE
    # ========================================================

    def drawdown_score(
        self,
        drawdown_percent: Any,
    ) -> float:

        value = abs(
            self.number(
                drawdown_percent,
                100.0,
            )
        )

        if value <= 3:

            return 100.0

        if value <= 5:

            return 90.0

        if value <= 8:

            return 75.0

        if value <= 12:

            return 60.0

        if value <= 20:

            return 40.0

        return 20.0

    # ========================================================
    # WIN RATE SCORE
    # ========================================================

    def win_rate_score(
        self,
        win_rate: Any,
    ) -> float:

        value = self.number(
            win_rate,
            0.0,
        )

        if value <= 0:

            return 0.0

        if value >= 65:

            return 100.0

        if value >= 55:

            return 85.0

        if value >= 45:

            return 70.0

        if value >= 35:

            return 55.0

        if value >= 25:

            return 40.0

        return 20.0

    # ========================================================
    # TRADE COUNT SCORE
    # ========================================================

    def sample_size_score(
        self,
        trades: Any,
    ) -> float:

        value = int(
            max(
                0,
                self.number(
                    trades,
                    0.0,
                ),
            )
        )

        if value >= 200:

            return 100.0

        if value >= 100:

            return 90.0

        if value >= 50:

            return 75.0

        if value >= 30:

            return 60.0

        if value >= 20:

            return 50.0

        if value >= 10:

            return 35.0

        return 15.0

    # ========================================================
    # WALK-FORWARD STABILITY
    # ========================================================

    def walk_forward_stability(
        self,
        windows: Optional[
            List[Dict[str, Any]]
        ],
    ) -> Dict[str, Any]:

        if not windows:

            return {

                "score":
                    0.0,

                "profitable_windows":
                    0,

                "total_windows":
                    0,

                "profit_factor_average":
                    0.0,

                "stable":
                    False,

            }

        returns = []
        profit_factors = []
        profitable = 0

        for window in windows:

            performance = (
                window.get(
                    "test",
                    {}
                ).get(
                    "performance",
                    {}
                )
            )

            return_percent = (
                self.number(
                    performance.get(
                        "return_percent",
                        0,
                    ),
                )
            )

            pf = self.number(
                performance.get(
                    "profit_factor",
                    0,
                ),
            )

            returns.append(
                return_percent
            )

            profit_factors.append(
                pf
            )

            if (
                return_percent > 0
                and
                pf >= 1.0
            ):

                profitable += 1

        total = len(
            windows
        )

        profitable_ratio = (
            profitable
            /
            total
            if total
            else
            0.0
        )

        average_return = (
            sum(returns)
            /
            len(returns)
            if returns
            else
            0.0
        )

        valid_pf = [
            pf
            for pf in profit_factors
            if pf > 0
        ]

        average_pf = (
            sum(valid_pf)
            /
            len(valid_pf)
            if valid_pf
            else
            0.0
        )

        if profitable_ratio >= 0.75:

            stability_score = 100.0

        elif profitable_ratio >= 0.66:

            stability_score = 85.0

        elif profitable_ratio >= 0.50:

            stability_score = 65.0

        elif profitable_ratio >= 0.33:

            stability_score = 40.0

        else:

            stability_score = 15.0

        stable = (
            profitable_ratio >= 0.66
            and
            average_pf >= 1.0
        )

        return {

            "score":
                stability_score,

            "profitable_windows":
                profitable,

            "total_windows":
                total,

            "profitable_ratio":
                profitable_ratio,

            "average_return":
                average_return,

            "average_profit_factor":
                average_pf,

            "stable":
                stable,

        }

    # ========================================================
    # VALIDATE ONE RESULT
    # ========================================================

    def evaluate(
        self,
        strategy: str,
        symbol: str,
        market: str,
        timeframe: str,
        backtest_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        strategy = str(
            strategy
        ).upper().strip()

        symbol = str(
            symbol
        ).upper().strip()

        market = str(
            market
        ).upper().strip()

        timeframe = str(
            timeframe
        ).lower().strip()

        train = backtest_result.get(
            "train",
            {}
        )

        test = backtest_result.get(
            "test",
            {}
        )

        train_perf = (
            train.get(
                "performance",
                {}
            )
        )

        test_perf = (
            test.get(
                "performance",
                {}
            )
        )

        out_of_sample_return = (
            self.number(
                test_perf.get(
                    "return_percent",
                    0,
                )
            )
        )

        out_of_sample_pf = (
            self.number(
                test_perf.get(
                    "profit_factor",
                    0,
                )
            )
        )

        out_of_sample_dd = (
            self.number(
                test_perf.get(
                    "max_drawdown_percent",
                    100,
                )
            )
        )

        out_of_sample_win_rate = (
            self.number(
                test_perf.get(
                    "win_rate",
                    0,
                )
            )
        )

        out_of_sample_trades = (
            self.number(
                test_perf.get(
                    "total_trades",
                    0,
                )
            )
        )

        train_return = (
            self.number(
                train_perf.get(
                    "return_percent",
                    0,
                )
            )
        )

        train_pf = (
            self.number(
                train_perf.get(
                    "profit_factor",
                    0,
                )
            )
        )

        train_positive = (
            train_return > 0
            and
            train_pf >= 1.0
        )

        test_positive = (
            out_of_sample_return > 0
            and
            out_of_sample_pf >= 1.0
        )

        windows = (
            backtest_result.get(
                "walk_forward",
                {}
            ).get(
                "windows",
                []
            )
        )

        stability = (
            self.walk_forward_stability(
                windows
            )
        )

        # ----------------------------------------------------
        # Component scores
        # ----------------------------------------------------

        pf_score = (
            self.profit_factor_score(
                out_of_sample_pf
            )
        )

        return_score = (
            self.return_score(
                out_of_sample_return
            )
        )

        dd_score = (
            self.drawdown_score(
                out_of_sample_dd
            )
        )

        win_rate_score = (
            self.win_rate_score(
                out_of_sample_win_rate
            )
        )

        sample_score = (
            self.sample_size_score(
                out_of_sample_trades
            )
        )

        stability_score = (
            stability[
                "score"
            ]
        )

        # ----------------------------------------------------
        # Core research score
        #
        # OOS performance is deliberately weighted most.
        # ----------------------------------------------------

        research_score = (

            pf_score * 0.30

            +

            return_score * 0.15

            +

            dd_score * 0.15

            +

            win_rate_score * 0.10

            +

            sample_score * 0.10

            +

            stability_score * 0.20

        )

        research_score = round(
            max(
                0.0,
                min(
                    100.0,
                    research_score,
                ),
            ),
            2,
        )

        warnings: List[str] = []

        # ----------------------------------------------------
        # Hard validation rules
        # ----------------------------------------------------

        validated = True

        if not test_positive:

            validated = False

            warnings.append(
                "Out-of-sample performance is not profitable."
            )

        if out_of_sample_pf < 1.10:

            validated = False

            warnings.append(
                "Out-of-sample profit factor is below 1.10."
            )

        if out_of_sample_trades < 20:

            validated = False

            warnings.append(
                "Out-of-sample sample size is small."
            )

        if not stability["stable"]:

            validated = False

            warnings.append(
                "Walk-forward stability is insufficient."
            )

        if (
            train_positive
            and
            not test_positive
        ):

            warnings.append(
                "Training performance does not generalize to the test period."
            )

        if out_of_sample_dd > 15:

            validated = False

            warnings.append(
                "Out-of-sample drawdown is high."
            )

        # ----------------------------------------------------
        # Quality
        # ----------------------------------------------------

        if (
            validated
            and
            research_score >= 80
        ):

            quality = "ROBUST"

        elif (
            validated
            and
            research_score >= 70
        ):

            quality = "PROMISING"

        elif (
            research_score >= 55
        ):

            quality = "WEAK_EDGE"

        else:

            quality = "UNVALIDATED"

        # ----------------------------------------------------
        # Record
        # ----------------------------------------------------

        record = {

            "strategy":
                strategy,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "research_score":
                research_score,

            "quality":
                quality,

            "validated":
                validated,

            "train": {

                "return_percent":
                    train_return,

                "profit_factor":
                    train_pf,

            },

            "out_of_sample": {

                "return_percent":
                    out_of_sample_return,

                "profit_factor":
                    out_of_sample_pf,

                "drawdown_percent":
                    out_of_sample_dd,

                "win_rate":
                    out_of_sample_win_rate,

                "trades":
                    out_of_sample_trades,

            },

            "walk_forward":
                stability,

            "warnings":
                warnings,

        }

        return {

            "success":
                True,

            **record,

        }

    # ========================================================
    # STORE RESULT
    # ========================================================

    def store(
        self,
        evaluation: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not evaluation.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Cannot store invalid evaluation.",

            }

        key_fields = (

            evaluation.get(
                "strategy"
            ),

            evaluation.get(
                "symbol"
            ),

            evaluation.get(
                "market"
            ),

            evaluation.get(
                "timeframe"
            ),

        )

        # Replace an existing record for the same
        # strategy/instrument/timeframe.
        replaced = False

        for index, existing in enumerate(
            self.records
        ):

            existing_key = (

                existing.get(
                    "strategy"
                ),

                existing.get(
                    "symbol"
                ),

                existing.get(
                    "market"
                ),

                existing.get(
                    "timeframe"
                ),

            )

            if existing_key == key_fields:

                self.records[
                    index
                ] = evaluation

                replaced = True

                break

        if not replaced:

            self.records.append(
                evaluation
            )

        saved = self.save()

        return {

            "success":
                saved,

            "replaced":
                replaced,

            "message":
                (
                    "Research edge saved."
                    if saved
                    else
                    "Research edge could not be saved."
                ),

        }

    # ========================================================
    # GET EDGE
    # ========================================================

    def get_edge(
        self,
        strategy: str,
        symbol: str,
        market: str,
        timeframe: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        target = (

            str(
                strategy
            ).upper().strip(),

            str(
                symbol
            ).upper().strip(),

            str(
                market
            ).upper().strip(),

            str(
                timeframe
            ).lower().strip(),

        )

        for record in (
            self.records
        ):

            current = (

                str(
                    record.get(
                        "strategy",
                        "",
                    )
                ).upper().strip(),

                str(
                    record.get(
                        "symbol",
                        "",
                    )
                ).upper().strip(),

                str(
                    record.get(
                        "market",
                        "",
                    )
                ).upper().strip(),

                str(
                    record.get(
                        "timeframe",
                        "",
                    )
                ).lower().strip(),

            )

            if current == target:

                return record

        return None

    # ========================================================
    # ALL EDGES
    # ========================================================

    def all_edges(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        return list(
            self.records
        )

    # ========================================================
    # BEST VALIDATED EDGE
    # ========================================================

    def best_edge(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Optional[
        Dict[str, Any]
    ]:

        candidates = []

        for record in (
            self.records
        ):

            if not record.get(
                "validated",
                False,
            ):

                continue

            if (
                symbol
                and
                str(
                    record.get(
                        "symbol",
                        "",
                    )
                ).upper()
                !=
                str(
                    symbol
                ).upper()
            ):

                continue

            if (
                market
                and
                str(
                    record.get(
                        "market",
                        "",
                    )
                ).upper()
                !=
                str(
                    market
                ).upper()
            ):

                continue

            if (
                timeframe
                and
                str(
                    record.get(
                        "timeframe",
                        "",
                    )
                ).lower()
                !=
                str(
                    timeframe
                ).lower()
            ):

                continue

            candidates.append(
                record
            )

        if not candidates:

            return None

        return max(

            candidates,

            key=lambda record:
                self.number(
                    record.get(
                        "research_score",
                        0,
                    )
                ),

        )

    # ========================================================
    # STRATEGY RANKING
    # ========================================================

    def rank_validated(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> List[
        Dict[str, Any]
    ]:

        results = []

        for record in (
            self.records
        ):

            if not record.get(
                "validated",
                False,
            ):

                continue

            if (
                symbol
                and
                str(
                    record.get(
                        "symbol",
                        "",
                    )
                ).upper()
                !=
                str(
                    symbol
                ).upper()
            ):

                continue

            if (
                market
                and
                str(
                    record.get(
                        "market",
                        "",
                    )
                ).upper()
                !=
                str(
                    market
                ).upper()
            ):

                continue

            if (
                timeframe
                and
                str(
                    record.get(
                        "timeframe",
                        "",
                    )
                ).lower()
                !=
                str(
                    timeframe
                ).lower()
            ):

                continue

            results.append(
                record
            )

        results.sort(

            key=lambda record:
                self.number(
                    record.get(
                        "research_score",
                        0,
                    )
                ),

            reverse=True,

        )

        return results

    # ========================================================
    # FINAL DECISION
    # ========================================================

    def decision(
        self,
        strategy_fit_score: float,
        strategy: str,
        symbol: str,
        market: str,
        timeframe: str,
        minimum_fit: float = 70.0,
        minimum_research: float = 70.0,
    ) -> Dict[str, Any]:

        fit = self.number(
            strategy_fit_score,
            0.0,
        )

        edge = self.get_edge(

            strategy=strategy,

            symbol=symbol,

            market=market,

            timeframe=timeframe,

        )

        if edge is None:

            return {

                "decision":
                    "WAIT",

                "reason":
                    (
                        "No validated research edge exists "
                        "for this strategy/instrument/timeframe."
                    ),

                "strategy_fit":
                    fit,

                "research_score":
                    0.0,

                "validated":
                    False,

            }

        research_score = self.number(
            edge.get(
                "research_score",
                0,
            )
        )

        validated = bool(
            edge.get(
                "validated",
                False,
            )
        )

        if (
            validated
            and
            fit >= minimum_fit
            and
            research_score >= minimum_research
        ):

            return {

                "decision":
                    "CANDIDATE",

                "reason":
                    (
                        "Current setup fit and validated "
                        "research edge both meet the threshold."
                    ),

                "strategy_fit":
                    fit,

                "research_score":
                    research_score,

                "validated":
                    True,

            }

        return {

            "decision":
                "WAIT",

            "reason":
                (
                    "Current setup or validated research "
                    "edge is insufficient."
                ),

            "strategy_fit":
                fit,

            "research_score":
                research_score,

            "validated":
                validated,

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_evaluation(
        self,
        evaluation: Dict[str, Any],
    ) -> str:

        if not evaluation.get(
            "success",
            False,
        ):

            return (
                "RESEARCH EDGE EVALUATION FAILED\n"
                +
                str(
                    evaluation.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        lines = []

        lines.append(
            "JARVIS RESEARCH EDGE"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Strategy: "
            f"{evaluation.get('strategy')}"
        )

        lines.append(
            f"Symbol: "
            f"{evaluation.get('symbol')}"
        )

        lines.append(
            f"Market: "
            f"{evaluation.get('market')}"
        )

        lines.append(
            f"Timeframe: "
            f"{evaluation.get('timeframe')}"
        )

        lines.append(
            f"Research Score: "
            f"{evaluation.get('research_score')}/100"
        )

        lines.append(
            f"Quality: "
            f"{evaluation.get('quality')}"
        )

        lines.append(
            f"Validated: "
            f"{evaluation.get('validated')}"
        )

        oos = evaluation.get(
            "out_of_sample",
            {},
        )

        lines.append("")

        lines.append(
            "OUT-OF-SAMPLE"
        )

        lines.append(
            f"Return: "
            f"{oos.get('return_percent', 0):.2f}%"
        )

        lines.append(
            f"Profit Factor: "
            f"{oos.get('profit_factor')}"
        )

        lines.append(
            f"Win Rate: "
            f"{oos.get('win_rate', 0):.2f}%"
        )

        lines.append(
            f"Trades: "
            f"{oos.get('trades', 0)}"
        )

        lines.append(
            f"Drawdown: "
            f"{oos.get('drawdown_percent', 0):.2f}%"
        )

        stability = evaluation.get(
            "walk_forward",
            {},
        )

        lines.append("")

        lines.append(
            "WALK-FORWARD"
        )

        lines.append(
            f"Profitable Windows: "
            f"{stability.get('profitable_windows', 0)}/"
            f"{stability.get('total_windows', 0)}"
        )

        lines.append(
            f"Average PF: "
            f"{stability.get('average_profit_factor', 0):.2f}"
        )

        lines.append(
            f"Stable: "
            f"{stability.get('stable')}"
        )

        warnings = evaluation.get(
            "warnings",
            [],
        )

        if warnings:

            lines.append("")

            lines.append(
                "WARNINGS"
            )

            for warning in warnings:

                lines.append(
                    f"- {warning}"
                )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

research_edge_engine = (
    ResearchEdgeEngine()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def evaluate_edge(
    strategy,
    symbol,
    market,
    timeframe,
    backtest_result,
):

    return research_edge_engine.evaluate(

        strategy=strategy,

        symbol=symbol,

        market=market,

        timeframe=timeframe,

        backtest_result=backtest_result,

    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS RESEARCH EDGE ENGINE"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # Synthetic example
    #
    # This is deliberately NOT marked as validated because
    # the sample size is small.
    # --------------------------------------------------------

    example = {

        "train": {

            "performance": {

                "return_percent":
                    8.5,

                "profit_factor":
                    1.45,

            },

        },

        "test": {

            "performance": {

                "return_percent":
                    6.2,

                "profit_factor":
                    1.32,

                "max_drawdown_percent":
                    5.8,

                "win_rate":
                    54.0,

                "total_trades":
                    28,

            },

        },

        "walk_forward": {

            "windows": [

                {

                    "test": {

                        "performance": {

                            "return_percent":
                                2.0,

                            "profit_factor":
                                1.15,

                        },

                    },

                },

                {

                    "test": {

                        "performance": {

                            "return_percent":
                                3.1,

                            "profit_factor":
                                1.28,

                        },

                    },

                },

                {

                    "test": {

                        "performance": {

                            "return_percent":
                                1.9,

                            "profit_factor":
                                1.20,

                        },

                    },

                },

            ],

        },

    }

    evaluation = (
        evaluate_edge(

            strategy="TREND_FOLLOWING",

            symbol="NIFTY",

            market="INDIA",

            timeframe="1d",

            backtest_result=example,

        )
    )

    print()

    print(
        research_edge_engine.format_evaluation(
            evaluation
        )
    )

    print()

    store_result = (
        research_edge_engine.store(
            evaluation
        )
    )

    print(
        "STORE RESULT"
    )

    print(
        store_result
    )

    print()

    print(
        "Database:"
    )

    print(
        research_edge_engine.database_path
    )

    print()

    print(
        "Research Edge Engine loaded successfully."
    )