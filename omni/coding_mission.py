from __future__ import annotations

from pathlib import Path


from omni.git_actions import (
    git_actions,
)

from omni.git_worktree_engine import (
    git_worktree_engine,
)


class CodingMission:

    @staticmethod
    def _validate_tests(
        test_args,
    ):

        arguments = tuple(
            str(
                item
            )
            for item
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


        if len(
            arguments
        ) < 2:

            raise PermissionError(
                "Coding test command rejected."
            )


        if (
            arguments[
                0
            ]
            != "-m"
        ):

            raise PermissionError(
                "Only Python module test runners "
                "are allowed."
            )


        if (
            arguments[
                1
            ]
            not in (
                "unittest",
                "pytest",
            )
        ):

            raise PermissionError(
                "Only unittest/pytest are allowed."
            )


        forbidden = (
            "-c",
            "-i",
            "subprocess",
            "powershell",
            "cmd.exe",
            "shell",
        )


        lower = " ".join(
            arguments
        ).lower()


        if any(
            token
            in lower
            for token
            in forbidden
        ):

            raise PermissionError(
                "Unsafe coding test arguments."
            )


        return arguments


    def prepare_create(
        self,
        repo,
        name,
    ):

        binding = (
            git_worktree_engine
            .create_binding(
                repo,
                name,
            )
        )


        return {
            "success":
                True,

            "binding":
                binding,
        }


    def create(
        self,
        repo,
        name,
        approval_id,
    ):

        return (
            git_worktree_engine
            .create(
                repo,
                name,

                approval_id=
                    approval_id,
            )
        )


    def prepare_tests(
        self,
        worktree,
        test_args=None,
    ):

        arguments = (
            self._validate_tests(
                test_args
            )
        )


        binding = (
            git_worktree_engine
            .test_binding(
                worktree,
                arguments,
            )
        )


        return {
            "success":
                True,

            "test_args":
                arguments,

            "binding":
                binding,
        }


    def run_tests(
        self,
        worktree,
        test_args,
        approval_id,
    ):

        arguments = (
            self._validate_tests(
                test_args
            )
        )


        return (
            git_worktree_engine
            .run_tests(
                worktree,

                arguments,

                approval_id=
                    approval_id,
            )
        )


    @staticmethod
    def diff(
        worktree,
    ):

        return git_actions.diff(
            Path(
                worktree
            ).resolve()
        )


    @staticmethod
    def merge(
        *args,
        **kwargs,
    ):

        raise PermissionError(
            "Automatic production merge blocked."
        )


    @staticmethod
    def push(
        *args,
        **kwargs,
    ):

        raise PermissionError(
            "Remote Git push blocked."
        )


coding_mission = (
    CodingMission()
)
