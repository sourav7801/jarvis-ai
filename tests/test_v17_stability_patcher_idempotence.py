from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.apply_v17_stability_patches import (
    NEW_REFRESH_ALL,
    OLD_REFRESH_ALL,
    STAGED_WATCHLIST_MARKERS,
    _replace_once,
)


MARKET_SESSION_VARIANT = NEW_REFRESH_ALL.replace(
    "updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale)})",
    "updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale),statusLabel:payload.market_closed?\"CLOSED\":payload.stale?\"STALE\":payload.stream_degraded?\"REST\":\"\"})",
)


class V17StabilityPatcherIdempotenceTests(unittest.TestCase):
    def test_market_session_enriched_watchlist_is_already_staged(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "app.js"
            path.write_text(MARKET_SESSION_VARIANT, encoding="utf-8")

            changed = _replace_once(
                path,
                OLD_REFRESH_ALL,
                NEW_REFRESH_ALL,
                "staged watchlist hydration",
                semantic_markers=STAGED_WATCHLIST_MARKERS,
            )

            self.assertFalse(changed)
            self.assertEqual(path.read_text(encoding="utf-8"), MARKET_SESSION_VARIANT)
            self.assertIn('statusLabel:payload.market_closed?"CLOSED"', MARKET_SESSION_VARIANT)

    def test_unrelated_missing_watchlist_still_fails_closed(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "app.js"
            path.write_text("function unrelated(){}\n", encoding="utf-8")

            with self.assertRaises(SystemExit):
                _replace_once(
                    path,
                    OLD_REFRESH_ALL,
                    NEW_REFRESH_ALL,
                    "staged watchlist hydration",
                    semantic_markers=STAGED_WATCHLIST_MARKERS,
                )


if __name__ == "__main__":
    unittest.main()
