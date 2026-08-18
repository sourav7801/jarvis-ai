import unittest
from unittest.mock import patch


import workstation.jarvis_v3_chart_provider as chart


class McxContractRoutingTests(
    unittest.TestCase
):

    def test_index_mapping_unchanged(
        self,
    ):

        self.assertEqual(
            chart.resolved_history_symbol(
                "NIFTY"
            ),
            "NSE:NIFTY50-INDEX",
        )


    def test_crude_uses_canonical_resolver(
        self,
    ):

        fake = {
            "provider_symbol":
                "MCX:CRUDEOILM26AUGFUT"
        }


        with patch(
            "workstation.paper_market_data."
            "UnifiedPaperMarketData.provider_symbol",
            return_value=fake,
        ):

            value = (
                chart.resolved_history_symbol(
                    "CRUDEOIL"
                )
            )


        self.assertEqual(
            value,
            "MCX:CRUDEOILM26AUGFUT",
        )


    def test_gold_uses_canonical_resolver(
        self,
    ):

        fake = {
            "provider_symbol":
                "MCX:GOLDM26SEPFUT"
        }


        with patch(
            "workstation.paper_market_data."
            "UnifiedPaperMarketData.provider_symbol",
            return_value=fake,
        ):

            value = (
                chart.resolved_history_symbol(
                    "GOLD"
                )
            )


        self.assertEqual(
            value,
            "MCX:GOLDM26SEPFUT",
        )


    def test_generic_commodity_contract_is_rejected(
        self,
    ):

        fake = {
            "provider_symbol":
                "MCX:CRUDEOIL"
        }


        with patch(
            "workstation.paper_market_data."
            "UnifiedPaperMarketData.provider_symbol",
            return_value=fake,
        ):

            with self.assertRaises(
                RuntimeError
            ):

                chart.resolved_history_symbol(
                    "CRUDEOIL"
                )


    def test_invoke_intraday_receives_exact_contract(
        self,
    ):

        captured = {}


        def provider(
            symbol,
            timeframe="15m",
            bars=20,
        ):

            captured[
                "symbol"
            ] = symbol

            captured[
                "timeframe"
            ] = timeframe

            return {
                "success":
                    False,
            }


        fake = {
            "provider_symbol":
                "MCX:CRUDEOILM26AUGFUT"
        }


        with patch(
            "workstation.paper_market_data."
            "UnifiedPaperMarketData.provider_symbol",
            return_value=fake,
        ):

            chart._invoke_intraday(
                provider,
                symbol="CRUDEOIL",
                timeframe="15m",
                limit=20,
            )


        self.assertEqual(
            captured[
                "symbol"
            ],
            "MCX:CRUDEOILM26AUGFUT",
        )


        self.assertEqual(
            captured[
                "timeframe"
            ],
            "15m",
        )


if __name__ == "__main__":

    unittest.main()
