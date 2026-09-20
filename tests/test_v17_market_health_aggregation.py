import unittest
from unittest import mock

from workstation import v17_terminal_http as http


class _Service:
    def status(self, workspace):
        return {
            "installed": True,
            "workspace": workspace,
            "verified_auto_option_underlyings": ["NIFTY", "BANKNIFTY", "SENSEX"],
        }


class _Runtime:
    v17_autonomy_service = _Service()


class V17MarketHealthAggregationTests(unittest.TestCase):
    def _status(self, *, stream, crypto):
        with mock.patch.object(http, "_fyers_stream_status", return_value=stream), \
             mock.patch.object(http, "_crypto_lane_status", return_value=crypto), \
             mock.patch.object(http, "load_preferences", return_value={"armed": True}), \
             mock.patch.object(
                 http.cross_market_control_plane,
                 "reconcile",
                 return_value={"armed": True, "lanes": {}, "last_error": None},
             ):
            return http._v17_status(_Runtime(), "INTRADAY")

    def test_fyers_failure_does_not_poison_healthy_crypto(self):
        payload = self._status(
            stream={
                "state": "DISCONNECTED",
                "running": False,
                "connected": False,
                "fresh": False,
            },
            crypto={
                "success": True,
                "running": True,
                "last_rows_summary": [{"symbol": "BTC", "success": True}],
                "mcx_underlying_paper": {
                    "success": True,
                    "running": False,
                    "session_open": False,
                },
            },
        )
        feeds = payload["market_data"]["feeds"]
        self.assertEqual(feeds["FYERS_STREAM"]["state"], "OFFLINE")
        self.assertEqual(feeds["BINANCE_PUBLIC"]["state"], "READY")
        self.assertEqual(feeds["MCX_FUTURES"]["state"], "CLOSED")
        self.assertEqual(payload["market_data"]["state"], "PARTIAL")

    def test_crypto_failure_does_not_poison_healthy_fyers(self):
        payload = self._status(
            stream={
                "state": "CONNECTED",
                "running": True,
                "connected": True,
                "fresh": True,
            },
            crypto={
                "success": True,
                "running": True,
                "last_rows_summary": [],
                "mcx_underlying_paper": {
                    "success": True,
                    "running": True,
                    "session_open": True,
                },
            },
        )
        feeds = payload["market_data"]["feeds"]
        self.assertEqual(feeds["FYERS_STREAM"]["state"], "READY")
        self.assertEqual(feeds["INDIA_INDEX_OPTIONS"]["state"], "READY")
        self.assertEqual(feeds["MCX_FUTURES"]["state"], "READY")
        self.assertEqual(feeds["BINANCE_PUBLIC"]["state"], "DEGRADED")
        self.assertEqual(payload["market_data"]["state"], "PARTIAL")

    def test_market_health_contract_remains_read_only_and_paper_only(self):
        payload = self._status(
            stream={
                "state": "CONNECTED",
                "running": True,
                "connected": True,
                "fresh": True,
            },
            crypto={
                "success": True,
                "running": True,
                "last_rows_summary": [{"symbol": "BTC", "success": True}],
                "mcx_underlying_paper": {
                    "success": True,
                    "running": True,
                    "session_open": True,
                },
            },
        )
        self.assertTrue(payload["market_data"]["read_only"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_execution"])
        self.assertTrue(payload["live_orders_locked"])

    def test_browser_data_session_consumes_aggregated_v17_health(self):
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        app = (
            root / "workstation" / "quant_terminal_v2_static" / "app.js"
        ).read_text(encoding="utf-8")
        self.assertIn("function applyV17MarketHealth(status)", app)
        self.assertIn('window.addEventListener("jarvis:v17-status"', app)
        self.assertIn("market=status?.market_data", app)
        self.assertIn("feeds.BINANCE_PUBLIC?.state", app)
        self.assertIn("feeds.MCX_FUTURES?.state", app)


if __name__ == "__main__":
    unittest.main()
