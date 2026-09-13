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

        with sqlite3.connect(self.terminal_db) as conn:
            conn.execute("CREATE TABLE terminal_workspaces (workspace TEXT PRIMARY KEY)")

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

    def test_legacy_exposure_reports_counts_and_paths_without_copying_position_payloads(self):
        self.legacy_account.write_text(
            json.dumps(
                {
                    "positions": [
                        {"symbol": "NSE:NIFTY50-INDEX", "qty": 1, "private_note": "do-not-copy"},
                        {"symbol": "NSE:SBIN-EQ", "qty": 2},
                    ]
                }
            ),
            encoding="utf-8",
        )
        with sqlite3.connect(self.legacy_spreads) as conn:
            conn.execute("CREATE TABLE option_spreads (status TEXT NOT NULL)")
            conn.executemany(
                "INSERT INTO option_spreads(status) VALUES (?)",
                [("OPEN",), ("CLOSED",), ("OPEN",)],
            )

        desk = SimpleNamespace(db_path=self.terminal_db)
        with self._patch_paths():
            issues = guard.legacy_exposure(desk)

        self.assertEqual(len(issues), 2)
        by_book = {item["book"]: item for item in issues}
        self.assertEqual(by_book["Legacy paper account"]["open_count"], 2)
        self.assertEqual(by_book["Legacy defined-risk spreads"]["open_count"], 2)
        self.assertEqual(by_book["Legacy paper account"]["path"], str(self.legacy_account))
        self.assertEqual(by_book["Legacy defined-risk spreads"]["path"], str(self.legacy_spreads))
        self.assertNotIn("positions", by_book["Legacy paper account"])
        self.assertNotIn("private_note", json.dumps(issues))

    def test_noncanonical_desk_does_not_report_legacy_exposure(self):
        self.legacy_account.write_text(json.dumps({"positions": [{"symbol": "NIFTY"}]}), encoding="utf-8")
        desk = SimpleNamespace(db_path=self.root / "isolated_test_book.sqlite3")

        with self._patch_paths():
            self.assertEqual(guard.legacy_exposure(desk), [])


if __name__ == "__main__":
    unittest.main()
