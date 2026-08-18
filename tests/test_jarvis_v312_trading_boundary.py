import unittest

from workstation.jarvis_os_v3 import (
    normalize_agent_command,
    normalize_master_command,
)


class TradingBoundaryTests(
    unittest.TestCase
):

    def test_master_wake_word_still_removed(
        self,
    ):

        self.assertEqual(
            normalize_master_command(
                "Jarvis, open Calculator"
            ),
            "open Calculator",
        )


    def test_crude_oil_15m(
        self,
    ):

        self.assertEqual(
            normalize_agent_command(
                "Jarvis, open crude oil trading terminal "
                "15 minute chart and analyze it."
            ),
            "CRUDEOIL 15m analyze",
        )


    def test_nifty_5m(
        self,
    ):

        self.assertEqual(
            normalize_agent_command(
                "Jarvis, can you analyse the nifty "
                "5 minute chart and tell me the trade setup"
            ),
            "NIFTY 5m analyze",
        )


    def test_banknifty_15m(
        self,
    ):

        self.assertEqual(
            normalize_agent_command(
                "Analyze BANKNIFTY 15 minute chart"
            ),
            "BANKNIFTY 15m analyze",
        )


    def test_crude_1h(
        self,
    ):

        self.assertEqual(
            normalize_agent_command(
                "Analyze crude oil 1 hour chart"
            ),
            "CRUDEOIL 1h analyze",
        )


    def test_non_trading_command_unchanged(
        self,
    ):

        self.assertEqual(
            normalize_agent_command(
                "Jarvis, open Notepad"
            ),
            "open Notepad",
        )


    def test_jarvis_not_symbol(
        self,
    ):

        value = normalize_agent_command(
            "Jarvis, analyze NIFTY 5 minute chart"
        )


        self.assertFalse(
            value.upper()
            .startswith(
                "JARVIS"
            )
        )


    def test_open_not_symbol(
        self,
    ):

        value = normalize_agent_command(
            "Jarvis, open crude oil trading terminal "
            "15 minute chart and analyze it"
        )


        self.assertFalse(
            value.upper()
            .startswith(
                "OPEN"
            )
        )


if __name__ == "__main__":

    unittest.main()
