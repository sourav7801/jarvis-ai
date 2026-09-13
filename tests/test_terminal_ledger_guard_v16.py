from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from workstation import terminal_ledger_guard as guard


class TerminalLedgerGuardV16Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.terminal_db = self.root / "paper_desk.sqlite3"
        self.legacy_account = self.root / "paper_portfolio.json"
        self.legacy_spreads = self.root / "paper_option_spreads.sqlite3"

        # sqlite3.Connection's context manager commits/rolls back but does not
        # close the handle. Close explicitly so Windows can remove the temp DB.
        with closing(sqlite3.connect(self.terminal_db)) as conn:
            conn.execute("CREATE TABLE terminal_workspaces (workspace TEXT PRIMARY KEY)")
            conn.commit()

    def tearDown(self):
        self._tmp.cleanup()

    def _patch_paths(self):
        return patch.multiple(
            guard,
            TERMINAL_DB=self.terminal_db,
            LEGACY_ACCOUNT=self.legacy_account,
            LEGACY_SPREADS=self.legacy_spreads,
        )

    def test_terminal_controls_known_legacy_books_when_canonical_authority_exists(self):
        with self._patch_paths():
            self.assertTrue(guard.terminal_controls(self.legacy_account))
            self.assertTrue(guard.terminal_controls(self.legacy_spreads))
            self.assertFalse(guard.terminal_controls(self.root / "unrelated_book.json"))

    def test_legacy_exposure_reports_sanitized_position_summaries(self):
        self.legacy_account.write_text(
            json.dumps(
                {
                    "positions": [
                        {
                            "symbol": "NSE:NIFTY50-INDEX",
                            "qty": 1,
                            "side": "LONG",
                            "entry_price": 23950.5,
                            "stop_loss": 23800.0,
                            "target": 24250.0,
                            "opened_at": "2026-09-01T09:30:00+05:30",
                            "private_note": "do-not-copy",
                            "metadata": {"secret": "do-not-copy"},
                        },
                        {"symbol": "NSE:SBIN-EQ", "qty": 2},
                    ]
                }
            ),
            encoding="utf-8",
        )
        with closing(sqlite3.connect(self.legacy_spreads)) as conn:
            conn.execute("CREATE TABLE option_spreads (status TEXT NOT NULL)")
            conn.executemany(
                "INSERT INTO option_spreads(status) VALUES (?)",
                [("OPEN",), ("CLOSED",), ("OPEN",)],
            )
            conn.commit()

        desk = SimpleNamespace(db_path=self.terminal_db)
        with self._patch_paths():
            issues = guard.legacy_exposure(desk)

        self.assertEqual(len(issues), 2)
        by_book = {item["book"]: item for item in issues}
        legacy = by_book["Legacy paper account"]
        self.assertEqual(legacy["open_count"], 2)
        self.assertEqual(by_book["Legacy defined-risk spreads"]["open_count"], 2)
        self.assertEqual(legacy["path"], str(self.legacy_account))
        self.assertEqual(by_book["Legacy defined-risk spreads"]["path"], str(self.legacy_spreads))
        self.assertEqual(len(legacy["position_summaries"]), 2)
        self.assertEqual(legacy["position_summaries"][0]["symbol"], "NSE:NIFTY50-INDEX")
        self.assertEqual(legacy["position_summaries"][0]["quantity"], 1)
        self.assertEqual(legacy["position_summaries"][0]["side"], "LONG")
        self.assertEqual(legacy["position_summaries"][0]["entry_price"], 23950.5)
        self.assertEqual(legacy["position_summaries"][0]["stop"], 23800.0)
        self.assertEqual(legacy["position_summaries"][0]["target"], 24250.0)
        serialized = json.dumps(issues)
        self.assertNotIn("private_note", serialized)
        self.assertNotIn("do-not-copy", serialized)
        self.assertNotIn("metadata", serialized)

    def test_noncanonical_desk_does_not_report_legacy_exposure(self):
        self.legacy_account.write_text(json.dumps({"positions": [{"symbol": "NIFTY"}]}), encoding="utf-8")
        desk = SimpleNamespace(db_path=self.root / "isolated_test_book.sqlite3")

        with self._patch_paths():
            self.assertEqual(guard.legacy_exposure(desk), [])


if __name__ == "__main__":
    unittest.main()
