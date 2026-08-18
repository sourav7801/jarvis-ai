from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PROTECTED_CORE = {
    "omni/model_router.py",
    "omni/model_provider.py",
    "omni/agent_registry.py",
    "omni/collaboration_runtime.py",
    "omni/runtime.py",
    "omni/hybrid_memory.py",
}

DEFAULT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


class DevAgentError(RuntimeError):
    pass


def run(cmd, check=True, capture=False):
    print(">", " ".join(str(x) for x in cmd))

    return subprocess.run(
        [str(x) for x in cmd],
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=check,
    )


def git(*args, capture=False, check=True):
    return run(
        ["git", *args],
        check=check,
        capture=capture,
    )


def git_text(*args):
    return git(
        *args,
        capture=True,
    ).stdout.strip()


def python_exe():
    if DEFAULT_PYTHON.exists():
        return str(DEFAULT_PYTHON)

    return sys.executable


def assert_repository():
    root = git_text(
        "rev-parse",
        "--show-toplevel",
    )

    expected = str(ROOT).replace("\\", "/").lower()
    actual = root.replace("\\", "/").lower()

    if expected != actual:
        raise DevAgentError(
            f"Repository mismatch. Expected {ROOT}, got {root}"
        )


def current_branch():
    branch = git_text(
        "branch",
        "--show-current",
    )

    return branch or "DETACHED"


def assert_clean():
    status = git_text(
        "status",
        "--porcelain",
    )

    if status:
        raise DevAgentError(
            "Working tree is not clean. "
            "Commit or stash existing changes first."
        )


def changed_files(base="HEAD"):
    output = git_text(
        "diff",
        "--name-only",
        base,
    )

    files = []

    for line in output.splitlines():
        value = line.strip().replace("\\", "/")

        if value:
            files.append(value)

    return files


def protected_changes(files):
    return sorted(
        set(files) & PROTECTED_CORE
    )


def compile_changed_python(files):
    python_files = []

    for item in files:
        if not item.endswith(".py"):
            continue

        path = ROOT / item

        if path.exists():
            python_files.append(str(path))

    if not python_files:
        print("Compile check: no changed Python files.")
        return

    run(
        [
            python_exe(),
            "-m",
            "py_compile",
            *python_files,
        ]
    )

    print(
        f"Compile check: PASS "
        f"({len(python_files)} Python files)"
    )


def run_tests(targets, full):
    py = python_exe()

    for target in targets:
        run(
            [
                py,
                "-m",
                "unittest",
                target,
            ]
        )

    if full:
        run(
            [
                py,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ]
        )

        print("Full regression: PASS")


def create_safety_branch(label):
    stamp = dt.datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    safe = "".join(
        char
        if char.isalnum() or char in "-_"
        else "-"
        for char in label
    )

    safe = safe.strip("-") or "change"

    branch = (
        f"jarvis-dev/"
        f"{stamp}-"
        f"{safe[:40]}"
    )

    git(
        "switch",
        "-c",
        branch,
    )

    return branch



def untracked_files():
    output = git_text(
        "ls-files",
        "--others",
        "--exclude-standard",
    )

    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def cleanup_untracked_paths(paths, root=ROOT):
    root = Path(root).resolve()
    removed = []

    for relative in sorted(set(paths), reverse=True):
        candidate = (root / relative).resolve()

        try:
            candidate.relative_to(root)
        except ValueError:
            continue

        if candidate.is_file() or candidate.is_symlink():
            candidate.unlink(missing_ok=True)
            removed.append(relative)

        parent = candidate.parent
        while parent != root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    return removed


def rollback(original_branch, original_head, original_untracked=None):
    print("")
    print("======================================")
    print("ROLLBACK")
    print("======================================")

    git(
        "reset",
        "--hard",
        original_head,
        check=False,
    )

    if original_branch != "DETACHED":
        git(
            "switch",
            original_branch,
            check=False,
        )

    before = set(original_untracked or ())
    created = untracked_files() - before
    removed = cleanup_untracked_paths(created)

    if removed:
        print(
            "Removed patch-created untracked files:",
            ", ".join(sorted(removed)),
        )

    residual = git_text(
        "status",
        "--porcelain",
    )

    if residual:
        print(
            "WARNING: rollback left repository changes:",
            residual,
        )
    else:
        print("Rollback verification: CLEAN")

    print("Previous JARVIS state restored.")


def cmd_status(args):
    assert_repository()

    print("")
    print("======================================")
    print("JARVIS DEV AGENT STATUS")
    print("======================================")

    print(
        "Repository:",
        ROOT,
    )

    print(
        "Branch:",
        current_branch(),
    )

    print(
        "HEAD:",
        git_text(
            "rev-parse",
            "--short",
            "HEAD",
        ),
    )

    print(
        "Python:",
        python_exe(),
    )

    status = git_text(
        "status",
        "--short",
    )

    print("")
    print("Working tree:")

    if status:
        print(status)

    if not status:
        print("clean")

    return 0


def cmd_verify(args):
    assert_repository()

    files = changed_files(
        args.base
    )

    blocked = protected_changes(
        files
    )

    if blocked and not args.allow_protected_core:
        raise DevAgentError(
            "Protected Core modification blocked: "
            + ", ".join(blocked)
        )

    compile_changed_python(
        files
    )

    run_tests(
        args.test,
        args.full,
    )

    print("")
    print("======================================")
    print("VERIFICATION PASS")
    print("======================================")

    return 0


def cmd_apply(args):
    assert_repository()
    assert_clean()

    patch = Path(
        args.patch
    ).expanduser().resolve()

    if not patch.exists():
        raise DevAgentError(
            f"Patch not found: {patch}"
        )

    original_branch = current_branch()
    original_untracked = untracked_files()

    original_head = git_text(
        "rev-parse",
        "HEAD",
    )

    branch = create_safety_branch(
        args.message or patch.stem
    )

    print(
        "Safety branch:",
        branch,
    )

    try:

        run(
            [
                "git",
                "apply",
                "--check",
                "--whitespace=nowarn",
                str(patch),
            ]
        )

        run(
            [
                "git",
                "apply",
                "--whitespace=nowarn",
                str(patch),
            ]
        )

        files = changed_files(
            "HEAD"
        )

        if not files:
            raise DevAgentError(
                "Patch produced no changes."
            )

        blocked = protected_changes(
            files
        )

        if blocked and not args.allow_protected_core:
            raise DevAgentError(
                "Protected Core modification blocked: "
                + ", ".join(blocked)
            )

        print("")
        print("Changed files:")

        for item in files:
            print(
                " -",
                item,
            )

        compile_changed_python(
            files
        )

        run_tests(
            args.test,
            args.full,
        )

        git(
            "add",
            "--all",
        )

        staged = git_text(
            "diff",
            "--cached",
            "--name-only",
        )

        if not staged:
            raise DevAgentError(
                "Nothing staged after verification."
            )

        message = (
            args.message
            or
            f"JARVIS dev update: {patch.stem}"
        )

        git(
            "commit",
            "-m",
            message,
        )

        if args.push:
            git(
                "push",
                "-u",
                "origin",
                branch,
            )

        print("")
        print("======================================")
        print("JARVIS DEV AGENT SUCCESS")
        print("======================================")

        print(
            "Branch:",
            branch,
        )

        print(
            "Commit:",
            git_text(
                "rev-parse",
                "--short",
                "HEAD",
            ),
        )

        if blocked:
            print(
                "Protected Core:",
                "explicitly allowed",
            )

        if not blocked:
            print(
                "Protected Core:",
                "unchanged",
            )

        if args.push:
            print(
                "Push:",
                "completed",
            )

        if not args.push:
            print(
                "Push:",
                "not requested",
            )

        return 0

    except Exception:
        rollback(
            original_branch,
            original_head,
            original_untracked,
        )

        raise


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Safe local development runner "
            "for JARVIS."
        )
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )


    status = sub.add_parser(
        "status",
    )

    status.set_defaults(
        func=cmd_status,
    )


    verify = sub.add_parser(
        "verify",
    )

    verify.add_argument(
        "--base",
        default="HEAD",
    )

    verify.add_argument(
        "--test",
        action="append",
        default=[],
    )

    verify.add_argument(
        "--full",
        action="store_true",
    )

    verify.add_argument(
        "--allow-protected-core",
        action="store_true",
    )

    verify.set_defaults(
        func=cmd_verify,
    )


    apply_parser = sub.add_parser(
        "apply",
    )

    apply_parser.add_argument(
        "patch",
    )

    apply_parser.add_argument(
        "--message",
    )

    apply_parser.add_argument(
        "--test",
        action="append",
        default=[],
    )

    apply_parser.add_argument(
        "--full",
        action="store_true",
    )

    apply_parser.add_argument(
        "--push",
        action="store_true",
    )

    apply_parser.add_argument(
        "--allow-protected-core",
        action="store_true",
    )

    apply_parser.set_defaults(
        func=cmd_apply,
    )

    return parser


def main():
    args = build_parser().parse_args()

    try:

        return int(
            args.func(args)
        )

    except subprocess.CalledProcessError as exc:

        print(
            "",
            file=sys.stderr,
        )

        print(
            f"COMMAND FAILED "
            f"({exc.returncode})",
            file=sys.stderr,
        )

        return exc.returncode or 1

    except DevAgentError as exc:

        print(
            "",
            file=sys.stderr,
        )

        print(
            "JARVIS DEV AGENT BLOCKED:",
            exc,
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
