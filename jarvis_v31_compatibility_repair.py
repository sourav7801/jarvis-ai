from __future__ import annotations

import ast
import hashlib
import io
import os
import shutil
import subprocess
import sys
import types
import unittest

from pathlib import Path


ROOT = Path(r"C:\Jarvis")

PYTHON = (
    ROOT
    / ".venv"
    / "Scripts"
    / "python.exe"
)

INSTALLER = Path(
    os.environ[
        "JARVIS_V31_INSTALLER"
    ]
)

ARCHIVE = (
    ROOT
    / "archive"
    / "jarvis_os_v3_1"
    / "compatibility_repair"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)


print("=" * 80)
print("JARVIS OS V3.1 — V3 BACKWARD-COMPATIBILITY REPAIR")
print("=" * 80)


# ============================================================
# 1. VERIFY ROLLED-BACK PRODUCTION
# ============================================================

print()
print("=" * 80)
print("CURRENT PRODUCTION BASELINE")
print("=" * 80)


import main

from omni.core_integrity import (
    verify_protected_core,
)


core = verify_protected_core()

assert core.ok, (
    core.changed,
    core.missing,
)


v8 = (
    main
    .jarvis_trading_v8_status()
)


assert v8[
    "live_execution"
] is False

assert v8[
    "automatic_broker_order"
] is False


print("Protected Core: PASS")
print("Trading V8: PASS")
print("Live execution: BLOCKED")
print("Automatic broker orders: BLOCKED")
print("Rollback production state: HEALTHY")


# ============================================================
# 2. LOAD / BACKUP INSTALLER
# ============================================================

if not INSTALLER.exists():

    raise RuntimeError(
        "V3.1 installer not found: "
        + str(INSTALLER)
    )


installer_text = (
    INSTALLER
    .read_text(
        encoding="utf-8-sig",
        errors="strict",
    )
)


backup = (
    ARCHIVE
    / "installer_BEFORE_v3_compatibility.py"
)


shutil.copy2(
    INSTALLER,
    backup,
)


print()
print(
    "Installer backup:",
    backup,
)


# ============================================================
# 3. EXTRACT EMBEDDED V3.1 SOURCES
# ============================================================

tree = ast.parse(
    installer_text,
    filename=str(
        INSTALLER
    ),
)


embedded_sources = []


for node in ast.walk(
    tree
):

    if not isinstance(
        node,
        ast.Call,
    ):

        continue


    if not isinstance(
        node.func,
        ast.Name,
    ):

        continue


    if node.func.id != "write":

        continue


    if len(
        node.args
    ) < 2:

        continue


    candidate = node.args[
        1
    ]


    if (
        isinstance(
            candidate,
            ast.Constant,
        )
        and isinstance(
            candidate.value,
            str,
        )
    ):

        embedded_sources.append(
            candidate.value
        )


def extract(
    marker,
):

    matches = [
        source

        for source
        in embedded_sources

        if marker in source
    ]


    if len(matches) != 1:

        raise RuntimeError(
            "Expected one embedded source containing "
            + repr(marker)
            + "; found "
            + str(len(matches))
        )


    return matches[0]


orchestrator_source = extract(
    "def interpret_workspace_command("
)

chart_source = extract(
    "def get_chart("
)

server_source = extract(
    "class Handler("
)

v31_test_source = extract(
    "class JarvisOSV31Tests("
)


print()
print("Embedded workspace orchestrator: FOUND")
print("Embedded chart provider: FOUND")
print("Embedded V3.1 server: FOUND")
print("Embedded V3.1 tests: FOUND")


# ============================================================
# 4. CONFIRM EXACT COMPATIBILITY BREAK
# ============================================================

required_old_api = (
    "_safe",
    "ui_actions",
    "market_snapshot",
)


print()
print("=" * 80)
print("EXACT V3 COMPATIBILITY DIAGNOSIS")
print("=" * 80)


print(
    "V3.1 safe():",
    "PRESENT"
    if "def safe(" in server_source
    else "MISSING",
)

print(
    "V3.1 market():",
    "PRESENT"
    if "def market(" in server_source
    else "MISSING",
)

print(
    "Workspace interpreter:",
    "PRESENT"
    if "interpret_workspace_command" in server_source
    else "MISSING",
)


missing_compat = []


for name in required_old_api:

    present = (
        (
            "def "
            + name
            + "("
        )
        in server_source
    )


    print(
        "Legacy",
        name + "():",
        (
            "PRESENT"
            if present
            else "MISSING"
        ),
    )


    if not present:

        missing_compat.append(
            name
        )


if not missing_compat:

    raise RuntimeError(
        "All compatibility APIs are already present. "
        "Stopping rather than double-patching."
    )


assert "def safe(" in server_source
assert "def market(" in server_source
assert "interpret_workspace_command" in server_source


print()
print(
    "Confirmed failure:",
    "V3 public compatibility surface removed by V3.1",
)

print(
    "Architecture failure:",
    "NO",
)

print(
    "Correct repair:",
    "BACKWARD-COMPATIBILITY SHIMS",
)


# ============================================================
# 5. COMPATIBILITY LAYER
#
# V3.1 itself continues using its new native APIs.
# These wrappers only preserve the old V3 public contract.
# ============================================================

compatibility = r'''

# ============================================================
# JARVIS OS V3 BACKWARD COMPATIBILITY
#
# V3.1 uses:
#     safe()
#     interpret_workspace_command()
#     market()
#
# Older V3 integrations/tests use:
#     _safe()
#     ui_actions()
#     market_snapshot()
#
# Keep both contracts alive.
# ============================================================


def _safe(
    value,
    depth=0,
):

    return safe(
        value,
        depth,
    )


def ui_actions(
    text,
):

    modern = tuple(
        interpret_workspace_command(
            text
        )
    )


    legacy = []

    seen = set()


    def add(
        action,
    ):

        key = repr(
            sorted(
                action.items()
            )
        )


        if key in seen:

            return


        seen.add(
            key
        )

        legacy.append(
            action
        )


    for action in modern:

        action = dict(
            action
        )


        action_type = action.get(
            "type"
        )


        # ----------------------------------------------------
        # V3's trading workspace was the legacy dashboard.
        #
        # V3.1's native trading surface is "chart".
        #
        # Preserve the historical V3 ui_actions() result
        # without changing V3.1's modern workspace behavior.
        # ----------------------------------------------------

        if (
            action_type
            == "open_window"

            and action.get(
                "window"
            )
            == "chart"
        ):

            add(
                {
                    "type":
                        "open_window",

                    "window":
                        "legacy",
                }
            )

            continue


        # Chart-specific V3.1 actions did not exist in V3.
        # They are intentionally omitted from the old shim.
        if action_type in {
            "chart_symbol",
            "chart_layout",
        }:

            continue


        add(
            action
        )


    return legacy


def market_snapshot():

    current = market()


    return {
        "nifty":
            current.get(
                "latest"
            ),

        "trading_status":
            current.get(
                "trading"
            ),

        "capture_history":
            current.get(
                "history_count",
                0,
            ),
    }

'''


marker = "\nclass Handler("


if marker not in server_source:

    raise RuntimeError(
        "Could not locate class Handler() insertion point."
    )


patched_server = (
    server_source.replace(
        marker,
        compatibility
        + marker,
        1,
    )
)


assert (
    patched_server
    != server_source
)


# ============================================================
# 6. IN-MEMORY MODULE HARNESS
# ============================================================

def make_module(
    name,
    source,
    filename,
):

    module = types.ModuleType(
        name
    )


    module.__file__ = str(
        filename
    )


    module.__package__ = (
        name.rpartition(
            "."
        )[0]
    )


    module.__dict__[
        "__file__"
    ] = str(
        filename
    )

    module.__dict__[
        "__name__"
    ] = name

    module.__dict__[
        "__package__"
    ] = module.__package__


    sys.modules[
        name
    ] = module


    exec(
        compile(
            source,
            str(
                filename
            ),
            "exec",
        ),
        module.__dict__,
    )


    return module


def load_v31_modules():

    import omni
    import workstation


    orchestrator = make_module(
        "omni.jarvis_workspace_orchestrator",
        orchestrator_source,
        (
            ROOT
            / "omni"
            / "jarvis_workspace_orchestrator.py"
        ),
    )


    setattr(
        omni,
        "jarvis_workspace_orchestrator",
        orchestrator,
    )


    chart = make_module(
        "workstation.jarvis_v3_chart_provider",
        chart_source,
        (
            ROOT
            / "workstation"
            / "jarvis_v3_chart_provider.py"
        ),
    )


    setattr(
        workstation,
        "jarvis_v3_chart_provider",
        chart,
    )


    server = make_module(
        "workstation.jarvis_os_v3",
        patched_server,
        (
            ROOT
            / "workstation"
            / "jarvis_os_v3.py"
        ),
    )


    setattr(
        workstation,
        "jarvis_os_v3",
        server,
    )


    return server


server = load_v31_modules()


# ============================================================
# 7. EXACT OLD-V3 CONTRACT PROBES
# ============================================================

print()
print("=" * 80)
print("V3 BACKWARD-COMPATIBILITY PROBES")
print("=" * 80)


# _safe()
value = server._safe(
    {
        "access_token":
            "DO_NOT_PRINT",

        "normal":
            "visible",
    }
)


assert (
    value[
        "access_token"
    ]
    == "<REDACTED>"
)

assert (
    value[
        "normal"
    ]
    == "visible"
)


print("_safe(): PASS")


# ui_actions() old trading behavior
actions = server.ui_actions(
    "Open trading terminal and run strategy"
)


windows = {
    item.get(
        "window"
    )

    for item in actions

    if item.get(
        "type"
    ) == "open_window"
}


assert "legacy" in windows, (
    actions
)

assert "quant" in windows, (
    actions
)


print(
    "ui_actions trading compatibility:",
    "PASS",
)


# Old research-layout behavior
actions = server.ui_actions(
    "Open research layout"
)


assert any(
    item.get(
        "type"
    ) == "layout"

    and item.get(
        "layout"
    ) == "research"

    for item in actions
), actions


print(
    "ui_actions research layout:",
    "PASS",
)


# Old close-all behavior
actions = server.ui_actions(
    "close all windows"
)


assert any(
    item.get(
        "type"
    ) == "close_all"

    for item in actions
), actions


print(
    "ui_actions close all:",
    "PASS",
)


# market_snapshot old contract
snapshot = (
    server
    .market_snapshot()
)


assert (
    "trading_status"
    in snapshot
)

assert (
    "capture_history"
    in snapshot
)

assert (
    "nifty"
    in snapshot
)


print(
    "market_snapshot(): PASS"
)


# ============================================================
# 8. RUN ACTUAL EXISTING V3 TEST FILE IN MEMORY
# ============================================================

old_test_path = (
    ROOT
    / "tests"
    / "test_jarvis_os_v3.py"
)


if not old_test_path.exists():

    raise RuntimeError(
        "Existing V3 regression test file is missing."
    )


old_test_source = (
    old_test_path
    .read_text(
        encoding="utf-8"
    )
)


old_test_module = types.ModuleType(
    "compat_test_jarvis_os_v3"
)


old_test_module.__file__ = str(
    old_test_path
)

old_test_module.__package__ = "tests"


exec(
    compile(
        old_test_source,
        str(
            old_test_path
        ),
        "exec",
    ),
    old_test_module.__dict__,
)


old_suite = (
    unittest
    .defaultTestLoader
    .loadTestsFromModule(
        old_test_module
    )
)


old_stream = io.StringIO()


old_result = (
    unittest
    .TextTestRunner(
        stream=old_stream,
        verbosity=2,
    )
    .run(
        old_suite
    )
)


print()
print("=" * 80)
print("ACTUAL V3 REGRESSION AGAINST PATCHED V3.1 SERVER")
print("=" * 80)

print(
    old_stream
    .getvalue()
    .rstrip()
)


if (
    old_result.failures
    or old_result.errors
):

    print()
    print(
        "Backward compatibility still fails."
    )


    for test, trace in (
        list(
            old_result.failures
        )
        + list(
            old_result.errors
        )
    ):

        print()
        print(
            "FAILED:",
            test.id(),
        )

        print(
            trace
        )


    raise SystemExit(
        2
    )


print()
print(
    "Old V3 tests:",
    f"{old_result.testsRun}/{old_result.testsRun}",
    "PASS",
)


# ============================================================
# 9. RUN V3.1 EMBEDDED SUITE AGAIN TOO
# ============================================================

v31_test_module = types.ModuleType(
    "compat_test_jarvis_os_v3_1"
)


v31_test_module.__file__ = str(
    ROOT
    / "tests"
    / "test_jarvis_os_v3_1.py"
)

v31_test_module.__package__ = "tests"


exec(
    compile(
        v31_test_source,
        v31_test_module.__file__,
        "exec",
    ),
    v31_test_module.__dict__,
)


v31_suite = (
    unittest
    .defaultTestLoader
    .loadTestsFromModule(
        v31_test_module
    )
)


v31_stream = io.StringIO()


v31_result = (
    unittest
    .TextTestRunner(
        stream=v31_stream,
        verbosity=2,
    )
    .run(
        v31_suite
    )
)


print()
print("=" * 80)
print("V3.1 REGRESSION WITH COMPATIBILITY LAYER")
print("=" * 80)

print(
    v31_stream
    .getvalue()
    .rstrip()
)


if (
    v31_result.failures
    or v31_result.errors
):

    raise RuntimeError(
        "Compatibility layer broke V3.1 targeted tests."
    )


print()
print(
    "V3.1 tests:",
    f"{v31_result.testsRun}/{v31_result.testsRun}",
    "PASS",
)


# ============================================================
# 10. PATCH ONLY INSTALLER EMBEDDED SERVER
# ============================================================

occurrences = (
    installer_text.count(
        server_source
    )
)


if occurrences != 1:

    raise RuntimeError(
        "Expected exact embedded server source once; found "
        + str(
            occurrences
        )
    )


repaired_installer = (
    installer_text.replace(
        server_source,
        patched_server,
        1,
    )
)


INSTALLER.write_text(
    repaired_installer,
    encoding="utf-8",
    newline="\n",
)


print()
print("=" * 80)
print("INSTALLER PATCH")
print("=" * 80)

print(
    "Compatibility layer inserted:",
    "YES",
)

print(
    "Installer only modified:",
    "YES",
)

print(
    "Production source modified:",
    "NO",
)


# ============================================================
# 11. COMPILE INSTALLER
# ============================================================

compile_result = subprocess.run(
    [
        str(PYTHON),
        "-m",
        "py_compile",
        str(
            INSTALLER
        ),
    ],
    cwd=ROOT,
)


if compile_result.returncode:

    shutil.copy2(
        backup,
        INSTALLER,
    )

    raise RuntimeError(
        "Patched installer compilation failed. "
        "Installer restored from backup."
    )


print(
    "Patched installer syntax:",
    "PASS",
)


# ============================================================
# 12. CURRENT PRODUCTION STILL SAFE
# ============================================================

core = verify_protected_core()

assert core.ok


v8 = (
    main
    .jarvis_trading_v8_status()
)


assert v8[
    "live_execution"
] is False

assert v8[
    "automatic_broker_order"
] is False


print()
print("=" * 80)
print("V3.1 COMPATIBILITY REPAIR: VERIFIED")
print("=" * 80)

print(
    "Old V3 regression:",
    f"{old_result.testsRun}/{old_result.testsRun}",
)

print(
    "V3.1 regression:",
    f"{v31_result.testsRun}/{v31_result.testsRun}",
)

print(
    "Protected Core:",
    "PASS",
)

print(
    "Live execution:",
    "BLOCKED",
)

print(
    "Ready to run installer:",
    "YES",
)
