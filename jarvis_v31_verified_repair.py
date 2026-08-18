from __future__ import annotations

import ast
import io
import os
import re
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
    / "verified_repair"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)


print("=" * 80)
print("JARVIS OS V3.1 — VERIFIED SURGICAL REPAIR")
print("=" * 80)


# ============================================================
# 1. CURRENT PRODUCTION SAFETY
# ============================================================

print()
print("=" * 80)
print("CURRENT PRODUCTION")
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
print("Broker orders: BLOCKED")
print("Current production: HEALTHY")


# ============================================================
# 2. LOAD INSTALLER
# ============================================================

if not INSTALLER.exists():

    raise RuntimeError(
        "V3.1 installer not found."
    )


installer_text = (
    INSTALLER
    .read_text(
        encoding="utf-8-sig"
    )
)


backup = (
    ARCHIVE
    / "installer_BEFORE_verified_repair.py"
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
# 3. EXTRACT EMBEDDED SOURCES
# ============================================================

tree = ast.parse(
    installer_text,
    filename=str(
        INSTALLER
    ),
)


embedded = []


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


    source_node = node.args[
        1
    ]


    if (
        isinstance(
            source_node,
            ast.Constant,
        )
        and isinstance(
            source_node.value,
            str,
        )
    ):

        embedded.append(
            source_node.value
        )


def extract(
    marker,
):

    values = [
        source

        for source
        in embedded

        if marker in source
    ]


    if len(
        values
    ) != 1:

        raise RuntimeError(
            "Expected exactly one source for "
            + repr(
                marker
            )
            + "; found "
            + str(
                len(
                    values
                )
            )
        )


    return values[
        0
    ]


orchestrator_source = extract(
    "def interpret_workspace_command("
)

chart_source = extract(
    "def get_chart("
)

server_source = extract(
    "class Handler("
)

test_source = extract(
    "class JarvisOSV31Tests("
)


print()
print("Embedded orchestrator: FOUND")
print("Embedded chart provider: FOUND")
print("Embedded V3.1 server: FOUND")
print("Embedded targeted suite: FOUND")


# ============================================================
# 4. SAFE IN-MEMORY MODULE EXECUTION
#
# The previous diagnostic failed because __file__ was absent.
# Every module now receives its real intended path.
# ============================================================

def module_from_source(
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


    sys.modules[
        name
    ] = module


    return module


def install_temp_modules(
    orchestrator_text,
):

    import omni
    import workstation


    orchestrator = module_from_source(
        "omni.jarvis_workspace_orchestrator",
        orchestrator_text,
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


    chart = module_from_source(
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


    server = module_from_source(
        "workstation.jarvis_os_v3",
        server_source,
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


    return (
        orchestrator,
        chart,
        server,
    )


def run_embedded_suite(
    orchestrator_text,
):

    install_temp_modules(
        orchestrator_text
    )


    module = types.ModuleType(
        "tests.test_jarvis_os_v3_1"
    )


    module.__file__ = str(
        ROOT
        / "tests"
        / "test_jarvis_os_v3_1.py"
    )


    module.__package__ = "tests"


    exec(
        compile(
            test_source,
            module.__file__,
            "exec",
        ),
        module.__dict__,
    )


    suite = (
        unittest
        .defaultTestLoader
        .loadTestsFromModule(
            module
        )
    )


    stream = io.StringIO()


    result = (
        unittest
        .TextTestRunner(
            stream=stream,
            verbosity=2,
        )
        .run(
            suite
        )
    )


    return (
        result,
        stream.getvalue(),
    )


# ============================================================
# 5. RUN ORIGINAL ACTUAL V3.1 TESTS
# ============================================================

print()
print("=" * 80)
print("ORIGINAL V3.1 TARGETED SUITE")
print("=" * 80)


before, before_output = (
    run_embedded_suite(
        orchestrator_source
    )
)


print(
    before_output.rstrip()
)


print()
print(
    "Tests:",
    before.testsRun,
)

print(
    "Failures:",
    len(
        before.failures
    ),
)

print(
    "Errors:",
    len(
        before.errors
    ),
)


problems = (
    list(
        before.failures
    )
    + list(
        before.errors
    )
)


if not problems:

    print()
    print(
        "Original embedded suite already passes."
    )

    raise RuntimeError(
        "The previous installer failure was not reproduced. "
        "Stopping instead of applying a speculative repair."
    )


print()
print("EXACT ORIGINAL FAILURES:")


problem_names = []


for test, traceback_text in problems:

    name = test.id()

    problem_names.append(
        name
    )


    print()
    print(
        "FAILED:",
        name,
    )


    for line in (
        traceback_text
        .strip()
        .splitlines()
        [
            -12:
        ]
    ):

        print(
            line
        )


# ============================================================
# 6. ONLY ACCEPT EXPECTED PARSER FAILURE
# ============================================================

unexpected = [
    name

    for name in problem_names

    if not any(
        marker in name

        for marker in (
            "test_compare",
            "test_trading_workspace_command",
        )
    )
]


if unexpected:

    print()
    print("=" * 80)
    print("UNEXPECTED V3.1 FAILURE")
    print("=" * 80)

    print(
        "Unexpected tests:",
        unexpected,
    )

    print()
    print(
        "Installer will NOT be patched."
    )


    raise SystemExit(
        3
    )


print()
print(
    "Failure category:",
    "WORKSPACE SYMBOL PARSER",
)

print(
    "Safe targeted repair:",
    "YES",
)


# ============================================================
# 7. STRUCTURAL PARSER REPAIR
# ============================================================

symbol_block = re.search(
    r"(?ms)^def _symbols\(.*?(?=^def _timeframe\()",
    orchestrator_source,
)


if symbol_block is None:

    raise RuntimeError(
        "Unable to locate embedded _symbols() function."
    )


print()
print("=" * 80)
print("CURRENT SYMBOL PARSER")
print("=" * 80)

print(
    symbol_block
    .group(0)
    .rstrip()
)


new_symbols = r'''def _symbols(
    text,
):

    lowered = str(
        text
    ).lower()


    candidates = []


    for alias, canonical in (
        SYMBOL_ALIASES.items()
    ):

        # Word-boundary style matching prevents:
        #
        # NIFTY matching inside BANKNIFTY.
        pattern = (
            r"(?<!\w)"
            + re.escape(
                alias
            )
            + r"(?!\w)"
        )


        for match in re.finditer(
            pattern,
            lowered,
        ):

            candidates.append(
                {
                    "start":
                        match.start(),

                    "end":
                        match.end(),

                    "length":
                        match.end()
                        - match.start(),

                    "canonical":
                        canonical,

                    "alias":
                        alias,
                }
            )


    # Preserve the order the user spoke the instruments.
    #
    # For aliases beginning at the same position,
    # prefer the longest match:
    #
    # "NIFTY 50" > "NIFTY"
    candidates.sort(
        key=lambda item: (
            item[
                "start"
            ],

            -item[
                "length"
            ],
        )
    )


    accepted = []


    for candidate in candidates:

        overlaps = any(
            not (
                candidate[
                    "end"
                ]
                <= existing[
                    "start"
                ]

                or

                candidate[
                    "start"
                ]
                >= existing[
                    "end"
                ]
            )

            for existing
            in accepted
        )


        if overlaps:

            continue


        accepted.append(
            candidate
        )


    accepted.sort(
        key=lambda item:
            item[
                "start"
            ]
    )


    values = []


    for candidate in accepted:

        canonical = candidate[
            "canonical"
        ]


        if canonical not in values:

            values.append(
                canonical
            )


    return tuple(
        values
    )


'''


patched_orchestrator = re.sub(
    r"(?ms)^def _symbols\(.*?(?=^def _timeframe\()",
    new_symbols,
    orchestrator_source,
    count=1,
)


if (
    patched_orchestrator
    == orchestrator_source
):

    raise RuntimeError(
        "Parser source was not changed."
    )


# ============================================================
# 8. DIRECT COMMAND SEMANTIC PROBES
# ============================================================

print()
print("=" * 80)
print("SEMANTIC COMMAND PROBES")
print("=" * 80)


probe = module_from_source(
    "v31_parser_probe",
    patched_orchestrator,
    (
        ROOT
        / "research"
        / "v31_parser_probe.py"
    ),
)


cases = (
    (
        "Compare NIFTY and BANKNIFTY",
        (
            "NIFTY",
            "BANKNIFTY",
        ),
    ),

    (
        "Compare BANKNIFTY and NIFTY",
        (
            "BANKNIFTY",
            "NIFTY",
        ),
    ),

    (
        "Compare BANK NIFTY and NIFTY",
        (
            "BANKNIFTY",
            "NIFTY",
        ),
    ),

    (
        "Open NIFTY 50 and SENSEX",
        (
            "NIFTY",
            "SENSEX",
        ),
    ),

    (
        "Open crude oil and NIFTY",
        (
            "CRUDEOIL",
            "NIFTY",
        ),
    ),

    (
        "Open NIFTY and crude oil",
        (
            "NIFTY",
            "CRUDEOIL",
        ),
    ),

    (
        "Compare BTC ETH and SOL",
        (
            "BTC",
            "ETH",
            "SOL",
        ),
    ),
)


for command, expected in cases:

    actual = (
        probe
        ._symbols(
            command
        )
    )


    if actual != expected:

        raise RuntimeError(
            repr(
                command
            )
            + ": "
            + repr(
                actual
            )
            + " != "
            + repr(
                expected
            )
        )


    print(
        "PASS:",
        command,
        "->",
        actual,
    )


# ============================================================
# 9. RUN FULL EMBEDDED V3.1 SUITE WITH PATCH
# ============================================================

print()
print("=" * 80)
print("PATCHED V3.1 TARGETED SUITE")
print("=" * 80)


after, after_output = (
    run_embedded_suite(
        patched_orchestrator
    )
)


print(
    after_output.rstrip()
)


if (
    after.failures
    or after.errors
):

    print()
    print("=" * 80)
    print("PATCHED TARGETED SUITE FAILED")
    print("=" * 80)


    for test, traceback_text in (
        list(
            after.failures
        )
        + list(
            after.errors
        )
    ):

        print()
        print(
            "FAILED:",
            test.id(),
        )


        for line in (
            traceback_text
            .strip()
            .splitlines()
            [
                -15:
            ]
        ):

            print(
                line
            )


    print()
    print(
        "Installer modified:",
        "NO",
    )


    raise SystemExit(
        4
    )


print()
print(
    "Targeted tests:",
    f"{after.testsRun}/{after.testsRun}",
)

print(
    "Failures:",
    0,
)

print(
    "Errors:",
    0,
)


# ============================================================
# 10. PATCH INSTALLER USING EXACT EXTRACTED SOURCE
# ============================================================

count = installer_text.count(
    orchestrator_source
)


if count != 1:

    raise RuntimeError(
        "Expected exact embedded orchestrator once; "
        + str(
            count
        )
        + " found."
    )


repaired_installer = (
    installer_text.replace(
        orchestrator_source,
        patched_orchestrator,
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
    "Embedded orchestrator patched:",
    "YES",
)

print(
    "Production application files changed:",
    "NO",
)


# ============================================================
# 11. COMPILE REPAIRED INSTALLER
# ============================================================

result = subprocess.run(
    [
        str(
            PYTHON
        ),

        "-m",
        "py_compile",

        str(
            INSTALLER
        ),
    ],
    cwd=ROOT,
)


if result.returncode:

    shutil.copy2(
        backup,
        INSTALLER,
    )


    raise RuntimeError(
        "Repaired installer failed compilation. "
        "Installer backup restored."
    )


print(
    "Installer syntax:",
    "PASS",
)


# ============================================================
# 12. FINAL PRE-INSTALL PRODUCTION CHECK
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


print(
    "Protected Core before install:",
    "PASS",
)

print(
    "Broker execution before install:",
    "BLOCKED",
)


print()
print("=" * 80)
print("VERIFIED V3.1 REPAIR READY")
print("=" * 80)

print(
    "Original failure reproduced:",
    "YES",
)

print(
    "Failure repaired:",
    "YES",
)

print(
    "Patched embedded suite:",
    f"{after.testsRun}/{after.testsRun}",
)

print(
    "Installer compile:",
    "PASS",
)

print(
    "Safe to install:",
    "YES",
)
