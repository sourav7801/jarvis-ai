"""Read-only operational health report for the canonical runtime."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from config import (
    AUDIT_DB,
    LIVE_TRADING_ENABLED,
    OLLAMA_URL,
    PROJECT_ROOT,
    STATE_DIR,
)
from main import AGENT_REGISTRY
from tools.capabilities import validate_capability_manifest
from tools.registry import list_tools


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def run_checks(check_network: bool = False) -> list[Check]:
    checks = []
    version_ok = (3, 11) <= sys.version_info[:2] < (3, 14)
    checks.append(
        Check(
            "python_version",
            "PASS" if version_ok else "FAIL",
            sys.version.split()[0],
        )
    )
    checks.append(
        Check(
            "live_trading_boundary",
            "PASS" if not LIVE_TRADING_ENABLED else "FAIL",
            "disabled" if not LIVE_TRADING_ENABLED else "enabled",
        )
    )
    capability_errors = validate_capability_manifest(list_tools())
    checks.append(
        Check(
            "tool_capabilities",
            "PASS" if not capability_errors else "FAIL",
            "; ".join(capability_errors) or f"{len(list_tools())} tools declared",
        )
    )
    checks.append(
        Check(
            "agent_registry",
            "PASS" if AGENT_REGISTRY.names() else "FAIL",
            ", ".join(AGENT_REGISTRY.names()),
        )
    )
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
        if any(word in path.stem for word in ("backup", "before", "old", "stable"))
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
        checks.append(
            Check(
                "ollama_reachable",
                "PASS" if reachable else "WARN",
                f"{parsed_host}:{parsed_port}",
            )
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser("OMNI-JARVIS doctor")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    checks = run_checks(args.network)
    if args.json:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
    return 1 if any(check.status == "FAIL" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
