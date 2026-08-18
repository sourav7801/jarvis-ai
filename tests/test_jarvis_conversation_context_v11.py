from __future__ import annotations

import unittest

from omni.conversation_turns import ConversationTurns


class ConversationContextV11Tests(unittest.TestCase):
    def test_go_ahead_with_song_is_followup(self):
        context = ConversationTurns()
        context.remember(
            "Some suggestion on Hindi Bollywood song?",
            'I recommend "Lag Jaa Gale" and "Mere Mehboob".',
            "MASTER_JARVIS",
        )

        value = context.augment("go ahead with the lagg ja gale")

        self.assertIn("Previous JARVIS response:", value)
        self.assertIn("Lag Jaa Gale", value)
        self.assertIn("go ahead with the lagg ja gale", value)

    def test_failed_clarification_does_not_erase_anchor(self):
        context = ConversationTurns()
        context.remember(
            "Some suggestion on Hindi Bollywood song?",
            'I recommend "Lag Jaa Gale" and "Mere Mehboob".',
            "MASTER_JARVIS",
        )
        context.remember(
            "go ahead with the lagg ja gale",
            "I can't understand what you mean by lagg ja gale. Could you please rephrase.",
            "MASTER_JARVIS",
        )

        value = context.augment("lag ja gale")

        self.assertIn('I recommend "Lag Jaa Gale"', value)
        self.assertNotIn("can't understand", value.lower())

    def test_explicit_command_stays_standalone(self):
        context = ConversationTurns()
        context.remember("hello", "hello", "MASTER_JARVIS")
        self.assertEqual(context.augment("open notepad"), "open notepad")


if __name__ == "__main__":
    unittest.main()
