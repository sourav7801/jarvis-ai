import unittest

from omni.benchmark_lab import (
    BenchmarkCase,
    CapabilityBenchmarkSuite,
)


class BenchmarkTests(
    unittest.TestCase
):

    def test_candidate_beats_baseline(self):

        suite = (
            CapabilityBenchmarkSuite(
                (
                    BenchmarkCase(
                        "one",
                        args=(1,),
                        expected=2,
                    ),

                    BenchmarkCase(
                        "two",
                        args=(2,),
                        expected=4,
                    ),
                )
            )
        )

        baseline = suite.run(
            "baseline",

            lambda value:
                value + 1,
        )

        candidate = suite.run(
            "candidate",

            lambda value:
                value * 2,
        )

        comparison = (
            suite.compare(
                baseline,
                candidate,
            )
        )

        self.assertTrue(
            comparison.improved
        )

        self.assertTrue(
            comparison.non_regression
        )


if __name__ == "__main__":
    unittest.main()
