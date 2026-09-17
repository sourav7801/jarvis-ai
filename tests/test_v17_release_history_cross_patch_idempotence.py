from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.apply_v17_release_patches import (
    V1706_HISTORY_MARKERS,
    _apply_legacy_history_patches,
    _has_v1706_history_snapshot,
)


class V17ReleaseHistoryCrossPatchIdempotenceTests(unittest.TestCase):
    def test_release_patcher_accepts_v1706_canonical_history_state(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "fyers_data_adapter.py"
            content = "\n".join(V1706_HISTORY_MARKERS) + "\n"
            path.write_text(content, encoding="utf-8")

            self.assertTrue(_has_v1706_history_snapshot(path))
            changed = _apply_legacy_history_patches(path)

            self.assertFalse(changed)
            self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_unknown_history_state_still_fails_closed(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "fyers_data_adapter.py"
            path.write_text("# unrelated history implementation\n", encoding="utf-8")

            self.assertFalse(_has_v1706_history_snapshot(path))
            with self.assertRaises(SystemExit):
                _apply_legacy_history_patches(path)


if __name__ == "__main__":
    unittest.main()
