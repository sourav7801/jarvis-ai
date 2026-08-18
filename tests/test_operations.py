import tomllib
import unittest
from pathlib import Path

from scripts.doctor import run_checks


ROOT = Path(__file__).resolve().parents[1]


class OperationsTests(unittest.TestCase):
    def test_doctor_has_no_failed_offline_checks(self):
        checks = run_checks(check_network=False)
        self.assertTrue(checks)
        self.assertFalse([check for check in checks if check.status == "FAIL"])

    def test_packaging_metadata_has_console_entry_points(self):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        self.assertEqual(project["requires-python"], ">=3.11,<3.13")
        self.assertIn("omni-jarvis", project["scripts"])
        self.assertIn("omni-workstation", project["scripts"])
        self.assertIn("omni-doctor", project["scripts"])


if __name__ == "__main__":
    unittest.main()
