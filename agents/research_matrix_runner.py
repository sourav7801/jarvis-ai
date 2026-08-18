# ============================================================
# JARVIS RESEARCH MATRIX RUNNER
# V1.2
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime
import json
import importlib


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_INSTRUMENTS = [
    ("NIFTY", "india"),
    ("BANKNIFTY", "india"),
    ("SENSEX", "india"),
]

DEFAULT_TIMEFRAMES = [
    "1d",
    "1h",
]

DEFAULT_BARS = 1000


# ============================================================
# STRATEGY MODULES
# ============================================================

STRATEGY_MODULES = {
    "TREND_FOLLOWING":
        "agents.trend_research_runner",

    "BREAKOUT":
        "agents.breakout_research_runner",

    "MOMENTUM":
        "agents.momentum_research_runner",

    "MEAN_REVERSION":
        "agents.mean_reversion_research_runner",
}


# ============================================================
# MATRIX
# ============================================================

class ResearchMatrixRunner:

    def __init__(
        self,
        instruments=None,
        timeframes=None,
        bars: int = DEFAULT_BARS,
    ):

        self.instruments = (
            instruments
            if instruments is not None
            else list(DEFAULT_INSTRUMENTS)
        )

        self.timeframes = (
            timeframes
            if timeframes is not None
            else list(DEFAULT_TIMEFRAMES)
        )

        self.bars = int(bars)

        # ----------------------------------------------------
        # Database path
        # ----------------------------------------------------

        from agents.research_edge_engine import (
            research_edge_engine,
        )

        self.research_edge_engine = (
            research_edge_engine
        )

        self.output_path = (
            self.research_edge_engine
            .database_path
            .parent
            /
            "research_matrix_latest.json"
        )

    # ========================================================
    # FIND RUNNER
    # ========================================================

    def load_runner(
        self,
        strategy_name: str,
    ):

        module_name = (
            STRATEGY_MODULES.get(
                strategy_name
            )
        )

        if not module_name:

            raise ImportError(
                f"No module configured for "
                f"{strategy_name}"
            )

        module = importlib.import_module(
            module_name
        )

        # ----------------------------------------------------
        # Try common naming conventions.
        # ----------------------------------------------------

        candidates = [

            # snake_case full runner
            strategy_name.lower()
            + "_research_runner",

            # class-style converted to snake case
            strategy_name.lower()
            .replace("-", "_")
            + "_research_runner",

            # generic
            "research_runner",

            # strategy-specific names
            "trend_research_runner",
            "breakout_research_runner",
            "momentum_research_runner",
            "mean_reversion_research_runner",

        ]

        for name in candidates:

            if hasattr(
                module,
                name,
            ):

                runner = getattr(
                    module,
                    name,
                )

                if hasattr(
                    runner,
                    "research",
                ):

                    return runner

        # ----------------------------------------------------
        # Search module attributes for any object exposing
        # research().
        # ----------------------------------------------------

        for name in dir(module):

            if name.startswith("_"):
                continue

            try:

                value = getattr(
                    module,
                    name,
                )

            except Exception:
                continue

            if hasattr(
                value,
                "research",
            ):

                return value

        raise ImportError(
            (
                f"Could not find a research runner "
                f"inside {module_name}. "
                f"The module must expose an object "
                f"with a research() method."
            )
        )

    # ========================================================
    # RUN ONE
    # ========================================================

    def run_one(
        self,
        strategy_name: str,
        symbol: str,
        market: str,
        timeframe: str,
    ) -> Dict[str, Any]:

        print()

        print(
            "-" * 60
        )

        print(
            "JARVIS MATRIX > "
            f"{strategy_name} | "
            f"{symbol} | "
            f"{timeframe}"
        )

        print(
            "-" * 60
        )

        try:

            runner = self.load_runner(
                strategy_name
            )

        except Exception as exc:

            return {

                "success":
                    False,

                "strategy":
                    strategy_name,

                "symbol":
                    symbol,

                "market":
                    market,

                "timeframe":
                    timeframe,

                "message":
                    (
                        "Runner loading failed: "
                        f"{exc}"
                    ),

            }

        try:

            result = runner.research(

                symbol=symbol,

                market=market,

                timeframe=timeframe,

                bars=self.bars,

            )

        except Exception as exc:

            return {

                "success":
                    False,

                "strategy":
                    strategy_name,

                "symbol":
                    symbol,

                "market":
                    market,

                "timeframe":
                    timeframe,

                "message":
                    (
                        "Research execution failed: "
                        f"{exc}"
                    ),

            }

        if not result.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "strategy":
                    strategy_name,

                "symbol":
                    symbol,

                "market":
                    market,

                "timeframe":
                    timeframe,

                "message":
                    result.get(
                        "message",
                        "Research failed.",
                    ),

            }

        evaluation = (
            result.get(
                "evaluation",
                {},
            )
        )

        backtest = (
            result.get(
                "backtest",
                {},
            )
        )

        test = (
            backtest
            .get(
                "test",
                {},
            )
            .get(
                "performance",
                {},
            )
        )

        walk_forward = (
            backtest
            .get(
                "walk_forward",
                {},
            )
        )

        return {

            "success":
                True,

            "strategy":
                strategy_name,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "research_score":
                evaluation.get(
                    "research_score",
                    0.0,
                ),

            "quality":
                evaluation.get(
                    "quality",
                    "UNKNOWN",
                ),

            "validated":
                bool(
                    evaluation.get(
                        "validated",
                        False,
                    )
                ),

            "oos_return":
                test.get(
                    "return_percent",
                    0.0,
                ),

            "oos_profit_factor":
                test.get(
                    "profit_factor",
                    0.0,
                ),

            "oos_win_rate":
                test.get(
                    "win_rate",
                    0.0,
                ),

            "oos_trades":
                test.get(
                    "total_trades",
                    0,
                ),

            "oos_drawdown":
                test.get(
                    "max_drawdown_percent",
                    0.0,
                ),

            "wf_profitable_windows":
                walk_forward.get(
                    "profitable_windows",
                    0,
                ),

            "wf_total_windows":
                walk_forward.get(
                    "total_windows",
                    0,
                ),

            "wf_average_pf":
                walk_forward.get(
                    "average_profit_factor",
                    0.0,
                ),

            "wf_stable":
                bool(
                    walk_forward.get(
                        "stable",
                        False,
                    )
                ),

        }

    # ========================================================
    # RUN EVERYTHING
    # ========================================================

    def run(self) -> Dict[str, Any]:

        started_at = (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        )

        results: List[
            Dict[str, Any]
        ] = []

        total_expected = (
            len(
                STRATEGY_MODULES
            )
            *
            len(
                self.instruments
            )
            *
            len(
                self.timeframes
            )
        )

        completed = 0

        print(
            "=" * 60
        )

        print(
            "JARVIS RESEARCH MATRIX RUNNER V1.2"
        )

        print(
            "=" * 60
        )

        print(
            f"Strategies: "
            f"{len(STRATEGY_MODULES)}"
        )

        print(
            f"Instruments: "
            f"{len(self.instruments)}"
        )

        print(
            f"Timeframes: "
            f"{len(self.timeframes)}"
        )

        print(
            f"Expected tests: "
            f"{total_expected}"
        )

        print()

        for symbol, market in (
            self.instruments
        ):

            for timeframe in (
                self.timeframes
            ):

                for strategy_name in (
                    STRATEGY_MODULES
                ):

                    result = self.run_one(

                        strategy_name=
                            strategy_name,

                        symbol=
                            symbol,

                        market=
                            market,

                        timeframe=
                            timeframe,

                    )

                    results.append(
                        result
                    )

                    completed += 1

                    print()

                    print(
                        "JARVIS MATRIX > "
                        f"Progress "
                        f"{completed}/"
                        f"{total_expected}"
                    )

        finished_at = (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        )

        successful = [

            item

            for item in results

            if item.get(
                "success",
                False,
            )

        ]

        failed = [

            item

            for item in results

            if not item.get(
                "success",
                False,
            )

        ]

        payload = {

            "started_at":
                started_at,

            "finished_at":
                finished_at,

            "bars":
                self.bars,

            "strategies":
                list(
                    STRATEGY_MODULES.keys()
                ),

            "instruments":
                self.instruments,

            "timeframes":
                self.timeframes,

            "successful_tests":
                len(successful),

            "failed_tests":
                len(failed),

            "results":
                results,

        }

        # ----------------------------------------------------
        # Save result
        # ----------------------------------------------------

        try:

            self.output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.output_path.write_text(

                json.dumps(
                    payload,
                    indent=2,
                    default=str,
                ),

                encoding="utf-8",

            )

        except Exception as exc:

            print()

            print(
                "JARVIS MATRIX WARNING > "
                f"Save failed: {exc}"
            )

        return payload

    # ========================================================
    # VALIDATED
    # ========================================================

    def validated_ranking(
        self,
        payload: Dict[str, Any],
    ):

        results = [

            item

            for item
            in payload.get(
                "results",
                [],
            )

            if (
                item.get(
                    "success",
                    False,
                )
                and
                item.get(
                    "validated",
                    False,
                )
            )

        ]

        results.sort(

            key=lambda item:
                float(
                    item.get(
                        "research_score",
                        0.0,
                    )
                ),

            reverse=True,

        )

        return results

    # ========================================================
    # TOP RESULTS
    # ========================================================

    def top_results(
        self,
        payload: Dict[str, Any],
    ):

        results = [

            item

            for item
            in payload.get(
                "results",
                [],
            )

            if item.get(
                "success",
                False,
            )

        ]

        def score(
            item
        ):

            try:

                research_score = float(
                    item.get(
                        "research_score",
                        0.0,
                    )
                )

            except Exception:

                research_score = 0.0

            try:

                pf = float(
                    item.get(
                        "oos_profit_factor"
                        or 0.0
                    )
                )

            except Exception:

                pf = 0.0

            return (
                research_score,
                pf,
            )

        results.sort(
            key=score,
            reverse=True,
        )

        return results

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(
        self,
        payload: Dict[str, Any],
    ) -> str:

        lines = []

        successful = int(
            payload.get(
                "successful_tests",
                0,
            )
        )

        failed = int(
            payload.get(
                "failed_tests",
                0,
            )
        )

        total = (
            successful
            +
            failed
        )

        lines.append(
            "JARVIS RESEARCH MATRIX"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Completed: "
            f"{successful}/{total}"
        )

        lines.append(
            f"Failed: "
            f"{failed}"
        )

        # ----------------------------------------------------
        # Validated
        # ----------------------------------------------------

        validated = (
            self.validated_ranking(
                payload
            )
        )

        lines.append("")

        lines.append(
            "VALIDATED EDGES"
        )

        if not validated:

            lines.append(
                "None."
            )

        else:

            for index, item in enumerate(
                validated[:10],
                1,
            ):

                lines.append(

                    f"{index}. "
                    f"{item['strategy']} | "
                    f"{item['symbol']} | "
                    f"{item['timeframe']} | "
                    f"Score={item['research_score']}/100 | "
                    f"OOS PF={item['oos_profit_factor']}"

                )

        # ----------------------------------------------------
        # Top results
        # ----------------------------------------------------

        top = (
            self.top_results(
                payload
            )
        )

        lines.append("")

        lines.append(
            "TOP RESEARCH RESULTS"
        )

        if not top:

            lines.append(
                "No successful research runs."
            )

        else:

            for index, item in enumerate(
                top[:15],
                1,
            ):

                status = (
                    "VALIDATED"
                    if item.get(
                        "validated",
                        False,
                    )
                    else
                    "UNVALIDATED"
                )

                lines.append(

                    f"{index}. "
                    f"{item['strategy']} | "
                    f"{item['symbol']} | "
                    f"{item['timeframe']} | "
                    f"Score={item['research_score']}/100 | "
                    f"OOS={item['oos_return']:.2f}% | "
                    f"PF={item['oos_profit_factor']} | "
                    f"Trades={item['oos_trades']} | "
                    f"{status}"

                )

        lines.append("")

        lines.append(
            "RESEARCH DATABASE"
        )

        lines.append(
            str(
                self.research_edge_engine.database_path
            )
        )

        lines.append("")

        lines.append(
            "MATRIX FILE"
        )

        lines.append(
            str(
                self.output_path
            )
        )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Historical research is evidence, "
            "not a guarantee of future performance."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

research_matrix_runner = (
    ResearchMatrixRunner()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    payload = (
        research_matrix_runner.run()
    )

    print()

    print(
        research_matrix_runner.summary(
            payload
        )
    )

    print()

    print(
        "Research Matrix Runner V1.2 loaded successfully."
    )