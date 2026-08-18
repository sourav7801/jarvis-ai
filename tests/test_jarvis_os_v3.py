import unittest


import main


from omni.core_integrity import (
    verify_protected_core,
)


from workstation.jarvis_os_v3 import (
    _safe,
    ui_actions,
    market_snapshot,
)


class JarvisOSV3Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_safe_redaction(
        self,
    ):

        value = _safe(
            {
                "access_token":
                    "secret-value",

                "normal":
                    "visible",
            }
        )


        self.assertEqual(
            value[
                "access_token"
            ],
            "<REDACTED>",
        )


        self.assertEqual(
            value[
                "normal"
            ],
            "visible",
        )


    def test_trading_ui_intent(
        self,
    ):

        actions = ui_actions(
            "Open trading terminal "
            "and run strategy"
        )


        windows = {
            item.get(
                "window"
            )

            for item in actions

            if item.get(
                "type"
            )
            == "open_window"
        }


        self.assertIn(
            "legacy",
            windows,
        )


        self.assertIn(
            "quant",
            windows,
        )


    def test_research_layout_intent(
        self,
    ):

        actions = ui_actions(
            "Open research layout"
        )


        self.assertTrue(
            any(
                item.get(
                    "layout"
                )
                == "research"

                for item in actions
            )
        )


    def test_close_all(
        self,
    ):

        actions = ui_actions(
            "close all windows"
        )


        self.assertTrue(
            any(
                item.get(
                    "type"
                )
                == "close_all"

                for item in actions
            )
        )


    def test_market_snapshot_safe(
        self,
    ):

        result = market_snapshot()


        self.assertIn(
            "trading_status",
            result,
        )


    def test_live_execution_still_blocked(
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
