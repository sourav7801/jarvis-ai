import tempfile
import unittest
from pathlib import Path

from omni.experience_learning import (
    ExperienceStore,
)


class ExperienceLearningTests(
    unittest.TestCase
):

    def test_append_and_recall(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        store = ExperienceStore(
            Path(temp.name)
            / "experience.jsonl"
        )

        store.append(
            kind="mission",

            capability="planning",

            success=True,

            score=88,

            summary="Good mission",

            lessons=(
                "Keep dependency ordering",
            ),
        )

        recent = store.recent()

        self.assertEqual(
            len(recent),
            1,
        )

        self.assertEqual(
            recent[0].capability,
            "planning",
        )


    def test_capability_history(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        store = ExperienceStore(
            Path(temp.name)
            / "experience.jsonl"
        )

        store.append(
            kind="x",
            capability="coding",
            success=True,
            score=90,
            summary="A",
        )

        store.append(
            kind="x",
            capability="research",
            success=True,
            score=80,
            summary="B",
        )

        self.assertEqual(
            len(
                store
                .capability_history(
                    "coding"
                )
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
