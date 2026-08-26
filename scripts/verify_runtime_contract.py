"""Verify the declared Windows JARVIS interpreter contracts.

This command is read-only.  It proves that each interpreter starts, imports the
real application boundary assigned to it, and reports the expected Nautilus
version.  Merely finding ``python.exe`` is intentionally insufficient.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimeResult:
    name: str
    executable: str
    required_modules: tuple[str, ...]
    success: bool
    returncode: int | None
    python_version: str | None
    nautilus_version: str | None
    reason: str | None


def verify_runtime(
    name: str,
    executable: Path,
    modules: Sequence[str],
    *,
    expected_nautilus_version: str | None = None,
    timeout: float = 30.0,
) -> RuntimeResult:
    module_list = tuple(str(item) for item in modules)
    if not executable.is_file():
        return RuntimeResult(
            name, str(executable), module_list, False, None, None, None,
            "INTERPRETER_MISSING",
        )
    code = [
        "import importlib, json, platform",
        f"modules={module_list!r}",
        "loaded={name: importlib.import_module(name) for name in modules}",
        "nautilus=loaded.get('nautilus_trader')",
        "print(json.dumps({'python_version': platform.python_version(), "
        "'nautilus_version': getattr(nautilus, '__version__', None)}))",
    ]
    try:
        completed = subprocess.run(
            [str(executable), "-c", ";".join(code)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout)),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return RuntimeResult(
            name, str(executable), module_list, False, None, None, None,
            f"{type(error).__name__}:RUNTIME_START_FAILED",
        )
    payload: dict[str, object] = {}
    if completed.returncode == 0:
        try:
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            payload = {}
    version = str(payload.get("nautilus_version") or "") or None
    version_ok = expected_nautilus_version is None or version == expected_nautilus_version
    success = completed.returncode == 0 and bool(payload.get("python_version")) and version_ok
    reason = None
    if not success:
        if completed.returncode != 0:
            reason = "IMPORT_CONTRACT_FAILED"
        elif not version_ok:
            reason = "NAUTILUS_VERSION_MISMATCH"
        else:
            reason = "INVALID_RUNTIME_RESPONSE"
    return RuntimeResult(
        name=name,
        executable=str(executable),
        required_modules=module_list,
        success=success,
        returncode=completed.returncode,
        python_version=str(payload.get("python_version") or "") or None,
        nautilus_version=version,
        reason=reason,
    )


def verify_declared_runtimes() -> dict[str, object]:
    scripts = "Scripts"
    results = [
        verify_runtime(
            "PRIMARY",
            ROOT / ".venv" / scripts / "python.exe",
            ("omni", "numpy", "pandas", "workstation.jarvis_os_v3"),
        ),
        verify_runtime(
            "FYERS_DATA",
            ROOT / ".venv-fyers" / scripts / "python.exe",
            ("fyers_apiv3", "numpy", "pandas", "agents.fyers_data_adapter"),
        ),
        verify_runtime(
            "NAUTILUS",
            ROOT / ".venv-nautilus" / scripts / "python.exe",
            (
                "nautilus_trader",
                "nautilus_trader.backtest.config",
                "numpy",
                "pandas",
                "workstation.nautilus_core_service",
            ),
            expected_nautilus_version="1.231.0",
        ),
    ]
    return {
        "success": all(item.success for item in results),
        "paper_only": True,
        "live_execution": False,
        "results": [asdict(item) for item in results],
    }


def main() -> int:
    payload = verify_declared_runtimes()
    print(json.dumps(payload, indent=2))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
