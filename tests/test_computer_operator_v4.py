import tempfile
import unittest

from pathlib import Path


import main


from omni.coding_mission import (
    CodingMission,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.goal_verifier import (
    GoalVerifier,
)

from omni.operator_dashboard import (
    OperatorDashboard,
)

from omni.operator_runtime import (
    UnifiedOperatorRuntime,
)

from omni.operator_runtime_schema import (
    from_dict,
)

from omni.vision_runtime import (
    vision_runtime,
)


class FakeRunner:

    def __call__(
        self,
        request,
    ):

        return {
            "response":
                (
                    '{"schema_version":1,'
                    '"steps":[{'
                    '"step_id":"observe",'
                    '"action":"desktop.observe",'
                    '"payload":{},'
                    '"verify":{}'
                    '}]}'
                )
        }


class ComputerOperatorV4Tests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_vision_preserved(
        self,
    ):

        self.assertTrue(
            vision_runtime.status()[
                "vision_ready"
            ]
        )


    def test_shell_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            from_dict(
                "danger",

                {
                    "steps": [
                        {
                            "action":
                                "shell.exec",

                            "payload":
                                {},
                        }
                    ]
                },
            )


    def test_trading_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            from_dict(
                "trade",

                {
                    "steps": [
                        {
                            "action":
                                "trading.execute",

                            "payload":
                                {},
                        }
                    ]
                },
            )


    def test_password_target_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            from_dict(
                "password",

                {
                    "steps": [
                        {
                            "action":
                                "browser.natural_fill",

                            "payload": {
                                "session_id":
                                    "x",

                                "target":
                                    "password field",

                                "value":
                                    "secret",
                            },
                        }
                    ]
                },
            )


    def test_brain_plan_validation(
        self,
    ):

        runtime = (
            UnifiedOperatorRuntime()
        )


        result = runtime.plan_goal(
            "Observe desktop",
            runner=FakeRunner(),
        )


        self.assertTrue(
            result[
                "valid"
            ],
            result,
        )


        self.assertFalse(
            result[
                "auto_execute"
            ]
        )


    def test_goal_verifier(
        self,
    ):

        verifier = GoalVerifier()


        result = verifier.verify(
            {
                "title_contains":
                    "example"
            },

            {
                "observation": {
                    "title":
                        "Example Domain"
                }
            },
        )


        self.assertTrue(
            result[
                "passed"
            ]
        )


    def test_unverified_is_distinct(
        self,
    ):

        result = (
            GoalVerifier()
            .verify(
                {},
                {
                    "success":
                        True
                },
            )
        )


        self.assertFalse(
            result[
                "required"
            ]
        )


        self.assertIsNone(
            result[
                "passed"
            ]
        )


    def test_test_runner_restriction(
        self,
    ):

        mission = CodingMission()


        allowed = (
            mission._validate_tests(
                (
                    "-m",
                    "unittest",
                    "discover",
                )
            )
        )


        self.assertEqual(
            allowed[
                1
            ],
            "unittest",
        )


        with self.assertRaises(
            PermissionError
        ):

            mission._validate_tests(
                (
                    "-c",
                    "print('bad')",
                )
            )


    def test_merge_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            CodingMission.merge()


    def test_push_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            CodingMission.push()


    def test_readonly_mission_execution(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            runtime = (
                UnifiedOperatorRuntime(
                    Path(
                        tmp
                    )
                )
            )


            plan = from_dict(
                "Observe desktop",

                {
                    "steps": [
                        {
                            "step_id":
                                "observe",

                            "action":
                                "desktop.observe",

                            "payload":
                                {},

                            "verify":
                                {},
                        }
                    ]
                },
            )


            mission = runtime.create(
                plan
            )


            result = runtime.advance(
                mission[
                    "mission_id"
                ]
            )


            self.assertEqual(
                result[
                    "status"
                ],
                "completed",
            )


            self.assertFalse(
                result[
                    "verified"
                ]
            )


    def test_browser_start_pauses_for_approval(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            runtime = (
                UnifiedOperatorRuntime(
                    Path(
                        tmp
                    )
                )
            )


            plan = from_dict(
                "Open example",

                {
                    "steps": [
                        {
                            "step_id":
                                "browser",

                            "action":
                                "browser.start",

                            "payload": {
                                "url":
                                    "https://example.com",

                                "headless":
                                    True,
                            },

                            "verify":
                                {},
                        }
                    ]
                },
            )


            mission = runtime.create(
                plan
            )


            result = runtime.advance(
                mission[
                    "mission_id"
                ]
            )


            self.assertEqual(
                result[
                    "status"
                ],
                "waiting_approval",
            )


            self.assertIn(
                "browser",
                result[
                    "approval_batches"
                ],
            )


    def test_dashboard(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            dashboard = (
                OperatorDashboard(
                    Path(
                        tmp
                    )
                )
            )


            result = dashboard.snapshot()


            self.assertIn(
                "pending_batches",
                result,
            )


            self.assertFalse(
                result[
                    "automatic_trading"
                ]
            )


    def test_public_apis(
        self,
    ):

        self.assertTrue(
            callable(
                main
                .jarvis_v4_plan
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v4_create_mission
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v4_resume_mission
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v4_dashboard
            )
        )


if __name__ == "__main__":

    unittest.main()
