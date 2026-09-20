import unittest
from pathlib import Path

from agents.fyers_live_stream import FyersLiveStream

ROOT = Path(__file__).resolve().parents[1]


class V17LiveRecoveryTests(unittest.TestCase):
    def test_transport_error_forces_reconnect_state(self):
        stream = FyersLiveStream()
        stream._running = True
        stream._connected = True
        stream._generation = 3
        stream._state = "CONNECTED"

        stream._on_error("Connection to remote host was lost.", generation=3)

        self.assertFalse(stream._connected)
        self.assertEqual(stream._state, "RECONNECTING")
        self.assertEqual(stream._transport_fault_generation, 3)
        self.assertIn("remote host was lost", stream._last_error)

    def test_stale_generation_error_does_not_poison_current_socket(self):
        stream = FyersLiveStream()
        stream._running = True
        stream._connected = True
        stream._generation = 4
        stream._state = "CONNECTED"

        stream._on_error("old socket error", generation=3)

        self.assertTrue(stream._connected)
        self.assertEqual(stream._state, "CONNECTED")
        self.assertIsNone(stream._transport_fault_generation)

    def test_watchlist_preserves_last_verified_display_on_timeout(self):
        text = (ROOT / "workstation" / "quant_terminal_v2_static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('tile.dataset.lastVerified==="1"', text)
        self.assertIn('" · LAST VERIFIED"', text)
        self.assertIn('const feedState=String(meta.statusLabel', text)
        self.assertIn('meta.stale?"STALE"', text)
        self.assertIn('meta.snapshotKind==="REST_QUOTE_FALLBACK"?"REST"', text)

    def test_v17_root_cache_busts_watchlist_runtime(self):
        text = (ROOT / "workstation" / "v17_terminal_http.py").read_text(encoding="utf-8")
        self.assertIn('/app.js?v=170400', text)


if __name__ == "__main__":
    unittest.main()
