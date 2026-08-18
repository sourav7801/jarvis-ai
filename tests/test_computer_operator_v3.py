import unittest


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.live_browser_session import (
    LiveBrowserSessionManager,
)

from omni.natural_target import (
    NaturalTargetResolver,
)

from omni.operator_brain_dsl import (
    BrainDSLPlanner,
)

from omni.operator_resume import (
    OperatorResumeManager,
)

from omni.target_fusion import (
    TargetCandidate,
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
                    '"payload":{}'
                    '}]}'
                )
        }


class ComputerOperatorV3Tests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_vision_verified(
        self,
    ):

        status = (
            vision_runtime
            .status()
        )


        self.assertTrue(
            status[
                "vision_ready"
            ],
            status,
        )


        self.assertTrue(
            status[
                "configured_model_vision_verified"
            ],
            status,
        )


    def test_brain_dsl_validated(
        self,
    ):

        result = (
            BrainDSLPlanner()
            .propose(
                "Observe desktop",
                runner=FakeRunner(),
            )
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


    def test_bad_dsl_blocked(
        self,
    ):

        class BadRunner:

            def __call__(
                self,
                request,
            ):

                return {
                    "response":
                        (
                            '{"steps":[{'
                            '"action":"shell.exec",'
                            '"payload":{}'
                            '}]}'
                        )
                }


        result = (
            BrainDSLPlanner()
            .propose(
                "danger",
                runner=BadRunner(),
            )
        )


        self.assertFalse(
            result[
                "valid"
            ]
        )


        self.assertFalse(
            result[
                "auto_execute"
            ]
        )


    def test_resume_validation(
        self,
    ):

        proposal = (
            '{"schema_version":1,'
            '"steps":[{'
            '"action":"desktop.observe",'
            '"payload":{}'
            '}]}'
        )


        result = (
            OperatorResumeManager()
            .prepare(
                "Observe",
                proposal,
            )
        )


        self.assertTrue(
            result[
                "valid"
            ]
        )


        self.assertFalse(
            result[
                "auto_execute"
            ]
        )


    def test_session_manager(
        self,
    ):

        manager = (
            LiveBrowserSessionManager(
                max_sessions=1
            )
        )


        self.assertEqual(
            manager.status(),
            (),
        )


    def test_dom_handle(
        self,
    ):

        candidate = TargetCandidate(
            source=
                "dom",

            label=
                "Save",

            role=
                "button",

            score=
                1.0,

            payload={
                "text":
                    "Save",

                "role":
                    "button",

                "id":
                    "save",
            },
        )


        handle = (
            NaturalTargetResolver
            ._dom_handle(
                candidate
            )
        )


        self.assertEqual(
            handle[
                "strategy"
            ],
            "role",
        )


    def test_public_apis(
        self,
    ):

        self.assertTrue(
            callable(
                main
                .jarvis_operator_v3_plan
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v3_start_browser
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v3_resolve_browser_target
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v3_prepare_resume
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_operator_v3_status
            )
        )


if __name__ == "__main__":

    unittest.main()
