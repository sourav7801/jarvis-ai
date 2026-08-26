from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni import runtime_paths
from scripts.verify_runtime_contract import verify_runtime


class RuntimeEnvironmentContractTests(unittest.TestCase):
    def test_canonical_path_prefers_declared_primary_environment(self):
        runtime_paths.python_for.cache_clear()
        with patch("omni.runtime_paths._can_import", return_value=True):
            selected = runtime_paths.canonical_python()
        self.assertEqual(selected, runtime_paths.PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
        runtime_paths.python_for.cache_clear()

    def test_nautilus_path_prefers_declared_environment(self):
        runtime_paths.python_for.cache_clear()
        with patch.dict("os.environ", {}, clear=False), patch(
            "omni.runtime_paths._can_import", return_value=True
        ):
            selected = runtime_paths.nautilus_python()
        self.assertEqual(selected, runtime_paths.PROJECT_ROOT / ".venv-nautilus" / "Scripts" / "python.exe")
        runtime_paths.python_for.cache_clear()

    def test_verifier_rejects_existence_only_when_import_contract_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "python.exe"
            executable.touch()
            failed = subprocess.CompletedProcess(
                [str(executable)], 1, "", "ModuleNotFoundError"
            )
            with patch("scripts.verify_runtime_contract.subprocess.run", return_value=failed):
                result = verify_runtime("PRIMARY", executable, ("omni",))
        self.assertFalse(result.success)
        self.assertEqual(result.reason, "IMPORT_CONTRACT_FAILED")

    def test_verifier_requires_exact_nautilus_version(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "python.exe"
            executable.touch()
            completed = subprocess.CompletedProcess(
                [str(executable)], 0,
                json.dumps({"python_version": "3.12.13", "nautilus_version": "0.0.0"}) + "\n",
                "",
            )
            with patch("scripts.verify_runtime_contract.subprocess.run", return_value=completed):
                result = verify_runtime(
                    "NAUTILUS", executable, ("nautilus_trader",),
                    expected_nautilus_version="1.231.0",
                )
        self.assertFalse(result.success)
        self.assertEqual(result.reason, "NAUTILUS_VERSION_MISMATCH")

    def test_declared_nautilus_contract_includes_worker_dependencies(self):
        source = (Path(__file__).parents[1] / "scripts" / "verify_runtime_contract.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"nautilus_trader.backtest.config"', source)
        self.assertIn('"numpy"', source)
        self.assertIn('"pandas"', source)


if __name__ == "__main__":
    unittest.main()
