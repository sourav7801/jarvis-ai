import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace


import main


from omni.action_replanner import (
    ActionReplanner,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.persistent_browser import (
    PersistentBrowser,
)

from omni.screen_perception import (
    ScreenPerception,
)

from omni.semantic_ui import (
    SemanticUI,
)

from omni.voice_adapter import (
    VoiceAdapter,
)


class FakePlan:

    lead_agent = "operator"

    agents = (
        "operator",
        "quality",
    )

    requires_approval = True


class FakeBrain:

    def plan(
        self,
        request,
    ):

        return FakePlan()


class ActionV3Tests(
    unittest.TestCase
):


    def test_protected_core(self):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_semantic_ui_available(self):

        self.assertTrue(
            SemanticUI.available()
        )


    def test_semantic_windows_tuple(self):

        self.assertIsInstance(
            SemanticUI()
            .windows(),
            tuple,
        )


    def test_persistent_browser_available(self):

        self.assertTrue(
            PersistentBrowser.available()
        )


    def test_browser_provider_probe(self):

        result = (
            PersistentBrowser()
            .provider_probe()
        )

        self.assertTrue(
            result[
                "success"
            ],
            result,
        )


    def test_browser_requires_approval(self):

        with tempfile.TemporaryDirectory() as tmp:

            browser = (
                PersistentBrowser(
                    Path(tmp)
                )
            )

            result = browser.inspect(
                "https://example.com"
            )

            self.assertTrue(
                result[
                    "requires_approval"
                ]
            )


    def test_password_fill_blocked(self):

        browser = (
            PersistentBrowser()
        )

        result = browser.fill(
            "https://example.com",
            'input[type="password"]',
            "secret",
        )

        self.assertFalse(
            result[
                "success"
            ]
        )


    def test_screen_metadata_without_model(self):

        with tempfile.TemporaryDirectory() as tmp:

            from PIL import Image

            path = (
                Path(tmp)
                / "screen.png"
            )

            Image.new(
                "RGB",
                (
                    100,
                    50,
                ),
            ).save(
                path
            )

            result = (
                ScreenPerception()
                .analyze_existing(
                    path
                )
            )

            self.assertEqual(
                result[
                    "width"
                ],
                100,
            )

            self.assertFalse(
                result[
                    "vision_provider_configured"
                ]
            )


    def test_replanner_does_not_auto_execute(self):

        result = SimpleNamespace(
            success=False,

            failed_step="click-login",

            steps=(
                SimpleNamespace(
                    success=False,

                    step_id=
                        "click-login",

                    error=
                        "element missing",

                    attempts=
                        2,
                ),
            ),
        )


        replanner = ActionReplanner(
            FakeBrain()
        )


        proposal = replanner.propose(
            "Open dashboard",
            result,
        )


        self.assertTrue(
            proposal[
                "needs_replan"
            ]
        )

        self.assertFalse(
            proposal[
                "auto_execute"
            ]
        )

        self.assertEqual(
            proposal[
                "lead_agent"
            ],
            "operator",
        )


    def test_voice_requires_approval(self):

        result = (
            VoiceAdapter()
            .listen_once()
        )

        self.assertTrue(
            result[
                "requires_approval"
            ]
        )


    def test_public_api(self):

        self.assertTrue(
            callable(
                main
                .jarvis_semantic_windows
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_ui_controls
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_persistent_browser_inspect
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_github_state
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_action_v3_status
            )
        )


if __name__ == "__main__":
    unittest.main()
