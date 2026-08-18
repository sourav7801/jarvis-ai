import tempfile
import unittest

from pathlib import Path


import main


from omni.approval_batch import (
    ApprovalBatchQueue,
)

from omni.computer_operator import (
    ComputerOperator,
    GoalCompiler,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.git_worktree_engine import (
    GitWorktreeEngine,
)

from omni.operator_schema import (
    OperatorPlan,
    OperatorStep,
    validate_plan,
)

from omni.safe_file_handoff import (
    SafeFileHandoff,
)

from omni.tool_capability_graph import (
    ToolCapabilityGraph,
)


class ComputerOperatorTests(
    unittest.TestCase
):


    def test_protected_core(self):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_unknown_action_blocked(self):

        plan = OperatorPlan(
            goal="danger",

            steps=(
                OperatorStep(
                    "one",
                    "shell.exec",
                    {},
                ),
            ),
        )


        with self.assertRaises(
            PermissionError
        ):

            validate_plan(
                plan
            )


    def test_compiler_browser_inspect(self):

        plan = (
            GoalCompiler()
            .compile(
                (
                    "Inspect "
                    "https://example.com"
                )
            )
        )


        self.assertTrue(
            plan.executable
        )

        self.assertEqual(
            plan.steps[
                0
            ].action,
            "browser.inspect",
        )


    def test_compiler_git_status(self):

        plan = (
            GoalCompiler()
            .compile(
                "Check git status"
            )
        )


        self.assertEqual(
            plan.steps[
                0
            ].action,
            "git.status",
        )


    def test_unknown_goal_not_executed(self):

        plan = (
            GoalCompiler()
            .compile(
                (
                    "Invent a completely "
                    "unknown machine action"
                )
            )
        )


        self.assertFalse(
            plan.executable
        )

        self.assertEqual(
            len(
                plan.steps
            ),
            0,
        )


    def test_structured_action_validation(self):

        plan = (
            GoalCompiler()
            .compile(
                "Read document",

                hints={
                    "steps": [
                        {
                            "action":
                                "document.read",

                            "payload": {
                                "path":
                                    "example.txt",
                            },
                        },
                    ],
                },
            )
        )


        self.assertTrue(
            validate_plan(
                plan
            )
        )


    def test_browser_binding_exact(self):

        step = OperatorStep(
            "one",

            "browser.inspect",

            {
                "url":
                    "https://example.com",

                "profile":
                    "default",
            },
        )


        binding = (
            ComputerOperator
            .binding_for_step(
                step
            )
        )


        self.assertEqual(
            binding[
                "action"
            ],
            (
                "persistent_browser."
                "inspect"
            ),
        )


    def test_batch_approval(self):

        with tempfile.TemporaryDirectory() as tmp:

            queue = (
                ApprovalBatchQueue(
                    Path(tmp)
                )
            )


            batch = queue.create(
                "test",

                (
                    {
                        "step_id":
                            "one",

                        "action":
                            "x",

                        "payload": {
                            "a": 1,
                        },

                        "display": {
                            "test":
                                True,
                        },
                    },
                ),
            )


            approved = queue.approve(
                batch[
                    "batch_id"
                ]
            )


            self.assertEqual(
                approved[
                    "status"
                ],
                "approved",
            )


            self.assertIsNotNone(
                queue.token_for_step(
                    batch[
                        "batch_id"
                    ],
                    "one",
                )
            )


    def test_download_executable_blocked(self):

        handoff = (
            SafeFileHandoff()
        )


        with self.assertRaises(
            PermissionError
        ):

            handoff.safe_name(
                (
                    "https://example.com/"
                    "malware.exe"
                )
            )


    def test_download_localhost_blocked(self):

        handoff = (
            SafeFileHandoff()
        )


        with self.assertRaises(
            PermissionError
        ):

            handoff.validate_url(
                "http://localhost/file.txt"
            )


    def test_download_needs_approval(self):

        with tempfile.TemporaryDirectory() as tmp:

            handoff = (
                SafeFileHandoff(
                    Path(tmp)
                )
            )


            result = (
                handoff.download(
                    (
                        "https://example.com/"
                        "report.pdf"
                    )
                )
            )


            self.assertTrue(
                result[
                    "requires_approval"
                ]
            )


    def test_worktree_merge_blocked(self):

        engine = (
            GitWorktreeEngine()
        )


        with self.assertRaises(
            PermissionError
        ):

            engine.merge()


    def test_worktree_push_blocked(self):

        engine = (
            GitWorktreeEngine()
        )


        with self.assertRaises(
            PermissionError
        ):

            engine.push()


    def test_capability_graph(self):

        graph = (
            ToolCapabilityGraph()
            .snapshot()
        )


        self.assertFalse(
            graph[
                "trading"
            ][
                "execution"
            ]
        )


        self.assertFalse(
            graph[
                "git"
            ][
                "automatic_push"
            ]
        )


    def test_safe_readonly_operator_execution(self):

        operator = (
            ComputerOperator()
        )


        plan = operator.compile(
            "Show visible windows"
        )


        result = operator.execute(
            plan
        )


        self.assertTrue(
            result.success
        )

        self.assertEqual(
            result.completed_steps,
            1,
        )


    def test_interactive_plan_requires_batch(self):

        operator = (
            ComputerOperator()
        )


        plan = operator.compile(
            (
                "Inspect "
                "https://example.com"
            )
        )


        result = operator.execute(
            plan
        )


        self.assertFalse(
            result.success
        )

        self.assertEqual(
            result.replan,
            {
                "approval_required":
                    True
            },
        )


    def test_public_api(self):

        self.assertTrue(
            callable(
                main
                .jarvis_operator_prepare
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_operator_execute
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_approve_batch
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_download_file
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_create_worktree
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_tool_capability_graph
            )
        )


if __name__ == "__main__":
    unittest.main()
