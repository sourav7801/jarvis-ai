from __future__ import annotations

import unittest

from omni.conversation_turns import ConversationTurns


class ConversationV23ResolvedHintTests(unittest.TestCase):
    def _context(self):
        context = ConversationTurns()
        context.remember(
            "Just give me top 3 Bollywood songs.",
            '1. "Lag Jaa Gale" from Woh Kaun Thi (1964)\n'
            '2. "Tum Hi Ho" from Aashiqui 2 (2013)\n'
            '3. "Udta Punjab" from Udta Punjab (2016)',
            "MASTER_JARVIS",
        )
        return context

    def test_exact_runtime_short_lyrics_followup_is_augmented(self):
        context = self._context()

        value = context.augment(
            "Give me the lyrics of first one."
        )

        self.assertIn(
            "Resolved reference hint: Lag Jaa Gale",
            value,
        )

    def test_voice_misrecognition_still_uses_first_entity(self):
        context = self._context()

        value = context.augment(
            "Leaks our first one."
        )

        self.assertIn(
            "Resolved reference hint: Lag Jaa Gale",
            value,
        )

    def test_bad_no_context_answer_does_not_poison_anchor(self):
        context = self._context()

        context.remember(
            "Give me the lyrics of first one.",
            "Unfortunately, I don't have any context about the song you're referring to. "
            "Could you please provide more information or clarify which song you'd like?",
            "MASTER_JARVIS",
        )

        value = context.augment(
            "Give me the lyrics of first one."
        )

        self.assertIn(
            "Resolved reference hint: Lag Jaa Gale",
            value,
        )
        self.assertNotIn(
            "I don't have any context",
            value,
        )

    def test_standalone_request_is_not_forced_into_context(self):
        context = self._context()

        self.assertEqual(
            context.augment("analyze crude oil"),
            "analyze crude oil",
        )


if __name__ == "__main__":
    unittest.main()