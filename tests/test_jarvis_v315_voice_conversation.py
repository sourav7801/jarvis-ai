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


class VoiceConversationTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.source = APP.read_text(
            encoding="utf-8"
        )


    def test_voice_module_present(
        self,
    ):

        self.assertIn(
            "JARVIS_V315_VOICE_CONVERSATION",
            self.source,
        )


    def test_wake_word_present(
        self,
    ):

        self.assertIn(
            "What can I do for you?",
            self.source,
        )


    def test_auto_submission_present(
        self,
    ):

        self.assertIn(
            "execute.click()",
            self.source,
        )


    def test_tts_present(
        self,
    ):

        self.assertIn(
            "SpeechSynthesisUtterance",
            self.source,
        )


    def test_final_transcripts_only(
        self,
    ):

        self.assertIn(
            "result.isFinal",
            self.source,
        )


    def test_duplicate_filter_present(
        self,
    ):

        self.assertIn(
            "lastTranscriptAt",
            self.source,
        )


    def test_confidence_filter_present(
        self,
    ):

        self.assertIn(
            "confidence < 0.48",
            self.source,
        )


    def test_no_broker_execution_code(
        self,
    ):

        forbidden = (
            "place_order(",
            "modify_order(",
            "cancel_order(",
        )


        for token in forbidden:

            self.assertNotIn(
                token,
                self.source[
                    self.source.find(
                        "JARVIS_V315_VOICE_CONVERSATION"
                    ):
                ],
            )


if __name__ == "__main__":

    unittest.main()
