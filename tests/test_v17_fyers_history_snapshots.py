from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from agents import fyers_data_adapter as adapter


class _FakeFyersClient:
    def __init__(self, rows):
        self.rows = rows
        self.history_calls = 0

    def history(self, data):
        self.history_calls += 1
        return {
            "s": "ok",
            "code": 200,
            "candles": self.rows,
        }


class V17FyersHistorySnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.cache_dir = root / "history_cache"
        self.state_path = root / "state.json"
        self.provider_lock = root / "provider.lock"
        self.patchers = [
            patch.object(adapter, "_GOVERNOR_DIR", root),
            patch.object(adapter, "_GOVERNOR_STATE", self.state_path),
            patch.object(adapter, "_GOVERNOR_LOCK", self.provider_lock),
            patch.object(adapter, "_HISTORY_CACHE_DIR", self.cache_dir),
            patch.object(adapter, "_MIN_REQUEST_INTERVAL_SECONDS", 0.0),
        ]
        for item in self.patchers:
            item.start()

        base = int(time.time()) - (1200 * 300)
        self.rows = [
            [
                base + index * 300,
                100.0 + index / 1000.0,
                101.0 + index / 1000.0,
                99.0 + index / 1000.0,
                100.5 + index / 1000.0,
                1000 + index,
            ]
            for index in range(1200)
        ]

    def tearDown(self):
        for item in reversed(self.patchers):
            item.stop()
        self.temp.cleanup()

    def test_cache_identity_ignores_requested_bar_count(self):
        small = adapter._history_cache_path("NSE:NIFTY50-INDEX", "5", 220)
        large = adapter._history_cache_path("NSE:NIFTY50-INDEX", "5", 500)
        other_timeframe = adapter._history_cache_path("NSE:NIFTY50-INDEX", "15", 500)
        self.assertEqual(small, large)
        self.assertNotEqual(large, other_timeframe)

    def test_different_bar_counts_reuse_one_provider_snapshot(self):
        client = _FakeFyersClient(self.rows)

        first = adapter.get_intraday_data("NIFTY", timeframe="5m", bars=220, client=client)
        second = adapter.get_intraday_data("NIFTY", timeframe="5m", bars=500, client=client)

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(client.history_calls, 1)
        self.assertEqual(first["bars"], 220)
        self.assertEqual(second["bars"], 500)
        self.assertFalse(first["provider_cache_hit"])
        self.assertTrue(second["provider_cache_hit"])
        self.assertEqual(second["cache_identity"], "provider_symbol+resolution")
        self.assertFalse(second["provider_cache_stale"])
        self.assertFalse(second["provider_rate_limited"])

    def test_rate_limit_cooldown_uses_only_explicit_stale_cache(self):
        client = _FakeFyersClient(self.rows)
        seed = adapter.get_intraday_data("NIFTY", timeframe="5m", bars=500, client=client)
        self.assertTrue(seed["success"])
        self.assertEqual(client.history_calls, 1)

        cache_path = adapter._history_cache_path("NSE:NIFTY50-INDEX", "5", 500)
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        cached["saved_at_epoch"] = time.time() - 120.0
        cache_path.write_text(json.dumps(cached), encoding="utf-8")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(
                {
                    "last_request_epoch": time.time(),
                    "cooldown_until_epoch": time.time() + 30.0,
                    "last_provider_code": 429,
                    "last_provider_state": "RATE_LIMITED",
                }
            ),
            encoding="utf-8",
        )

        degraded = adapter.get_intraday_data(
            "NIFTY",
            timeframe="5m",
            bars=300,
            client=client,
        )

        self.assertTrue(degraded["success"])
        self.assertEqual(client.history_calls, 1, "cooldown must prevent another FYERS HTTP call")
        self.assertEqual(degraded["provider_state"], "RATE_LIMITED")
        self.assertEqual(degraded["data_quality"], "BROKER_HISTORICAL_STALE")
        self.assertTrue(degraded["provider_cache_hit"])
        self.assertTrue(degraded["provider_cache_stale"])
        self.assertTrue(degraded["provider_rate_limited"])
        self.assertTrue(degraded["stale"])
        self.assertTrue(degraded["stream_degraded"])
        self.assertEqual(degraded["bars"], 300)

    def test_quant_evidence_source_hard_blocks_provider_stale_history(self):
        quant = (
            Path(__file__).resolve().parents[1]
            / "workstation"
            / "quant_terminal_v2.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"provider_cache_stale": bool(payload.get("provider_cache_stale"))', quant)
        self.assertIn('payload.get("provider_rate_limited")', quant)
        self.assertIn("if provider_stale:", quant)
        stale_guard = quant.split("if provider_stale:", 1)[1].split(
            "from workstation.terminal_data import validate_candles",
            1,
        )[0]
        self.assertIn('"available": False', stale_guard)
        self.assertIn('"stale": True', stale_guard)


if __name__ == "__main__":
    unittest.main()
