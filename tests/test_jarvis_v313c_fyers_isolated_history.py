import json
import unittest

from types import SimpleNamespace


from workstation.fyers_isolated_history_bridge import (
    FYERS_PYTHON,
    get_intraday_data_isolated,
    isolated_fyers_available,
)


class IsolatedFyersHistoryTests(
    unittest.TestCase
):

    def test_isolated_python_exists(
        self,
    ):

        self.assertTrue(
            isolated_fyers_available()
        )


        self.assertTrue(
            FYERS_PYTHON.exists()
        )


    def test_fake_success_payload(
        self,
    ):

        calls = []


        def runner(
            argv,
            **kwargs,
        ):

            calls.append(
                (
                    argv,
                    kwargs,
                )
            )


            payload = {
                "success":
                    True,

                "source":
                    "FYERS",

                "symbol":
                    "NIFTY",

                "provider_symbol":
                    "NSE:NIFTY50-INDEX",

                "timeframe":
                    "5m",

                "bars":
                    2,

                "data":
                    [
                        {
                            "timestamp":
                                "2026-08-18T09:15:00+05:30",

                            "open":
                                100.0,

                            "high":
                                110.0,

                            "low":
                                99.0,

                            "close":
                                105.0,

                            "volume":
                                1000.0,
                        },

                        {
                            "timestamp":
                                "2026-08-18T09:20:00+05:30",

                            "open":
                                105.0,

                            "high":
                                111.0,

                            "low":
                                103.0,

                            "close":
                                109.0,

                            "volume":
                                900.0,
                        },
                    ],
            }


            return SimpleNamespace(
                returncode=0,
                stdout=(
                    json.dumps(
                        payload
                    )
                    + "\n"
                ),
                stderr="",
            )


        value = get_intraday_data_isolated(
            "NIFTY",
            timeframe="5m",
            bars=20,
            runner=runner,
        )


        self.assertTrue(
            value[
                "success"
            ]
        )


        self.assertEqual(
            value[
                "bridge"
            ],
            "isolated_fyers_history",
        )


        self.assertEqual(
            len(
                value[
                    "data"
                ]
            ),
            2,
        )


        request = json.loads(
            calls[
                0
            ][
                1
            ][
                "input"
            ]
        )


        self.assertEqual(
            request[
                "timeframe"
            ],
            "5m",
        )


        self.assertEqual(
            request[
                "bars"
            ],
            20,
        )


    def test_failure_payload_is_preserved(
        self,
    ):

        def runner(
            argv,
            **kwargs,
        ):

            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "success":
                            False,

                        "source":
                            "FYERS",

                        "message":
                            "FYERS rejected request.",

                        "data":
                            None,
                    }
                ),
                stderr="",
            )


        value = get_intraday_data_isolated(
            "NIFTY",
            runner=runner,
        )


        self.assertFalse(
            value[
                "success"
            ]
        )


        self.assertIn(
            "rejected",
            value[
                "message"
            ],
        )


    def test_worker_has_no_order_surface(
        self,
    ):

        from workstation import (
            fyers_isolated_history_bridge
            as bridge
        )


        forbidden = (
            "place_order",
            "modify_order",
            "cancel_order",
            "place_basket_orders",
        )


        for name in forbidden:

            self.assertFalse(
                hasattr(
                    bridge,
                    name,
                )
            )


    def test_timeout_is_bounded(
        self,
    ):

        import subprocess


        def runner(
            argv,
            **kwargs,
        ):

            raise subprocess.TimeoutExpired(
                cmd=argv,
                timeout=1,
            )


        value = get_intraday_data_isolated(
            "NIFTY",
            timeout=1,
            runner=runner,
        )


        self.assertFalse(
            value[
                "success"
            ]
        )


        self.assertIn(
            "timed out",
            value[
                "message"
            ].lower(),
        )


if __name__ == "__main__":

    unittest.main()
