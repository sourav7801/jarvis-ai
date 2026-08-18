import tempfile
import unittest
from pathlib import Path

import main
from workstation import app

from omni.improvement_lab import (
    CandidatePatchLab,
)


class ImprovementLabTests(
    unittest.TestCase
):

    def mini_project(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        root = Path(
            temp.name
        )

        target = (
            root
            / "module.py"
        )

        target.write_text(
            (
                "def value():\n"
                "    return 1\n"
            ),
            encoding="utf-8",
        )

        lab = CandidatePatchLab(
            root,

            root
            / "lab",
        )

        return (
            root,
            target,
            lab,
        )


    def test_path_escape_blocked(self):

        root, target, lab = (
            self.mini_project()
        )

        with self.assertRaises(
            PermissionError
        ):

            lab.create_candidate(
                capability="coding",

                target_file=
                    root.parent
                    / "outside.py",

                candidate_source=
                    "def run():\n"
                    "    return 1\n",

                rationale="bad",
            )


    def test_new_eval_is_blocked(self):

        root, target, lab = (
            self.mini_project()
        )

        candidate = (
            lab.create_candidate(
                capability="coding",

                target_file=
                    target,

                candidate_source=(
                    "def value():\n"
                    "    return eval('2')\n"
                ),

                rationale="unsafe",
            )
        )

        review = (
            lab.security_review(
                candidate[
                    "candidate_id"
                ]
            )
        )

        self.assertFalse(
            review[
                "passed"
            ]
        )


    def test_candidate_evaluation(self):

        root, target, lab = (
            self.mini_project()
        )

        candidate = (
            lab.create_candidate(
                capability="coding",

                target_file=
                    target,

                candidate_source=(
                    "def value():\n"
                    "    return 2\n"
                ),

                rationale="improve",
            )
        )

        result = lab.evaluate(
            candidate[
                "candidate_id"
            ],

            test_args=[
                "-c",
                "import module; "
                "assert isinstance("
                "module.value(), int)",
            ],
        )

        self.assertEqual(
            result[
                "state"
            ],
            "evaluated",
        )


    def test_promotion_requires_approval(self):

        root, target, lab = (
            self.mini_project()
        )

        candidate = (
            lab.create_candidate(
                capability="coding",

                target_file=
                    target,

                candidate_source=(
                    "def value():\n"
                    "    return 2\n"
                ),

                rationale="improve",
            )
        )

        cid = candidate[
            "candidate_id"
        ]

        lab.evaluate(
            cid,

            test_args=[
                "-c",
                "import module; "
                "assert isinstance("
                "module.value(), int)",
            ],
        )

        with self.assertRaises(
            PermissionError
        ):

            lab.promote(
                cid,
                approved=False,
            )


    def test_approved_promotion(self):

        root, target, lab = (
            self.mini_project()
        )

        candidate = (
            lab.create_candidate(
                capability="coding",

                target_file=
                    target,

                candidate_source=(
                    "def value():\n"
                    "    return 2\n"
                ),

                rationale="improve",
            )
        )

        cid = candidate[
            "candidate_id"
        ]

        args = [
            "-c",
            "import module; "
            "assert isinstance("
            "module.value(), int)",
        ]

        lab.evaluate(
            cid,
            test_args=args,
        )

        result = lab.promote(
            cid,
            approved=True,
            post_test_args=args,
        )

        self.assertEqual(
            result[
                "state"
            ],
            "promoted",
        )

        self.assertIn(
            "return 2",
            target.read_text(
                encoding="utf-8"
            ),
        )


    def test_failed_post_test_rolls_back(self):

        root, target, lab = (
            self.mini_project()
        )

        original = (
            target.read_text(
                encoding="utf-8"
            )
        )

        candidate = (
            lab.create_candidate(
                capability="coding",

                target_file=
                    target,

                candidate_source=(
                    "def value():\n"
                    "    return 2\n"
                ),

                rationale="candidate",
            )
        )

        cid = candidate[
            "candidate_id"
        ]

        lab.evaluate(
            cid,

            test_args=[
                "-c",
                "import sys; "
                "sys.exit(0)",
            ],
        )

        result = lab.promote(
            cid,

            approved=True,

            post_test_args=[
                "-c",
                "import sys; "
                "sys.exit(1)",
            ],
        )

        self.assertEqual(
            result[
                "state"
            ],
            "rolled_back",
        )

        self.assertEqual(
            target.read_text(
                encoding="utf-8"
            ),
            original,
        )


    def test_main_api_exists(self):

        self.assertTrue(
            callable(
                main
                .jarvis_self_improvement_status
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_find_weaknesses
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_create_candidate_patch
            )
        )


    def test_workstation_api_exists(self):

        self.assertTrue(
            callable(
                app
                .jarvis_self_improvement_payload
            )
        )


if __name__ == "__main__":
    unittest.main()
