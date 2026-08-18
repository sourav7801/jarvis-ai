import unittest
from types import SimpleNamespace

from omni.reflection_engine import (
    reflect_mission,
)


class ReflectionTests(
    unittest.TestCase
):

    def test_clean_success_scores_high(self):

        result = SimpleNamespace(
            mission_id="m1",
            success=True,
            verified=True,
            errors=(),
            recovery_count=0,
            plan=SimpleNamespace(
                tasks=()
            ),
        )

        reflection = (
            reflect_mission(
                result
            )
        )

        self.assertEqual(
            reflection.score,
            100.0,
        )


    def test_failure_creates_lessons(self):

        result = SimpleNamespace(
            mission_id="m2",
            success=False,
            verified=False,
            errors=(
                "failure",
            ),
            recovery_count=1,
            plan=SimpleNamespace(
                tasks=()
            ),
        )

        reflection = (
            reflect_mission(
                result
            )
        )

        self.assertLess(
            reflection.score,
            60,
        )

        self.assertTrue(
            reflection.lessons
        )


if __name__ == "__main__":
    unittest.main()
