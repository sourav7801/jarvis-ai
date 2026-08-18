from __future__ import annotations

from pathlib import Path

import subprocess


class GitActions:

    READ_ONLY_COMMANDS = {
        "status",
        "diff",
        "log",
        "branch",
        "show",
        "rev-parse",
    }


    @staticmethod
    def _repo(
        repo,
    ):

        path = Path(
            repo
        ).resolve()


        if not path.exists():

            raise FileNotFoundError(
                path
            )


        return path


    @staticmethod
    def _run(
        repo,
        arguments,
    ):

        result = subprocess.run(
            [
                "git",
                *arguments,
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            shell=False,
        )


        return {
            "success":
                result.returncode
                == 0,

            "returncode":
                result.returncode,

            "stdout":
                (
                    result.stdout
                    or ""
                )[-20000:],

            "stderr":
                (
                    result.stderr
                    or ""
                )[-10000:],
        }


    def read(
        self,
        repo,
        command,
        *arguments,
    ):

        command = str(
            command
        )


        if command not in (
            self.READ_ONLY_COMMANDS
        ):

            raise PermissionError(
                "Git command is not "
                "read-only approved."
            )


        return self._run(
            self._repo(
                repo
            ),

            [
                command,
                *[
                    str(
                        value
                    )
                    for value
                    in arguments
                ],
            ],
        )


    def status(
        self,
        repo,
    ):

        return self.read(
            repo,
            "status",
            "--short",
            "--branch",
        )


    def diff(
        self,
        repo,
    ):

        return self.read(
            repo,
            "diff",
        )


    def recent_log(
        self,
        repo,
        limit=10,
    ):

        limit = max(
            1,
            min(
                int(
                    limit
                ),
                100,
            ),
        )


        return self.read(
            repo,
            "log",

            (
                "--max-count="
                + str(
                    limit
                )
            ),

            "--oneline",
            "--decorate",
        )


    def create_branch(
        self,
        repo,
        branch,
        *,
        approved=False,
    ):

        if not approved:

            raise PermissionError(
                "Creating a Git branch "
                "requires explicit approval."
            )


        branch = str(
            branch
        ).strip()


        if not branch:

            raise ValueError(
                "branch cannot be empty"
            )


        if any(
            value in branch

            for value in (
                "..",
                "~",
                "^",
                ":",
                "\\",
                " ",
            )
        ):

            raise ValueError(
                "Unsafe branch name."
            )


        return self._run(
            self._repo(
                repo
            ),

            [
                "switch",
                "-c",
                branch,
            ],
        )


    def commit(
        self,
        repo,
        message,
        *,
        approved=False,
    ):

        if not approved:

            raise PermissionError(
                "Git commit requires "
                "explicit approval."
            )


        message = str(
            message
        ).strip()


        if not message:

            raise ValueError(
                "commit message required"
            )


        # No git add is performed here.
        # Only already-staged changes can be committed.

        return self._run(
            self._repo(
                repo
            ),

            [
                "commit",
                "-m",
                message[:500],
            ],
        )


    def push(
        self,
        *args,
        **kwargs,
    ):

        raise PermissionError(
            "Remote Git push is blocked "
            "in Action Engine V1."
        )


git_actions = (
    GitActions()
)
