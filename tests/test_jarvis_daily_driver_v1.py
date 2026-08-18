from __future__ import annotations

import unittest
from pathlib import Path

from omni.conversation_turns import ConversationTurns
from omni.paper_trade_monitor import PaperTradeMonitor


ROOT = Path(__file__).resolve().parents[1]


class ConversationV2Tests(unittest.TestCase):
    def test_ordinal_reference_resolves_first_recommendation(self):
        context = ConversationTurns()
        context.remember(
            "Give me three Hindi Bollywood songs",
            '1. "Lag Jaa Gale"\n2. "Ajeeb Dastan Hai Yeh"\n3. "Pal Pal Dil Ke Paas"',
            "MASTER_JARVIS",
        )

        value = context.augment("give me first song lyrics")

        self.assertIn("Resolved reference hint: Lag Jaa Gale", value)
        self.assertIn("Current user follow-up: give me first song lyrics", value)

    def test_typoed_title_resolves_against_anchor(self):
        context = ConversationTurns()
        context.remember(
            "Suggest a Hindi song",
            'I recommend "Lag Jaa Gale".',
            "MASTER_JARVIS",
        )

        value = context.augment("lagg ja gale")

        self.assertIn("Resolved reference hint: Lag Jaa Gale", value)

    def test_failed_answer_does_not_poison_anchor(self):
        context = ConversationTurns()
        context.remember(
            "Suggest a Hindi song",
            'I recommend "Lag Jaa Gale".',
            "MASTER_JARVIS",
        )
        context.remember(
            "lagg ja gale",
            "I can't understand what you mean. Could you please rephrase.",
            "MASTER_JARVIS",
        )

        value = context.augment("give me first song lyrics")

        self.assertIn("Lag Jaa Gale", value)
        self.assertNotIn("can't understand", value.lower())

    def test_explanation_followup_is_detected(self):
        self.assertTrue(
            ConversationTurns.is_explanation_followup("Why?")
        )
        self.assertFalse(
            ConversationTurns.is_explanation_followup("latest news")
        )


class PaperMonitorV2Tests(unittest.TestCase):
    def test_interval_is_bounded(self):
        self.assertEqual(
            PaperTradeMonitor.interval_from_request("check every 2 seconds"),
            15.0,
        )
        self.assertEqual(
            PaperTradeMonitor.interval_from_request("check every 2 minutes"),
            120.0,
        )

    def test_empty_status_is_paper_only(self):
        monitor = PaperTradeMonitor()
        value = monitor.status()

        self.assertEqual(value["active_count"], 0)
        self.assertTrue(value["paper_only"])
        self.assertFalse(value["live_execution"])

    def test_monitor_source_contains_no_order_api_calls(self):
        source = (
            ROOT
            / "omni"
            / "paper_trade_monitor.py"
        ).read_text(encoding="utf-8").lower()

        for forbidden in (
            "place_order(",
            "modify_order(",
            "cancel_order(",
            "broker_order(",
        ):
            self.assertNotIn(forbidden, source)


class DailyDriverRoutingSourceTests(unittest.TestCase):
    def test_router_exposes_monitor_control_and_status_endpoint(self):
        source = (
            ROOT
            / "workstation"
            / "jarvis_os_v3.py"
        ).read_text(encoding="utf-8")

        self.assertIn("PAPER_MONITOR_CONTROL", source)
        self.assertIn('/api/paper-monitors', source)
        self.assertIn("CHAT_FOLLOWUP", source)


    def test_voice_recognition_has_transient_error_self_heal(self):
        source = (
            ROOT
            / "workstation"
            / "jarvis_os_v3_assets"
            / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "Self-heal transient browser recognition failures",
            source,
        )
        self.assertIn(
            '"service-not-allowed"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
