import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import launch_workstation


class LaunchWorkstationTests(unittest.TestCase):
    def test_local_api_token_is_stable_across_launches(self):
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "workstation-token.txt"
            with (
                patch.object(launch_workstation, "TOKEN_FILE", token_file),
                patch.dict(os.environ, {"JARVIS_WORKSTATION_API_TOKEN": ""}),
            ):
                first = launch_workstation.local_api_token()
                second = launch_workstation.local_api_token()

            self.assertGreaterEqual(len(first), 32)
            self.assertEqual(second, first)
            self.assertEqual(token_file.read_text(encoding="utf-8"), first)

    def test_configured_token_takes_precedence_without_writing_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "workstation-token.txt"
            configured = "configured_token_value_1234567890_abcd"
            with (
                patch.object(launch_workstation, "TOKEN_FILE", token_file),
                patch.dict(
                    os.environ,
                    {"JARVIS_WORKSTATION_API_TOKEN": configured},
                ),
            ):
                actual = launch_workstation.local_api_token()

            self.assertEqual(actual, configured)
            self.assertFalse(token_file.exists())


if __name__ == "__main__":
    unittest.main()
