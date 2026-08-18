import unittest

from workstation.jarvis_os_v3 import (
    normalize_master_command,
)


class MasterBoundaryTests(
    unittest.TestCase
):

    def test_standard_wake_word(self):

        self.assertEqual(
            normalize_master_command(
                "Jarvis, open crude oil trading terminal"
            ),
            "open crude oil trading terminal",
        )


    def test_hey_jarvis(self):

        self.assertEqual(
            normalize_master_command(
                "Hey Jarvis, analyze NIFTY"
            ),
            "analyze NIFTY",
        )


    def test_hi_jarvis(self):

        self.assertEqual(
            normalize_master_command(
                "Hi Jarvis, open Calculator"
            ),
            "open Calculator",
        )


    def test_hello_jarvis(self):

        self.assertEqual(
            normalize_master_command(
                "Hello Jarvis analyze crude oil"
            ),
            "analyze crude oil",
        )


    def test_okay_jarvis(self):

        self.assertEqual(
            normalize_master_command(
                "Okay Jarvis, compare NIFTY and BANKNIFTY"
            ),
            "compare NIFTY and BANKNIFTY",
        )


    def test_do_not_remove_middle_jarvis(self):

        value = (
            "search for JARVIS architecture"
        )

        self.assertEqual(
            normalize_master_command(
                value
            ),
            value,
        )


    def test_empty_wake_word_not_destroyed(self):

        self.assertEqual(
            normalize_master_command(
                "Jarvis"
            ),
            "Jarvis",
        )


    def test_crude_oil_command(self):

        result = (
            normalize_master_command(
                "Jarvis, open crude oil trading terminal "
                "15 minute chart and analyze it."
            )
        )


        self.assertFalse(
            result.lower()
            .startswith(
                "jarvis"
            )
        )


        self.assertIn(
            "crude oil",
            result.lower(),
        )


if __name__ == "__main__":

    unittest.main()
