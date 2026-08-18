import unittest
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "workstation" / "jarvis_trading_workstation_v7" / "static"


class WorkstationFrontendTests(unittest.TestCase):
    def test_paper_desk_has_separate_chat_and_explicit_controls(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="paper"', html)
        self.assertIn('data-chat-context="paper"', html)
        self.assertIn('id="paperArm"', html)
        self.assertIn('id="paperPause"', html)
        self.assertIn("No FYERS or crypto order API is called", html)
        self.assertIn('id="paperUniverse"', html)

    def test_continuous_master_voice_accepts_plain_speech_and_reports_permission(self):
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn("recognition.continuous=false", javascript)
        self.assertIn("getUserMedia({audio:true})", javascript)
        self.assertIn("MICROPHONE PERMISSION REQUIRED", javascript)
        self.assertIn("voiceMasterMode", javascript)
        self.assertIn("scheduleVoiceRestart", javascript)
        self.assertIn("pendingVoiceCommand", javascript)
        self.assertIn("speech_confidence", javascript)
        self.assertIn("if(pendingVoiceCommand?.text)", javascript)
        self.assertNotIn("setVoiceArmed(false,recognitionContext);agent", javascript)
        self.assertNotIn('if(!/^jarvis\\b/i.test', javascript)

    def test_paper_monitoring_exposes_in_app_and_desktop_alerts(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="jarvisAlerts"', html)
        self.assertIn('id="paperAlertMode"', html)
        self.assertIn("processPaperAlerts", javascript)
        self.assertIn("new Notification", javascript)

    def test_master_omnidock_and_answer_first_web_ui_are_present(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="omniDock"', html)
        self.assertIn('id="omniInput"', html)
        self.assertIn('id="omniVoice"', html)
        self.assertIn('id="webAnswerPanel"', html)

    def test_cinematic_core_exposes_live_voice_state(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        css = (STATIC / "style.css").read_text(encoding="utf-8")
        self.assertIn('id="coreState"', html)
        self.assertIn('id="voiceWave"', html)
        self.assertIn("body.voice-listening", css)
        self.assertIn("body.voice-speaking", css)

    def test_automatic_trade_loop_and_learning_are_visible(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")
        for element_id in (
            "autoLoopState",
            "autoBestSetup",
            "autoRiskState",
            "autoLearningState",
            "autoDailyReview",
            "paperTradeReviews",
            "paperScorecards",
            "quantStrategy",
            "quantRiskReward",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('data-quant-symbol="CRUDEOIL"', html)
        self.assertIn('data-quant-symbol="BTC"', html)
        self.assertIn("renderAutonomy(paper)", javascript)


if __name__ == "__main__":
    unittest.main()
