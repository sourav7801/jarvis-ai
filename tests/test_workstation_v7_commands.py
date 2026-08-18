import unittest

from workstation.jarvis_trading_workstation_v7 import app


class WorkstationV7CommandTests(unittest.TestCase):
    def test_singular_find_the_trade_routes_to_quant_lab(self):
        result = app.local_agent("find the trade")
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "open_quant")
        self.assertEqual(result["symbol"], "BANKNIFTY")

    def test_news_command_extracts_subject(self):
        result = app.local_agent("hi top 10 news crude oil")
        self.assertEqual(result["action"], "open_news")
        self.assertEqual(result["query"], "crude oil")
        self.assertEqual(result["limit"], 10)

    def test_generic_news_command_uses_market_default(self):
        result = app.local_agent("what news")
        self.assertEqual(result["query"], "India markets NIFTY Sensex")

    def test_tell_me_news_requests_spoken_briefing(self):
        result = app.local_agent("Jarvis tell me the news")
        self.assertTrue(result["auto_brief"])
        self.assertEqual(result["query"], "India markets NIFTY Sensex")

    def test_typed_wake_word_is_not_sent_to_news_provider(self):
        result = app.local_agent("Jarvis tell me the top 3 crude oil news")
        self.assertEqual(result["query"], "crude oil")

    def test_related_to_noise_is_removed_from_news_query(self):
        result = app.local_agent("top news today related to crude oil")
        self.assertEqual(result["query"], "crude oil")
        self.assertEqual(result["timespan"], "1d")

    def test_current_commodity_question_never_falls_through_to_chat(self):
        result = app.local_agent(
            "can you check crude oil US future how it is behaving"
        )
        self.assertEqual(result["action"], "open_quant")
        self.assertEqual(result["symbol"], "CRUDE OIL")
        self.assertIn("current FYERS MCX contract", result["speech"])

    def test_current_index_question_uses_broker_quant_lab(self):
        result = app.local_agent("check how BANKNIFTY is behaving")
        self.assertEqual(result["action"], "open_quant")
        self.assertEqual(result["symbol"], "BANKNIFTY")

    def test_index_chart_uses_fyers_alias(self):
        result = app.chart_request("open BANKNIFTY for 3 months on 5 minute chart")
        self.assertEqual(result["symbol"], "BANKNIFTY")
        self.assertEqual(result["interval"], "5")
        self.assertEqual(result["range"], "3M")
        self.assertTrue(result["native_supported"])

    def test_commodity_alias_does_not_replace_chart_with_blank_panel(self):
        before = list(app.STATE["charts"])
        result = app.local_agent("open crude oil chart")
        self.assertEqual(result["action"], "chart_unavailable")
        self.assertEqual(app.STATE["charts"], before)

    def test_conversation_histories_are_separate(self):
        original = {name: list(messages) for name, messages in app.STATE["conversations"].items()}
        try:
            app.add_message("user", "master message", "master")
            app.add_message("user", "chart message", "charts")
            self.assertEqual(app.conversation_messages("master")[-1]["text"], "master message")
            self.assertEqual(app.conversation_messages("charts")[-1]["text"], "chart message")
        finally:
            for name, messages in original.items():
                app.STATE["conversations"][name][:] = messages

    def test_paper_conversation_is_separate(self):
        self.assertIn("paper", app.CONVERSATION_CONTEXTS)
        self.assertIsNot(app.conversation_messages("paper"), app.conversation_messages("quant"))


if __name__ == "__main__":
    unittest.main()
