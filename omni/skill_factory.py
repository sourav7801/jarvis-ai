from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import shutil
import time


SAFE_IMPORTS = {
    "math",
    "statistics",
    "datetime",
    "json",
    "re",
    "collections",
    "itertools",
    "functools",
    "decimal",
    "fractions",
    "typing",
    "dataclasses",
}


BLOCKED_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "input",
    "open",
}


class SkillFactory:

    def __init__(
        self,
        root,
    ):

        self.root = Path(
            root
        )

        self.candidates = (
            self.root
            / "candidates"
        )

        self.promoted = (
            self.root
            / "promoted"
        )


    @staticmethod
    def normalize_name(
        name,
    ):

        value = re.sub(
            r"[^a-zA-Z0-9_]+",
            "_",
            str(
                name
            ).strip(),
        ).strip(
            "_"
        ).lower()

        if not value:

            raise ValueError(
                "Invalid skill name."
            )

        return value[:80]


    def folder(
        self,
        name,
    ):

        return (
            self.candidates
            / self.normalize_name(
                name
            )
        )


    def source_path(
        self,
        name,
    ):

        return (
            self.folder(
                name
            )
            / "skill.py"
        )


    def manifest_path(
        self,
        name,
    ):

        return (
            self.folder(
                name
            )
            / "manifest.json"
        )


    def create_candidate(
        self,
        name,
        *,
        purpose,
        source,
    ):

        name = (
            self.normalize_name(
                name
            )
        )

        self.folder(
            name
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

        self.source_path(
            name
        ).write_text(
            str(source),
            encoding="utf-8",
        )

        manifest = {
            "name": name,

            "purpose":
                str(purpose),

            "state":
                "candidate",

            "candidate_path":
                str(
                    self.source_path(
                        name
                    )
                ),

            "promoted_path":
                None,

            "validation_errors":
                [],

            "created_at":
                time.time(),
        }

        self._write_manifest(
            name,
            manifest,
        )

        return manifest


    def validate(
        self,
        name,
    ):

        name = (
            self.normalize_name(
                name
            )
        )

        source = (
            self.source_path(
                name
            )
            .read_text(
                encoding="utf-8"
            )
        )

        errors = []

        try:

            tree = ast.parse(
                source
            )

        except SyntaxError as exc:

            errors.append(
                "syntax: "
                + str(exc)
            )

            return (
                self._finish(
                    name,
                    errors,
                )
            )

        has_run = False


        for node in ast.walk(
            tree
        ):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):

                if node.name == "run":
                    has_run = True


            elif isinstance(
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

                    if (
                        root
                        not in SAFE_IMPORTS
                    ):

                        errors.append(
                            "blocked import: "
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

                if (
                    root
                    and root
                    not in SAFE_IMPORTS
                ):

                    errors.append(
                        "blocked import: "
                        + str(
                            node.module
                        )
                    )


            elif isinstance(
                node,
                ast.Call,
            ):

                if isinstance(
                    node.func,
                    ast.Name,
                ):

                    if (
                        node.func.id
                        in BLOCKED_CALLS
                    ):

                        errors.append(
                            "blocked call: "
                            + node.func.id
                        )


        if not has_run:

            errors.append(
                "skill must define run()"
            )


        try:

            compile(
                source,
                str(
                    self.source_path(
                        name
                    )
                ),
                "exec",
            )

        except Exception as exc:

            errors.append(
                "compile: "
                + str(exc)
            )


        return self._finish(
            name,
            errors,
        )


    def _finish(
        self,
        name,
        errors,
    ):

        manifest = (
            self.load_manifest(
                name
            )
        )

        manifest[
            "state"
        ] = (
            "rejected"
            if errors
            else "validated"
        )

        manifest[
            "validation_errors"
        ] = list(
            errors
        )

        self._write_manifest(
            name,
            manifest,
        )

        return manifest


    def promote(
        self,
        name,
        *,
        approved=False,
    ):

        if not approved:

            raise PermissionError(
                "Skill promotion requires "
                "explicit approval."
            )

        name = (
            self.normalize_name(
                name
            )
        )

        manifest = (
            self.load_manifest(
                name
            )
        )

        if (
            manifest[
                "state"
            ]
            != "validated"
        ):

            raise RuntimeError(
                "Only validated skills "
                "may be promoted."
            )

        destination = (
            self.promoted
            / f"{name}.py"
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            self.source_path(
                name
            ),
            destination,
        )

        manifest[
            "state"
        ] = "promoted"

        manifest[
            "promoted_path"
        ] = str(
            destination
        )

        self._write_manifest(
            name,
            manifest,
        )

        return manifest


    def load_manifest(
        self,
        name,
    ):

        return json.loads(
            self.manifest_path(
                name
            ).read_text(
                encoding="utf-8"
            )
        )


    def _write_manifest(
        self,
        name,
        manifest,
    ):

        path = (
            self.manifest_path(
                name
            )
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
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
