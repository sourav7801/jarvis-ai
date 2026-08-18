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


class EchoSuppressionTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.source = APP.read_text(
            encoding="utf-8"
        )


    def test_v316b2_preserved(
        self,
    ):

        self.assertIn(
            "JARVIS_V316B2_CONVERSATIONAL_VOICE",
            self.source,
        )


    def test_echo_detector(
        self,
    ):

        self.assertIn(
            "function looksLikeJarvisEcho(",
            self.source,
        )


    def test_echo_quarantine(
        self,
    ):

        self.assertIn(
            "echoBlockUntil",
            self.source,
        )

        self.assertIn(
            "+ 1600",
            self.source,
        )


    def test_recent_spoken_similarity(
        self,
    ):

        self.assertIn(
            "looksLikeJarvisEcho(",
            self.source,
        )

        self.assertIn(
            "ratio >= 0.60",
            self.source,
        )


    def test_stop_priority(
        self,
    ):

        self.assertIn(
            "ABSOLUTE PRIORITY: STOP",
            self.source,
        )

        self.assertIn(
            "stop talking",
            self.source,
        )


    def test_followup_window(
        self,
    ):

        self.assertIn(
            "followupDeadline",
            self.source,
        )

        self.assertIn(
            "+ 10000",
            self.source,
        )


    def test_background_speech_ignored(
        self,
    ):

        self.assertIn(
            "ignored non-wake background speech",
            self.source,
        )


    def test_old_confidence_contract(
        self,
    ):

        self.assertIn(
            "confidence < 0.48",
            self.source,
        )


    def test_old_voice_marker(
        self,
    ):

        self.assertIn(
            "JARVIS_V315_VOICE_CONVERSATION",
            self.source,
        )


    def test_no_live_order_code(
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
