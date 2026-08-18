import inspect
import unittest

from agents.trading_agent import (
    extract_timeframe,
    TradingAgent,
)


class ExactTradingContextTests(
    unittest.TestCase
):

    def test_5m_compact(self):

        self.assertEqual(
            extract_timeframe(
                "NIFTY 5m analyze"
            ),
            "5m",
        )


    def test_15m_compact(self):

        self.assertEqual(
            extract_timeframe(
                "CRUDEOIL 15m analyze"
            ),
            "15m",
        )


    def test_human_5m(self):

        self.assertEqual(
            extract_timeframe(
                "analyze nifty 5 minute chart"
            ),
            "5m",
        )


    def test_human_hour(self):

        self.assertEqual(
            extract_timeframe(
                "analyze nifty 1 hour chart"
            ),
            "1h",
        )


    def test_default_daily(self):

        self.assertEqual(
            extract_timeframe(
                "analyze nifty"
            ),
            "1d",
        )


    def test_trade_not_hardcoded(self):

        source = inspect.getsource(
            TradingAgent.trade
        )

        self.assertIn(
            "extract_timeframe",
            source,
        )

        self.assertNotIn(
            'timeframe="1d"',
            source,
        )


    def test_market_agent_isolated(self):

        import agents.market_data_agent as module

        source = inspect.getsource(
            module
        )

        self.assertIn(
            "get_intraday_data_isolated_frame",
            source,
        )


if __name__ == "__main__":

    unittest.main()
