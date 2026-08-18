import unittest


from workstation.jarvis_v3_chart_provider import (
    _normalize_frame,
)


class CandleCaseNormalizationTests(
    unittest.TestCase
):

    def test_fyers_title_case_payload(
        self,
    ):

        rows = [
            {
                "Timestamp":
                    "2026-08-18T13:05:00+05:30",

                "Open":
                    24192.4,

                "High":
                    24200.2,

                "Low":
                    24185.6,

                "Close":
                    24198.75,

                "Volume":
                    2202080,
            },

            {
                "Timestamp":
                    "2026-08-18T13:10:00+05:30",

                "Open":
                    24198.75,

                "High":
                    24203.0,

                "Low":
                    24196.0,

                "Close":
                    24200.5,

                "Volume":
                    1500000,
            },
        ]


        bars = _normalize_frame(
            rows,
            limit=20,
        )


        self.assertEqual(
            len(
                bars
            ),
            2,
        )


        self.assertEqual(
            bars[
                0
            ][
                "open"
            ],
            24192.4,
        )


        self.assertEqual(
            bars[
                1
            ][
                "close"
            ],
            24200.5,
        )


    def test_lowercase_payload_still_works(
        self,
    ):

        rows = [
            {
                "timestamp":
                    "2026-08-18T13:05:00+05:30",

                "open":
                    100,

                "high":
                    110,

                "low":
                    90,

                "close":
                    105,

                "volume":
                    1000,
            }
        ]


        bars = _normalize_frame(
            rows
        )


        self.assertEqual(
            len(
                bars
            ),
            1,
        )


    def test_mixed_case_payload(
        self,
    ):

        rows = [
            {
                "TIMESTAMP":
                    "2026-08-18T13:05:00+05:30",

                "oPeN":
                    100,

                "HIGH":
                    110,

                "Low":
                    90,

                "cLoSe":
                    105,

                "VOLUME":
                    1000,
            }
        ]


        bars = _normalize_frame(
            rows
        )


        self.assertEqual(
            len(
                bars
            ),
            1,
        )


        self.assertEqual(
            bars[
                0
            ][
                "close"
            ],
            105.0,
        )


    def test_abbreviated_fields_still_work(
        self,
    ):

        rows = [
            {
                "ts":
                    1234567890,

                "o":
                    1,

                "h":
                    2,

                "l":
                    0.5,

                "c":
                    1.5,

                "v":
                    50,
            }
        ]


        bars = _normalize_frame(
            rows
        )


        self.assertEqual(
            len(
                bars
            ),
            1,
        )


    def test_high_below_low_rejected(
        self,
    ):

        rows = [
            {
                "Timestamp":
                    "2026-08-18T13:05:00+05:30",

                "Open":
                    100,

                "High":
                    90,

                "Low":
                    110,

                "Close":
                    100,

                "Volume":
                    10,
            }
        ]


        bars = _normalize_frame(
            rows
        )


        self.assertEqual(
            len(
                bars
            ),
            0,
        )


if __name__ == "__main__":

    unittest.main()
