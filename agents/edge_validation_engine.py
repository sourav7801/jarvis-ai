# ============================================================
# JARVIS EDGE VALIDATION ENGINE
# V1
# ============================================================
#
# Purpose:
#   Aggregate independent research results across markets and
#   timeframes before allowing a strategy to be considered
#   robust.
#
# Important distinction:
#
#   Research Score
#       = performance of ONE strategy / market / timeframe
#
#   Aggregate Edge
#       = consistency across MULTIPLE independent cells
#
# A strategy is NOT validated merely because one cell has a
# high score or high profit factor.
#
# No live orders.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json
import math


# ============================================================
# DEFAULT RULES
# ============================================================

DEFAULT_MIN_CELLS = 3

DEFAULT_MIN_TOTAL_TRADES = 30

DEFAULT_MIN_MEDIAN_PF = 1.10

DEFAULT_MIN_AGGREGATE_RETURN = 0.0

DEFAULT_MIN_PROFITABLE_CELL_RATIO = 0.60

DEFAULT_MAX_CELL_DRAWDOWN = 20.0

DEFAULT_MIN_VALIDATED_CELL_SCORE = 55.0


# ============================================================
# ENGINE
# ============================================================

class EdgeValidationEngine:

    def __init__(
        self,
        min_cells: int = DEFAULT_MIN_CELLS,
        min_total_trades: int = DEFAULT_MIN_TOTAL_TRADES,
        min_median_pf: float = DEFAULT_MIN_MEDIAN_PF,
        min_aggregate_return: float = DEFAULT_MIN_AGGREGATE_RETURN,
        min_profitable_cell_ratio: float = DEFAULT_MIN_PROFITABLE_CELL_RATIO,
        max_cell_drawdown: float = DEFAULT_MAX_CELL_DRAWDOWN,
        min_cell_score: float = DEFAULT_MIN_VALIDATED_CELL_SCORE,
    ):

        self.min_cells = int(
            min_cells
        )

        self.min_total_trades = int(
            min_total_trades
        )

        self.min_median_pf = float(
            min_median_pf
        )

        self.min_aggregate_return = float(
            min_aggregate_return
        )

        self.min_profitable_cell_ratio = float(
            min_profitable_cell_ratio
        )

        self.max_cell_drawdown = float(
            max_cell_drawdown
        )

        self.min_cell_score = float(
            min_cell_score
        )

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
    # MEDIAN
    # ========================================================

    def median(
        self,
        values: List[float],
    ) -> float:

        if not values:
            return 0.0

        ordered = sorted(
            values
        )

        length = len(
            ordered
        )

        middle = length // 2

        if length % 2 == 1:

            return ordered[
                middle
            ]

        return (
            ordered[middle - 1]
            +
            ordered[middle]
        ) / 2.0

    # ========================================================
    # VALID CELL
    # ========================================================

    def valid_cell(
        self,
        cell: Dict[str, Any],
    ) -> bool:

        return bool(
            cell.get(
                "success",
                False,
            )
        )

    # ========================================================
    # AGGREGATE
    # ========================================================

    def aggregate_strategy(
        self,
        strategy: str,
        results: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        strategy = (
            str(
                strategy
            )
            .upper()
            .strip()
        )

        cells = [

            item

            for item in results

            if self.valid_cell(
                item
            )

            and
            str(
                item.get(
                    "strategy",
                    "",
                )
            )
            .upper()
            .strip()
            ==
            strategy

        ]

        if not cells:

            return {

                "success":
                    False,

                "strategy":
                    strategy,

                "message":
                    "No successful research cells found.",

            }

        # ----------------------------------------------------
        # Extract metrics
        # ----------------------------------------------------

        oos_returns = [

            self.number(
                item.get(
                    "oos_return",
                    0.0,
                )
            )

            for item in cells

        ]

        profit_factors = [

            self.number(
                item.get(
                    "oos_profit_factor",
                    0.0,
                )
            )

            for item in cells

            if (
                item.get(
                    "oos_profit_factor"
                )
                is not None
                and
                self.number(
                    item.get(
                        "oos_profit_factor",
                        0.0,
                    )
                )
                > 0
            )

        ]

        trade_counts = [

            int(
                max(
                    0,
                    self.number(
                        item.get(
                            "oos_trades",
                            0,
                        )
                    )
                )
            )

            for item in cells

        ]

        drawdowns = [

            self.number(
                item.get(
                    "oos_drawdown",
                    0.0,
                )
            )

            for item in cells

        ]

        research_scores = [

            self.number(
                item.get(
                    "research_score",
                    0.0,
                )
            )

            for item in cells

        ]

        # ----------------------------------------------------
        # Profitable cells
        # ----------------------------------------------------

        profitable_cells = [

            item

            for item in cells

            if (
                self.number(
                    item.get(
                        "oos_return",
                        0.0,
                    )
                )
                > 0
                and
                self.number(
                    item.get(
                        "oos_profit_factor",
                        0.0,
                    )
                )
                >= 1.0
            )

        ]

        stable_cells = [

            item

            for item in cells

            if bool(
                item.get(
                    "wf_stable",
                    False,
                )
            )

        ]

        bad_drawdown_cells = [

            item

            for item in cells

            if (
                self.number(
                    item.get(
                        "oos_drawdown",
                        0.0,
                    )
                )
                >
                self.max_cell_drawdown
            )

        ]

        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        cell_count = len(
            cells
        )

        total_trades = sum(
            trade_counts
        )

        aggregate_return = sum(
            oos_returns
        )

        median_pf = self.median(
            profit_factors
        )

        average_pf = (

            sum(profit_factors)
            /
            len(profit_factors)

            if profit_factors

            else
            0.0

        )

        median_score = self.median(
            research_scores
        )

        profitable_ratio = (

            len(profitable_cells)
            /
            cell_count

            if cell_count
            else
            0.0

        )

        stable_ratio = (

            len(stable_cells)
            /
            cell_count

            if cell_count
            else
            0.0

        )

        average_drawdown = (

            sum(drawdowns)
            /
            len(drawdowns)

            if drawdowns

            else
            0.0

        )

        max_drawdown = (
            max(drawdowns)
            if drawdowns
            else 0.0
        )

        # ----------------------------------------------------
        # Cross-market/timeframe diversity
        # ----------------------------------------------------

        instruments = sorted(
            {
                str(
                    item.get(
                        "symbol",
                        "",
                    )
                )
                .upper()
                for item in cells
            }
        )

        timeframes = sorted(
            {
                str(
                    item.get(
                        "timeframe",
                        "",
                    )
                )
                .lower()
                for item in cells
            }
        )

        markets = sorted(
            {
                str(
                    item.get(
                        "market",
                        "",
                    )
                )
                .upper()
                for item in cells
            }
        )

        # ----------------------------------------------------
        # Validation rules
        # ----------------------------------------------------

        checks = {}

        checks[
            "minimum_cells"
        ] = (
            cell_count
            >=
            self.min_cells
        )

        checks[
            "minimum_total_trades"
        ] = (
            total_trades
            >=
            self.min_total_trades
        )

        checks[
            "minimum_median_profit_factor"
        ] = (
            median_pf
            >=
            self.min_median_pf
        )

        checks[
            "positive_aggregate_return"
        ] = (
            aggregate_return
            >
            self.min_aggregate_return
        )

        checks[
            "profitable_cell_ratio"
        ] = (
            profitable_ratio
            >=
            self.min_profitable_cell_ratio
        )

        checks[
            "drawdown_control"
        ] = (
            max_drawdown
            <=
            self.max_cell_drawdown
        )

        checks[
            "research_score"
        ] = (
            median_score
            >=
            self.min_cell_score
        )

        # ----------------------------------------------------
        # Strong diversity requirement
        #
        # At least two distinct instruments and two distinct
        # timeframes are preferred. This is NOT mandatory for
        # promising status, but is required for ROBUST.
        # ----------------------------------------------------

        diversity_score = 0

        if len(instruments) >= 2:
            diversity_score += 1

        if len(timeframes) >= 2:
            diversity_score += 1

        if len(markets) >= 1:
            diversity_score += 1

        robust_diversity = (
            diversity_score >= 2
        )

        # ----------------------------------------------------
        # Core validation
        # ----------------------------------------------------

        all_core_pass = all(
            checks.values()
        )

        robust = (
            all_core_pass
            and
            robust_diversity
            and
            stable_ratio >= 0.50
        )

        promising = (
            cell_count >= 2
            and
            total_trades >= 15
            and
            median_pf >= 1.0
            and
            aggregate_return > 0
            and
            profitable_ratio >= 0.50
        )

        if robust:

            status = "ROBUST"

        elif promising:

            status = "PROMISING"

        else:

            status = "UNVALIDATED"

        # ----------------------------------------------------
        # Warnings
        # ----------------------------------------------------

        warnings = []

        if cell_count < self.min_cells:

            warnings.append(
                "Too few independent research cells."
            )

        if total_trades < self.min_total_trades:

            warnings.append(
                "Total out-of-sample trade count is too small."
            )

        if median_pf < self.min_median_pf:

            warnings.append(
                "Median out-of-sample profit factor is below threshold."
            )

        if aggregate_return <= self.min_aggregate_return:

            warnings.append(
                "Aggregate out-of-sample return is not positive."
            )

        if profitable_ratio < self.min_profitable_cell_ratio:

            warnings.append(
                "Too few research cells are profitable."
            )

        if max_drawdown > self.max_cell_drawdown:

            warnings.append(
                "At least one research cell has excessive drawdown."
            )

        if median_score < self.min_cell_score:

            warnings.append(
                "Median research score is below threshold."
            )

        if not robust_diversity:

            warnings.append(
                "Cross-market/timeframe diversity is insufficient for robust validation."
            )

        if stable_ratio < 0.50:

            warnings.append(
                "Less than half of research cells have stable walk-forward results."
            )

        # ----------------------------------------------------
        # Aggregate score
        #
        # This is NOT probability of profit.
        # ----------------------------------------------------

        pf_component = min(
            100.0,
            max(
                0.0,
                (
                    median_pf
                    / 2.0
                    * 100.0
                ),
            ),
        )

        return_component = min(
            100.0,
            max(
                0.0,
                (
                    aggregate_return
                    / 20.0
                    * 100.0
                ),
            ),
        )

        profitability_component = min(
            100.0,
            profitable_ratio
            * 100.0,
        )

        stability_component = min(
            100.0,
            stable_ratio
            * 100.0,
        )

        sample_component = min(
            100.0,
            (
                total_trades
                /
                max(
                    self.min_total_trades,
                    1,
                )
                *
                100.0
            ),
        )

        diversity_component = min(
            100.0,
            (
                diversity_score
                /
                3.0
                *
                100.0
            ),
        )

        aggregate_score = (

            pf_component
            * 0.25

            +

            return_component
            * 0.15

            +

            profitability_component
            * 0.15

            +

            stability_component
            * 0.15

            +

            sample_component
            * 0.15

            +

            diversity_component
            * 0.15

        )

        aggregate_score = round(
            min(
                100.0,
                max(
                    0.0,
                    aggregate_score,
                ),
            ),
            2,
        )

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        return {

            "success":
                True,

            "strategy":
                strategy,

            "status":
                status,

            "aggregate_score":
                aggregate_score,

            "cells":
                cell_count,

            "total_trades":
                total_trades,

            "aggregate_return":
                aggregate_return,

            "median_profit_factor":
                median_pf,

            "average_profit_factor":
                average_pf,

            "median_research_score":
                median_score,

            "profitable_cells":
                len(profitable_cells),

            "profitable_cell_ratio":
                profitable_ratio,

            "stable_cells":
                len(stable_cells),

            "stable_cell_ratio":
                stable_ratio,

            "average_drawdown":
                average_drawdown,

            "max_drawdown":
                max_drawdown,

            "instruments":
                instruments,

            "timeframes":
                timeframes,

            "markets":
                markets,

            "diversity_score":
                diversity_score,

            "checks":
                checks,

            "warnings":
                warnings,

            "robust":
                robust,

            "promising":
                promising,

            "validated":
                robust,

            "research_cells":
                cells,

            "evaluated_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

        }

    # ========================================================
    # VALIDATE MATRIX
    # ========================================================

    def validate_matrix(
        self,
        matrix_payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        results = (
            matrix_payload.get(
                "results",
                [],
            )
        )

        strategies = sorted(
            {
                str(
                    item.get(
                        "strategy",
                        "",
                    )
                )
                .upper()
                .strip()

                for item in results

                if item.get(
                    "success",
                    False,
                )

            }
        )

        evaluations = {}

        for strategy in strategies:

            evaluations[
                strategy
            ] = self.aggregate_strategy(

                strategy=strategy,

                results=results,

            )

        validated = [

            item

            for item
            in evaluations.values()

            if item.get(
                "validated",
                False,
            )

        ]

        validated.sort(

            key=lambda item:
                self.number(
                    item.get(
                        "aggregate_score",
                        0.0,
                    )
                ),

            reverse=True,

        )

        return {

            "success":
                True,

            "evaluated_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "evaluations":
                evaluations,

            "validated_strategies":
                validated,

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_report(
        self,
        report: Dict[str, Any],
    ) -> str:

        if not report.get(
            "success",
            False,
        ):

            return (
                "EDGE VALIDATION FAILED\n"
                "--------------------------------------------------\n"
                +
                str(
                    report.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        lines = []

        lines.append(
            "JARVIS EDGE VALIDATION ENGINE"
        )

        lines.append(
            "--------------------------------------------------"
        )

        validated = (
            report.get(
                "validated_strategies",
                [],
            )
        )

        lines.append(
            "VALIDATED STRATEGIES"
        )

        if not validated:

            lines.append(
                "None."
            )

        else:

            for index, item in enumerate(
                validated,
                1,
            ):

                lines.append(

                    f"{index}. "
                    f"{item.get('strategy')} | "
                    f"Aggregate Score="
                    f"{item.get('aggregate_score')}/100 | "
                    f"Median PF="
                    f"{item.get('median_profit_factor'):.2f} | "
                    f"Trades="
                    f"{item.get('total_trades')}"

                )

        lines.append("")

        lines.append(
            "STRATEGY EVALUATIONS"
        )

        evaluations = report.get(
            "evaluations",
            {},
        )

        for strategy, evaluation in (
            sorted(
                evaluations.items()
            )
        ):

            lines.append("")

            lines.append(
                f"{strategy}"
            )

            lines.append(
                f"Status: "
                f"{evaluation.get('status')}"
            )

            lines.append(
                f"Aggregate Score: "
                f"{evaluation.get('aggregate_score')}/100"
            )

            lines.append(
                f"Cells: "
                f"{evaluation.get('cells')}"
            )

            lines.append(
                f"Total OOS Trades: "
                f"{evaluation.get('total_trades')}"
            )

            lines.append(
                f"Aggregate OOS Return: "
                f"{evaluation.get('aggregate_return', 0):.2f}%"
            )

            lines.append(
                f"Median PF: "
                f"{evaluation.get('median_profit_factor', 0):.2f}"
            )

            lines.append(
                f"Profitable Cells: "
                f"{evaluation.get('profitable_cells')}/"
                f"{evaluation.get('cells')}"
            )

            lines.append(
                f"Stable Cells: "
                f"{evaluation.get('stable_cells')}/"
                f"{evaluation.get('cells')}"
            )

            lines.append(
                f"Validated: "
                f"{evaluation.get('validated')}"
            )

            warnings = evaluation.get(
                "warnings",
                [],
            )

            if warnings:

                lines.append(
                    "Warnings:"
                )

                for warning in warnings:

                    lines.append(
                        f"- {warning}"
                    )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Aggregate validation is research evidence, "
            "not a probability of profit or a guarantee "
            "of future performance."
        )

        return "\n".join(
            lines
        )

    # ========================================================
    # SAVE REPORT
    # ========================================================

    def save_report(
        self,
        report: Dict[str, Any],
        path: Optional[
            str
        ] = None,
    ) -> Dict[str, Any]:

        output = Path(
            path
            if path
            else
            (
                self.research_edge_path()
                /
                "edge_validation_latest.json"
            )
        )

        try:

            output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            output.write_text(

                json.dumps(
                    report,
                    indent=2,
                    default=str,
                ),

                encoding="utf-8",

            )

            return {

                "success":
                    True,

                "path":
                    str(
                        output
                    ),

            }

        except Exception as exc:

            return {

                "success":
                    False,

                "message":
                    str(
                        exc
                    ),

            }

    # ========================================================
    # DATABASE LOCATION
    # ========================================================

    def research_edge_path(
        self,
    ) -> Path:

        try:

            path = Path(
                self
                ._database_path()
            )

            return path.parent

        except Exception:

            return (
                Path.home()
                /
                "Documents"
                /
                "JARVIS_Trading"
            )

    def _database_path(
        self,
    ):

        try:

            from agents.research_edge_engine import (
                research_edge_engine,
            )

            return (
                research_edge_engine.database_path
            )

        except Exception:

            return (
                Path.home()
                /
                "Documents"
                /
                "JARVIS_Trading"
                /
                "research_edge_database.json"
            )

    # ========================================================
    # LOAD MATRIX FILE
    # ========================================================

    def load_matrix_file(
        self,
        path: Optional[
            str
        ] = None,
    ) -> Dict[str, Any]:

        file_path = Path(

            path

            if path

            else

            (
                self.research_edge_path()
                /
                "research_matrix_latest.json"
            )

        )

        if not file_path.exists():

            return {

                "success":
                    False,

                "message":
                    (
                        f"Matrix file not found: "
                        f"{file_path}"
                    ),

            }

        try:

            data = json.loads(
                file_path.read_text(
                    encoding="utf-8"
                )
            )

            return {

                "success":
                    True,

                "path":
                    str(
                        file_path
                    ),

                "data":
                    data,

            }

        except Exception as exc:

            return {

                "success":
                    False,

                "message":
                    str(
                        exc
                    ),

            }


# ============================================================
# GLOBAL
# ============================================================

edge_validation_engine = (
    EdgeValidationEngine()
)


# ============================================================
# SIMPLE HELPER
# ============================================================

def validate_research_matrix(
    matrix_payload:
    Dict[str, Any],
):

    return (
        edge_validation_engine.validate_matrix(
            matrix_payload
        )
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS EDGE VALIDATION ENGINE"
    )

    print(
        "=" * 60
    )

    loaded = (
        edge_validation_engine.load_matrix_file()
    )

    if not loaded.get(
        "success",
        False,
    ):

        print()

        print(
            loaded.get(
                "message"
            )
        )

        print()

        print(
            "Run the research matrix first:"
        )

        print(
            "python -m agents.research_matrix_runner"
        )

    else:

        report = (
            edge_validation_engine.validate_matrix(

                loaded["data"]

            )
        )

        print()

        print(
            edge_validation_engine.format_report(
                report
            )
        )

        saved = (
            edge_validation_engine.save_report(
                report
            )
        )

        print()

        print(
            "REPORT SAVED"
        )

        print(
            saved
        )

    print()

    print(
        "Edge Validation Engine loaded successfully."
    )