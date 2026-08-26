import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from workstation.multi_timeframe_feature_store import MultiTimeframeFeatureStore


def snapshot(bar: int, timeframe: str = "5m", *, verified: bool = True, stale: bool = False):
    return {
        "success": True, "feature_version": "V1", "symbol": "BTC", "timeframe": timeframe,
        "generated_at": "2026-08-26T08:00:00+00:00", "price": 100.0,
        "data": {
            "provider": "BINANCE_PUBLIC", "provider_symbol": "BTCUSDT",
            "quality": "PUBLIC_LIVE", "verified": verified, "stale": stale,
            "last_time": bar,
        },
        "paper_only": True, "live_execution": False,
    }


class MultiTimeframeFeatureStoreTests(unittest.TestCase):
    def test_records_deduplicates_and_returns_latest_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MultiTimeframeFeatureStore(Path(directory) / "features.sqlite3")
            first = store.record(snapshot(100, "5m"))
            duplicate = store.record(snapshot(100, "5m"))
            store.record(snapshot(200, "15m"))
            self.assertTrue(first["stored"])
            self.assertTrue(duplicate["deduplicated"])
            matrix = store.latest_matrix("btc")
            self.assertEqual(matrix["snapshot_count"], 2)
            self.assertEqual(matrix["timeframes"]["5m"]["price"], 100.0)
            self.assertFalse(matrix["live_execution"])

    def test_unverified_stale_or_missing_provenance_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MultiTimeframeFeatureStore(Path(directory) / "features.sqlite3")
            with self.assertRaises(ValueError):
                store.record(snapshot(100, verified=False))
            with self.assertRaises(ValueError):
                store.record(snapshot(100, stale=True))
            invalid = snapshot(100)
            invalid["data"]["provider"] = None
            with self.assertRaises(ValueError):
                store.record(invalid)

    def test_retention_is_bounded_per_symbol_and_timeframe(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MultiTimeframeFeatureStore(Path(directory) / "features.sqlite3", retention_per_series=10)
            for bar in range(20):
                store.record(snapshot(bar))
            with closing(store._connect()) as connection:
                count = connection.execute("SELECT COUNT(*) FROM feature_snapshots").fetchone()[0]
            self.assertEqual(count, 10)
            self.assertEqual(store.latest("BTC", "5m")["data"]["last_time"], 19)


if __name__ == "__main__":
    unittest.main()
