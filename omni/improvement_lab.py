from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "archive",
    "data",
    "node_modules",
}


CRITICAL_CALLS = {
    "eval",
    "exec",
    "__import__",
    "os.system",
}


WARNING_IMPORTS = {
    "subprocess",
    "socket",
    "ctypes",
    "winreg",
    "pickle",
    "marshal",
}


def _hash_text(
    text,
):

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


def _call_name(node):

    if isinstance(
        node,
        ast.Name,
    ):
        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):

        parent = _call_name(
            node.value
        )

        if parent:
            return (
                parent
                + "."
                + node.attr
            )

        return node.attr

    return ""


def scan_source(
    source,
):

    critical = set()
    warnings = set()

    try:

        tree = ast.parse(
            source
        )

    except SyntaxError as exc:

        return {
            "syntax_ok": False,

            "critical": (
                "syntax_error:"
                + str(exc),
            ),

            "warnings": (),
        }


    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                root = (
                    alias.name
                    .split(
                        ".",
                        1,
                    )[0]
                )

                if root in WARNING_IMPORTS:

                    warnings.add(
                        "import:"
                        + alias.name
                    )


        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            root = (
                str(
                    node.module
                    or ""
                )
                .split(
                    ".",
                    1,
                )[0]
            )

            if root in WARNING_IMPORTS:

                warnings.add(
                    "import:"
                    + str(
                        node.module
                    )
                )


        elif isinstance(
            node,
            ast.Call,
        ):

            name = _call_name(
                node.func
            )

            if name in CRITICAL_CALLS:

                critical.add(
                    "call:"
                    + name
                )


            if name in {
                "subprocess.run",
                "subprocess.Popen",
                "subprocess.call",
            }:

                for keyword in node.keywords:

                    if (
                        keyword.arg
                        == "shell"
                        and isinstance(
                            keyword.value,
                            ast.Constant,
                        )
                        and keyword.value.value
                        is True
                    ):

                        critical.add(
                            name
                            + ":shell=True"
                        )


    return {
        "syntax_ok": True,

        "critical":
            tuple(
                sorted(
                    critical
                )
            ),

        "warnings":
            tuple(
                sorted(
                    warnings
                )
            ),
    }


class CandidatePatchLab:

    def __init__(
        self,
        project_root,
        workspace_root,
    ):

        self.project_root = (
            Path(
                project_root
            )
            .resolve()
        )

        self.workspace_root = (
            Path(
                workspace_root
            )
            .resolve()
        )


    def _candidate_dir(
        self,
        candidate_id,
    ):

        return (
            self.workspace_root
            / str(
                candidate_id
            )
        )


    def _manifest_path(
        self,
        candidate_id,
    ):

        return (
            self._candidate_dir(
                candidate_id
            )
            / "manifest.json"
        )


    def _load(
        self,
        candidate_id,
    ):

        return json.loads(
            self._manifest_path(
                candidate_id
            ).read_text(
                encoding="utf-8"
            )
        )


    def _save(
        self,
        manifest,
    ):

        folder = (
            self._candidate_dir(
                manifest[
                    "candidate_id"
                ]
            )
        )

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = (
            folder
            / "manifest.json"
        )

        temp = path.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temp.replace(
            path
        )


    def _target(
        self,
        target_file,
    ):

        target = (
            Path(
                target_file
            )
        )

        if not target.is_absolute():

            target = (
                self.project_root
                / target
            )

        target = target.resolve()

        try:

            target.relative_to(
                self.project_root
            )

        except ValueError:

            raise PermissionError(
                "Candidate target must stay "
                "inside the JARVIS project."
            )

        if target.suffix.lower() != ".py":

            raise ValueError(
                "Self-improvement candidate "
                "must target a Python file."
            )

        if not target.exists():

            raise FileNotFoundError(
                target
            )

        return target


    def create_candidate(
        self,
        *,
        capability,
        target_file,
        candidate_source,
        rationale,
    ):

        target = self._target(
            target_file
        )

        baseline_source = (
            target.read_text(
                encoding="utf-8"
            )
        )

        candidate_source = str(
            candidate_source
        )

        candidate_id = (
            "candidate-"
            + uuid.uuid4().hex[:16]
        )

        folder = (
            self._candidate_dir(
                candidate_id
            )
        )

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            folder
            / "baseline.py"
        ).write_text(
            baseline_source,
            encoding="utf-8",
        )

        (
            folder
            / "candidate.py"
        ).write_text(
            candidate_source,
            encoding="utf-8",
        )

        relative = (
            target.relative_to(
                self.project_root
            )
        )

        manifest = {
            "candidate_id":
                candidate_id,

            "capability":
                str(
                    capability
                ),

            "target_file":
                str(
                    relative
                ),

            "rationale":
                str(
                    rationale
                )[:4000],

            "state":
                "candidate",

            "created_at":
                time.time(),

            "baseline_sha256":
                _hash_text(
                    baseline_source
                ),

            "candidate_sha256":
                _hash_text(
                    candidate_source
                ),

            "security":
                None,

            "evaluation":
                None,

            "promotion":
                None,
        }

        self._save(
            manifest
        )

        return manifest


    def security_review(
        self,
        candidate_id,
    ):

        manifest = self._load(
            candidate_id
        )

        folder = (
            self._candidate_dir(
                candidate_id
            )
        )

        baseline = (
            folder
            / "baseline.py"
        ).read_text(
            encoding="utf-8"
        )

        candidate = (
            folder
            / "candidate.py"
        ).read_text(
            encoding="utf-8"
        )

        baseline_scan = (
            scan_source(
                baseline
            )
        )

        candidate_scan = (
            scan_source(
                candidate
            )
        )

        baseline_critical = set(
            baseline_scan[
                "critical"
            ]
        )

        candidate_critical = set(
            candidate_scan[
                "critical"
            ]
        )

        new_critical = tuple(
            sorted(
                candidate_critical
                - baseline_critical
            )
        )

        passed = bool(
            candidate_scan[
                "syntax_ok"
            ]
            and not new_critical
        )

        review = {
            "passed":
                passed,

            "syntax_ok":
                candidate_scan[
                    "syntax_ok"
                ],

            "new_critical":
                new_critical,

            "warnings":
                candidate_scan[
                    "warnings"
                ],
        }

        manifest[
            "security"
        ] = review

        self._save(
            manifest
        )

        return review


    @staticmethod
    def _command(
        cwd,
        args,
    ):

        started = (
            time.perf_counter()
        )

        result = subprocess.run(
            [
                sys.executable,
                *list(args),
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
        )

        duration = (
            time.perf_counter()
            - started
        )

        output = (
            (
                result.stdout
                or ""
            )
            + "\n"
            + (
                result.stderr
                or ""
            )
        )

        return {
            "returncode":
                result.returncode,

            "passed":
                result.returncode
                == 0,

            "duration_seconds":
                round(
                    duration,
                    4,
                ),

            "output_tail":
                output[
                    -5000:
                ],
        }


    def _copy_project(
        self,
    ):

        sandbox = Path(
            tempfile.mkdtemp(
                prefix=
                    "jarvis_candidate_"
            )
        )

        def ignore(
            directory,
            names,
        ):

            return [
                name
                for name in names
                if name in EXCLUDED_DIRS
            ]

        shutil.copytree(
            self.project_root,
            sandbox,
            dirs_exist_ok=True,
            ignore=ignore,
        )

        return sandbox


    def evaluate(
        self,
        candidate_id,
        *,
        test_args=None,
    ):

        manifest = self._load(
            candidate_id
        )

        security = (
            self.security_review(
                candidate_id
            )
        )

        if not security[
            "passed"
        ]:

            manifest = self._load(
                candidate_id
            )

            manifest[
                "state"
            ] = "rejected"

            manifest[
                "evaluation"
            ] = {
                "passed": False,

                "reason":
                    "security_review_failed",
            }

            self._save(
                manifest
            )

            return manifest


        target_relative = Path(
            manifest[
                "target_file"
            ]
        )

        if test_args is None:

            tests = (
                self.project_root
                / "tests"
            )

            if tests.exists():

                test_args = [
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-q",
                ]

            else:

                test_args = [
                    "-m",
                    "py_compile",
                    str(
                        target_relative
                    ),
                ]


        baseline_result = (
            self._command(
                self.project_root,
                test_args,
            )
        )

        sandbox = (
            self._copy_project()
        )

        try:

            sandbox_target = (
                sandbox
                / target_relative
            )

            sandbox_target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            candidate_source = (
                self._candidate_dir(
                    candidate_id
                )
                / "candidate.py"
            ).read_text(
                encoding="utf-8"
            )

            sandbox_target.write_text(
                candidate_source,
                encoding="utf-8",
            )

            candidate_result = (
                self._command(
                    sandbox,
                    test_args,
                )
            )

        finally:

            shutil.rmtree(
                sandbox,
                ignore_errors=True,
            )


        comparison = {
            "baseline_passed":
                baseline_result[
                    "passed"
                ],

            "candidate_passed":
                candidate_result[
                    "passed"
                ],

            "non_regression":
                bool(
                    baseline_result[
                        "passed"
                    ]
                    and candidate_result[
                        "passed"
                    ]
                ),

            "baseline_duration":
                baseline_result[
                    "duration_seconds"
                ],

            "candidate_duration":
                candidate_result[
                    "duration_seconds"
                ],
        }

        passed = bool(
            security[
                "passed"
            ]
            and comparison[
                "non_regression"
            ]
        )

        manifest = self._load(
            candidate_id
        )

        manifest[
            "evaluation"
        ] = {
            "passed":
                passed,

            "test_args":
                list(
                    test_args
                ),

            "baseline":
                baseline_result,

            "candidate":
                candidate_result,

            "comparison":
                comparison,
        }

        manifest[
            "state"
        ] = (
            "evaluated"
            if passed
            else "rejected"
        )

        self._save(
            manifest
        )

        return manifest


    def promote(
        self,
        candidate_id,
        *,
        approved=False,
        post_test_args=None,
    ):

        if not approved:

            raise PermissionError(
                "Production promotion requires "
                "explicit approval."
            )

        manifest = self._load(
            candidate_id
        )

        if (
            manifest[
                "state"
            ]
            != "evaluated"
        ):

            raise RuntimeError(
                "Candidate must pass evaluation "
                "before promotion."
            )

        if not (
            manifest.get(
                "security",
                {}
            ).get(
                "passed",
                False,
            )
        ):

            raise RuntimeError(
                "Security review did not pass."
            )

        evaluation = (
            manifest.get(
                "evaluation"
            )
            or {}
        )

        if not evaluation.get(
            "passed",
            False,
        ):

            raise RuntimeError(
                "Candidate evaluation did not pass."
            )


        target = self._target(
            manifest[
                "target_file"
            ]
        )

        current_source = (
            target.read_text(
                encoding="utf-8"
            )
        )

        current_hash = (
            _hash_text(
                current_source
            )
        )

        if (
            current_hash
            != manifest[
                "baseline_sha256"
            ]
        ):

            raise RuntimeError(
                "Target changed after candidate "
                "creation. Candidate is stale."
            )


        folder = (
            self._candidate_dir(
                candidate_id
            )
        )

        candidate_source = (
            folder
            / "candidate.py"
        ).read_text(
            encoding="utf-8"
        )

        backup_path = (
            folder
            / "pre_promotion_backup.py"
        )

        backup_path.write_text(
            current_source,
            encoding="utf-8",
        )


        temp_target = (
            target.with_suffix(
                target.suffix
                + ".jarvis_candidate"
            )
        )

        temp_target.write_text(
            candidate_source,
            encoding="utf-8",
        )

        temp_target.replace(
            target
        )


        if post_test_args is None:

            post_test_args = (
                evaluation.get(
                    "test_args"
                )
                or [
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-q",
                ]
            )


        post_result = (
            self._command(
                self.project_root,
                post_test_args,
            )
        )


        if not post_result[
            "passed"
        ]:

            restore_temp = (
                target.with_suffix(
                    target.suffix
                    + ".jarvis_rollback"
                )
            )

            restore_temp.write_text(
                current_source,
                encoding="utf-8",
            )

            restore_temp.replace(
                target
            )

            manifest[
                "state"
            ] = "rolled_back"

            manifest[
                "promotion"
            ] = {
                "passed": False,

                "automatic_rollback":
                    True,

                "post_test":
                    post_result,
            }

            self._save(
                manifest
            )

            return manifest


        manifest[
            "state"
        ] = "promoted"

        manifest[
            "promotion"
        ] = {
            "passed": True,

            "automatic_rollback":
                False,

            "post_test":
                post_result,

            "promoted_at":
                time.time(),
        }

        self._save(
            manifest
        )

        return manifest


    def rollback(
        self,
        candidate_id,
    ):

        manifest = self._load(
            candidate_id
        )

        backup_path = (
            self._candidate_dir(
                candidate_id
            )
            / "pre_promotion_backup.py"
        )

        if not backup_path.exists():

            raise FileNotFoundError(
                "No promotion backup exists."
            )

        target = self._target(
            manifest[
                "target_file"
            ]
        )

        restore = (
            target.with_suffix(
                target.suffix
                + ".manual_rollback"
            )
        )

        restore.write_text(
            backup_path.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )

        restore.replace(
            target
        )

        manifest[
            "state"
        ] = "rolled_back"

        manifest[
            "manual_rollback_at"
        ] = time.time()

        self._save(
            manifest
        )

        return manifest


    def get(
        self,
        candidate_id,
    ):

        return self._load(
            candidate_id
        )
