import json
from pathlib import Path
import tempfile
import time
import unittest

from workstation import v17_display_history as display_history


class V1741DisplayHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_dir = display_history.CACHE_DIR
        display_history.CACHE_DIR = Path(self.temp.name)
        display_history._INDEX = {}
        display_history._INDEX_AT = 0.0

    def tearDown(self):
        display_history.CACHE_DIR = self.old_dir
        display_history._INDEX = {}
        display_history._INDEX_AT = 0.0
        self.temp.cleanup()

    @staticmethod
    def _rows(count=12):
        base = 1_789_900_000
        return [
            {
                "Timestamp": base + i * 3600,
                "Open": 100 + i,
                "High": 101 + i,
                "Low": 99 + i,
                "Close": 100.5 + i,
                "Volume": 1000 + i,
            }
            for i in range(count)
        ]

    def test_canonical_snapshot_is_immediate_display_only_history(self):
        provider = "NSE:NIFTY50-INDEX"
        resolution = "60"
        path = display_history._canonical_path(provider, resolution)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "saved_at_epoch": time.time() - 600,
                    "provider_symbol": provider,
                    "resolution": resolution,
                    "rows": self._rows(),
                }
            ),
            encoding="utf-8",
        )

        payload = display_history.load_verified_history_snapshot(
            provider, "1h", 8
        )

        self.assertTrue(payload["success"])
        self.assertTrue(payload["display_only"])
        self.assertFalse(payload["execution_eligible"])
        self.assertTrue(payload["stale"])
        self.assertEqual(payload["bars"], 8)
        self.assertEqual(payload["cache_path_kind"], "CANONICAL_SYMBOL_TIMEFRAME")

    def test_legacy_bar_count_cache_is_discovered(self):
        provider = "NSE:NIFTYBANK-INDEX"
        path = display_history.CACHE_DIR / "legacy-bars-key.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "saved_at_epoch": time.time(),
                    "provider_symbol": provider,
                    "resolution": "60",
                    "bars": 500,
                    "rows": self._rows(),
                }
            ),
            encoding="utf-8",
        )

        payload = display_history.load_verified_history_snapshot(
            provider, "1h", 10
        )

        self.assertTrue(payload["success"])
        self.assertEqual(payload["bars"], 10)
        self.assertEqual(payload["cache_path_kind"], "LEGACY_DISCOVERED")

    def test_too_old_snapshot_is_not_used(self):
        provider = "BSE:SENSEX-INDEX"
        path = display_history._canonical_path(provider, "60")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "saved_at_epoch": time.time() - 10_000,
                    "provider_symbol": provider,
                    "resolution": "60",
                    "rows": self._rows(),
                }
            ),
            encoding="utf-8",
        )

        payload = display_history.load_verified_history_snapshot(
            provider, "1h", 8, max_display_age_seconds=60
        )

        self.assertFalse(payload["success"])
        self.assertEqual(payload["reason"], "DISPLAY_CACHE_TOO_OLD")

    def test_workspace_chart_route_is_display_only_until_manual_refresh(self):
        root = Path(__file__).resolve().parents[1]
        app = (
            root / "workstation" / "quant_terminal_v2_static" / "app.js"
        ).read_text(encoding="utf-8")
        server = (root / "workstation" / "quant_terminal_v2.py").read_text(
            encoding="utf-8"
        )
        router = (
            root
            / "workstation"
            / "quant_terminal_v2_static"
            / "v16_workspace_router.js"
        ).read_text(encoding="utf-8")

        self.assertIn('display:"1"', app)
        self.assertIn('params.set("fresh","1")', app)
        self.assertIn("display_candles_payload(symbol, timeframe, bars)", server)
        self.assertIn("if display and not fresh", server)
        self.assertIn('"execution_eligible": False', (
            root / "workstation" / "v17_display_history.py"
        ).read_text(encoding="utf-8"))

        route = router.split("function route()", 1)[1].split("function boot()", 1)[0]
        entering = route.split("if (entering)", 1)[1].split("setOptionsVisibility", 1)[0]
        self.assertNotIn("syncUnderlyingChartContext()", entering)


if __name__ == "__main__":
    unittest.main()
