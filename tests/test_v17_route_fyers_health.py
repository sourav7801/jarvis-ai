import time
import unittest

from agents.fyers_live_stream import FyersLiveStream
from workstation.v17_terminal_http import _route_metadata, _v17_status


class _Service:
    def __init__(self):
        self.last_workspace = None

    def status(self, workspace):
        self.last_workspace = workspace
        return {
            "installed": True,
            "workspace": workspace,
            "verified_auto_option_underlyings": ["BANKNIFTY", "NIFTY", "SENSEX"],
            "decision_source": "LIVE_PROVIDER_DATA_AND_COMPLETED_BARS",
        }


class _Runtime:
    def __init__(self):
        self.v17_autonomy_service = _Service()


class V17RouteAndFyersHealthTests(unittest.TestCase):
    def test_options_route_preserves_requested_identity_and_safe_execution_route(self):
        route = _route_metadata("options")
        self.assertEqual(route["requested_workspace"], "OPTIONS")
        self.assertEqual(route["execution_workspace"], "INTRADAY")
        self.assertFalse(route["fallback_applied"])

        runtime = _Runtime()
        payload = _v17_status(runtime, "OPTIONS")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["workspace"], "OPTIONS")
        self.assertEqual(payload["execution_workspace"], "INTRADAY")
        self.assertEqual(runtime.v17_autonomy_service.last_workspace, "INTRADAY")
        self.assertEqual(payload["route"]["requested_workspace"], "OPTIONS")
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_execution"])
        self.assertTrue(payload["live_orders_locked"])
        self.assertTrue(payload["market_data"]["read_only"])

    def test_unknown_route_fails_to_known_intraday_route_without_unlocking_execution(self):
        route = _route_metadata("made-up-route")
        self.assertEqual(route["requested_workspace"], "INTRADAY")
        self.assertEqual(route["execution_workspace"], "INTRADAY")
        self.assertTrue(route["fallback_applied"])

    def test_stream_status_is_secret_free_read_only_and_can_become_stale(self):
        stream = FyersLiveStream(stale_after_seconds=1.0)
        stream._running = True
        stream._connected = True
        stream._state = "CONNECTED"
        stream._last_connected_at = time.time()
        stream._on_message({"symbol": "NSE:NIFTY50-INDEX", "ltp": 25000.0})

        live = stream.status()
        self.assertEqual(live["state"], "CONNECTED")
        self.assertTrue(live["fresh"])
        self.assertTrue(live["data_only"])
        self.assertTrue(live["read_only"])
        self.assertFalse(live["order_socket_enabled"])
        self.assertFalse(live["live_order_execution"])

        stream._last_message_at = time.time() - 2.0
        stale = stream.status()
        self.assertEqual(stale["state"], "STALE")
        self.assertFalse(stale["fresh"])

        serialized = repr(stale).lower()
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("refresh_token", serialized)

    def test_reconnect_backoff_is_bounded(self):
        stream = FyersLiveStream(
            reconnect_base_seconds=1.0,
            reconnect_max_seconds=8.0,
            reconnect_jitter_seconds=0.0,
        )
        self.assertEqual(stream._retry_delay(1), 1.0)
        self.assertEqual(stream._retry_delay(2), 2.0)
        self.assertEqual(stream._retry_delay(4), 8.0)
        self.assertEqual(stream._retry_delay(20), 8.0)


if __name__ == "__main__":
    unittest.main()
