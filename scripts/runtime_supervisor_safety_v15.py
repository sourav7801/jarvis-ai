from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from scripts.jarvis_runtime_supervisor import JarvisRuntimeSupervisor


class SupervisorLeaseV15:
    """OS-held single-supervisor lease.

    The lock file may remain after exit, but the OS lock is released with the
    process. Unknown processes are never terminated to obtain this lease.

    Windows note: another JARVIS process can hold a byte-range lock on byte 0.
    Reading that byte *before* attempting ``msvcrt.locking`` can itself raise
    ``PermissionError``.  Lease contention must therefore be detected by the
    lock attempt, not by reading the sentinel byte first.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.path = self.root / "data" / "reliability" / "runtime" / "supervisor_v15.lock"
        self.handle = None
        self.acquired = False

    def acquire(self) -> bool:
        if self.acquired and self.handle is not None:
            return True

        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = self.path.open("a+b")
        except OSError:
            return False

        try:
            # A one-byte file is required because Windows locks a byte range.
            # Use fstat instead of read(1): fstat remains safe when another
            # process already owns the byte-range lock.
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"1")
                handle.flush()

            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ImportError):
            try:
                handle.close()
            except OSError:
                pass
            return False

        self.handle = handle
        self.acquired = True
        return True

    def release(self) -> None:
        handle = self.handle
        self.handle = None
        if handle is None:
            self.acquired = False
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            handle.close()
        finally:
            self.acquired = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("V15_SUPERVISOR_ALREADY_OWNED")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


class JarvisRuntimeSupervisorV15(JarvisRuntimeSupervisor):
    """Base supervisor with concurrency-safe atomic runtime snapshots."""

    def _persist_snapshot(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        temp_path = None
        try:
            fd, name = tempfile.mkstemp(
                prefix=f"state.{os.getpid()}.",
                suffix=".tmp",
                dir=str(self.state_dir),
                text=True,
            )
            temp_path = Path(name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(data)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            last_error = None
            for attempt in range(4):
                try:
                    os.replace(str(temp_path), str(self.state_path))
                    temp_path = None
                    return
                except OSError as exc:
                    last_error = exc
                    if attempt >= 3:
                        raise
                    time.sleep(0.025 * (attempt + 1))
            if last_error is not None:
                raise last_error
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass


def status() -> dict[str, Any]:
    return {
        "success": True,
        "version": "15.0",
        "service": "JARVIS_RUNTIME_SUPERVISOR_SAFETY_V15",
        "single_supervisor_os_lease": True,
        "unique_atomic_snapshot_tempfiles": True,
        "shared_state_tmp_removed": True,
        "unknown_process_termination": False,
        "paper_only": True,
        "live_execution": False,
    }


__all__ = ["SupervisorLeaseV15", "JarvisRuntimeSupervisorV15", "status"]
