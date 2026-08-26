from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _python_path(environment: str) -> Path:
    scripts = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    return PROJECT_ROOT / environment / scripts / executable


def _can_import(executable: Path, module: str) -> bool:
    if not executable.exists():
        return False
    try:
        result = subprocess.run(
            [str(executable), "-c", f"import {module}"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


@lru_cache(maxsize=None)
def python_for(module: str, preferred_environment: str) -> Path:
    """Return a project interpreter proven to import ``module``.

    Old Windows Store Python upgrades can leave a virtual environment's
    ``python.exe`` present but unusable.  Existence alone is therefore not a
    sufficient readiness check.
    """

    candidates = (
        _python_path(preferred_environment),
        _python_path(".venv-new"),
        Path(sys.executable),
        _python_path(".venv"),
    )
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if _can_import(candidate, module):
            return candidate
    return _python_path(preferred_environment)


def nautilus_python() -> Path:
    configured = os.getenv("JARVIS_NAUTILUS_PYTHON", "").strip()
    if configured and _can_import(Path(configured), "nautilus_trader"):
        return Path(configured)
    return python_for("nautilus_trader", ".venv-nautilus")


def fyers_python() -> Path:
    configured = os.getenv("JARVIS_FYERS_PYTHON", "").strip()
    if configured and _can_import(Path(configured), "fyers_apiv3"):
        return Path(configured)
    return python_for("fyers_apiv3", ".venv-fyers")


def canonical_python() -> Path:
    return python_for("omni", ".venv")
