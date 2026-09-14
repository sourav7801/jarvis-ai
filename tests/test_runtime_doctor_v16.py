from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.doctor import (
    _package_spec_check,
    check_safety_payload,
    inspect_ledger,
    python_supported,
)


class RuntimeDoctorV16Tests(unittest.TestCase):
    def test_python_313_is_supported_but_314_is_not(self):
        self.assertTrue(python_supported((3, 11)))
        self.assertTrue(python_supported((3, 12)))
        self.assertTrue(python_supported((3, 13)))
        self.assertFalse(python_supported((3, 10)))
        self.assertFalse(python_supported((3, 14)))

    def test_package_python_spec_matches_runtime_contract(self):
        check = _package_spec_check()
        self.assertEqual(check.status, "PASS", check.detail)

    def test_missing_ledger_is_warning_and_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "paper_desk.sqlite3"
            check = inspect_ledger(ledger)
            self.assertEqual(check.status, "WARN")
            self.assertFalse(ledger.exists())

    def test_wal_ledger_is_inspected_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "paper_desk.sqlite3"
            connection = sqlite3.connect(ledger)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, value TEXT)")
            connection.execute("INSERT INTO events(value) VALUES ('seed')")
            connection.commit()
            connection.close()

            size_before = ledger.stat().st_size
            check = inspect_ledger(ledger)
            size_after = ledger.stat().st_size

            self.assertEqual(check.status, "PASS", check.detail)
            self.assertEqual(size_before, size_after)
            connection = sqlite3.connect(ledger)
            row_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            connection.close()
            self.assertEqual(row_count, 1)

    def test_safe_workspace_payload_passes(self):
        check = check_safety_payload(
            {
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "live_orders_locked": True,
                "naked_option_selling": False,
            }
        )
        self.assertEqual(check.status, "PASS", check.detail)

    def test_missing_or_unsafe_workspace_lock_fails_closed(self):
        unsafe = check_safety_payload(
            {
                "paper_only": True,
                "live_execution": True,
                "automatic_broker_order": False,
                "live_orders_locked": True,
            }
        )
        self.assertEqual(unsafe.status, "FAIL")
        self.assertIn("live_execution", unsafe.detail)
        self.assertIn("naked_option_selling", unsafe.detail)


if __name__ == "__main__":
    unittest.main()
