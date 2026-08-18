import unittest


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.jarvis_workspace_orchestrator import (
    interpret_workspace_command,
)

from workstation.jarvis_os_v3 import (
    safe,
)

from workstation.jarvis_v3_chart_provider import (
    _normalize_frame,
)


class JarvisOSV31Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_sensitive_redaction(
        self,
    ):

        value = safe(
            {
                "token":
                    "SECRET",

                "normal":
                    "visible",
            }
        )


        self.assertEqual(
            value[
                "token"
            ],
            "<REDACTED>",
        )


        self.assertEqual(
            value[
                "normal"
            ],
            "visible",
        )


    def test_trading_workspace_command(
        self,
    ):

        actions = (
            interpret_workspace_command(
                "Open crude oil trading terminal "
                "15 minute chart and analyze it"
            )
        )


        types = [
            (
                item[
                    "type"
                ],
                item.get(
                    "window"
                ),
            )

            for item
            in actions
        ]


        self.assertIn(
            (
                "open_window",
                "chart",
            ),
            types,
        )


        self.assertIn(
            (
                "open_window",
                "quant",
            ),
            types,
        )


        chart_actions = [
            item

            for item in actions

            if item[
                "type"
            ] == "chart_symbol"
        ]


        self.assertEqual(
            chart_actions[
                0
            ][
                "symbol"
            ],
            "CRUDEOIL",
        )


        self.assertEqual(
            chart_actions[
                0
            ][
                "timeframe"
            ],
            "15m",
        )


    def test_compare(
        self,
    ):

        actions = (
            interpret_workspace_command(
                "Compare NIFTY and BANKNIFTY"
            )
        )


        symbols = [
            item[
                "symbol"
            ]

            for item in actions

            if item[
                "type"
            ] == "chart_symbol"
        ]


        self.assertEqual(
            symbols,
            [
                "NIFTY",
                "BANKNIFTY",
            ],
        )


        self.assertTrue(
            any(
                item[
                    "type"
                ] == "chart_layout"

                for item in actions
            )
        )


    def test_window_maximize(
        self,
    ):

        actions = (
            interpret_workspace_command(
                "Make chart full screen"
            )
        )


        self.assertTrue(
            any(
                item[
                    "type"
                ] == "maximize_window"

                and item[
                    "window"
                ] == "chart"

                for item in actions
            )
        )


    def test_synthetic_candle_normalization(
        self,
    ):

        rows = _normalize_frame(
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


        self.assertEqual(
            len(
                rows
            ),
            2,
        )


        self.assertEqual(
            rows[
                1
            ][
                "close"
            ],
            108.0,
        )


    def test_trading_still_blocked(
        self,
    ):

        status = (
            main
            .jarvis_trading_v8_status()
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "automatic_broker_order"
            ]
        )


if __name__ == "__main__":

    unittest.main()
