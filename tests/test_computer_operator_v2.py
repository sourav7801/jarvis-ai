import tempfile
import unittest

from pathlib import Path


import main


from omni.browser_observation_loop import (
    BrowserObservationLoop,
)

from omni.computer_operator_v2 import (
    ComputerOperatorV2,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.desktop_state import (
    DesktopSnapshot,
    DesktopState,
)

from omni.operator_dsl import (
    from_dict,
)

from omni.target_fusion import (
    TargetFusion,
)

from omni.vision_runtime import (
    VisionRuntime,
)


class ComputerOperatorV2Tests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_shell_block(
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


    def test_password_block(
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
                                "browser.observe_fill",

                            "payload": {
                                "url":
                                    "https://example.com",

                                "selector":
                                    'input[type="password"]',

                                "value":
                                    "secret",
                            },
                        }
                    ]
                },
            )


    def test_dom_provider(
        self,
    ):

        result = (
            BrowserObservationLoop()
            .provider_probe()
        )

        self.assertTrue(
            result[
                "success"
            ],
            result,
        )

        self.assertTrue(
            result[
                "has_save"
            ]
        )


    def test_desktop_diff(
        self,
    ):

        before = DesktopSnapshot(
            1,
            (
                "A",
            ),
            (),
            "one",
        )

        after = DesktopSnapshot(
            2,
            (
                "A",
                "B",
            ),
            (),
            "two",
        )


        result = (
            DesktopState.compare(
                before,
                after,
            )
        )


        self.assertEqual(
            result[
                "windows_opened"
            ],
            (
                "B",
            ),
        )


    def test_fusion(
        self,
    ):

        result = (
            TargetFusion()
            .resolve(
                "Save",

                dom=(
                    {
                        "text":
                            "Save",

                        "role":
                            "button",
                    },
                ),

                vision=(
                    {
                        "label":
                            "Save",

                        "confidence":
                            0.3,
                    },
                ),
            )
        )


        self.assertTrue(
            result.resolved
        )

        self.assertEqual(
            result.best.source,
            "dom",
        )


    def test_vision_truthfulness(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            runtime = VisionRuntime(
                Path(
                    tmp
                )
                / "vision.json",

                "http://127.0.0.1:1",
            )


            self.assertFalse(
                runtime.status()[
                    "vision_ready"
                ]
            )


    def test_readonly_execution(
        self,
    ):

        operator = (
            ComputerOperatorV2()
        )


        plan = from_dict(
            "Observe desktop",

            {
                "steps": [
                    {
                        "action":
                            "desktop.observe",

                        "payload":
                            {},
                    }
                ]
            },
        )


        self.assertTrue(
            operator.execute(
                plan
            ).success
        )


    def test_public_apis(
        self,
    ):

        self.assertTrue(
            callable(
                main
                .jarvis_operator_v2_prompt
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_operator_v2_execute
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_vision_status
            )
        )


if __name__ == "__main__":

    unittest.main()
