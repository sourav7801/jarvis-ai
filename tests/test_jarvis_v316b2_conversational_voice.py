import unittest
from pathlib import Path


ROOT = Path(
    r"C:\Jarvis"
)


APP = (
    ROOT
    / "workstation"
    / "jarvis_os_v3_assets"
    / "app.js"
)


class VoiceV316B2Tests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.source = APP.read_text(
            encoding="utf-8"
        )


    def test_new_module(
        self,
    ):

        self.assertIn(
            "JARVIS_V316B2_CONVERSATIONAL_VOICE",
            self.source,
        )


    def test_old_marker_compatibility(
        self,
    ):

        self.assertIn(
            "JARVIS_V315_VOICE_CONVERSATION",
            self.source,
        )


    def test_old_confidence_contract(
        self,
    ):

        self.assertIn(
            "confidence < 0.48",
            self.source,
        )


    def test_legacy_setup_not_started(
        self,
    ):

        self.assertNotIn(
            "\nsetupVoice();\n",
            self.source,
        )


    def test_wake_greeting(
        self,
    ):

        self.assertIn(
            "Hi. What can I do for you?",
            self.source,
        )


    def test_trading_summary(
        self,
    ):

        self.assertIn(
            "function tradingSpeech(",
            self.source,
        )


    def test_auto_submit(
        self,
    ):

        self.assertIn(
            "execute.click()",
            self.source,
        )


    def test_final_only(
        self,
    ):

        self.assertIn(
            "result.isFinal",
            self.source,
        )


    def test_barge_in(
        self,
    ):

        self.assertIn(
            "function interrupt(",
            self.source,
        )


    def test_command_only_tts(
        self,
    ):

        self.assertIn(
            'url.includes(',
            self.source,
        )

        self.assertIn(
            '"/api/command"',
            self.source,
        )


    def test_no_live_orders(
        self,
    ):

        section = self.source[
            self.source.find(
                "JARVIS_V316B2_CONVERSATIONAL_VOICE"
            ):
        ]


        for token in (
            "place_order(",
            "modify_order(",
            "cancel_order(",
        ):

            self.assertNotIn(
                token,
                section,
            )


if __name__ == "__main__":

    unittest.main()
