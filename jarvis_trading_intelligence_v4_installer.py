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

GENOME = PKG / "strategy_genome.py"
MUTATION = PKG / "strategy_mutation.py"
CROSSOVER = PKG / "strategy_crossover.py"
FITNESS = PKG / "strategy_fitness.py"
REGIME_LAB = PKG / "regime_strategy_lab.py"
CHAMPION = PKG / "champion_challenger.py"
RETIREMENT = PKG / "strategy_retirement.py"
EVOLUTION = PKG / "strategy_evolution_lab.py"
STORE = PKG / "evolution_store.py"
STATUS = PKG / "trading_v4_status.py"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"
TEST = ROOT / "tests" / "test_trading_intelligence_v4.py"

MANIFEST = ROOT / "config" / "protected_core_manifest.json"

ARCHIVE = (
    ROOT
    / "archive"
    / "trading_intelligence_v4"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    GENOME,
    MUTATION,
    CROSSOVER,
    FITNESS,
    REGIME_LAB,
    CHAMPION,
    RETIREMENT,
    EVOLUTION,
    STORE,
    STATUS,
    MAIN,
    APP,
    TEST,
]

BACKUPS = {}


def run(
    *args,
    capture=False,
):

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


def write(
    path,
    source,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(
            source
        ).lstrip(),
        encoding="utf-8",
    )


def rollback():

    print()
    print("ROLLBACK")

    for path, existed in BACKUPS.items():

        backup = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        if existed:

            shutil.copy2(
                backup,
                path,
            )

        else:

            path.unlink(
                missing_ok=True
            )

    print(
        "JARVIS source restored."
    )


print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V4")
print("STRATEGY EVOLUTION + REGIME LAB + CHAMPION/CHALLENGER")
print("=" * 80)


# ============================================================
# BACKUP
# ============================================================

for path in FILES:

    BACKUPS[path] = path.exists()

    if path.exists():

        destination = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


# ============================================================
# BASELINE 548
# ============================================================

print()
print("Checking Trading Intelligence V3 / 548 checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "v2=main.jarvis_trading_v2_status(); "
        "v3=main.jarvis_trading_v3_status(); "
        "assert v2['historical_backtester']; "
        "assert v3['option_chain_schema']; "
        "assert v3['defined_risk_vertical_spreads']; "
        "assert v3['live_execution'] is False; "
        "assert v3['automatic_strategy_promotion'] is False; "
        "assert v3['automatic_broker_order'] is False; "
        "print('Main import: PASS'); "
        "print('Protected Core: PASS'); "
        "print('Trading V2: PASS'); "
        "print('Trading V3: PASS'); "
        "print('Live execution: BLOCKED')"
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
        sha(
            ROOT / relative
        )

    for relative
    in manifest.get(
        "files",
        {}
    )
}


print(
    "Protected files:",
    len(PROTECTED),
)

print("Baseline: PASS")


# ============================================================
# STRATEGY GENOME
# ============================================================

write(
    GENOME,
    r'''
from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)

from omni.trading_intelligence.strategy_schema import (
    StrategySpec,
)


@dataclass(frozen=True)
class StrategyGenome:

    candidate_id: str

    strategy: StrategySpec

    generation: int = 0

    parent_ids: tuple[str, ...] = ()

    config_overrides: dict = field(
        default_factory=dict
    )

    mutation_log: tuple[str, ...] = ()

    metadata: dict = field(
        default_factory=dict
    )


    def __post_init__(
        self,
    ):

        if not self.candidate_id:

            raise ValueError(
                "candidate_id is required."
            )


        if not isinstance(
            self.strategy,
            StrategySpec,
        ):

            raise TypeError(
                "strategy must be StrategySpec."
            )


        if self.generation < 0:

            raise ValueError(
                "generation cannot be negative."
            )


    def to_dict(
        self,
    ):

        return {
            "candidate_id":
                self.candidate_id,

            "strategy":
                self.strategy.to_dict(),

            "generation":
                self.generation,

            "parent_ids":
                self.parent_ids,

            "config_overrides":
                dict(
                    self.config_overrides
                ),

            "mutation_log":
                self.mutation_log,

            "metadata":
                dict(
                    self.metadata
                ),

            "research_only":
                True,
        }
'''
)


# ============================================================
# STRATEGY MUTATION
# ============================================================

write(
    MUTATION,
    r'''
from __future__ import annotations

import random
import uuid

from dataclasses import (
    replace,
)


from omni.trading_intelligence.strategy_genome import (
    StrategyGenome,
)

from omni.trading_intelligence.strategy_schema import (
    Condition,
    StrategySpec,
)


CONFIG_FIELDS = (
    "stop_loss_pct",
    "target_pct",
    "trailing_stop_pct",
    "max_bars_in_trade",
)


class StrategyMutator:

    def __init__(
        self,
        seed=None,
    ):

        self.random = random.Random(
            seed
        )


    def _mutate_numeric(
        self,
        value,
    ):

        value = float(
            value
        )


        factor = self.random.choice(
            (
                0.80,
                0.90,
                0.95,
                1.05,
                1.10,
                1.20,
            )
        )


        return (
            value
            * factor
        )


    def _mutate_conditions(
        self,
        conditions,
    ):

        conditions = list(
            conditions
        )


        numeric_indexes = [
            index

            for index, condition
            in enumerate(
                conditions
            )

            if isinstance(
                condition.right,
                (
                    int,
                    float,
                ),
            )
        ]


        if not numeric_indexes:

            return (
                tuple(
                    conditions
                ),
                None,
            )


        index = self.random.choice(
            numeric_indexes
        )


        original = conditions[
            index
        ]


        mutated = Condition(
            left=
                original.left,

            operator=
                original.operator,

            right=
                self._mutate_numeric(
                    original.right
                ),
        )


        conditions[
            index
        ] = mutated


        return (
            tuple(
                conditions
            ),

            (
                original.left
                + ":"
                + str(
                    original.right
                )
                + "->"
                + str(
                    mutated.right
                )
            ),
        )


    def mutate(
        self,
        strategy,
        *,
        parent_id=None,
        generation=1,
    ):

        if not isinstance(
            strategy,
            StrategySpec,
        ):

            raise TypeError(
                "strategy must be StrategySpec."
            )


        long_entry, long_log = (
            self._mutate_conditions(
                strategy.long_entry
            )
        )


        short_entry, short_log = (
            self._mutate_conditions(
                strategy.short_entry
            )
        )


        config_overrides = {}


        config_choice = self.random.choice(
            CONFIG_FIELDS
        )


        if config_choice == "stop_loss_pct":

            value = self.random.choice(
                (
                    0.005,
                    0.01,
                    0.015,
                    0.02,
                    0.03,
                )
            )


        elif config_choice == "target_pct":

            value = self.random.choice(
                (
                    0.01,
                    0.02,
                    0.03,
                    0.04,
                    0.06,
                )
            )


        elif config_choice == "trailing_stop_pct":

            value = self.random.choice(
                (
                    None,
                    0.01,
                    0.015,
                    0.02,
                    0.03,
                )
            )


        else:

            value = self.random.choice(
                (
                    5,
                    10,
                    20,
                    30,
                    50,
                )
            )


        config_overrides[
            config_choice
        ] = value


        candidate_id = (
            "candidate-"
            + uuid.uuid4()
            .hex[:12]
        )


        child = replace(
            strategy,

            strategy_id=
                (
                    strategy.strategy_id
                    + "__"
                    + candidate_id
                ),

            name=
                (
                    strategy.name
                    + " Challenger"
                ),

            long_entry=
                long_entry,

            short_entry=
                short_entry,

            metadata={
                **strategy.metadata,

                "evolved_candidate":
                    True,

                "production_registered":
                    False,
            },
        )


        logs = [
            item

            for item in (
                long_log,
                short_log,
                (
                    "config:"
                    + config_choice
                    + "="
                    + str(
                        value
                    )
                ),
            )

            if item
        ]


        return StrategyGenome(
            candidate_id=
                candidate_id,

            strategy=
                child,

            generation=
                int(
                    generation
                ),

            parent_ids=
                (
                    (str(
                        parent_id
                    ),)
                    if parent_id
                    else (
                        strategy.strategy_id,
                    )
                ),

            config_overrides=
                config_overrides,

            mutation_log=
                tuple(
                    logs
                ),

            metadata={
                "mutation":
                    True,

                "automatic_promotion":
                    False,
            },
        )


strategy_mutator = StrategyMutator()
'''
)


# ============================================================
# CROSSOVER
# ============================================================

write(
    CROSSOVER,
    r'''
from __future__ import annotations

import uuid

from omni.trading_intelligence.strategy_genome import (
    StrategyGenome,
)

from omni.trading_intelligence.strategy_schema import (
    StrategySpec,
)


def _intersection(
    left,
    right,
):

    return tuple(
        item

        for item in left

        if item in set(
            right
        )
    )


class StrategyCrossover:

    def crossover(
        self,
        left,
        right,
        *,
        generation=1,
    ):

        if (
            not isinstance(
                left,
                StrategySpec,
            )
            or not isinstance(
                right,
                StrategySpec,
            )
        ):

            raise TypeError(
                "Parents must be StrategySpec."
            )


        assets = _intersection(
            left.supported_asset_classes,
            right.supported_asset_classes,
        )


        instruments = _intersection(
            left.supported_instrument_types,
            right.supported_instrument_types,
        )


        timeframes = _intersection(
            left.supported_timeframes,
            right.supported_timeframes,
        )


        if (
            not assets
            or not instruments
            or not timeframes
        ):

            raise ValueError(
                "Parents have no compatible trading domain."
            )


        candidate_id = (
            "candidate-"
            + uuid.uuid4()
            .hex[:12]
        )


        required = tuple(
            dict.fromkeys(
                (
                    *left.required_features,
                    *right.required_features,
                )
            )
        )


        long_entry = tuple(
            dict.fromkeys(
                (
                    *left.long_entry,
                    *right.long_entry,
                )
            )
        )


        short_entry = tuple(
            dict.fromkeys(
                (
                    *left.short_entry,
                    *right.short_entry,
                )
            )
        )


        child = StrategySpec(
            strategy_id=
                (
                    "cross__"
                    + candidate_id
                ),

            name=
                (
                    left.name
                    + " x "
                    + right.name
                ),

            family=
                "crossover",

            supported_asset_classes=
                assets,

            supported_instrument_types=
                instruments,

            supported_timeframes=
                timeframes,

            required_features=
                required,

            long_entry=
                long_entry,

            short_entry=
                short_entry,

            exit_conditions=
                tuple(
                    dict.fromkeys(
                        (
                            *left.exit_conditions,
                            *right.exit_conditions,
                        )
                    )
                ),

            parameters={
                "parent_a":
                    left.strategy_id,

                "parent_b":
                    right.strategy_id,
            },

            metadata={
                "evolved_candidate":
                    True,

                "crossover":
                    True,

                "production_registered":
                    False,
            },
        )


        return StrategyGenome(
            candidate_id=
                candidate_id,

            strategy=
                child,

            generation=
                int(
                    generation
                ),

            parent_ids=(
                left.strategy_id,
                right.strategy_id,
            ),

            mutation_log=(
                "rule_crossover",
            ),

            metadata={
                "crossover":
                    True,

                "automatic_promotion":
                    False,
            },
        )


strategy_crossover = StrategyCrossover()
'''
)


# ============================================================
# FITNESS
# ============================================================

write(
    FITNESS,
    r'''
from __future__ import annotations

from math import (
    isfinite,
    tanh,
)

from statistics import (
    fmean,
    pstdev,
)


def _finite(
    value,
    default=0.0,
):

    if value is None:

        return float(
            default
        )


    value = float(
        value
    )


    if not isfinite(
        value
    ):

        return float(
            default
        )


    return value


def result_fitness(
    result,
    *,
    minimum_trades=5,
):

    metrics = result[
        "metrics"
    ]


    trades = int(
        metrics.get(
            "trades",
            0,
        )
    )


    return_pct = _finite(
        metrics.get(
            "return_pct"
        )
    )


    expectancy = _finite(
        metrics.get(
            "expectancy"
        )
    )


    average_loss = abs(
        _finite(
            metrics.get(
                "avg_loss"
            ),
            1.0,
        )
    )


    if average_loss <= 0:

        average_loss = 1.0


    expectancy_ratio = (
        expectancy
        / average_loss
    )


    profit_factor = _finite(
        metrics.get(
            "profit_factor"
        )
    )


    win_rate = max(
        0.0,
        min(
            1.0,
            _finite(
                metrics.get(
                    "win_rate"
                )
            ),
        ),
    )


    drawdown_pct = max(
        0.0,
        _finite(
            metrics.get(
                "max_drawdown_pct"
            )
        ),
    )


    return_score = (
        tanh(
            return_pct
            * 8.0
        )
        * 30.0
    )


    expectancy_score = (
        tanh(
            expectancy_ratio
        )
        * 20.0
    )


    pf_score = (
        max(
            0.0,
            min(
                3.0,
                profit_factor,
            )
        )
        / 3.0
        * 20.0
    )


    win_score = (
        win_rate
        * 10.0
    )


    drawdown_penalty = (
        min(
            1.0,
            drawdown_pct
        )
        * 35.0
    )


    trade_penalty = (
        (
            minimum_trades
            - trades
        )
        / minimum_trades
        * 20.0

        if trades
        < minimum_trades

        else 0.0
    )


    score = (
        return_score
        + expectancy_score
        + pf_score
        + win_score
        - drawdown_penalty
        - trade_penalty
    )


    return {
        "score":
            score,

        "components": {
            "return_score":
                return_score,

            "expectancy_score":
                expectancy_score,

            "profit_factor_score":
                pf_score,

            "win_rate_score":
                win_score,

            "drawdown_penalty":
                drawdown_penalty,

            "trade_count_penalty":
                trade_penalty,
        },

        "trades":
            trades,

        "research_only":
            True,
    }


def multi_regime_fitness(
    regime_results,
):

    if not regime_results:

        raise ValueError(
            "At least one regime result required."
        )


    regime_scores = {
        regime:
            result_fitness(
                result
            )[
                "score"
            ]

        for regime, result
        in regime_results.items()
    }


    values = list(
        regime_scores.values()
    )


    average = fmean(
        values
    )


    stability_penalty = (
        pstdev(
            values
        )
        if len(
            values
        ) > 1
        else 0.0
    )


    worst = min(
        values
    )


    robust_score = (
        average
        - 0.50
        * stability_penalty
        + 0.20
        * worst
    )


    return {
        "score":
            robust_score,

        "average_regime_score":
            average,

        "stability_penalty":
            stability_penalty,

        "worst_regime_score":
            worst,

        "regime_scores":
            regime_scores,

        "research_only":
            True,
    }
'''
)


# ============================================================
# REGIME LAB
# ============================================================

write(
    REGIME_LAB,
    r'''
from __future__ import annotations

from dataclasses import (
    replace,
)


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    multi_regime_fitness,
)


class RegimeStrategyLab:

    def evaluate(
        self,
        genome,
        regime_datasets,
        base_config,
    ):

        if not regime_datasets:

            raise ValueError(
                "regime_datasets cannot be empty."
            )


        config = replace(
            base_config,
            **genome.config_overrides
        )


        results = {}


        for regime, bars in (
            regime_datasets.items()
        ):

            results[
                str(
                    regime
                )
            ] = (
                historical_backtester
                .run(
                    bars,
                    genome.strategy,
                    config,
                )
            )


        fitness = multi_regime_fitness(
            results
        )


        return {
            "success":
                True,

            "candidate_id":
                genome.candidate_id,

            "generation":
                genome.generation,

            "parent_ids":
                genome.parent_ids,

            "config_overrides":
                genome.config_overrides,

            "mutation_log":
                genome.mutation_log,

            "regime_results":
                results,

            "fitness":
                fitness,

            "automatic_promotion":
                False,

            "research_only":
                True,
        }


regime_strategy_lab = (
    RegimeStrategyLab()
)
'''
)


# ============================================================
# CHAMPION / CHALLENGER
# ============================================================

write(
    CHAMPION,
    r'''
from __future__ import annotations


class ChampionChallenger:

    def compare(
        self,
        champion,
        challenger,
        *,
        minimum_margin=2.0,
    ):

        champion_score = float(
            champion[
                "fitness"
            ][
                "score"
            ]
        )


        challenger_score = float(
            challenger[
                "fitness"
            ][
                "score"
            ]
        )


        margin = (
            challenger_score
            - champion_score
        )


        if margin >= float(
            minimum_margin
        ):

            decision = (
                "RESEARCH_CHALLENGER_WINS"
            )


        elif margin > 0:

            decision = (
                "KEEP_TESTING"
            )


        elif margin <= -10:

            decision = (
                "CHALLENGER_DEGRADE"
            )


        else:

            decision = (
                "CHAMPION_RETAINS"
            )


        return {
            "decision":
                decision,

            "champion_score":
                champion_score,

            "challenger_score":
                challenger_score,

            "margin":
                margin,

            "production_promotion":
                False,

            "registry_mutation":
                False,

            "research_only":
                True,
        }


champion_challenger = (
    ChampionChallenger()
)
'''
)


# ============================================================
# RETIREMENT PROPOSAL
# ============================================================

write(
    RETIREMENT,
    r'''
from __future__ import annotations


class StrategyRetirementEngine:

    def evaluate(
        self,
        evaluation,
        *,
        retire_below=-20.0,
        degrade_below=0.0,
    ):

        score = float(
            evaluation[
                "fitness"
            ][
                "score"
            ]
        )


        if score <= retire_below:

            recommendation = (
                "RETIRE_PROPOSAL"
            )


        elif score <= degrade_below:

            recommendation = (
                "DEGRADE"
            )


        else:

            recommendation = (
                "KEEP"
            )


        return {
            "candidate_id":
                evaluation[
                    "candidate_id"
                ],

            "score":
                score,

            "recommendation":
                recommendation,

            "automatic_delete":
                False,

            "automatic_registry_change":
                False,

            "research_only":
                True,
        }


strategy_retirement_engine = (
    StrategyRetirementEngine()
)
'''
)


print()
print("PART 1 SAVED")
print("Paste PART 2.")


# ============================================================
# EVOLUTION STORE
# ============================================================

write(
    STORE,
    r'''
from __future__ import annotations

from pathlib import (
    Path,
)

import json
import os
import uuid


class EvolutionStore:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "trading"
                / "evolution"
            )
        )


    def save(
        self,
        artifact,
    ):

        if not artifact.get(
            "research_only",
            False,
        ):

            raise ValueError(
                "Only research artifacts may be stored."
            )


        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        path = (
            self.root
            / (
                "evolution_"
                + uuid.uuid4()
                .hex[:12]
                + ".json"
            )
        )


        temporary = path.with_suffix(
            ".tmp"
        )


        temporary.write_text(
            json.dumps(
                artifact,
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
                str(
                    path
                ),

            "research_only":
                True,
        }


evolution_store = EvolutionStore()
'''
)


# ============================================================
# EVOLUTION LAB
# ============================================================

write(
    EVOLUTION,
    r'''
from __future__ import annotations

from omni.trading_intelligence.champion_challenger import (
    champion_challenger,
)

from omni.trading_intelligence.derivatives_strategy_registry import (
    ensure_derivatives_strategies,
)

from omni.trading_intelligence.regime_strategy_lab import (
    regime_strategy_lab,
)

from omni.trading_intelligence.strategy_crossover import (
    strategy_crossover,
)

from omni.trading_intelligence.strategy_genome import (
    StrategyGenome,
)

from omni.trading_intelligence.strategy_mutation import (
    StrategyMutator,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.strategy_retirement import (
    strategy_retirement_engine,
)


HISTORICAL_FEATURES = {
    "close",
    "sma20",
    "ema9",
    "ema21",
    "ema50",
    "rsi14",
    "atr14",
    "atr_pct",
    "vwap",
    "volume_z20",
    "return_1",
    "realized_vol20",
}


class StrategyEvolutionLab:

    MAX_CANDIDATES = 50


    @staticmethod
    def _ensure_registry():

        ensure_derivatives_strategies()


    @classmethod
    def historically_compatible(
        cls,
        strategy,
    ):

        required = set(
            strategy.required_features
        )


        return required.issubset(
            HISTORICAL_FEATURES
        )


    def seed_genome(
        self,
        strategy_id,
    ):

        self._ensure_registry()


        strategy = strategy_registry.get(
            strategy_id
        )


        if strategy is None:

            raise ValueError(
                "Unknown seed strategy: "
                + str(
                    strategy_id
                )
            )


        return StrategyGenome(
            candidate_id=
                (
                    "seed:"
                    + strategy.strategy_id
                ),

            strategy=
                strategy,

            generation=
                0,

            parent_ids=(),

            metadata={
                "seed":
                    True,

                "production_registered":
                    True,

                "automatic_promotion":
                    False,
            },
        )


    def mutate(
        self,
        strategy_id,
        *,
        count=5,
        random_seed=1,
        generation=1,
    ):

        count = int(
            count
        )


        if (
            count <= 0
            or count > self.MAX_CANDIDATES
        ):

            raise ValueError(
                "count must be between 1 and "
                + str(
                    self.MAX_CANDIDATES
                )
            )


        seed_genome = self.seed_genome(
            strategy_id
        )


        mutator = StrategyMutator(
            random_seed
        )


        output = []


        for _ in range(
            count
        ):

            output.append(
                mutator.mutate(
                    seed_genome.strategy,
                    parent_id=
                        seed_genome.candidate_id,
                    generation=
                        generation,
                )
            )


        return tuple(
            output
        )


    def crossover(
        self,
        left_strategy_id,
        right_strategy_id,
        *,
        generation=1,
    ):

        left = self.seed_genome(
            left_strategy_id
        )


        right = self.seed_genome(
            right_strategy_id
        )


        return strategy_crossover.crossover(
            left.strategy,
            right.strategy,
            generation=generation,
        )


    def evaluate(
        self,
        genome,
        regime_datasets,
        base_config,
    ):

        if not self.historically_compatible(
            genome.strategy
        ):

            raise ValueError(
                "Candidate requires features unavailable "
                "in the V2 historical backtester. "
                "Use snapshot research until V5/V6 provides "
                "historical derivatives feature streams."
            )


        return regime_strategy_lab.evaluate(
            genome,
            regime_datasets,
            base_config,
        )


    def evolve(
        self,
        strategy_id,
        regime_datasets,
        base_config,
        *,
        candidate_count=8,
        random_seed=1,
    ):

        seed = self.seed_genome(
            strategy_id
        )


        if not self.historically_compatible(
            seed.strategy
        ):

            raise ValueError(
                "Seed is not compatible with current "
                "historical feature stream."
            )


        champion_evaluation = (
            self.evaluate(
                seed,
                regime_datasets,
                base_config,
            )
        )


        challengers = self.mutate(
            strategy_id,
            count=candidate_count,
            random_seed=random_seed,
            generation=1,
        )


        evaluated = []


        for challenger in challengers:

            evaluation = self.evaluate(
                challenger,
                regime_datasets,
                base_config,
            )


            comparison = (
                champion_challenger
                .compare(
                    champion_evaluation,
                    evaluation,
                )
            )


            retirement = (
                strategy_retirement_engine
                .evaluate(
                    evaluation
                )
            )


            evaluated.append(
                {
                    "genome":
                        challenger.to_dict(),

                    "evaluation":
                        evaluation,

                    "comparison":
                        comparison,

                    "retirement":
                        retirement,
                }
            )


        evaluated.sort(
            key=lambda item:
                item[
                    "evaluation"
                ][
                    "fitness"
                ][
                    "score"
                ],
            reverse=True,
        )


        return {
            "success":
                True,

            "seed_strategy_id":
                strategy_id,

            "champion":
                champion_evaluation,

            "challengers":
                tuple(
                    evaluated
                ),

            "best_challenger":
                (
                    evaluated[
                        0
                    ]
                    if evaluated
                    else None
                ),

            "candidate_count":
                len(
                    evaluated
                ),

            "production_promotion":
                False,

            "registry_mutation":
                False,

            "automatic_retirement":
                False,

            "research_only":
                True,
        }


strategy_evolution_lab = (
    StrategyEvolutionLab()
)
'''
)


# ============================================================
# V4 STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)


class TradingIntelligenceV4Status:

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

            "strategy_genomes":
                True,

            "parameter_mutation":
                True,

            "numeric_rule_mutation":
                True,

            "strategy_crossover":
                True,

            "historical_compatibility_gate":
                True,

            "regime_aware_evaluation":
                True,

            "multi_regime_fitness":
                True,

            "expectancy_component":
                True,

            "profit_factor_component":
                True,

            "return_component":
                True,

            "drawdown_penalty":
                True,

            "trade_count_penalty":
                True,

            "regime_stability_penalty":
                True,

            "worst_regime_component":
                True,

            "champion_challenger":
                True,

            "retirement_proposals":
                True,

            "candidate_limit":
                50,

            "evolution_artifact_store":
                True,

            "automatic_registry_mutation":
                False,

            "automatic_strategy_promotion":
                False,

            "automatic_strategy_retirement":
                False,

            "automatic_broker_order":
                False,

            "production_self_modification":
                False,
        }


trading_intelligence_v4_status = (
    TradingIntelligenceV4Status()
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
    "def jarvis_trading_v4_status("
    not in main_source
):

    main_source += r'''


def jarvis_trading_v4_status():

    from omni.trading_intelligence.trading_v4_status import (
        trading_intelligence_v4_status,
    )

    return trading_intelligence_v4_status.status()


def jarvis_strategy_mutate(
    strategy_id,
    count=5,
    random_seed=1,
    generation=1,
):

    from omni.trading_intelligence.strategy_evolution_lab import (
        strategy_evolution_lab,
    )

    return strategy_evolution_lab.mutate(
        strategy_id,
        count=count,
        random_seed=random_seed,
        generation=generation,
    )


def jarvis_strategy_crossover(
    left_strategy_id,
    right_strategy_id,
    generation=1,
):

    from omni.trading_intelligence.strategy_evolution_lab import (
        strategy_evolution_lab,
    )

    return strategy_evolution_lab.crossover(
        left_strategy_id,
        right_strategy_id,
        generation=generation,
    )


def jarvis_evaluate_strategy_candidate(
    genome,
    regime_datasets,
    base_config,
):

    from omni.trading_intelligence.strategy_evolution_lab import (
        strategy_evolution_lab,
    )

    return strategy_evolution_lab.evaluate(
        genome,
        regime_datasets,
        base_config,
    )


def jarvis_evolve_strategy(
    strategy_id,
    regime_datasets,
    base_config,
    candidate_count=8,
    random_seed=1,
):

    from omni.trading_intelligence.strategy_evolution_lab import (
        strategy_evolution_lab,
    )

    return strategy_evolution_lab.evolve(
        strategy_id,
        regime_datasets,
        base_config,
        candidate_count=candidate_count,
        random_seed=random_seed,
    )


def jarvis_compare_champion_challenger(
    champion,
    challenger,
    minimum_margin=2.0,
):

    from omni.trading_intelligence.champion_challenger import (
        champion_challenger,
    )

    return champion_challenger.compare(
        champion,
        challenger,
        minimum_margin=minimum_margin,
    )


def jarvis_strategy_retirement_proposal(
    evaluation,
    retire_below=-20.0,
    degrade_below=0.0,
):

    from omni.trading_intelligence.strategy_retirement import (
        strategy_retirement_engine,
    )

    return strategy_retirement_engine.evaluate(
        evaluation,
        retire_below=retire_below,
        degrade_below=degrade_below,
    )


def jarvis_save_evolution_artifact(
    artifact,
):

    from omni.trading_intelligence.evolution_store import (
        evolution_store,
    )

    return evolution_store.save(
        artifact
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
    "def jarvis_trading_intelligence_v4_payload("
    not in app_source
):

    app_source += r'''


def jarvis_trading_intelligence_v4_payload():

    from omni.trading_intelligence.trading_v4_status import (
        trading_intelligence_v4_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v4_status.status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
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

from pathlib import (
    Path,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.backtest_schema import (
    BacktestConfig,
)

from omni.trading_intelligence.champion_challenger import (
    ChampionChallenger,
)

from omni.trading_intelligence.evolution_store import (
    EvolutionStore,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)

from omni.trading_intelligence.strategy_evolution_lab import (
    StrategyEvolutionLab,
)

from omni.trading_intelligence.strategy_fitness import (
    multi_regime_fitness,
    result_fitness,
)

from omni.trading_intelligence.strategy_retirement import (
    StrategyRetirementEngine,
)


def trend_up(
    count=100,
):

    start = datetime(
        2026,
        1,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    return [
        Bar(
            timestamp=
                start
                + timedelta(
                    minutes=index
                ),

            open=
                100
                + index
                * 0.4,

            high=
                101
                + index
                * 0.4,

            low=
                99.5
                + index
                * 0.4,

            close=
                100.5
                + index
                * 0.4,

            volume=
                1000
                + index
                * 10,
        )

        for index
        in range(
            count
        )
    ]


def trend_down(
    count=100,
):

    start = datetime(
        2026,
        2,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    return [
        Bar(
            timestamp=
                start
                + timedelta(
                    minutes=index
                ),

            open=
                200
                - index
                * 0.4,

            high=
                200.5
                - index
                * 0.4,

            low=
                199
                - index
                * 0.4,

            close=
                199.5
                - index
                * 0.4,

            volume=
                1000
                + index
                * 10,
        )

        for index
        in range(
            count
        )
    ]


def regimes():

    return {
        "TREND_UP":
            trend_up(),

        "TREND_DOWN":
            trend_down(),
    }


class TradingIntelligenceV4Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_seed(
        self,
    ):

        lab = StrategyEvolutionLab()


        seed = lab.seed_genome(
            "rsi_mean_reversion_v1"
        )


        self.assertEqual(
            seed.generation,
            0,
        )


    def test_mutation_count(
        self,
    ):

        lab = StrategyEvolutionLab()


        candidates = lab.mutate(
            "rsi_mean_reversion_v1",
            count=5,
            random_seed=7,
        )


        self.assertEqual(
            len(
                candidates
            ),
            5,
        )


    def test_candidate_not_registered(
        self,
    ):

        from omni.trading_intelligence.strategy_registry import (
            strategy_registry,
        )


        lab = StrategyEvolutionLab()


        candidate = lab.mutate(
            "rsi_mean_reversion_v1",
            count=1,
            random_seed=5,
        )[0]


        self.assertIsNone(
            strategy_registry.get(
                candidate.strategy.strategy_id
            )
        )


    def test_mutation_has_log(
        self,
    ):

        candidate = (
            StrategyEvolutionLab()
            .mutate(
                "rsi_mean_reversion_v1",
                count=1,
                random_seed=3,
            )[0]
        )


        self.assertGreater(
            len(
                candidate.mutation_log
            ),
            0,
        )


    def test_crossover(
        self,
    ):

        child = (
            StrategyEvolutionLab()
            .crossover(
                "vwap_momentum_v1",
                "rsi_mean_reversion_v1",
            )
        )


        self.assertEqual(
            child.strategy.family,
            "crossover",
        )


        self.assertEqual(
            len(
                child.parent_ids
            ),
            2,
        )


    def test_derivatives_historical_gate(
        self,
    ):

        lab = StrategyEvolutionLab()


        genome = lab.seed_genome(
            "derivatives_confirmation_v1"
        )


        self.assertFalse(
            lab.historically_compatible(
                genome.strategy
            )
        )


        with self.assertRaises(
            ValueError
        ):

            lab.evaluate(
                genome,
                regimes(),

                BacktestConfig(
                    warmup_bars=30
                ),
            )


    def test_base_strategy_compatible(
        self,
    ):

        lab = StrategyEvolutionLab()


        genome = lab.seed_genome(
            "vwap_momentum_v1"
        )


        self.assertTrue(
            lab.historically_compatible(
                genome.strategy
            )
        )


    def test_candidate_evaluation(
        self,
    ):

        lab = StrategyEvolutionLab()


        candidate = lab.mutate(
            "rsi_mean_reversion_v1",
            count=1,
            random_seed=1,
        )[0]


        result = lab.evaluate(
            candidate,
            regimes(),

            BacktestConfig(
                warmup_bars=30,
            ),
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertIn(
            "score",
            result[
                "fitness"
            ],
        )


    def test_evolution_lab(
        self,
    ):

        result = (
            StrategyEvolutionLab()
            .evolve(
                "rsi_mean_reversion_v1",
                regimes(),

                BacktestConfig(
                    warmup_bars=30,
                ),

                candidate_count=4,
                random_seed=42,
            )
        )


        self.assertEqual(
            result[
                "candidate_count"
            ],
            4,
        )


        self.assertFalse(
            result[
                "production_promotion"
            ]
        )


        self.assertFalse(
            result[
                "registry_mutation"
            ]
        )


    def test_candidate_limit(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            StrategyEvolutionLab().mutate(
                "rsi_mean_reversion_v1",
                count=51,
            )


    def test_fitness(
        self,
    ):

        fake = {
            "metrics": {
                "trades":
                    20,

                "return_pct":
                    0.10,

                "expectancy":
                    100,

                "avg_loss":
                    50,

                "profit_factor":
                    2.0,

                "win_rate":
                    0.60,

                "max_drawdown_pct":
                    0.08,
            }
        }


        result = result_fitness(
            fake
        )


        self.assertIn(
            "score",
            result,
        )


    def test_multiregime_penalty(
        self,
    ):

        good = {
            "metrics": {
                "trades": 20,
                "return_pct": 0.10,
                "expectancy": 50,
                "avg_loss": 50,
                "profit_factor": 1.8,
                "win_rate": 0.55,
                "max_drawdown_pct": 0.05,
            }
        }


        bad = {
            "metrics": {
                "trades": 20,
                "return_pct": -0.10,
                "expectancy": -50,
                "avg_loss": 50,
                "profit_factor": 0.7,
                "win_rate": 0.35,
                "max_drawdown_pct": 0.20,
            }
        }


        result = multi_regime_fitness(
            {
                "A":
                    good,

                "B":
                    bad,
            }
        )


        self.assertGreater(
            result[
                "stability_penalty"
            ],
            0,
        )


    def test_champion_challenger(
        self,
    ):

        comparator = (
            ChampionChallenger()
        )


        result = comparator.compare(
            {
                "fitness": {
                    "score": 10
                }
            },

            {
                "fitness": {
                    "score": 15
                }
            },
        )


        self.assertEqual(
            result[
                "decision"
            ],
            "RESEARCH_CHALLENGER_WINS",
        )


        self.assertFalse(
            result[
                "production_promotion"
            ]
        )


    def test_retirement_proposal(
        self,
    ):

        result = (
            StrategyRetirementEngine()
            .evaluate(
                {
                    "candidate_id":
                        "bad",

                    "fitness": {
                        "score":
                            -30
                    },
                }
            )
        )


        self.assertEqual(
            result[
                "recommendation"
            ],
            "RETIRE_PROPOSAL",
        )


        self.assertFalse(
            result[
                "automatic_delete"
            ]
        )


    def test_store(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = EvolutionStore(
                Path(
                    tmp
                )
            )


            saved = store.save(
                {
                    "research_only":
                        True,

                    "candidate":
                        "x",
                }
            )


            self.assertTrue(
                Path(
                    saved[
                        "path"
                    ]
                ).exists()
            )


    def test_status(
        self,
    ):

        status = main.jarvis_trading_v4_status()


        self.assertTrue(
            status[
                "strategy_genomes"
            ]
        )


        self.assertTrue(
            status[
                "champion_challenger"
            ]
        )


        self.assertFalse(
            status[
                "automatic_strategy_promotion"
            ]
        )


        self.assertFalse(
            status[
                "production_self_modification"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_v3_preserved(
        self,
    ):

        status = main.jarvis_trading_v3_status()


        self.assertTrue(
            status[
                "option_chain_schema"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_public_apis(
        self,
    ):

        for name in (
            "jarvis_trading_v4_status",
            "jarvis_strategy_mutate",
            "jarvis_strategy_crossover",
            "jarvis_evaluate_strategy_candidate",
            "jarvis_evolve_strategy",
            "jarvis_compare_champion_challenger",
            "jarvis_strategy_retirement_proposal",
            "jarvis_save_evolution_artifact",
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
print("Checking Trading Intelligence V4 syntax...")


r = run(
    "-m",
    "py_compile",

    str(GENOME),
    str(MUTATION),
    str(CROSSOVER),
    str(FITNESS),
    str(REGIME_LAB),
    str(CHAMPION),
    str(RETIREMENT),
    str(EVOLUTION),
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
# PROTECTED CORE
# ============================================================

print()
print("Checking protected core...")


for relative, before in PROTECTED.items():

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

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
# MUTATION PROBE
# ============================================================

print()
print("Checking strategy candidate generation...")


probe = r'''
import main

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.derivatives_strategy_registry import (
    ensure_derivatives_strategies,
)


# Establish the already-approved V3 runtime registry first.
# V3 derivative strategies are lazily registered in each process.
ensure_derivatives_strategies()


before = len(
    strategy_registry.all()
)


candidates = main.jarvis_strategy_mutate(
    "rsi_mean_reversion_v1",
    count=8,
    random_seed=42,
)


assert len(candidates) == 8


for candidate in candidates:

    assert candidate.generation == 1
    assert candidate.mutation_log

    assert (
        strategy_registry.get(
            candidate.strategy.strategy_id
        )
        is None
    )


after = len(
    strategy_registry.all()
)


assert after == before


print("Candidates generated:", len(candidates))
print("Numeric rule mutation: ACTIVE")
print("Backtest-config mutation: ACTIVE")
print("Generation tracking: ACTIVE")
print("Parent tracking: ACTIVE")
print("Mutation log: ACTIVE")
print("Automatic registry insertion: BLOCKED")
print("Candidate generation: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("MUTATION PROBE FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# EVOLUTION PROBE
# ============================================================

print()
print("Checking multi-regime strategy evolution...")


probe = r'''
from datetime import datetime, timedelta, timezone

import main

from omni.trading_intelligence.market_schema import Bar


def bars(direction):

    start = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    result = []

    for i in range(100):

        p = (
            100 + i * 0.4
            if direction > 0
            else 200 - i * 0.4
        )

        result.append(
            Bar(
                timestamp=
                    start
                    + timedelta(
                        minutes=i
                    ),

                open=p,
                high=p + 1,
                low=p - 1,
                close=(
                    p + 0.5
                    if direction > 0
                    else p - 0.5
                ),
                volume=1000 + i * 10,
            )
        )

    return result


config = main.jarvis_backtest_config(
    warmup_bars=30,
)


result = main.jarvis_evolve_strategy(
    "rsi_mean_reversion_v1",

    {
        "TREND_UP":
            bars(1),

        "TREND_DOWN":
            bars(-1),
    },

    config,

    candidate_count=6,
    random_seed=11,
)


assert result["success"]
assert result["candidate_count"] == 6

assert result["production_promotion"] is False
assert result["registry_mutation"] is False
assert result["automatic_retirement"] is False

assert result["best_challenger"] is not None


print("Regime datasets: ACTIVE")
print("Candidate backtesting: ACTIVE")
print("Expectancy fitness: ACTIVE")
print("Profit-factor fitness: ACTIVE")
print("Return fitness: ACTIVE")
print("Drawdown penalty: ACTIVE")
print("Regime stability penalty: ACTIVE")
print("Worst-regime component: ACTIVE")
print("Champion/challenger: ACTIVE")
print("Retirement proposals: ACTIVE")
print("Production promotion: BLOCKED")
print("Registry mutation: BLOCKED")
print("Evolution laboratory: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("EVOLUTION PROBE FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# DERIVATIVES HISTORICAL TRUTHFULNESS
# ============================================================

print()
print("Checking derivatives historical compatibility gate...")


probe = r'''
from omni.trading_intelligence.strategy_evolution_lab import (
    StrategyEvolutionLab,
)


lab = StrategyEvolutionLab()


candidate = lab.seed_genome(
    "derivatives_confirmation_v1"
)


assert not lab.historically_compatible(
    candidate.strategy
)


print("Derivative snapshot strategy detected: PASS")
print("Missing historical derivative features fabricated: NO")
print("Unsupported historical evolution: BLOCKED")
print("Historical compatibility gate: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("HISTORICAL COMPATIBILITY FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# SAFETY PROBE
# ============================================================

print()
print("Checking V4 safety...")


probe = r'''
import main


v4 = main.jarvis_trading_v4_status()


assert v4["research_only"]
assert v4["live_execution"] is False

assert v4["automatic_registry_mutation"] is False
assert v4["automatic_strategy_promotion"] is False
assert v4["automatic_strategy_retirement"] is False
assert v4["automatic_broker_order"] is False
assert v4["production_self_modification"] is False


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
        )[
            "allowed"
        ]
        is False
    )


print("Live execution: BLOCKED")
print("Automatic broker orders: BLOCKED")
print("Automatic production promotion: BLOCKED")
print("Automatic registry mutation: BLOCKED")
print("Automatic retirement/deletion: BLOCKED")
print("Production self-modification: BLOCKED")
print("V4 safety: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("V4 SAFETY FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# TARGETED REGRESSION
# ============================================================

print()
print("Running Trading Intelligence V4 targeted regression...")


r = run(
    "-m",
    "unittest",

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
# FINAL CORE / V3 / BROWSER
# ============================================================

for relative, before in PROTECTED.items():

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

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
        "v3=main.jarvis_trading_v3_status(); "
        "v4=main.jarvis_trading_v4_status(); "
        "assert v3['option_chain_schema']; "
        "assert v4['live_execution'] is False; "
        "assert v4['automatic_strategy_promotion'] is False; "
        "print('Final Protected Core: PASS'); "
        "print('Trading V3: PRESERVED'); "
        "print('Trading V4 safety: PASS')"
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

    print("FINAL BROWSER TEST FAILURE")
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
        "pprint.pp(main.jarvis_trading_v4_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V4 SUCCESS")
print("=" * 80)

print()
print("STRATEGY GENOMES")
print("Candidate identity: ACTIVE")
print("Generation lineage: ACTIVE")
print("Parent tracking: ACTIVE")
print("Mutation history: ACTIVE")
print("Backtest-config overrides: ACTIVE")
print()

print("EVOLUTION")
print("Numeric rule mutation: ACTIVE")
print("Stop-loss mutation: ACTIVE")
print("Target mutation: ACTIVE")
print("Trailing-stop mutation: ACTIVE")
print("Holding-period mutation: ACTIVE")
print("Compatible strategy crossover: ACTIVE")
print("Candidate cap: 50")
print()

print("REGIME-AWARE RESEARCH")
print("Named regime datasets: ACTIVE")
print("Independent regime backtests: ACTIVE")
print("Multi-regime fitness: ACTIVE")
print("Worst-regime evaluation: ACTIVE")
print("Stability penalty: ACTIVE")
print()

print("FITNESS")
print("Return component: ACTIVE")
print("Expectancy component: ACTIVE")
print("Profit-factor component: ACTIVE")
print("Win-rate component: ACTIVE")
print("Drawdown penalty: ACTIVE")
print("Insufficient-trade penalty: ACTIVE")
print()

print("CHAMPION / CHALLENGER")
print("Champion baseline: ACTIVE")
print("Challenger ranking: ACTIVE")
print("Research challenger winner: ACTIVE")
print("Keep-testing state: ACTIVE")
print("Degrade state: ACTIVE")
print("Retirement proposal: ACTIVE")
print()

print("TRUTHFULNESS")
print("Historical-feature compatibility gate: ACTIVE")
print("Derivative snapshot strategy historical fabrication: BLOCKED")
print("Unsupported historical derivatives evolution: BLOCKED")
print()

print("GOVERNANCE")
print("Candidate auto-registration: BLOCKED")
print("Automatic production promotion: BLOCKED")
print("Automatic retirement/deletion: BLOCKED")
print("Automatic broker order: BLOCKED")
print("Production self-modification: BLOCKED")
print("Research artifact storage: ACTIVE")
print()

print("PRESERVED")
print("Trading V1: YES")
print("Trading V1.1: YES")
print("Trading V2 backtester: YES")
print("Trading V3 derivatives: YES")
print("Canonical FYERS bridge: YES")
print("Browser Windows-lock repair: YES")
print("Protected Core: UNCHANGED")
print("Full regression: PASS")
print()

print("STATUS:")
print(status.stdout.strip())
print()

print("NEXT: TRADING INTELLIGENCE V5")
print("Walk-forward validation")
print("True train / validation / out-of-sample partitions")
print("Monte Carlo trade-sequence simulation")
print("Parameter sensitivity surfaces")
print("Cost/slippage stress testing")
print("Regime robustness testing")
print("Data sufficiency checks")
print("Overfitting risk score")
print("Candidate rejection gates")
print("PROMOTE / KEEP TESTING / DEGRADE / RETIRE recommendation")
print("Still NO automatic production promotion")
