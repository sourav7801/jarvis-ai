from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

PKG = ROOT / "omni" / "trading_intelligence"

PARTITIONS   = PKG / "validation_partitions.py"
WALK_FORWARD = PKG / "walk_forward.py"
MONTE_CARLO  = PKG / "monte_carlo.py"
SENSITIVITY  = PKG / "parameter_sensitivity.py"
COST_STRESS  = PKG / "cost_stress.py"
ROBUSTNESS   = PKG / "robustness_evaluator.py"
OVERFIT      = PKG / "overfitting_risk.py"
GATE         = PKG / "candidate_validation_gate.py"
LAB          = PKG / "strategy_validation_lab.py"
STORE        = PKG / "validation_store.py"
STATUS       = PKG / "trading_v5_status.py"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"
TEST = ROOT / "tests" / "test_trading_intelligence_v5.py"

MANIFEST = ROOT / "config" / "protected_core_manifest.json"

ARCHIVE = ROOT / "archive" / "trading_intelligence_v5"
ARCHIVE.mkdir(parents=True, exist_ok=True)

FILES = [
    PARTITIONS,
    WALK_FORWARD,
    MONTE_CARLO,
    SENSITIVITY,
    COST_STRESS,
    ROBUSTNESS,
    OVERFIT,
    GATE,
    LAB,
    STORE,
    STATUS,
    MAIN,
    APP,
    TEST,
]

BACKUPS = {}


def run(*args, capture=False):
    return subprocess.run(
        [str(PY), *args],
        cwd=ROOT,
        capture_output=capture,
        text=True,
    )


def sha(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(path, source):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(source).lstrip(),
        encoding="utf-8",
    )


def rollback():
    print()
    print("ROLLBACK")

    for path, existed in BACKUPS.items():

        backup = ARCHIVE / path.relative_to(ROOT)

        if existed:
            shutil.copy2(
                backup,
                path,
            )
        else:
            path.unlink(
                missing_ok=True
            )

    print("JARVIS source restored.")


print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V5")
print("WALK-FORWARD + MONTE CARLO + ANTI-OVERFITTING VALIDATION")
print("=" * 80)


# ============================================================
# BACKUP
# ============================================================

for path in FILES:

    BACKUPS[path] = path.exists()

    if path.exists():

        destination = ARCHIVE / path.relative_to(ROOT)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


# ============================================================
# BASELINE V4 / 567
# ============================================================

print()
print("Checking Trading Intelligence V4 / 567 checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "v3=main.jarvis_trading_v3_status(); "
        "v4=main.jarvis_trading_v4_status(); "
        "assert v3['option_chain_schema']; "
        "assert v4['strategy_genomes']; "
        "assert v4['champion_challenger']; "
        "assert v4['live_execution'] is False; "
        "assert v4['automatic_strategy_promotion'] is False; "
        "assert v4['automatic_registry_mutation'] is False; "
        "assert v4['production_self_modification'] is False; "
        "print('Main import: PASS'); "
        "print('Protected Core: PASS'); "
        "print('Trading V3: PASS'); "
        "print('Trading V4 / Strategy Evolution: PASS'); "
        "print('Automatic production promotion: BLOCKED')"
    ),
)

if r.returncode:
    print("BASELINE FAILURE")
    sys.exit(1)


r = run(
    "-m",
    "unittest",
    (
        "tests.test_computer_operator_v2."
        "ComputerOperatorV2Tests.test_dom_provider"
    ),
    "-q",
)

if r.returncode:
    print("BROWSER BASELINE FAILURE")
    sys.exit(1)


print("Browser DOM repair: PASS")


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)


PROTECTED = {
    relative:
        sha(ROOT / relative)

    for relative
    in manifest.get("files", {})
}


print("Protected files:", len(PROTECTED))
print("Baseline: PASS")


# ============================================================
# CHRONOLOGICAL PARTITIONS
# ============================================================

write(
    PARTITIONS,
    r'''
from __future__ import annotations


def chronological_split(
    bars,
    *,
    train_ratio=0.60,
    validation_ratio=0.20,
    minimum_segment_bars=32,
):

    bars = tuple(bars)

    total = len(bars)

    if total < minimum_segment_bars * 3:
        raise ValueError(
            "Insufficient data for independent "
            "train/validation/out-of-sample partitions."
        )


    train_ratio = float(train_ratio)
    validation_ratio = float(validation_ratio)

    if not 0 < train_ratio < 1:
        raise ValueError(
            "train_ratio must be between 0 and 1."
        )

    if not 0 < validation_ratio < 1:
        raise ValueError(
            "validation_ratio must be between 0 and 1."
        )

    if train_ratio + validation_ratio >= 1:
        raise ValueError(
            "A positive out-of-sample partition is required."
        )


    train_end = int(
        total * train_ratio
    )

    validation_end = train_end + int(
        total * validation_ratio
    )


    train = bars[:train_end]
    validation = bars[
        train_end:validation_end
    ]
    out_of_sample = bars[
        validation_end:
    ]


    for name, segment in (
        ("train", train),
        ("validation", validation),
        ("out_of_sample", out_of_sample),
    ):

        if len(segment) < minimum_segment_bars:
            raise ValueError(
                name
                + " partition is too small."
            )


    return {
        "train":
            train,

        "validation":
            validation,

        "out_of_sample":
            out_of_sample,

        "counts": {
            "total":
                total,

            "train":
                len(train),

            "validation":
                len(validation),

            "out_of_sample":
                len(out_of_sample),
        },

        "chronological":
            True,

        "shuffled":
            False,

        "research_only":
            True,
    }


def rolling_windows(
    bars,
    *,
    train_size,
    validation_size,
    test_size,
    step=None,
):

    bars = tuple(bars)

    train_size = int(train_size)
    validation_size = int(validation_size)
    test_size = int(test_size)

    step = int(
        step
        if step is not None
        else test_size
    )


    if min(
        train_size,
        validation_size,
        test_size,
        step,
    ) <= 0:
        raise ValueError(
            "Walk-forward window sizes must be positive."
        )


    required = (
        train_size
        + validation_size
        + test_size
    )


    if len(bars) < required:
        raise ValueError(
            "Insufficient bars for walk-forward validation."
        )


    output = []

    start = 0
    window_id = 0


    while (
        start
        + required
        <= len(bars)
    ):

        train_end = (
            start
            + train_size
        )

        validation_end = (
            train_end
            + validation_size
        )

        test_end = (
            validation_end
            + test_size
        )


        output.append(
            {
                "window_id":
                    window_id,

                "train":
                    bars[
                        start:train_end
                    ],

                "validation":
                    bars[
                        train_end:validation_end
                    ],

                "out_of_sample":
                    bars[
                        validation_end:test_end
                    ],

                "indexes": {
                    "start":
                        start,

                    "train_end":
                        train_end,

                    "validation_end":
                        validation_end,

                    "test_end":
                        test_end,
                },
            }
        )


        window_id += 1
        start += step


    return tuple(output)
'''
)


# ============================================================
# WALK FORWARD
# ============================================================

write(
    WALK_FORWARD,
    r'''
from __future__ import annotations

from statistics import fmean


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)

from omni.trading_intelligence.validation_partitions import (
    rolling_windows,
)


class WalkForwardValidator:

    def run(
        self,
        bars,
        strategy,
        config,
        *,
        train_size,
        validation_size,
        test_size,
        step=None,
    ):

        windows = rolling_windows(
            bars,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            step=step,
        )


        results = []


        for window in windows:

            train_result = historical_backtester.run(
                window["train"],
                strategy,
                config,
            )

            validation_result = historical_backtester.run(
                window["validation"],
                strategy,
                config,
            )

            oos_result = historical_backtester.run(
                window["out_of_sample"],
                strategy,
                config,
            )


            train_fitness = result_fitness(
                train_result
            )

            validation_fitness = result_fitness(
                validation_result
            )

            oos_fitness = result_fitness(
                oos_result
            )


            results.append(
                {
                    "window_id":
                        window["window_id"],

                    "indexes":
                        window["indexes"],

                    "train":
                        train_result,

                    "validation":
                        validation_result,

                    "out_of_sample":
                        oos_result,

                    "fitness": {
                        "train":
                            train_fitness,

                        "validation":
                            validation_fitness,

                        "out_of_sample":
                            oos_fitness,
                    },

                    "oos_profitable":
                        (
                            float(
                                oos_result[
                                    "metrics"
                                ].get(
                                    "net_pnl",
                                    0.0,
                                )
                            )
                            > 0
                        ),
                }
            )


        oos_scores = [
            item[
                "fitness"
            ][
                "out_of_sample"
            ][
                "score"
            ]

            for item in results
        ]


        profitable = sum(
            1
            for item in results
            if item[
                "oos_profitable"
            ]
        )


        pass_rate = (
            profitable
            / len(results)
            if results
            else 0.0
        )


        return {
            "success":
                True,

            "windows":
                tuple(results),

            "window_count":
                len(results),

            "oos_profitable_windows":
                profitable,

            "oos_pass_rate":
                pass_rate,

            "average_oos_fitness":
                (
                    fmean(oos_scores)
                    if oos_scores
                    else 0.0
                ),

            "chronological":
                True,

            "candidate_reoptimized_on_oos":
                False,

            "research_only":
                True,
        }


walk_forward_validator = (
    WalkForwardValidator()
)
'''
)


# ============================================================
# MONTE CARLO
# ============================================================

write(
    MONTE_CARLO,
    r'''
from __future__ import annotations

import random

from statistics import (
    fmean,
)


def _percentile(
    values,
    percentile,
):

    values = sorted(
        float(value)
        for value in values
    )


    if not values:
        return 0.0


    index = (
        len(values)
        - 1
    ) * float(percentile)


    lower = int(index)
    upper = min(
        lower + 1,
        len(values) - 1,
    )


    fraction = (
        index
        - lower
    )


    return (
        values[lower]
        * (
            1.0
            - fraction
        )
        + values[upper]
        * fraction
    )


class MonteCarloTradeSimulator:

    MAX_ITERATIONS = 5000


    @staticmethod
    def _drawdown(
        pnl_sequence,
        initial_capital,
    ):

        equity = float(
            initial_capital
        )

        peak = equity
        max_drawdown = 0.0


        for pnl in pnl_sequence:

            equity += float(pnl)

            peak = max(
                peak,
                equity,
            )

            max_drawdown = max(
                max_drawdown,
                peak - equity,
            )


        return (
            equity,
            max_drawdown,
        )


    def run(
        self,
        trades,
        *,
        initial_capital,
        iterations=1000,
        random_seed=1,
        bootstrap=True,
    ):

        trades = tuple(trades)

        if not trades:
            raise ValueError(
                "Monte Carlo requires at least one trade."
            )


        iterations = int(iterations)

        if (
            iterations <= 0
            or iterations > self.MAX_ITERATIONS
        ):
            raise ValueError(
                "Invalid Monte Carlo iteration count."
            )


        pnl = [
            float(
                trade.get(
                    "net_pnl",
                    0.0,
                )
            )

            for trade in trades
        ]


        rng = random.Random(
            random_seed
        )


        endings = []
        drawdowns = []


        for _ in range(iterations):

            if bootstrap:

                sequence = [
                    rng.choice(pnl)

                    for _ in range(
                        len(pnl)
                    )
                ]

            else:

                sequence = list(pnl)

                rng.shuffle(
                    sequence
                )


            ending, drawdown = (
                self._drawdown(
                    sequence,
                    initial_capital,
                )
            )


            endings.append(
                ending
            )

            drawdowns.append(
                drawdown
            )


        initial_capital = float(
            initial_capital
        )


        losing_runs = sum(
            1

            for value in endings

            if value < initial_capital
        )


        return {
            "success":
                True,

            "iterations":
                iterations,

            "trade_count":
                len(pnl),

            "bootstrap":
                bool(bootstrap),

            "median_ending_equity":
                _percentile(
                    endings,
                    0.50,
                ),

            "ending_equity_p05":
                _percentile(
                    endings,
                    0.05,
                ),

            "ending_equity_p95":
                _percentile(
                    endings,
                    0.95,
                ),

            "median_max_drawdown":
                _percentile(
                    drawdowns,
                    0.50,
                ),

            "max_drawdown_p95":
                _percentile(
                    drawdowns,
                    0.95,
                ),

            "loss_probability":
                (
                    losing_runs
                    / iterations
                ),

            "average_ending_equity":
                fmean(endings),

            "research_only":
                True,
        }


monte_carlo_trade_simulator = (
    MonteCarloTradeSimulator()
)
'''
)


# ============================================================
# PARAMETER SENSITIVITY
# ============================================================

write(
    SENSITIVITY,
    r'''
from __future__ import annotations

from dataclasses import replace

from statistics import (
    fmean,
    pstdev,
)


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)


DEFAULT_VALUES = {
    "stop_loss_pct":
        (
            0.01,
            0.02,
            0.03,
        ),

    "target_pct":
        (
            0.02,
            0.04,
            0.06,
        ),

    "trailing_stop_pct":
        (
            None,
            0.01,
            0.02,
        ),

    "max_bars_in_trade":
        (
            10,
            20,
            40,
        ),
}


class ParameterSensitivityAnalyzer:

    MAX_RUNS = 30


    def run(
        self,
        bars,
        strategy,
        base_config,
        *,
        fields=(
            "stop_loss_pct",
            "target_pct",
            "max_bars_in_trade",
        ),
    ):

        results = []

        run_count = 0


        for field in fields:

            if field not in DEFAULT_VALUES:

                raise ValueError(
                    "Unsupported sensitivity field: "
                    + str(field)
                )


            field_results = []


            for value in DEFAULT_VALUES[
                field
            ]:

                run_count += 1

                if run_count > self.MAX_RUNS:
                    raise ValueError(
                        "Sensitivity analysis exceeds run limit."
                    )


                config = replace(
                    base_config,
                    **{
                        field:
                            value
                    }
                )


                backtest = historical_backtester.run(
                    bars,
                    strategy,
                    config,
                )


                fitness = result_fitness(
                    backtest
                )


                field_results.append(
                    {
                        "value":
                            value,

                        "fitness":
                            fitness,

                        "net_pnl":
                            float(
                                backtest[
                                    "metrics"
                                ].get(
                                    "net_pnl",
                                    0.0,
                                )
                            ),
                    }
                )


            scores = [
                item[
                    "fitness"
                ][
                    "score"
                ]

                for item
                in field_results
            ]


            mean_score = (
                fmean(scores)
                if scores
                else 0.0
            )


            dispersion = (
                pstdev(scores)
                if len(scores) > 1
                else 0.0
            )


            normalized_instability = (
                dispersion
                / max(
                    abs(mean_score),
                    10.0,
                )
            )


            results.append(
                {
                    "field":
                        field,

                    "results":
                        tuple(field_results),

                    "mean_fitness":
                        mean_score,

                    "dispersion":
                        dispersion,

                    "normalized_instability":
                        normalized_instability,
                }
            )


        instability = (
            fmean(
                item[
                    "normalized_instability"
                ]
                for item in results
            )
            if results
            else 0.0
        )


        return {
            "success":
                True,

            "fields":
                tuple(results),

            "runs":
                run_count,

            "instability_score":
                instability,

            "automatic_parameter_selection":
                False,

            "research_only":
                True,
        }


parameter_sensitivity_analyzer = (
    ParameterSensitivityAnalyzer()
)
'''
)


# ============================================================
# COST / SLIPPAGE STRESS
# ============================================================

write(
    COST_STRESS,
    r'''
from __future__ import annotations

from dataclasses import replace


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)


DEFAULT_SCENARIOS = (
    {
        "name":
            "baseline",

        "fee_multiplier":
            1.0,

        "extra_slippage_bps":
            0.0,

        "extra_spread_bps":
            0.0,
    },

    {
        "name":
            "moderate_stress",

        "fee_multiplier":
            1.5,

        "extra_slippage_bps":
            5.0,

        "extra_spread_bps":
            5.0,
    },

    {
        "name":
            "severe_stress",

        "fee_multiplier":
            2.0,

        "extra_slippage_bps":
            15.0,

        "extra_spread_bps":
            15.0,
    },
)


def _scaled_cost(
    cost,
    scenario,
):

    multiplier = float(
        scenario[
            "fee_multiplier"
        ]
    )


    return replace(
        cost,

        brokerage_bps=
            cost.brokerage_bps
            * multiplier,

        exchange_bps=
            cost.exchange_bps
            * multiplier,

        other_bps=
            cost.other_bps
            * multiplier,

        tax_bps_buy=
            cost.tax_bps_buy
            * multiplier,

        tax_bps_sell=
            cost.tax_bps_sell
            * multiplier,

        fixed_per_order=
            cost.fixed_per_order
            * multiplier,

        per_contract=
            cost.per_contract
            * multiplier,

        slippage_bps=
            (
                cost.slippage_bps
                * multiplier
                + float(
                    scenario[
                        "extra_slippage_bps"
                    ]
                )
            ),

        spread_bps=
            (
                cost.spread_bps
                * multiplier
                + float(
                    scenario[
                        "extra_spread_bps"
                    ]
                )
            ),
    )


class CostStressTester:

    def run(
        self,
        bars,
        strategy,
        base_config,
        *,
        scenarios=DEFAULT_SCENARIOS,
    ):

        results = []


        for scenario in scenarios:

            stressed_cost = _scaled_cost(
                base_config.cost,
                scenario,
            )


            config = replace(
                base_config,
                cost=stressed_cost,
            )


            result = historical_backtester.run(
                bars,
                strategy,
                config,
            )


            fitness = result_fitness(
                result
            )


            results.append(
                {
                    "scenario":
                        dict(
                            scenario
                        ),

                    "metrics":
                        result[
                            "metrics"
                        ],

                    "fitness":
                        fitness,

                    "profitable":
                        (
                            float(
                                result[
                                    "metrics"
                                ].get(
                                    "net_pnl",
                                    0.0,
                                )
                            )
                            > 0
                        ),
                }
            )


        surviving = sum(
            1

            for item in results

            if item[
                "profitable"
            ]
        )


        return {
            "success":
                True,

            "scenarios":
                tuple(results),

            "scenario_count":
                len(results),

            "profitable_scenarios":
                surviving,

            "survival_rate":
                (
                    surviving
                    / len(results)
                    if results
                    else 0.0
                ),

            "hardcoded_current_fee_schedule":
                False,

            "research_only":
                True,
        }


cost_stress_tester = (
    CostStressTester()
)
'''
)


print()
print("PART 1 SAVED")
print("Paste PART 2.")


# ============================================================
# REGIME ROBUSTNESS
# ============================================================

write(
    ROBUSTNESS,
    r'''
from __future__ import annotations

from statistics import (
    fmean,
    pstdev,
)


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)


class RegimeRobustnessEvaluator:

    def run(
        self,
        regime_datasets,
        strategy,
        config,
    ):

        if not regime_datasets:
            raise ValueError(
                "At least one regime dataset is required."
            )


        rows = []


        for regime, bars in regime_datasets.items():

            result = historical_backtester.run(
                bars,
                strategy,
                config,
            )


            fitness = result_fitness(
                result
            )


            rows.append(
                {
                    "regime":
                        str(regime),

                    "metrics":
                        result[
                            "metrics"
                        ],

                    "fitness":
                        fitness,

                    "profitable":
                        (
                            float(
                                result[
                                    "metrics"
                                ].get(
                                    "net_pnl",
                                    0.0,
                                )
                            )
                            > 0
                        ),
                }
            )


        scores = [
            item[
                "fitness"
            ][
                "score"
            ]

            for item in rows
        ]


        profitable = sum(
            1
            for item in rows
            if item["profitable"]
        )


        return {
            "success":
                True,

            "regimes":
                tuple(rows),

            "regime_count":
                len(rows),

            "profitable_regime_rate":
                profitable
                / len(rows),

            "average_fitness":
                fmean(scores),

            "worst_fitness":
                min(scores),

            "fitness_dispersion":
                (
                    pstdev(scores)
                    if len(scores) > 1
                    else 0.0
                ),

            "research_only":
                True,
        }


regime_robustness_evaluator = (
    RegimeRobustnessEvaluator()
)
'''
)


# ============================================================
# OVERFITTING RISK
# ============================================================

write(
    OVERFIT,
    r'''
from __future__ import annotations


def _gap(
    stronger,
    weaker,
):

    stronger = float(stronger)
    weaker = float(weaker)

    deterioration = max(
        0.0,
        stronger - weaker,
    )


    return (
        deterioration
        / max(
            abs(stronger),
            10.0,
        )
    )


def overfitting_risk(
    *,
    train_fitness,
    validation_fitness,
    oos_fitness,
    walk_forward_pass_rate,
    sensitivity_instability,
    monte_carlo_loss_probability,
    cost_survival_rate,
    data_sufficient=True,
):

    train_gap = _gap(
        train_fitness,
        validation_fitness,
    )


    validation_gap = _gap(
        validation_fitness,
        oos_fitness,
    )


    train_validation_penalty = min(
        25.0,
        train_gap
        * 25.0,
    )


    oos_penalty = min(
        25.0,
        validation_gap
        * 25.0,
    )


    walk_forward_penalty = (
        max(
            0.0,
            1.0
            - float(
                walk_forward_pass_rate
            ),
        )
        * 15.0
    )


    sensitivity_penalty = min(
        15.0,
        max(
            0.0,
            float(
                sensitivity_instability
            ),
        )
        * 15.0,
    )


    monte_carlo_penalty = (
        max(
            0.0,
            min(
                1.0,
                float(
                    monte_carlo_loss_probability
                ),
            ),
        )
        * 10.0
    )


    cost_penalty = (
        max(
            0.0,
            1.0
            - float(
                cost_survival_rate
            ),
        )
        * 10.0
    )


    insufficiency_penalty = (
        25.0
        if not data_sufficient
        else 0.0
    )


    score = min(
        100.0,
        (
            train_validation_penalty
            + oos_penalty
            + walk_forward_penalty
            + sensitivity_penalty
            + monte_carlo_penalty
            + cost_penalty
            + insufficiency_penalty
        ),
    )


    if score <= 25:
        level = "LOW"

    elif score <= 45:
        level = "MODERATE"

    elif score <= 70:
        level = "HIGH"

    else:
        level = "SEVERE"


    return {
        "score":
            score,

        "level":
            level,

        "components": {
            "train_validation_gap":
                train_validation_penalty,

            "validation_oos_gap":
                oos_penalty,

            "walk_forward":
                walk_forward_penalty,

            "parameter_sensitivity":
                sensitivity_penalty,

            "monte_carlo":
                monte_carlo_penalty,

            "cost_stress":
                cost_penalty,

            "data_sufficiency":
                insufficiency_penalty,
        },

        "research_only":
            True,
    }
'''
)


# ============================================================
# CANDIDATE GATE
# ============================================================

write(
    GATE,
    r'''
from __future__ import annotations


def validation_recommendation(
    *,
    risk,
    oos_fitness,
    walk_forward_pass_rate,
    cost_survival_rate,
    oos_trades,
    data_sufficient,
):

    risk_score = float(
        risk[
            "score"
        ]
    )


    oos_fitness = float(
        oos_fitness
    )


    oos_trades = int(
        oos_trades
    )


    if (
        not data_sufficient
        or oos_trades < 3
    ):

        recommendation = "KEEP_TESTING"

        reasons = (
            "insufficient_evidence",
        )


    elif (
        risk_score <= 25
        and oos_fitness > 0
        and walk_forward_pass_rate >= 0.60
        and cost_survival_rate >= 0.50
    ):

        recommendation = "PROMOTE"

        reasons = (
            "research_validation_passed",
        )


    elif (
        risk_score <= 45
        and oos_fitness >= -5
    ):

        recommendation = "KEEP_TESTING"

        reasons = (
            "mixed_but_acceptable_evidence",
        )


    elif risk_score <= 70:

        recommendation = "DEGRADE"

        reasons = (
            "high_overfitting_or_robustness_risk",
        )


    else:

        recommendation = "RETIRE"

        reasons = (
            "severe_validation_failure",
        )


    return {
        "recommendation":
            recommendation,

        "reasons":
            reasons,

        "production_promotion":
            False,

        "automatic_registry_change":
            False,

        "automatic_live_deployment":
            False,

        "automatic_retirement":
            False,

        "research_recommendation_only":
            True,
    }
'''
)


# ============================================================
# VALIDATION STORE
# ============================================================

write(
    STORE,
    r'''
from __future__ import annotations

from pathlib import Path

import json
import os
import uuid


class ValidationStore:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "trading"
                / "validation"
            )
        )


    def save(
        self,
        report,
    ):

        if not report.get(
            "research_only",
            False,
        ):
            raise ValueError(
                "Only research validation reports may be stored."
            )


        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        path = (
            self.root
            / (
                "validation_"
                + uuid.uuid4()
                .hex[:12]
                + ".json"
            )
        )


        temporary = (
            path.with_suffix(
                ".tmp"
            )
        )


        temporary.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )


        os.replace(
            temporary,
            path,
        )


        return {
            "success":
                True,

            "path":
                str(path),

            "research_only":
                True,
        }


validation_store = ValidationStore()
'''
)


# ============================================================
# MASTER V5 VALIDATION LAB
# ============================================================

write(
    LAB,
    r'''
from __future__ import annotations

from dataclasses import replace


from omni.trading_intelligence.candidate_validation_gate import (
    validation_recommendation,
)

from omni.trading_intelligence.cost_stress import (
    cost_stress_tester,
)

from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.monte_carlo import (
    monte_carlo_trade_simulator,
)

from omni.trading_intelligence.overfitting_risk import (
    overfitting_risk,
)

from omni.trading_intelligence.parameter_sensitivity import (
    parameter_sensitivity_analyzer,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)

from omni.trading_intelligence.validation_partitions import (
    chronological_split,
)

from omni.trading_intelligence.walk_forward import (
    walk_forward_validator,
)

from omni.trading_intelligence.robustness_evaluator import (
    regime_robustness_evaluator,
)


class StrategyValidationLab:

    @staticmethod
    def _strategy_and_config(
        candidate,
        base_config,
    ):

        if hasattr(
            candidate,
            "strategy"
        ):

            strategy = candidate.strategy

            overrides = dict(
                getattr(
                    candidate,
                    "config_overrides",
                    {},
                )
            )


            config = replace(
                base_config,
                **overrides
            )


            candidate_id = getattr(
                candidate,
                "candidate_id",
                strategy.strategy_id,
            )


        else:

            strategy = candidate
            config = base_config

            candidate_id = getattr(
                strategy,
                "strategy_id",
                "candidate",
            )


        return (
            strategy,
            config,
            str(candidate_id),
        )


    def validate(
        self,
        candidate,
        bars,
        base_config,
        *,
        regime_datasets=None,
        monte_carlo_iterations=500,
        random_seed=1,
    ):

        strategy, config, candidate_id = (
            self._strategy_and_config(
                candidate,
                base_config,
            )
        )


        minimum_segment = max(
            32,
            int(
                config.warmup_bars
            )
            + 2,
        )


        split = chronological_split(
            bars,
            train_ratio=0.60,
            validation_ratio=0.20,
            minimum_segment_bars=
                minimum_segment,
        )


        train_result = historical_backtester.run(
            split["train"],
            strategy,
            config,
        )


        validation_result = historical_backtester.run(
            split["validation"],
            strategy,
            config,
        )


        oos_result = historical_backtester.run(
            split["out_of_sample"],
            strategy,
            config,
        )


        train_fitness = result_fitness(
            train_result
        )

        validation_fitness = result_fitness(
            validation_result
        )

        oos_fitness = result_fitness(
            oos_result
        )


        total = len(bars)

        train_size = max(
            minimum_segment,
            int(
                total * 0.40
            ),
        )

        validation_size = max(
            minimum_segment,
            int(
                total * 0.20
            ),
        )

        test_size = max(
            minimum_segment,
            int(
                total * 0.20
            ),
        )


        while (
            train_size
            + validation_size
            + test_size
            > total
        ):

            if train_size > minimum_segment:
                train_size -= 1

            elif validation_size > minimum_segment:
                validation_size -= 1

            elif test_size > minimum_segment:
                test_size -= 1

            else:
                raise ValueError(
                    "Insufficient data for walk-forward validation."
                )


        walk_forward = walk_forward_validator.run(
            bars,
            strategy,
            config,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            step=test_size,
        )


        development_bars = tuple(
            split["train"]
        ) + tuple(
            split["validation"]
        )


        sensitivity = (
            parameter_sensitivity_analyzer
            .run(
                development_bars,
                strategy,
                config,
            )
        )


        cost_stress = cost_stress_tester.run(
            split["out_of_sample"],
            strategy,
            config,
        )


        oos_trades = tuple(
            oos_result[
                "trades"
            ]
        )


        monte_source = (
            oos_trades

            if oos_trades

            else tuple(
                validation_result[
                    "trades"
                ]
            )
        )


        monte_carlo = None


        if monte_source:

            monte_carlo = (
                monte_carlo_trade_simulator
                .run(
                    monte_source,
                    initial_capital=
                        config.initial_capital,
                    iterations=
                        monte_carlo_iterations,
                    random_seed=
                        random_seed,
                    bootstrap=True,
                )
            )


        data_sufficient = (
            split[
                "counts"
            ][
                "out_of_sample"
            ]
            >= minimum_segment
            and len(
                oos_trades
            )
            >= 3
        )


        loss_probability = (
            monte_carlo[
                "loss_probability"
            ]
            if monte_carlo is not None
            else 1.0
        )


        risk = overfitting_risk(
            train_fitness=
                train_fitness[
                    "score"
                ],

            validation_fitness=
                validation_fitness[
                    "score"
                ],

            oos_fitness=
                oos_fitness[
                    "score"
                ],

            walk_forward_pass_rate=
                walk_forward[
                    "oos_pass_rate"
                ],

            sensitivity_instability=
                sensitivity[
                    "instability_score"
                ],

            monte_carlo_loss_probability=
                loss_probability,

            cost_survival_rate=
                cost_stress[
                    "survival_rate"
                ],

            data_sufficient=
                data_sufficient,
        )


        recommendation = (
            validation_recommendation(
                risk=risk,

                oos_fitness=
                    oos_fitness[
                        "score"
                    ],

                walk_forward_pass_rate=
                    walk_forward[
                        "oos_pass_rate"
                    ],

                cost_survival_rate=
                    cost_stress[
                        "survival_rate"
                    ],

                oos_trades=
                    len(
                        oos_trades
                    ),

                data_sufficient=
                    data_sufficient,
            )
        )


        regime_robustness = None


        if regime_datasets:

            regime_robustness = (
                regime_robustness_evaluator
                .run(
                    regime_datasets,
                    strategy,
                    config,
                )
            )


        return {
            "success":
                True,

            "candidate_id":
                candidate_id,

            "strategy_id":
                strategy.strategy_id,

            "partitions":
                {
                    "counts":
                        split[
                            "counts"
                        ],

                    "chronological":
                        True,

                    "oos_used_for_tuning":
                        False,
                },

            "train":
                train_result,

            "validation":
                validation_result,

            "out_of_sample":
                oos_result,

            "fitness": {
                "train":
                    train_fitness,

                "validation":
                    validation_fitness,

                "out_of_sample":
                    oos_fitness,
            },

            "walk_forward":
                walk_forward,

            "parameter_sensitivity":
                sensitivity,

            "cost_stress":
                cost_stress,

            "monte_carlo":
                monte_carlo,

            "regime_robustness":
                regime_robustness,

            "data_sufficient":
                data_sufficient,

            "overfitting_risk":
                risk,

            "recommendation":
                recommendation,

            "production_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "live_execution":
                False,

            "research_only":
                True,
        }


strategy_validation_lab = (
    StrategyValidationLab()
)
'''
)


# ============================================================
# V5 STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)


class TradingIntelligenceV5Status:

    def status(
        self,
    ):

        core = verify_protected_core()


        return {
            "protected_core":
                core.ok,

            "research_only":
                True,

            "live_execution":
                False,

            "chronological_train_validation_oos":
                True,

            "oos_tuning":
                False,

            "walk_forward_validation":
                True,

            "rolling_oos_windows":
                True,

            "monte_carlo_bootstrap":
                True,

            "monte_carlo_max_iterations":
                5000,

            "parameter_sensitivity":
                True,

            "automatic_parameter_selection":
                False,

            "cost_stress":
                True,

            "slippage_stress":
                True,

            "spread_stress":
                True,

            "hardcoded_current_fees":
                False,

            "regime_robustness":
                True,

            "data_sufficiency_gate":
                True,

            "overfitting_risk_score":
                True,

            "train_validation_gap":
                True,

            "validation_oos_gap":
                True,

            "walk_forward_penalty":
                True,

            "parameter_instability_penalty":
                True,

            "monte_carlo_tail_risk":
                True,

            "cost_survival_gate":
                True,

            "recommendations": (
                "PROMOTE",
                "KEEP_TESTING",
                "DEGRADE",
                "RETIRE",
            ),

            "promotion_is_research_recommendation_only":
                True,

            "automatic_strategy_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "automatic_strategy_retirement":
                False,

            "automatic_broker_order":
                False,

            "production_self_modification":
                False,
        }


trading_intelligence_v5_status = (
    TradingIntelligenceV5Status()
)
'''
)


# ============================================================
# MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_v5_status("
    not in main_source
):

    main_source += r'''


def jarvis_trading_v5_status():

    from omni.trading_intelligence.trading_v5_status import (
        trading_intelligence_v5_status,
    )

    return trading_intelligence_v5_status.status()


def jarvis_trading_validate_candidate(
    candidate,
    bars,
    base_config,
    regime_datasets=None,
    monte_carlo_iterations=500,
    random_seed=1,
):

    from omni.trading_intelligence.strategy_validation_lab import (
        strategy_validation_lab,
    )

    return strategy_validation_lab.validate(
        candidate,
        bars,
        base_config,
        regime_datasets=regime_datasets,
        monte_carlo_iterations=monte_carlo_iterations,
        random_seed=random_seed,
    )


def jarvis_walk_forward(
    bars,
    strategy,
    config,
    train_size,
    validation_size,
    test_size,
    step=None,
):

    from omni.trading_intelligence.walk_forward import (
        walk_forward_validator,
    )

    return walk_forward_validator.run(
        bars,
        strategy,
        config,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step=step,
    )


def jarvis_monte_carlo_trades(
    trades,
    initial_capital,
    iterations=1000,
    random_seed=1,
    bootstrap=True,
):

    from omni.trading_intelligence.monte_carlo import (
        monte_carlo_trade_simulator,
    )

    return monte_carlo_trade_simulator.run(
        trades,
        initial_capital=initial_capital,
        iterations=iterations,
        random_seed=random_seed,
        bootstrap=bootstrap,
    )


def jarvis_parameter_sensitivity(
    bars,
    strategy,
    config,
    fields=(
        "stop_loss_pct",
        "target_pct",
        "max_bars_in_trade",
    ),
):

    from omni.trading_intelligence.parameter_sensitivity import (
        parameter_sensitivity_analyzer,
    )

    return parameter_sensitivity_analyzer.run(
        bars,
        strategy,
        config,
        fields=fields,
    )


def jarvis_cost_stress(
    bars,
    strategy,
    config,
):

    from omni.trading_intelligence.cost_stress import (
        cost_stress_tester,
    )

    return cost_stress_tester.run(
        bars,
        strategy,
        config,
    )


def jarvis_save_validation_report(
    report,
):

    from omni.trading_intelligence.validation_store import (
        validation_store,
    )

    return validation_store.save(
        report
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# WORKSTATION STATUS
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_intelligence_v5_payload("
    not in app_source
):

    app_source += r'''


def jarvis_trading_intelligence_v5_payload():

    from omni.trading_intelligence.trading_v5_status import (
        trading_intelligence_v5_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v5_status.status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(exc).__name__
                    + ": "
                    + str(exc)
                ),
        }
'''


    APP.write_text(
        app_source,
        encoding="utf-8",
    )


# ============================================================
# TESTS
# ============================================================

write(
    TEST,
    r'''
import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import Path


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.backtest_schema import (
    BacktestConfig,
    ExecutionCostConfig,
)

from omni.trading_intelligence.candidate_validation_gate import (
    validation_recommendation,
)

from omni.trading_intelligence.cost_stress import (
    CostStressTester,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)

from omni.trading_intelligence.monte_carlo import (
    MonteCarloTradeSimulator,
)

from omni.trading_intelligence.overfitting_risk import (
    overfitting_risk,
)

from omni.trading_intelligence.parameter_sensitivity import (
    ParameterSensitivityAnalyzer,
)

from omni.trading_intelligence.strategy_evolution_lab import (
    StrategyEvolutionLab,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.strategy_validation_lab import (
    StrategyValidationLab,
)

from omni.trading_intelligence.validation_partitions import (
    chronological_split,
    rolling_windows,
)

from omni.trading_intelligence.validation_store import (
    ValidationStore,
)

from omni.trading_intelligence.walk_forward import (
    WalkForwardValidator,
)


def trend_bars(
    count=360,
    direction=1,
):

    start = datetime(
        2026,
        1,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    rows = []


    for index in range(count):

        trend = (
            index
            * 0.18
            * direction
        )

        wave = (
            (
                index % 20
            )
            - 10
        ) * 0.06


        price = (
            150
            + trend
            + wave
        )


        close = (
            price
            + 0.25
            * direction
        )


        rows.append(
            Bar(
                timestamp=
                    start
                    + timedelta(
                        minutes=index
                    ),

                open=
                    price,

                high=
                    max(
                        price,
                        close,
                    )
                    + 0.5,

                low=
                    min(
                        price,
                        close,
                    )
                    - 0.5,

                close=
                    close,

                volume=
                    1000
                    + index * 5,
            )
        )


    return rows


class TradingIntelligenceV5Tests(
    unittest.TestCase
):

    def test_core(self):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_chronological_split(self):

        result = chronological_split(
            trend_bars()
        )


        self.assertTrue(
            result[
                "chronological"
            ]
        )

        self.assertFalse(
            result[
                "shuffled"
            ]
        )

        self.assertGreater(
            len(
                result[
                    "out_of_sample"
                ]
            ),
            0,
        )


    def test_split_is_ordered(self):

        result = chronological_split(
            trend_bars()
        )


        self.assertLess(
            result[
                "train"
            ][-1].timestamp,
            result[
                "validation"
            ][0].timestamp,
        )

        self.assertLess(
            result[
                "validation"
            ][-1].timestamp,
            result[
                "out_of_sample"
            ][0].timestamp,
        )


    def test_walk_windows(self):

        windows = rolling_windows(
            trend_bars(),
            train_size=120,
            validation_size=60,
            test_size=60,
            step=60,
        )


        self.assertGreaterEqual(
            len(windows),
            2,
        )


    def test_walk_forward(self):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        result = WalkForwardValidator().run(
            trend_bars(),
            strategy,

            BacktestConfig(
                warmup_bars=30,
                max_bars_in_trade=10,
            ),

            train_size=120,
            validation_size=60,
            test_size=60,
            step=60,
        )


        self.assertTrue(
            result[
                "success"
            ]
        )

        self.assertFalse(
            result[
                "candidate_reoptimized_on_oos"
            ]
        )


    def test_monte_carlo(self):

        trades = [
            {
                "net_pnl":
                    value
            }

            for value in (
                100,
                150,
                -80,
                120,
                -50,
                90,
            )
        ]


        result = MonteCarloTradeSimulator().run(
            trades,
            initial_capital=100000,
            iterations=100,
            random_seed=7,
        )


        self.assertEqual(
            result[
                "iterations"
            ],
            100,
        )

        self.assertGreaterEqual(
            result[
                "loss_probability"
            ],
            0,
        )

        self.assertLessEqual(
            result[
                "loss_probability"
            ],
            1,
        )


    def test_monte_carlo_limit(self):

        with self.assertRaises(
            ValueError
        ):

            MonteCarloTradeSimulator().run(
                [
                    {
                        "net_pnl":
                            1
                    }
                ],
                initial_capital=100,
                iterations=5001,
            )


    def test_parameter_sensitivity(self):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        result = (
            ParameterSensitivityAnalyzer()
            .run(
                trend_bars(240),
                strategy,

                BacktestConfig(
                    warmup_bars=30,
                    max_bars_in_trade=10,
                ),

                fields=(
                    "target_pct",
                    "max_bars_in_trade",
                ),
            )
        )


        self.assertEqual(
            result[
                "runs"
            ],
            6,
        )

        self.assertFalse(
            result[
                "automatic_parameter_selection"
            ]
        )


    def test_cost_stress(self):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        result = CostStressTester().run(
            trend_bars(180),
            strategy,

            BacktestConfig(
                warmup_bars=30,
                max_bars_in_trade=10,

                cost=ExecutionCostConfig(
                    brokerage_bps=1,
                    slippage_bps=1,
                    spread_bps=1,
                ),
            ),
        )


        self.assertEqual(
            result[
                "scenario_count"
            ],
            3,
        )

        self.assertFalse(
            result[
                "hardcoded_current_fee_schedule"
            ]
        )


    def test_overfit_low(self):

        result = overfitting_risk(
            train_fitness=20,
            validation_fitness=19,
            oos_fitness=18,
            walk_forward_pass_rate=1.0,
            sensitivity_instability=0.1,
            monte_carlo_loss_probability=0.1,
            cost_survival_rate=1.0,
            data_sufficient=True,
        )


        self.assertLess(
            result[
                "score"
            ],
            25,
        )


    def test_overfit_high(self):

        result = overfitting_risk(
            train_fitness=80,
            validation_fitness=10,
            oos_fitness=-30,
            walk_forward_pass_rate=0.1,
            sensitivity_instability=3.0,
            monte_carlo_loss_probability=0.9,
            cost_survival_rate=0.0,
            data_sufficient=False,
        )


        self.assertGreater(
            result[
                "score"
            ],
            70,
        )


    def test_promote_is_not_production(self):

        result = validation_recommendation(
            risk={
                "score":
                    10
            },
            oos_fitness=15,
            walk_forward_pass_rate=0.8,
            cost_survival_rate=1.0,
            oos_trades=10,
            data_sufficient=True,
        )


        self.assertEqual(
            result[
                "recommendation"
            ],
            "PROMOTE",
        )

        self.assertFalse(
            result[
                "production_promotion"
            ]
        )

        self.assertTrue(
            result[
                "research_recommendation_only"
            ]
        )


    def test_insufficient_keeps_testing(self):

        result = validation_recommendation(
            risk={
                "score":
                    5
            },
            oos_fitness=20,
            walk_forward_pass_rate=1,
            cost_survival_rate=1,
            oos_trades=1,
            data_sufficient=False,
        )


        self.assertEqual(
            result[
                "recommendation"
            ],
            "KEEP_TESTING",
        )


    def test_candidate_validation(self):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        report = StrategyValidationLab().validate(
            strategy,
            trend_bars(),

            BacktestConfig(
                warmup_bars=30,
                max_bars_in_trade=8,

                cost=ExecutionCostConfig(
                    brokerage_bps=1,
                    slippage_bps=1,
                    spread_bps=1,
                ),
            ),

            monte_carlo_iterations=100,
            random_seed=5,
        )


        self.assertTrue(
            report[
                "success"
            ]
        )

        self.assertFalse(
            report[
                "partitions"
            ][
                "oos_used_for_tuning"
            ]
        )

        self.assertIn(
            report[
                "recommendation"
            ][
                "recommendation"
            ],
            {
                "PROMOTE",
                "KEEP_TESTING",
                "DEGRADE",
                "RETIRE",
            },
        )

        self.assertFalse(
            report[
                "production_promotion"
            ]
        )


    def test_evolved_candidate_validation(self):

        candidate = (
            StrategyEvolutionLab()
            .mutate(
                "vwap_momentum_v1",
                count=1,
                random_seed=3,
            )[0]
        )


        report = StrategyValidationLab().validate(
            candidate,
            trend_bars(),

            BacktestConfig(
                warmup_bars=30,
            ),

            monte_carlo_iterations=50,
        )


        self.assertEqual(
            report[
                "candidate_id"
            ],
            candidate.candidate_id,
        )


    def test_validation_store(self):

        with tempfile.TemporaryDirectory() as tmp:

            store = ValidationStore(
                Path(tmp)
            )


            result = store.save(
                {
                    "research_only":
                        True,

                    "candidate":
                        "x",
                }
            )


            self.assertTrue(
                Path(
                    result[
                        "path"
                    ]
                ).exists()
            )


    def test_status(self):

        status = main.jarvis_trading_v5_status()


        self.assertTrue(
            status[
                "walk_forward_validation"
            ]
        )

        self.assertTrue(
            status[
                "overfitting_risk_score"
            ]
        )

        self.assertFalse(
            status[
                "oos_tuning"
            ]
        )

        self.assertFalse(
            status[
                "automatic_strategy_promotion"
            ]
        )

        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_v4_preserved(self):

        status = main.jarvis_trading_v4_status()

        self.assertTrue(
            status[
                "strategy_genomes"
            ]
        )

        self.assertFalse(
            status[
                "automatic_strategy_promotion"
            ]
        )


    def test_public_apis(self):

        for name in (
            "jarvis_trading_v5_status",
            "jarvis_trading_validate_candidate",
            "jarvis_walk_forward",
            "jarvis_monte_carlo_trades",
            "jarvis_parameter_sensitivity",
            "jarvis_cost_stress",
            "jarvis_save_validation_report",
        ):

            self.assertTrue(
                callable(
                    getattr(
                        main,
                        name,
                    )
                )
            )


if __name__ == "__main__":

    unittest.main()
'''
)


# ============================================================
# COMPILE
# ============================================================

print()
print("Checking Trading Intelligence V5 syntax...")


r = run(
    "-m",
    "py_compile",
    str(PARTITIONS),
    str(WALK_FORWARD),
    str(MONTE_CARLO),
    str(SENSITIVITY),
    str(COST_STRESS),
    str(ROBUSTNESS),
    str(OVERFIT),
    str(GATE),
    str(LAB),
    str(STORE),
    str(STATUS),
    str(MAIN),
    str(APP),
    str(TEST),
)


if r.returncode:
    print("COMPILE FAILURE")
    rollback()
    sys.exit(1)


print("Syntax: PASS")


# ============================================================
# CORE
# ============================================================

print()
print("Checking protected core...")


for relative, before in PROTECTED.items():

    if sha(
        ROOT / relative
    ) != before:

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()
        sys.exit(1)


r = run(
    "-c",
    (
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "import main; "
        "print('Protected Core: PASS'); "
        "print('Main import: PASS')"
    ),
)


if r.returncode:
    rollback()
    sys.exit(1)


# ============================================================
# PARTITION / WALK-FORWARD PROBE
# ============================================================

print()
print("Checking chronological OOS isolation...")


probe = r'''
from datetime import datetime, timedelta, timezone

from omni.trading_intelligence.market_schema import Bar
from omni.trading_intelligence.validation_partitions import chronological_split


start = datetime(
    2026,
    1,
    1,
    tzinfo=timezone.utc,
)


bars = []


for i in range(300):

    p = 100 + i * 0.1

    bars.append(
        Bar(
            timestamp=start + timedelta(minutes=i),
            open=p,
            high=p + 1,
            low=p - 1,
            close=p + 0.2,
            volume=1000 + i,
        )
    )


split = chronological_split(
    bars,
    minimum_segment_bars=32,
)


assert split["chronological"]
assert not split["shuffled"]

assert (
    split["train"][-1].timestamp
    < split["validation"][0].timestamp
)

assert (
    split["validation"][-1].timestamp
    < split["out_of_sample"][0].timestamp
)


print("Train partition: ISOLATED")
print("Validation partition: ISOLATED")
print("Out-of-sample partition: ISOLATED")
print("Chronological ordering: PASS")
print("Random data shuffle: BLOCKED")
print("OOS isolation: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:
    print("PARTITION FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# MONTE CARLO PROBE
# ============================================================

print()
print("Checking Monte Carlo robustness engine...")


probe = r'''
import main


trades = [
    {"net_pnl": 100},
    {"net_pnl": -60},
    {"net_pnl": 120},
    {"net_pnl": 80},
    {"net_pnl": -40},
    {"net_pnl": 90},
]


result = main.jarvis_monte_carlo_trades(
    trades,
    100000,
    iterations=250,
    random_seed=42,
)


assert result["iterations"] == 250
assert 0 <= result["loss_probability"] <= 1
assert result["max_drawdown_p95"] >= 0


print("Bootstrap resampling: ACTIVE")
print("Ending-equity distribution: ACTIVE")
print("5th-percentile equity: ACTIVE")
print("95th-percentile equity: ACTIVE")
print("Max-drawdown distribution: ACTIVE")
print("Loss probability: ACTIVE")
print("Monte Carlo: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:
    print("MONTE CARLO FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# OVERFITTING GATE
# ============================================================

print()
print("Checking anti-overfitting gates...")


probe = r'''
from omni.trading_intelligence.overfitting_risk import overfitting_risk
from omni.trading_intelligence.candidate_validation_gate import validation_recommendation


risk = overfitting_risk(
    train_fitness=50,
    validation_fitness=45,
    oos_fitness=40,
    walk_forward_pass_rate=0.8,
    sensitivity_instability=0.1,
    monte_carlo_loss_probability=0.1,
    cost_survival_rate=1.0,
    data_sufficient=True,
)


decision = validation_recommendation(
    risk=risk,
    oos_fitness=40,
    walk_forward_pass_rate=0.8,
    cost_survival_rate=1.0,
    oos_trades=10,
    data_sufficient=True,
)


assert decision["production_promotion"] is False
assert decision["automatic_registry_change"] is False
assert decision["automatic_live_deployment"] is False
assert decision["automatic_retirement"] is False


print("Train -> validation degradation: ACTIVE")
print("Validation -> OOS degradation: ACTIVE")
print("Walk-forward penalty: ACTIVE")
print("Parameter-instability penalty: ACTIVE")
print("Monte-Carlo penalty: ACTIVE")
print("Cost-survival penalty: ACTIVE")
print("Research recommendation: ACTIVE")
print("Automatic production promotion: BLOCKED")
print("Anti-overfitting gates: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:
    print("ANTI-OVERFITTING FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# SAFETY
# ============================================================

print()
print("Checking V5 safety...")


probe = r'''
import main


v5 = main.jarvis_trading_v5_status()


assert v5["research_only"]
assert v5["live_execution"] is False
assert v5["oos_tuning"] is False

assert v5["automatic_parameter_selection"] is False
assert v5["automatic_strategy_promotion"] is False
assert v5["automatic_registry_mutation"] is False
assert v5["automatic_strategy_retirement"] is False
assert v5["automatic_broker_order"] is False
assert v5["production_self_modification"] is False


for capability in (
    "order.place",
    "order.modify",
    "order.cancel",
    "trade.execute",
    "trading.live.execute",
):

    assert (
        main.jarvis_trading_guard(
            capability
        )["allowed"]
        is False
    )


print("OOS tuning: BLOCKED")
print("Automatic parameter selection: BLOCKED")
print("Automatic production promotion: BLOCKED")
print("Automatic registry mutation: BLOCKED")
print("Automatic retirement: BLOCKED")
print("Live broker execution: BLOCKED")
print("Production self-modification: BLOCKED")
print("V5 safety: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:
    print("V5 SAFETY FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# TARGETED REGRESSION
# ============================================================

print()
print("Running Trading Intelligence V5 targeted regression...")


r = run(
    "-m",
    "unittest",

    "tests.test_trading_intelligence_v5",
    "tests.test_trading_intelligence_v4",
    "tests.test_trading_intelligence_v3",
    "tests.test_trading_intelligence_v2",
    "tests.test_trading_v1_1_fyers_bridge",
    "tests.test_trading_intelligence_v1",

    "tests.test_computer_operator_v2",
    "tests.test_computer_operator_v3",
    "tests.test_computer_operator_v4",
    "tests.test_computer_operator",

    "tests.test_connected_services_v3",
    "tests.test_connected_services_v2",
    "tests.test_connected_services_v1",

    "tests.test_real_world_action_v3",
    "tests.test_real_world_action_v2",
    "tests.test_real_world_action_engine",

    "tests.test_universal_learning_v5",
    "tests.test_autonomy_engine",
    "tests.test_improvement_lab",

    "-q",
)


if r.returncode:
    print("TARGETED TEST FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# FULL REGRESSION
# ============================================================

print()
print("Running full regression...")


r = run(
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
)


if r.returncode:
    print("FULL REGRESSION FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# FINAL VERIFICATION
# ============================================================

for relative, before in PROTECTED.items():

    if sha(
        ROOT / relative
    ) != before:

        print(
            "PROTECTED CORE CHANGED:",
            relative,
        )

        rollback()
        sys.exit(1)


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "v4=main.jarvis_trading_v4_status(); "
        "v5=main.jarvis_trading_v5_status(); "
        "assert v4['strategy_genomes']; "
        "assert v5['walk_forward_validation']; "
        "assert v5['oos_tuning'] is False; "
        "assert v5['live_execution'] is False; "
        "assert v5['automatic_strategy_promotion'] is False; "
        "print('Final Protected Core: PASS'); "
        "print('Trading V4 Evolution: PRESERVED'); "
        "print('Trading V5 safety: PASS')"
    ),
)


if r.returncode:
    rollback()
    sys.exit(1)


r = run(
    "-m",
    "unittest",
    (
        "tests.test_computer_operator_v2."
        "ComputerOperatorV2Tests.test_dom_provider"
    ),
    "-q",
)


if r.returncode:
    print("FINAL BROWSER FAILURE")
    rollback()
    sys.exit(1)


print("Final browser DOM test: PASS")


# ============================================================
# SUCCESS
# ============================================================

status = run(
    "-c",
    (
        "import main,pprint; "
        "pprint.pp(main.jarvis_trading_v5_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V5 SUCCESS")
print("=" * 80)

print()
print("DATA VALIDATION")
print("Chronological train partition: ACTIVE")
print("Chronological validation partition: ACTIVE")
print("Untouched out-of-sample partition: ACTIVE")
print("OOS tuning: BLOCKED")
print()

print("WALK-FORWARD")
print("Rolling train windows: ACTIVE")
print("Rolling validation windows: ACTIVE")
print("Rolling unseen test windows: ACTIVE")
print("OOS profitable-window rate: ACTIVE")
print("Candidate reoptimization on OOS: BLOCKED")
print()

print("MONTE CARLO")
print("Trade bootstrap: ACTIVE")
print("Ending-equity distribution: ACTIVE")
print("5th/50th/95th percentiles: ACTIVE")
print("95th-percentile max drawdown: ACTIVE")
print("Loss probability: ACTIVE")
print()

print("PARAMETER ROBUSTNESS")
print("Stop sensitivity: ACTIVE")
print("Target sensitivity: ACTIVE")
print("Holding-period sensitivity: ACTIVE")
print("Fitness dispersion: ACTIVE")
print("Automatic best-parameter selection: BLOCKED")
print()

print("EXECUTION STRESS")
print("Brokerage stress: ACTIVE")
print("Spread stress: ACTIVE")
print("Slippage stress: ACTIVE")
print("Severe-cost scenario: ACTIVE")
print("Hard-coded current statutory fees: NO")
print()

print("ANTI-OVERFITTING")
print("Train-validation gap: ACTIVE")
print("Validation-OOS gap: ACTIVE")
print("Walk-forward stability: ACTIVE")
print("Parameter instability: ACTIVE")
print("Monte Carlo tail risk: ACTIVE")
print("Cost survival: ACTIVE")
print("Data sufficiency: ACTIVE")
print("Overfitting score 0-100: ACTIVE")
print()

print("DECISION ENGINE")
print("PROMOTE: RESEARCH RECOMMENDATION ONLY")
print("KEEP_TESTING: ACTIVE")
print("DEGRADE: ACTIVE")
print("RETIRE: ACTIVE")
print("Automatic production promotion: BLOCKED")
print("Automatic deletion: BLOCKED")
print()

print("PRESERVED")
print("Trading V1/V1.1: YES")
print("Trading V2 Backtester: YES")
print("Trading V3 Derivatives: YES")
print("Trading V4 Evolution: YES")
print("Canonical FYERS bridge: YES")
print("Browser lock repair: YES")
print("Protected Core: UNCHANGED")
print("Full regression: PASS")
print()

print("STATUS:")
print(status.stdout.strip())
print()

print("NEXT: TRADING INTELLIGENCE V6")
print("Live-data PAPER / SHADOW trading only")
print("Real-time signal observation")
print("Virtual fills")
print("Performance drift detection")
print("Strategy-weight adaptation")
print("Evidence ledger")
print("Shadow champion/challenger")
print("Daily/weekly paper performance summaries")
print("Kill-switch + stale-data protection")
print("NO broker-order execution")
print()
print("THEN:")
print("NautilusTrader isolated simulation/backtest kernel")
