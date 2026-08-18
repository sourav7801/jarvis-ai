from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import hashlib
import json
import time


@dataclass(frozen=True)
class CoreIntegrityResult:

    ok: bool

    checked: int

    changed: tuple[str, ...]

    missing: tuple[str, ...]


def _sha(path):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _root():

    return (
        Path(__file__)
        .resolve()
        .parents[1]
    )


def _manifest_path():

    return (
        _root()
        / "config"
        / "protected_core_manifest.json"
    )


def verify_protected_core():

    root = _root()

    manifest = json.loads(
        _manifest_path().read_text(
            encoding="utf-8"
        )
    )

    changed = []
    missing = []

    files = manifest.get(
        "files",
        {},
    )

    for relative, expected in files.items():

        path = (
            root
            / relative
        )

        if not path.exists():

            missing.append(
                relative
            )

            continue

        actual = _sha(
            path
        )

        if actual != expected:

            changed.append(
                relative
            )


    return CoreIntegrityResult(
        ok=(
            not changed
            and not missing
        ),

        checked=
            len(files),

        changed=
            tuple(changed),

        missing=
            tuple(missing),
    )


def rebaseline_protected_core(
    *,
    approved=False,
    reason="",
):

    if not approved:

        raise PermissionError(
            "Protected-core rebaseline requires "
            "explicit approval."
        )


    reason = str(
        reason
    ).strip()

    if not reason:

        raise ValueError(
            "A rebaseline reason is required."
        )


    root = _root()

    path = _manifest_path()

    manifest = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    files = manifest.get(
        "files",
        {},
    )


    new_hashes = {}

    for relative in files:

        target = (
            root
            / relative
        )

        if not target.exists():

            raise FileNotFoundError(
                target
            )

        new_hashes[
            relative
        ] = _sha(
            target
        )


    manifest[
        "files"
    ] = new_hashes

    manifest[
        "updated_at"
    ] = time.time()

    manifest[
        "last_rebaseline_reason"
    ] = reason


    temp = path.with_suffix(
        ".tmp"
    )

    temp.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temp.replace(
        path
    )


    audit = (
        root
        / "data"
        / "audit"
        / "protected_core.jsonl"
    )

    audit.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with audit.open(
        "a",
        encoding="utf-8",
    ) as handle:

        handle.write(
            json.dumps(
                {
                    "event":
                        "protected_core_rebaseline",

                    "reason":
                        reason,

                    "timestamp":
                        time.time(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )


    return verify_protected_core()
