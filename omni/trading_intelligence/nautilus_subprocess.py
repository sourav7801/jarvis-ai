from __future__ import annotations

import errno
import subprocess
import time
from pathlib import Path
from typing import Iterable

from omni.runtime_paths import nautilus_python, python_for


_RETRY_DELAYS = (0.15, 0.45, 0.9)
_RETRYABLE_WINERRORS = {5, 32}


def _refresh_runtime_resolution() -> None:
    """Forget cached interpreter selection before a retry.

    Windows can transiently deny process creation for a venv launcher while an
    antivirus/indexer is inspecting it.  The old Nautilus bridges cached the
    chosen executable at module import, so one stale or temporarily blocked
    launcher could poison every later research call in the process.  Clearing
    only the interpreter-selection cache lets the normal runtime-path policy
    re-probe .venv-nautilus and any safe project fallback.
    """

    cache_clear = getattr(python_for, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def _retryable_launch_error(exc: OSError) -> bool:
    winerror = getattr(exc, "winerror", None)
    if winerror in _RETRYABLE_WINERRORS:
        return True
    return getattr(exc, "errno", None) in {errno.EACCES, errno.EBUSY}


def run_nautilus_worker(
    worker: Path,
    args: Iterable[str] = (),
    *,
    cwd: Path,
    timeout: float,
    attempts: int = 4,
) -> subprocess.CompletedProcess[str]:
    """Run a Nautilus research worker with bounded Windows launch recovery.

    This helper does not weaken JARVIS safety boundaries: it only launches the
    existing local research/backtest worker.  It retries process-creation
    failures such as WinError 5/32, refreshes the interpreter selection between
    attempts, and never falls through to broker or live-execution surfaces.
    """

    worker_path = Path(worker)
    if not worker_path.exists():
        raise RuntimeError(f"Nautilus worker is missing: {worker_path}")

    bounded_attempts = max(1, min(int(attempts), 4))
    last_error: OSError | None = None

    for attempt in range(bounded_attempts):
        if attempt:
            _refresh_runtime_resolution()

        executable = nautilus_python()
        command = [str(executable), str(worker_path), *(str(item) for item in args)]

        try:
            return subprocess.run(
                command,
                cwd=Path(cwd),
                capture_output=True,
                text=True,
                timeout=float(timeout),
                check=False,
            )
        except OSError as exc:
            if not _retryable_launch_error(exc):
                raise
            last_error = exc
            if attempt + 1 >= bounded_attempts:
                break
            delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
            time.sleep(delay)

    detail = "unknown launch failure" if last_error is None else (
        f"{type(last_error).__name__}: {last_error}"
    )
    raise RuntimeError(
        "Nautilus research worker could not be launched after bounded retries: "
        + detail
    )


__all__ = ["run_nautilus_worker"]
