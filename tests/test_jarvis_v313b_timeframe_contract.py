import unittest


from workstation.jarvis_v3_chart_provider import (
    _invoke_intraday,
)


class TimeframeContractTests(
    unittest.TestCase
):

    def test_timeframe_parameter_gets_jarvis_label(
        self,
    ):

        captured = {}


        def provider(
            symbol,
            market="india",
            timeframe="5m",
            bars=500,
        ):

            captured.update(
                {
                    "symbol":
                        symbol,

                    "market":
                        market,

                    "timeframe":
                        timeframe,

                    "bars":
                        bars,
                }
            )


            return {
                "success":
                    True,
            }


        _invoke_intraday(
            provider,
            symbol="NIFTY",
            timeframe="5m",
            limit=20,
        )


        self.assertEqual(
            captured[
                "timeframe"
            ],
            "5m",
        )


        self.assertEqual(
            captured[
                "bars"
            ],
            20,
        )


    def test_resolution_parameter_gets_provider_value(
        self,
    ):

        captured = {}


        def provider(
            symbol,
            resolution,
            limit=100,
        ):

            captured.update(
                {
                    "symbol":
                        symbol,

                    "resolution":
                        resolution,

                    "limit":
                        limit,
                }
            )


            return []


        _invoke_intraday(
            provider,
            symbol="NIFTY",
            timeframe="5m",
            limit=20,
        )


        self.assertEqual(
            captured[
                "resolution"
            ],
            "5",
        )


    def test_interval_parameter_gets_provider_value(
        self,
    ):

        captured = {}


        def provider(
            ticker,
            interval,
            count=100,
        ):

            captured.update(
                {
                    "ticker":
                        ticker,

                    "interval":
                        interval,

                    "count":
                        count,
                }
            )


            return []


        _invoke_intraday(
            provider,
            symbol="NIFTY",
            timeframe="1h",
            limit=30,
        )


        self.assertEqual(
            captured[
                "interval"
            ],
            "60",
        )


    def test_daily_resolution_mapping(
        self,
    ):

        captured = {}


        def provider(
            symbol,
            resolution,
        ):

            captured[
                "resolution"
            ] = resolution

            return []


        _invoke_intraday(
            provider,
            symbol="NIFTY",
            timeframe="1d",
            limit=10,
        )


        self.assertEqual(
            captured[
                "resolution"
            ],
            "D",
        )


    def test_fyers_style_signature_keeps_15m(
        self,
    ):

        captured = {}


        def get_intraday_data(
            symbol,
            market="india",
            timeframe="5m",
            bars=500,
            *,
            client=None,
        ):

            captured[
                "timeframe"
            ] = timeframe

            captured[
                "symbol"
            ] = symbol

            return {
                "success":
                    False,
            }


        _invoke_intraday(
            get_intraday_data,
            symbol="CRUDEOIL",
            timeframe="15m",
            limit=180,
        )


        self.assertEqual(
            captured[
                "timeframe"
            ],
            "15m",
        )


if __name__ == "__main__":

    unittest.main()
