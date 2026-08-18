import unittest

import pandas as pd


from workstation.jarvis_v3_chart_provider import (
    _normalize_frame,
    _provider_error,
    _provider_payload,
)


class JarvisChartBridgeTests(
    unittest.TestCase
):

    def test_fyers_success_dataframe_is_unwrapped(
        self,
    ):

        frame = pd.DataFrame(
            [
                {
                    "timestamp":
                        "2026-08-18T09:15:00+05:30",

                    "open":
                        100,

                    "high":
                        110,

                    "low":
                        95,

                    "close":
                        105,

                    "volume":
                        1000,
                },

                {
                    "timestamp":
                        "2026-08-18T09:20:00+05:30",

                    "open":
                        105,

                    "high":
                        112,

                    "low":
                        101,

                    "close":
                        108,

                    "volume":
                        900,
                },
            ]
        )


        raw = {
            "success":
                True,

            "source":
                "FYERS",

            "data":
                frame,
        }


        payload = _provider_payload(
            raw
        )


        self.assertIs(
            payload,
            frame,
        )


        bars = _normalize_frame(
            payload,
            limit=10,
        )


        self.assertEqual(
            len(
                bars
            ),
            2,
        )


        self.assertEqual(
            bars[
                -1
            ][
                "close"
            ],
            108.0,
        )


    def test_failure_is_not_treated_as_candles(
        self,
    ):

        raw = {
            "success":
                False,

            "message":
                "FYERS returned no candles.",

            "data":
                None,
        }


        self.assertIsNone(
            _provider_payload(
                raw
            )
        )


        self.assertEqual(
            _provider_error(
                raw
            ),
            "FYERS returned no candles.",
        )


    def test_plain_dataframe_is_preserved(
        self,
    ):

        frame = pd.DataFrame(
            [
                {
                    "timestamp":
                        "2026-08-18",

                    "open":
                        1,

                    "high":
                        2,

                    "low":
                        0.5,

                    "close":
                        1.5,
                }
            ]
        )


        self.assertIs(
            _provider_payload(
                frame
            ),
            frame,
        )


    def test_list_payload_is_preserved(
        self,
    ):

        rows = [
            [
                1,
                100,
                110,
                90,
                105,
                1000,
            ]
        ]


        self.assertIs(
            _provider_payload(
                rows
            ),
            rows,
        )


if __name__ == "__main__":

    unittest.main()
