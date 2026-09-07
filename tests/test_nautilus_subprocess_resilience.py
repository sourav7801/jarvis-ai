from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.trading_intelligence import nautilus_subprocess


ROOT = Path(__file__).resolve().parents[1]


class NautilusSubprocessResilienceTests(unittest.TestCase):
    def test_winerror_5_is_retried_with_runtime_refresh(self) -> None:
        denied = PermissionError(13, "Access is denied")
        denied.winerror = 5
        completed = subprocess.CompletedProcess(
            args=["python", "worker.py"],
            returncode=0,
            stdout='{"success": true}',
            stderr="",
        )

        with (
            patch.object(
                nautilus_subprocess,
                "nautilus_python",
                return_value=Path("C:/Jarvis/.venv-nautilus/Scripts/python.exe"),
            ),
            patch.object(
                nautilus_subprocess,
                "_refresh_runtime_resolution",
            ) as refresh,
            patch.object(
                nautilus_subprocess.time,
                "sleep",
            ),
            patch.object(
                nautilus_subprocess.subprocess,
                "run",
                side_effect=[denied, completed],
            ) as run,
        ):
            result = nautilus_subprocess.run_nautilus_worker(
                Path(__file__),
                ("--version-json",),
                cwd=ROOT,
                timeout=10,
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(run.call_count, 2)
        refresh.assert_called_once_with()

    def test_non_retryable_os_error_is_not_hidden(self) -> None:
        failure = FileNotFoundError(2, "missing executable")

        with (
            patch.object(
                nautilus_subprocess,
                "nautilus_python",
                return_value=Path("C:/missing/python.exe"),
            ),
            patch.object(
                nautilus_subprocess.subprocess,
                "run",
                side_effect=failure,
            ) as run,
        ):
            with self.assertRaises(FileNotFoundError):
                nautilus_subprocess.run_nautilus_worker(
                    Path(__file__),
                    (),
                    cwd=ROOT,
                    timeout=10,
                )

        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
