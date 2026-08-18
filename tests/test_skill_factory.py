import tempfile
import unittest
from pathlib import Path

from omni.skill_factory import (
    SkillFactory,
)


class SkillFactoryTests(
    unittest.TestCase
):

    def factory(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        return SkillFactory(
            Path(temp.name)
        )


    def test_safe_candidate(self):

        factory = self.factory()

        factory.create_candidate(
            "double_number",

            purpose=
                "Double numeric input.",

            source=(
                "def run(value):\n"
                "    return value * 2\n"
            ),
        )

        result = factory.validate(
            "double_number"
        )

        self.assertEqual(
            result["state"],
            "validated",
        )


    def test_dangerous_candidate(self):

        factory = self.factory()

        factory.create_candidate(
            "dangerous",

            purpose="bad",

            source=(
                "import subprocess\n\n"
                "def run(value):\n"
                "    return subprocess.run(value)\n"
            ),
        )

        result = factory.validate(
            "dangerous"
        )

        self.assertEqual(
            result["state"],
            "rejected",
        )


    def test_promotion_requires_approval(self):

        factory = self.factory()

        factory.create_candidate(
            "safe",

            purpose="safe",

            source=(
                "def run(value):\n"
                "    return value\n"
            ),
        )

        factory.validate(
            "safe"
        )

        with self.assertRaises(
            PermissionError
        ):

            factory.promote(
                "safe",
                approved=False,
            )


    def test_approved_promotion(self):

        factory = self.factory()

        factory.create_candidate(
            "safe",

            purpose="safe",

            source=(
                "def run(value):\n"
                "    return value\n"
            ),
        )

        factory.validate(
            "safe"
        )

        result = factory.promote(
            "safe",
            approved=True,
        )

        self.assertEqual(
            result["state"],
            "promoted",
        )

        self.assertTrue(
            Path(
                result[
                    "promoted_path"
                ]
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
