from __future__ import annotations

from pathlib import Path

import hashlib
import re
import subprocess
import sys
import time


from omni.approval_queue import (
    approval_queue,
)


class GitWorktreeEngine:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path(
                    r"C:\JarvisWorktrees"
                )
            )
        )


    @staticmethod
    def _repo(
        repo,
    ):

        repo = Path(
            repo
        ).resolve()


        if not repo.exists():

            raise FileNotFoundError(
                repo
            )


        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "--is-inside-work-tree",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            shell=False,
        )


        if result.returncode:

            raise ValueError(
                "Path is not a Git repository."
            )


        return repo


    @staticmethod
    def _safe_branch(
        name,
    ):

        value = re.sub(
            r"[^A-Za-z0-9._/-]+",
            "-",
            str(
                name
            ),
        ).strip(
            "-/"
        )


        if not value:

            raise ValueError(
                "branch name required"
            )


        if (
            ".."
            in value
            or value.startswith(
                "-"
            )
        ):

            raise ValueError(
                "unsafe branch name"
            )


        return (
            "jarvis/"
            + value[:80]
        )


    def create_binding(
        self,
        repo,
        name,
    ):

        repo = self._repo(
            repo
        )


        branch = self._safe_branch(
            name
        )


        folder_name = (
            branch.replace(
                "/",
                "_"
            )
        )


        destination = (
            self.root
            / folder_name
        ).resolve()


        payload = {
            "repo":
                str(
                    repo
                ),

            "branch":
                branch,

            "worktree":
                str(
                    destination
                ),
        }


        return {
            "action":
                "git.worktree.create",

            "payload":
                payload,

            "display":
                payload,

            "risk":
                "engineering-write",
        }


    def create(
        self,
        repo,
        name,
        *,
        approval_id=None,
    ):

        binding = (
            self.create_binding(
                repo,
                name,
            )
        )


        payload = binding[
            "payload"
        ]


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue
                    .request(
                        binding[
                            "action"
                        ],

                        payload,

                        display=
                            binding[
                                "display"
                            ],

                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,

            binding[
                "action"
            ],

            payload,
        )


        destination = Path(
            payload[
                "worktree"
            ]
        )


        if destination.exists():

            return {
                "success":
                    False,

                "error":
                    "Worktree destination "
                    "already exists.",
            }


        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        result = subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                payload[
                    "branch"
                ],
                str(
                    destination
                ),
                "HEAD",
            ],

            cwd=
                payload[
                    "repo"
                ],

            capture_output=True,

            text=True,

            shell=False,
        )


        return {
            "success":
                result.returncode
                == 0,

            "branch":
                payload[
                    "branch"
                ],

            "worktree":
                str(
                    destination
                ),

            "stdout":
                (
                    result.stdout
                    or ""
                )[-10000:],

            "stderr":
                (
                    result.stderr
                    or ""
                )[-10000:],

            "production_unchanged":
                True,

            "automatic_merge":
                False,

            "automatic_push":
                False,
        }


    def test_binding(
        self,
        worktree,
        test_args,
    ):

        worktree = Path(
            worktree
        ).resolve()


        arguments = tuple(
            str(
                value
            )
            for value
            in (
                test_args
                or (
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-q",
                )
            )
        )


        payload = {
            "worktree":
                str(
                    worktree
                ),

            "arguments":
                arguments,
        }


        return {
            "action":
                "git.worktree.test",

            "payload":
                payload,

            "display": {
                "worktree":
                    str(
                        worktree
                    ),

                "arguments":
                    arguments,
            },

            "risk":
                "local-code-execution",
        }


    def run_tests(
        self,
        worktree,
        test_args=None,
        *,
        approval_id=None,
    ):

        binding = (
            self.test_binding(
                worktree,
                test_args,
            )
        )


        payload = binding[
            "payload"
        ]


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue
                    .request(
                        binding[
                            "action"
                        ],

                        payload,

                        display=
                            binding[
                                "display"
                            ],

                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,

            binding[
                "action"
            ],

            payload,
        )


        worktree = Path(
            payload[
                "worktree"
            ]
        ).resolve()


        result = subprocess.run(
            [
                sys.executable,
                *payload[
                    "arguments"
                ],
            ],

            cwd=
                worktree,

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
                )[-20000:],

            "worktree":
                str(
                    worktree
                ),

            "production_unchanged":
                True,
        }


    @staticmethod
    def merge(
        *args,
        **kwargs,
    ):

        raise PermissionError(
            "Automatic worktree merge "
            "is blocked."
        )


    @staticmethod
    def push(
        *args,
        **kwargs,
    ):

        raise PermissionError(
            "Automatic Git push "
            "is blocked."
        )


git_worktree_engine = (
    GitWorktreeEngine()
)
