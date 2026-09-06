from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from omni.conversation_turns import ConversationTurns
from workstation.quant_terminal_bridge import (
    dispatch_quant_terminal,
    is_quant_terminal_request,
    is_terminal_diagnostic_request,
)
from workstation.jarvis_os_v3 import dispatch_command, render_response


ROOT = Path(__file__).resolve().parents[1]


class ConversationRouteIsolationTests(unittest.TestCase):
    def test_acknowledgement_does_not_inherit_previous_trading_route(self):
        context = ConversationTurns()
        context.remember(
            "open trading terminal",
            "Quant Trading Intelligence terminal opened.",
            "QUANT_TRADING_INTELLIGENCE",
        )

        self.assertFalse(context.is_ambiguous_followup("Now can."))
        self.assertEqual(context.augment("Now can."), "Now can.")

    def test_lyrics_ordinal_is_a_reference_followup(self):
        self.assertTrue(
            ConversationTurns.is_reference_followup(
                "Can you give me the lyrics of the first one?"
            )
        )


class QuantSelfHealRoutingTests(unittest.TestCase):
    def test_blank_quant_charts_request_routes_to_terminal_diagnostics(self):
        text = "scan my Quant trading intelligence window and check why the charts are not loading"
        self.assertTrue(is_terminal_diagnostic_request(text))
        self.assertTrue(is_quant_terminal_request(text))

    @patch("workstation.quant_terminal_bridge.diagnose_and_repair_terminal")
    def test_diagnostic_dispatch_returns_concrete_self_heal_result(self, diagnose):
        diagnose.return_value = {
            "success": True,
            "speech": "Backend healthy; opened a repaired terminal.",
            "browser_opened": True,
            "paper_only": True,
            "live_execution": False,
        }

        result = dispatch_quant_terminal(
            "check why my Quant Terminal charts are blank"
        ).to_dict()

        self.assertTrue(result["success"])
        self.assertTrue(result["browser_opened"])
        self.assertIn("repaired", result["response"])
        self.assertFalse(result["live_execution"])


class QuantFrontendRepairTests(unittest.TestCase):
    def test_chart_slot_retains_status_element(self):
        source = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn("signalBadge,patternState,status,chart:null", source)
        self.assertIn("chart-pattern-state", source)
        self.assertIn("async function fetchJson", source)
        self.assertIn("Market-data request timed out", source)
        self.assertIn("slot.pendingCrypto", source)
        self.assertIn("},500)", source)

    def test_chart_library_is_served_locally(self):
        html = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "index.html"
        ).read_text(encoding="utf-8")
        server = (ROOT / "workstation" / "quant_terminal_v2.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('src="/lightweight-charts.standalone.production.js"', html)
        self.assertNotIn("unpkg.com/lightweight-charts", html)
        self.assertIn('path == "/lightweight-charts.standalone.production.js"', server)

    def test_expired_session_repair_does_not_create_mutation_loop(self):
        source = (
            ROOT
            / "workstation"
            / "quant_terminal_v2_static"
            / "session_hotfix.js"
        ).read_text(encoding="utf-8")

        self.assertIn('button.textContent !== "FYERS · SESSION EXPIRED"', source)
        self.assertIn('state.textContent !== "SESSION EXPIRED"', source)
        self.assertIn("message.textContent !==", source)


class MasterRouterRepairTests(unittest.TestCase):
    def test_empty_web_answer_falls_through_to_status_message(self):
        rendered = render_response(
            {
                "answer": "",
                "message": "Public search is temporarily unavailable.",
            }
        )

        self.assertEqual(rendered, "Public search is temporarily unavailable.")

    @patch("agents.local_media_agent.analyze_local_media_request")
    @patch("agents.local_media_agent.is_local_media_request", return_value=True)
    def test_local_download_video_routes_to_media_intelligence(self, _recognize, analyze):
        analyze.return_value = {
            "success": True,
            "response": "Four governed video frames were analyzed locally.",
        }

        result = dispatch_command("analyze Video-83486 from download section")

        self.assertEqual(result["route"], "LOCAL_MEDIA_INTELLIGENCE")
        self.assertIn("analyzed locally", result["response"])

    def test_sing_request_returns_original_spoken_content(self):
        result = dispatch_command("can you sing a song for me?")

        self.assertEqual(result["route"], "VOICE_ORIGINAL_SONG")
        self.assertTrue(result["raw"]["original_content"])
        self.assertTrue(result["raw"]["speech_enabled"])

    @patch("agents.web_intelligence_agent.web_intelligence")
    @patch("agents.web_intelligence_agent.is_web_request", return_value=True)
    def test_current_song_request_uses_web_intelligence(self, _recognize, research):
        research.return_value = {
            "success": True,
            "response": "Current songs were verified from public sources.",
        }

        result = dispatch_command("top 3 Bollywood songs trending right now")

        self.assertEqual(result["route"], "WEB_INTELLIGENCE")
        self.assertIn("verified", result["response"])


if __name__ == "__main__":
    unittest.main()
