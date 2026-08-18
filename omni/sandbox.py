"""A restrictive subprocess boundary for future coding/research workers."""

from __future__ import annotations

import subprocess
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class SandboxPolicy:
    allowed_executables: frozenset[str]
    allowed_roots: tuple[Path, ...]
    max_timeout_seconds: int = 60
    max_output_chars: int = 100_000

    def __post_init__(self) -> None:
        if self.max_timeout_seconds < 1 or self.max_timeout_seconds > 300:
            raise ValueError("Sandbox timeout must be between 1 and 300 seconds.")
        if self.max_output_chars < 1:
            raise ValueError("Sandbox output limit must be positive.")


@dataclass(frozen=True)
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SubprocessSandbox:
    def __init__(self, policy: SandboxPolicy):
        self.policy = policy

    @staticmethod
    def _inside(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def run(
        self,
        command: Sequence[str],
        cwd: Path | str,
        timeout_seconds: int = 30,
        input_text: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> SandboxResult:
        if not command or not all(isinstance(item, str) for item in command):
            raise ValueError("Sandbox command must be a non-empty string sequence.")

        executable = Path(command[0]).name.lower()
        allowed = {item.lower() for item in self.policy.allowed_executables}
        if executable not in allowed:
            raise PermissionError(f"Executable '{executable}' is not allowed.")

        resolved_cwd = Path(cwd).resolve(strict=True)
        roots = tuple(root.resolve(strict=True) for root in self.policy.allowed_roots)
        if not any(self._inside(resolved_cwd, root) for root in roots):
            raise PermissionError("Sandbox working directory is outside allowed roots.")

        timeout = min(max(int(timeout_seconds), 1), self.policy.max_timeout_seconds)
        child_environment = None
        if environment is not None:
            child_environment = {
                key: value
                for key, value in {
                    "SystemRoot": os.environ.get("SystemRoot", ""),
                    "WINDIR": os.environ.get("WINDIR", ""),
                    "PATH": os.environ.get("PATH", ""),
                    "TEMP": str(resolved_cwd),
                    "TMP": str(resolved_cwd),
                    **environment,
                }.items()
                if value
            }
        try:
            completed = subprocess.run(
                list(command),
                cwd=resolved_cwd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                input=input_text,
                env=child_environment,
            )
            return SandboxResult(
                completed.returncode,
                completed.stdout[: self.policy.max_output_chars],
                completed.stderr[: self.policy.max_output_chars],
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            return SandboxResult(
                -1,
                str(stdout)[: self.policy.max_output_chars],
                str(stderr)[: self.policy.max_output_chars],
                timed_out=True,
            )
