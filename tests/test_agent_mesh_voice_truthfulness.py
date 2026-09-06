from __future__ import annotations

import unittest
from pathlib import Path

from agents.chat_agent import _truthful_chat_message
from agents.company_department_agent import strategy
from omni.agent_registry import AgentSpec
from omni.brain import JarvisBrain
from workstation.jarvis_os_v3 import agent_readiness, uncertain_voice_transcript


ROOT = Path(__file__).resolve().parents[1]


class AgentMeshVoiceTruthfulnessTests(unittest.TestCase):
    def test_fabricated_cultural_origin_fails_closed(self):
        result = _truthful_chat_message(
            "Jab tak paisa liquidity tha bana tha.",
            "A famous line from the film Bobby, spoken by Dharmendra.",
        )
        self.assertIn("will not invent", result)
        self.assertNotIn("Dharmendra", result)

    def test_department_agent_never_leaks_internal_context(self):
        result = strategy(
            "Please review my idea.\n[JARVIS INTERNAL CONTEXT]\n"
            '{"specialist_findings": ["secret orchestration payload"]}'
        )
        self.assertEqual(result["objective"], "Please review my idea.")
        self.assertNotIn("INTERNAL CONTEXT", result["message"])

    def test_ordinary_company_mention_is_not_an_automatic_strategy_mission(self):
        decision = JarvisBrain().decide(
            "Aur company ka tax proper rahega naa toh paise de denge wo."
        )
        self.assertEqual(decision.primary_agent, "chat")

    def test_explicit_company_plan_still_routes_to_strategy(self):
        decision = JarvisBrain().decide("Create a business plan for my startup")
        self.assertEqual(decision.primary_agent, "strategy")

    def test_low_confidence_voice_is_rejected_before_agent_routing(self):
        self.assertTrue(uncertain_voice_transcript("misheard sentence", 0.31))
        self.assertFalse(uncertain_voice_transcript("open the quant terminal", 0.88))

    def test_agent_readiness_checks_the_real_callable(self):
        ready = agent_readiness(
            (
                AgentSpec(
                    "chat_probe",
                    "agents.chat_agent",
                    "chat",
                    "Chat Probe",
                    frozenset({"conversation"}),
                ),
            )
        )
        self.assertEqual(ready[0]["status"], "READY")
        self.assertEqual(ready[0]["execution_mode"], "ON_DEMAND")

    def test_frontend_sends_voice_confidence_and_renders_health(self):
        script = (
            ROOT / "workstation" / "jarvis_os_v3_assets" / "app.js"
        ).read_text(encoding="utf-8")
        self.assertIn("speech_confidence:", script)
        self.assertIn('inputMode: "voice"', script)
        self.assertIn("value.agent_health", script)
        self.assertNotIn("of agents.slice(\n            0,\n            24", script)

    def test_frontend_reports_owner_voice_status_without_claiming_identity(self):
        script = (
            ROOT / "workstation" / "jarvis_os_v3_assets" / "app.js"
        ).read_text(encoding="utf-8")
        markup = (
            ROOT / "workstation" / "jarvis_os_v3_assets" / "index.html"
        ).read_text(encoding="utf-8")
        server = (
            ROOT / "workstation" / "jarvis_os_v3.py"
        ).read_text(encoding="utf-8")

        self.assertIn("/api/voice/owner-status", script)
        self.assertIn("VOICE DICTATION", markup)
        self.assertIn('parsed.path == "/api/voice/owner-status"', server)
        self.assertIn("authorize_voice_command", server)


if __name__ == "__main__":
    unittest.main()
