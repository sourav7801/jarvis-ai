from __future__ import annotations

import unittest

from omni.conversation_turns import ConversationTurns


class ConversationV21RuntimeRegressionTests(unittest.TestCase):
    def test_long_ordinal_followup_uses_previous_recommendation(self):
        context = ConversationTurns()
        context.remember(
            "Just give me 3 Bollywood song which I can listen.",
            '1. "Lag Jaa Gale" from Woh Kaun Thi (1964)\n'
            '2. "Ajeeb Dastan Hai Yeh"\n'
            '3. "Pal Pal Dil Ke Paas"',
            "MASTER_JARVIS",
        )

        followup = (
            "Can you give me the lyrics of first one song which you suggested me?"
        )

        self.assertTrue(context.is_reference_followup(followup))
        self.assertTrue(context.is_ambiguous_followup(followup))

        value = context.augment(followup)

        self.assertIn("Resolved reference hint: Lag Jaa Gale", value)
        self.assertIn("Previous JARVIS response:", value)
        self.assertIn("Current user follow-up:", value)

    def test_false_no_context_answer_does_not_replace_anchor(self):
        context = ConversationTurns()
        context.remember(
            "Suggest three songs",
            '1. "Lag Jaa Gale"\n2. "Ajeeb Dastan Hai Yeh"\n3. "Pal Pal Dil Ke Paas"',
            "MASTER_JARVIS",
        )
        context.remember(
            "Can you give me the lyrics of first one song which you suggested me?",
            "I didn't suggest any song, and I don't have prior context about a specific song. "
            "I'm a new conversation each time you interact with me.",
            "MASTER_JARVIS",
        )

        value = context.augment("Check.")

        self.assertIn("Lag Jaa Gale", value)
        self.assertNotIn("I didn't suggest any song", value)

    def test_standalone_current_request_not_forced_into_context(self):
        context = ConversationTurns()
        context.remember("Suggest songs", '1. "Lag Jaa Gale"', "MASTER_JARVIS")

        self.assertFalse(context.is_reference_followup("latest news"))
        self.assertFalse(context.is_reference_followup("analyze crude oil"))


if __name__ == "__main__":
    unittest.main()
