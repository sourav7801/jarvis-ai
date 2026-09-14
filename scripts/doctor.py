"""Read-only operational health report for the canonical JARVIS V16 runtime.

The doctor intentionally does not start services, create databases, place paper
orders, contact a broker, or mutate runtime state.  Optional runtime probes use
loopback GET requests only.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import socket
import sqlite3
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from config import (
    AUDIT_DB,
    LIVE_TRADING_ENABLED,
    OLLAMA_URL,
    PROJECT_ROOT,
    STATE_DIR,
    WORKSTATION_PORT,
)


CANONICAL_LEDGER = PROJECT_ROOT / "data" / "trading" / "paper_desk.sqlite3"
EXPECTED_PYTHON_SPEC = ">=3.11,<3.14"
REQUIRED_V16_PATHS = (
    "start_jarvis_v16_workstation.py",
    "workstation/v16_terminal_http.py",
    "workstation/professional_terminal.py",
    "workstation/paper_runtime.py",
    "workstation/v16_autonomous_paper.py",
    "workstation/v16_option_paper.py",
    "workstation/quant_terminal_v2_static/v16_workspace_router.js",
)
SAFETY_INVARIANTS = {
    "paper_only": True,
    "live_execution": False,
    "automatic_broker_order": False,
    "live_orders_locked": True,
    "naked_option_selling": False,
}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def python_supported(version: tuple[int, int] | None = None) -> bool:
    """Return whether a Python major/minor is supported by this V16 branch."""
    current = tuple(version or sys.version_info[:2])
    return (3, 11) <= current < (3, 14)


def _package_spec_check() -> Check:
    path = PROJECT_ROOT / "pyproject.toml"
    try:
        with path.open("rb") as handle:
            spec = str(tomllib.load(handle)["project"]["requires-python"])
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        return Check("package_python_spec", "FAIL", f"unreadable: {type(exc).__name__}: {exc}")

    normalized = "".join(spec.split())
    expected = "".join(EXPECTED_PYTHON_SPEC.split())
    return Check(
        "package_python_spec",
        "PASS" if normalized == expected else "FAIL",
        spec,
    )


def _topology_check() -> Check:
    missing = [name for name in REQUIRED_V16_PATHS if not (PROJECT_ROOT / name).is_file()]
    return Check(
        "v16_runtime_topology",
        "FAIL" if missing else "PASS",
        "missing: " + ", ".join(missing) if missing else f"{len(REQUIRED_V16_PATHS)} canonical files present",
    )


def inspect_ledger(path: Path = CANONICAL_LEDGER) -> Check:
    """Inspect the canonical paper ledger without creating or modifying it."""
    path = Path(path)
    if not path.exists():
        return Check("canonical_paper_ledger", "WARN", f"not initialized: {path}")
    if not path.is_file():
        return Check("canonical_paper_ledger", "FAIL", f"not a file: {path}")

    connection = None
    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=1.0)
        journal_row = connection.execute("PRAGMA journal_mode").fetchone()
        check_row = connection.execute("PRAGMA quick_check(1)").fetchone()
        table_row = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()
        journal_mode = str(journal_row[0] if journal_row else "unknown").lower()
        quick_check = str(check_row[0] if check_row else "unknown").lower()
        table_count = int(table_row[0] if table_row else 0)
    except sqlite3.Error as exc:
        return Check("canonical_paper_ledger", "FAIL", f"SQLite read failed: {exc}")
    finally:
        if connection is not None:
            connection.close()

    if quick_check != "ok":
        return Check(
            "canonical_paper_ledger",
            "FAIL",
            f"quick_check={quick_check}; journal={journal_mode}; tables={table_count}",
        )
    if journal_mode != "wal":
        return Check(
            "canonical_paper_ledger",
            "WARN",
            f"healthy but journal={journal_mode}; expected wal; tables={table_count}",
        )
    return Check(
        "canonical_paper_ledger",
        "PASS",
        f"read-only quick_check=ok; journal=wal; tables={table_count}",
    )


def check_safety_payload(payload: object) -> Check:
    """Verify the fail-closed trading invariants exposed by V16 state."""
    if not isinstance(payload, dict):
        return Check("v16_safety_invariants", "FAIL", "workspace state is not a JSON object")

    mismatches = []
    for key, expected in SAFETY_INVARIANTS.items():
        actual = payload.get(key, "<missing>")
        if type(actual) is not bool or actual != expected:
            mismatches.append(f"{key}={actual!r} expected {expected!r}")
    return Check(
        "v16_safety_invariants",
        "FAIL" if mismatches else "PASS",
        "; ".join(mismatches) if mismatches else "paper-only and live-order locks verified",
    )


def _port_check(name: str, port: int) -> tuple[Check, bool]:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.75):
            reachable = True
    except OSError:
        reachable = False
    return (
        Check(
            name,
            "PASS" if reachable else "WARN",
            f"127.0.0.1:{port} " + ("listening" if reachable else "not listening"),
        ),
        reachable,
    )


def _workspace_safety_check(port: int) -> Check:
    url = (
        f"http://127.0.0.1:{int(port)}"
        "/api/v16/trading/workspace-state?workspace=INTRADAY"
    )
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "JARVIS-V16-Doctor/1"},
        method="GET",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return Check(
            "v16_safety_invariants",
            "WARN",
            f"canonical state probe unavailable: {type(exc).__name__}: {exc}",
        )
    return check_safety_payload(payload)


def _tool_capability_check() -> Check:
    try:
        # Some optional tool modules print availability warnings while loading.
        # Capture those messages so --json remains machine-readable.
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            from tools.capabilities import validate_capability_manifest
            from tools.registry import list_tools

            tools = list_tools()
            errors = validate_capability_manifest(tools)
        detail = "; ".join(errors) or f"{len(tools)} tools declared"
        if output.getvalue().strip() and not errors:
            detail += "; optional loader warnings captured"
        return Check("tool_capabilities", "PASS" if not errors else "FAIL", detail)
    except Exception as exc:
        return Check("tool_capabilities", "FAIL", f"{type(exc).__name__}: {exc}")


def _agent_registry_check() -> Check:
    try:
        from omni.agent_registry import default_agent_specs

        specs = tuple(default_agent_specs())
        names = [spec.name for spec in specs]
        unique = len(names) == len(set(names))
        valid = bool(names) and unique
        detail = f"{len(names)} agent specs declared"
        if not unique:
            detail += "; duplicate names detected"
        return Check("agent_registry", "PASS" if valid else "FAIL", detail)
    except Exception as exc:
        return Check("agent_registry", "FAIL", f"{type(exc).__name__}: {exc}")


def _ollama_check() -> Check:
    parsed_host = "127.0.0.1"
    parsed_port = 11434
    try:
        from urllib.parse import urlsplit

        parsed = urlsplit(OLLAMA_URL)
        parsed_host = parsed.hostname or parsed_host
        parsed_port = parsed.port or parsed_port
        with socket.create_connection((parsed_host, parsed_port), timeout=1):
            reachable = True
    except OSError:
        reachable = False
    return Check(
        "ollama_reachable",
        "PASS" if reachable else "WARN",
        f"{parsed_host}:{parsed_port}",
    )


def run_checks(
    check_network: bool = False,
    check_runtime: bool = False,
) -> list[Check]:
    checks: list[Check] = []
    checks.append(
        Check(
            "python_version",
            "PASS" if python_supported() else "FAIL",
            f"{sys.version.split()[0]} via {sys.executable}",
        )
    )
    checks.append(_package_spec_check())
    checks.append(_topology_check())
    checks.append(
        Check(
            "live_trading_boundary",
            "PASS" if not LIVE_TRADING_ENABLED else "FAIL",
            "disabled" if not LIVE_TRADING_ENABLED else "enabled",
        )
    )
    checks.append(_tool_capability_check())
    checks.append(_agent_registry_check())
    checks.append(inspect_ledger())

    state_parent = STATE_DIR if STATE_DIR.exists() else STATE_DIR.parent
    checks.append(
        Check(
            "state_path",
            "PASS" if state_parent.exists() and os.access(state_parent, os.W_OK) else "WARN",
            str(STATE_DIR),
        )
    )
    checks.append(
        Check(
            "audit_database",
            "PASS" if AUDIT_DB.exists() else "WARN",
            "initialized" if AUDIT_DB.exists() else "created on first runtime event",
        )
    )
    historical = [
        path
        for path in PROJECT_ROOT.glob("*.py")
        if any(word in path.stem.lower() for word in ("backup", "before", "old", "stable"))
    ]
    checks.append(
        Check(
            "historical_root_files",
            "WARN" if historical else "PASS",
            f"{len(historical)} preserved historical files",
        )
    )
    checks.append(
        Check(
            "source_control",
            "PASS" if (PROJECT_ROOT / ".git").is_dir() else "WARN",
            "Git repository initialized"
            if (PROJECT_ROOT / ".git").is_dir()
            else "Git repository not initialized",
        )
    )

    if check_network:
        checks.append(_ollama_check())

    if check_runtime:
        master_port = int(os.getenv("JARVIS_MASTER_PORT", "8797"))
        quant_port = int(os.getenv("JARVIS_WORKSTATION_PORT", str(WORKSTATION_PORT)))
        nautilus_port = int(os.getenv("JARVIS_NAUTILUS_PORT", "8792"))
        master_check, _ = _port_check("master_ui", master_port)
        quant_check, quant_up = _port_check("quant_terminal", quant_port)
        nautilus_check, _ = _port_check("nautilus", nautilus_port)
        checks.extend((master_check, quant_check, nautilus_check))
        if quant_up:
            checks.append(_workspace_safety_check(quant_port))
        else:
            checks.append(
                Check(
                    "v16_safety_invariants",
                    "WARN",
                    "quant terminal is offline; runtime safety state was not probed",
                )
            )

    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser("OMNI-JARVIS V16 doctor")
    parser.add_argument(
        "--network",
        action="store_true",
        help="also probe the configured local Ollama endpoint",
    )
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="also probe local V16 services and canonical safety state",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI marker; runtime/network probes remain opt-in",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    checks = run_checks(args.network, args.runtime)
    if args.json:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
    return 1 if any(check.status == "FAIL" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
