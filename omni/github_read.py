from __future__ import annotations

from pathlib import Path

import shutil
import subprocess


from omni.git_actions import (
    git_actions,
)


class GitHubRead:

    @staticmethod
    def _run(
        repo,
        args,
    ):

        repo = Path(
            repo
        ).resolve()


        result = subprocess.run(
            [
                "git",
                *args,
            ],

            cwd=
                repo,

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


    def repository_state(
        self,
        repo,
    ):

        repo = Path(
            repo
        ).resolve()


        return {
            "repo":
                str(
                    repo
                ),

            "status":
                git_actions.status(
                    repo
                ),

            "recent_log":
                git_actions.recent_log(
                    repo,
                    10,
                ),

            "branch":
                self._run(
                    repo,

                    [
                        "branch",
                        "--show-current",
                    ],
                ),

            "remotes":
                self._run(
                    repo,

                    [
                        "remote",
                        "-v",
                    ],
                ),

            "remote_write":
                False,
        }


    @staticmethod
    def gh_available():

        return bool(
            shutil.which(
                "gh"
            )
        )


    def gh_repo_view(
        self,
        repo,
    ):

        if not self.gh_available():

            return {
                "success":
                    False,

                "error":
                    "GitHub CLI is not installed.",
            }


        repo = Path(
            repo
        ).resolve()


        result = subprocess.run(
            [
                "gh",
                "repo",
                "view",
                "--json",
                (
                    "nameWithOwner,url,"
                    "defaultBranchRef"
                ),
            ],

            cwd=
                repo,

            capture_output=True,

            text=True,

            shell=False,
        )


        return {
            "success":
                result.returncode
                == 0,

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

            "read_only":
                True,
        }


github_read = (
    GitHubRead()
)
