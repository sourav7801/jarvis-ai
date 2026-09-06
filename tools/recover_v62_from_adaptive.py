from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOVERY_BRANCH = "jarvis-dev/20260907-JARVIS-V6-2-recovery-integration"
V61_BRANCH = "jarvis-dev/20260828-101921-JARVIS-V6-1-command-center"
ADAPTIVE_BRANCH = "jarvis-dev/20260907-011550-JARVIS-Quant-V6-Adaptive-Brain"
V61_HEAD = "9650b0a7fe4999f6b22ed31a8d9f4893b07cf50a"

# Files that are genuinely additive in Quant V6. Existing V6.1 files are never
# blindly replaced: the upstream integration script patches them by anchors.
ADAPTIVE_NEW_FILES = (
    "docs/JARVIS_QUANT_INTELLIGENCE_BLUEPRINT.md",
    "omni/trading_intelligence/adaptive_quant_brain.py",
    "omni/trading_intelligence/chart_pattern_engine.py",
    "omni/trading_intelligence/indicator_plugin_registry.py",
    "omni/trading_intelligence/self_improvement_coordinator.py",
    "omni/trading_intelligence/strategy_research_lab.py",
    "omni/trading_intelligence/trade_learning_engine.py",
    "workstation/quant_intelligence_commands.py",
    "workstation/quant_terminal_v2_static/adaptive_brain_runtime.js",
    "tests/test_adaptive_quant_brain_v6.py",
    "tests/test_chart_pattern_engine_v6.py",
    "tests/test_quant_v6_adaptive_integration.py",
    "tests/test_quant_v6_chart_runtime.py",
    "tests/test_self_improvement_v6.py",
    "tools/integrate_quant_v6_adaptive.py",
    "tools/integrate_quant_v6_postfix.py",
)

CRITICAL_V61_FILES = (
    "omni/workspace_command_center.py",
    "workstation/jarvis_os_v3_assets/company.html",
    "workstation/jarvis_os_v3_assets/company.js",
    "workstation/jarvis_os_v3_assets/company.css",
    "workstation/quant_terminal_v2_static/intelligence.html",
    "workstation/quant_terminal_v2_static/intelligence.js",
    "workstation/quant_terminal_v2_static/intelligence.css",
    "workstation/quant_terminal_v2_static/option_chart_runtime.js",
    "workstation/quant_terminal_v2_static/paper_desk_runtime.js",
    "workstation/options_chain_analytics.py",
    "workstation/paper_portfolio_controller.py",
    "workstation/paper_scan_ledger.py",
    "workstation/advanced_pattern_engine.py",
)

TARGETED_TESTS = (
    "tests.test_workspace_command_center",
    "tests.test_workspace_command_center_health",
    "tests.test_company_terminal",
    "tests.test_quant_terminal_v2",
    "tests.test_options_chain_analytics",
    "tests.test_paper_trading_desk",
    "tests.test_adaptive_quant_brain_v6",
    "tests.test_chart_pattern_engine_v6",
    "tests.test_quant_v6_adaptive_integration",
    "tests.test_quant_v6_chart_runtime",
    "tests.test_self_improvement_v6",
)


def run(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stdout or ""
        if result.stderr:
            message += ("\n" if message else "") + result.stderr
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(args)}\n{message}")
    return result


def git(*args: str, check: bool = True) -> str:
    result = run("git", *args, check=check, capture=True)
    return (result.stdout or "").strip()


def python_exe() -> Path:
    candidates = (
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def remote_ref(branch: str) -> str:
    return f"origin/{branch}"


def show_file(ref: str, path: str) -> str:
    result = run("git", "show", f"{ref}:{path}", check=False, capture=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not read {path} from {ref}.\n{result.stderr or result.stdout or ''}"
        )
    return result.stdout


def write_from_ref(ref: str, path: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(show_file(ref, path), encoding="utf-8", newline="\n")


def normalize_integrator_root(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    source = source.replace(
        'ROOT = Path(r"C:\\Jarvis")',
        f"ROOT = Path({str(ROOT)!r})",
        1,
    )
    path.write_text(source, encoding="utf-8", newline="\n")


def verify_v61_surface() -> None:
    missing = [path for path in CRITICAL_V61_FILES if not (ROOT / path).exists()]
    if missing:
        raise RuntimeError(
            "Recovery base is missing advanced V6.1 files:\n - " + "\n - ".join(missing)
        )


def verify_git_state() -> tuple[str, str]:
    if not (ROOT / ".git").exists():
        raise RuntimeError(f"{ROOT} is not a Git working tree")

    current = git("branch", "--show-current")
    if current != RECOVERY_BRANCH:
        raise RuntimeError(
            f"Run this only on {RECOVERY_BRANCH}. Current branch: {current or '(detached)'}"
        )

    dirty = git("status", "--porcelain")
    if dirty:
        raise RuntimeError(
            "Working tree must be clean before recovery. Commit/stash unrelated work first:\n" + dirty
        )

    if run("git", "merge-base", "--is-ancestor", V61_HEAD, "HEAD", check=False).returncode != 0:
        raise RuntimeError(
            "Recovery branch is not descended from the complete V6.1 checkpoint. Refusing to continue."
        )

    head = git("rev-parse", "HEAD")
    return current, head


def fetch_sources() -> None:
    print("FETCH > refreshing origin refs")
    run("git", "fetch", "origin", V61_BRANCH, ADAPTIVE_BRANCH, RECOVERY_BRANCH)
    # Prove both remote source refs are now resolvable before touching files.
    git("rev-parse", remote_ref(V61_BRANCH))
    git("rev-parse", remote_ref(ADAPTIVE_BRANCH))


def copy_adaptive_additions() -> None:
    source_ref = remote_ref(ADAPTIVE_BRANCH)
    print("COPY > additive Quant V6 modules/tests/runtime")
    for path in ADAPTIVE_NEW_FILES:
        write_from_ref(source_ref, path)
        print("  +", path)

    normalize_integrator_root(ROOT / "tools" / "integrate_quant_v6_adaptive.py")
    normalize_integrator_root(ROOT / "tools" / "integrate_quant_v6_postfix.py")


def run_integrators(py: Path) -> None:
    print("PATCH > anchor-based Adaptive Quant V6 integration over V6.1")
    run(str(py), str(ROOT / "tools" / "integrate_quant_v6_adaptive.py"))
    run(str(py), str(ROOT / "tools" / "integrate_quant_v6_postfix.py"))


def smoke_contract(py: Path) -> None:
    smoke = r'''
from omni.workspace_command_center import snapshot
payload = snapshot()
assert payload["workspace_count"] >= 12, payload
keys = {row["key"] for row in payload["rows"]}
assert {"company", "quant", "paper", "research", "missions", "system"} <= keys, keys
assert payload["safety"]["paper_only"] is True
assert payload["safety"]["live_execution"] is False

from workstation.quant_firm_runtime import decision_payload
from omni.trading_intelligence.adaptive_quant_brain import adaptive_decide
from omni.trading_intelligence.strategy_research_lab import strategy_research_lab
from omni.trading_intelligence.trade_learning_engine import learning_engine
from omni.trading_intelligence.self_improvement_coordinator import self_improvement_coordinator

import main
status = main.jarvis_trading_v8_status()
assert status["live_execution"] is False
assert status["automatic_broker_order"] is False
print("V6.2 RECOVERY CONTRACT: PASS")
'''
    run(str(py), "-c", smoke)


def run_tests(py: Path, skip_full: bool) -> None:
    print("TEST > targeted V6.1 + Adaptive Quant V6 regression")
    run(str(py), "-m", "unittest", *TARGETED_TESTS, "-q")

    if not skip_full:
        print("TEST > full JARVIS regression")
        run(str(py), "-m", "unittest", "discover", "-s", "tests", "-q")


def validate_diff() -> None:
    verify_v61_surface()
    run("git", "diff", "--check")

    status = git("status", "--short")
    if not status:
        raise RuntimeError("Recovery produced no changes; expected Adaptive Quant V6 integration")

    deleted = [line for line in status.splitlines() if line[:2].strip() == "D"]
    if deleted:
        raise RuntimeError("Recovery unexpectedly deleted tracked files:\n" + "\n".join(deleted))

    print("\nCHANGED FILES")
    print(status)


def commit_recovery() -> str:
    run("git", "add", "-A")
    run("git", "diff", "--cached", "--check")
    run(
        "git",
        "commit",
        "-m",
        "JARVIS V6.2 recover complete workspaces and integrate Adaptive Quant V6",
    )
    return git("rev-parse", "--short", "HEAD")


def rollback(preflight_head: str) -> None:
    print("ROLLBACK > restoring pre-recovery checkpoint")
    run("git", "reset", "--hard", preflight_head, check=False)
    # Preflight requires a clean tree, so any remaining untracked files were
    # created by this recovery attempt.
    run("git", "clean", "-fd", check=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover complete JARVIS V6.1 workspaces and layer Adaptive Quant V6 on top."
    )
    parser.add_argument(
        "--skip-full",
        action="store_true",
        help="Run targeted regression only (full regression is recommended).",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push the successful recovery commit to the existing recovery branch on origin.",
    )
    args = parser.parse_args()

    print("=" * 88)
    print("JARVIS V6.2 RECOVERY — V6.1 COMPLETE SYSTEM + ADAPTIVE QUANT V6")
    print("=" * 88)

    current, preflight_head = verify_git_state()
    verify_v61_surface()
    fetch_sources()

    backup = "jarvis-backup/v62-preflight-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    run("git", "branch", backup, preflight_head)
    print("BACKUP >", backup, preflight_head[:8])

    py = python_exe()
    print("PYTHON >", py)

    try:
        copy_adaptive_additions()
        run_integrators(py)
        validate_diff()
        smoke_contract(py)
        run_tests(py, args.skip_full)
        validate_diff()
        commit = commit_recovery()

        if args.push:
            print("PUSH >", current)
            run("git", "push", "-u", "origin", current)

        print("\n" + "=" * 88)
        print("JARVIS V6.2 RECOVERY: SUCCESS")
        print("=" * 88)
        print("Branch :", current)
        print("Commit :", commit)
        print("Backup :", backup)
        print("Preserved: Command Center, Company OS, advanced Quant/Options/Paper workspaces")
        print("Added    : Adaptive Brain, chart patterns, indicator plugins, Strategy Lab, learning")
        print("Safety   : PAPER ONLY; live execution and automatic broker orders remain locked")
        print()
        print(r'Restart with: & "C:\Jarvis\JARVIS.bat"')
        print("Then hard refresh the browser once with Ctrl+Shift+R.")
        if not args.push:
            print(f"Push after verification: git push -u origin {current}")
        return 0

    except Exception as exc:
        print("\nRECOVERY FAILED:", type(exc).__name__, exc)
        rollback(preflight_head)
        print("Your pre-recovery branch state has been restored.")
        print("Backup branch retained:", backup)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
