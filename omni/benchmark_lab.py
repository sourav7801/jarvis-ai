from __future__ import annotations

from dataclasses import (
    dataclass,
)

import time


@dataclass(frozen=True)
class BenchmarkCase:

    name: str

    args: tuple = ()

    kwargs: dict | None = None

    expected: object = None


@dataclass(frozen=True)
class BenchmarkResult:

    subject: str

    passed: int

    failed: int

    total: int

    score: float

    duration_seconds: float

    failures: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkComparison:

    baseline_score: float

    candidate_score: float

    delta: float

    improved: bool

    non_regression: bool


class CapabilityBenchmarkSuite:

    def __init__(
        self,
        cases,
    ):

        self.cases = tuple(
            cases
        )


    def run(
        self,
        subject,
        function,
    ):

        started = (
            time.perf_counter()
        )

        passed = 0
        failures = []

        for case in self.cases:

            try:

                output = function(
                    *tuple(
                        case.args
                    ),
                    **dict(
                        case.kwargs
                        or {}
                    ),
                )

                if (
                    output
                    == case.expected
                ):

                    passed += 1

                else:

                    failures.append(
                        (
                            case.name
                            + ": expected "
                            + repr(
                                case.expected
                            )
                            + ", got "
                            + repr(
                                output
                            )
                        )
                    )

            except Exception as exc:

                failures.append(
                    case.name
                    + ": "
                    + type(exc).__name__
                    + ": "
                    + str(exc)
                )

        total = len(
            self.cases
        )

        failed = (
            total
            - passed
        )

        score = (
            100.0
            if total == 0
            else (
                passed
                / total
                * 100.0
            )
        )

        return BenchmarkResult(
            subject=str(
                subject
            ),

            passed=passed,

            failed=failed,

            total=total,

            score=round(
                score,
                4,
            ),

            duration_seconds=(
                time.perf_counter()
                - started
            ),

            failures=tuple(
                failures
            ),
        )


    @staticmethod
    def compare(
        baseline,
        candidate,
        *,
        minimum_delta=0.0,
    ):

        delta = (
            float(
                candidate.score
            )
            - float(
                baseline.score
            )
        )

        return BenchmarkComparison(
            baseline_score=
                float(
                    baseline.score
                ),

            candidate_score=
                float(
                    candidate.score
                ),

            delta=
                round(
                    delta,
                    4,
                ),

            improved=(
                delta
                > float(
                    minimum_delta
                )
            ),

            non_regression=(
                delta
                >= 0.0
            ),
        )
