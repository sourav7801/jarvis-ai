"""Guards the interpreter/venv contract for the active JARVIS runtime.

Regression cover for the ``.venv`` corruption found during the master
blueprint audit: ``.venv`` was rebuilt with ``python -m venv --upgrade``
from ``.venv-new``, which moved the interpreter from CPython 3.13 to
CPython 3.12 in place and left 102 compiled extension modules behind
with a ``cp313`` ABI tag.  Nothing imported them at collection time, so
the whole suite still reported green while matplotlib, statsmodels,
numba, SQLAlchemy, duckdb, PyAudio, RapidFuzz, arch and Bottleneck were
all unimportable at runtime.

These tests fail loudly on that class of breakage instead of letting it
surface as a mid-session runtime error.
"""

import importlib
import os
import re
import sysconfig
import unittest
from pathlib import Path


ABI_TAG_PATTERN = re.compile(
    r"\.cp(\d{2,3})-",
)


SITE_PACKAGES = Path(
    sysconfig.get_paths()["purelib"]
)


CURRENT_ABI_TAG = "cp{major}{minor}".format(
    major=os.sys.version_info.major,
    minor=os.sys.version_info.minor,
)


# Packages whose compiled extensions are load bearing for JARVIS.
# Each entry maps the import name to the capability it unblocks so a
# failure message points at the affected subsystem, not just a module.
CRITICAL_BINARY_MODULES = {
    "numpy": "numeric core for every feature/indicator computation",
    "pandas": "candle and feature frames",
    "matplotlib": "chart rendering",
    "statsmodels": "walk-forward and regression validation",
    "arch": "volatility models",
    "bottleneck": "rolling-window acceleration",
    "numba": "hot-path acceleration",
    "sqlalchemy": "persistent portfolio and journal storage",
    "duckdb": "analytical store for research datasets",
    "pyaudio": "voice capture",
    "rapidfuzz": "speech/typo repair for the command router",
    "lxml": "web research parsing",
    "xxhash": "content hashing for caches and provenance",
    "zstandard": "compressed history storage",
}


class EnvironmentAbiIntegrityTests(unittest.TestCase):

    @unittest.skipUnless(
        os.name == "nt",
        "Windows CPython ABI tag layout",
    )
    def test_no_orphaned_extension_modules(self):
        """No compiled extension may target a foreign CPython ABI.

        An extension tagged for another interpreter version is only a
        problem when no correctly tagged sibling exists next to it, so
        the check compares against the sibling rather than flagging
        every foreign tag.
        """

        orphans = []

        for module in SITE_PACKAGES.rglob("*.pyd"):

            match = ABI_TAG_PATTERN.search(module.name)

            if match is None:
                continue

            tag = "cp{digits}".format(
                digits=match.group(1),
            )

            if tag == CURRENT_ABI_TAG:
                continue

            sibling = module.with_name(
                module.name.replace(
                    tag,
                    CURRENT_ABI_TAG,
                )
            )

            if sibling.exists():
                continue

            orphans.append(
                module.relative_to(
                    SITE_PACKAGES
                ).as_posix()
            )

        self.assertEqual(
            orphans,
            [],
            msg=(
                "site-packages holds compiled modules for a foreign "
                f"CPython ABI (expected {CURRENT_ABI_TAG}). Reinstall "
                "the owning distributions with the active interpreter: "
                f"{sorted(orphans)[:20]}"
            ),
        )

    def test_critical_binary_modules_import(self):
        """Every load-bearing compiled dependency must import."""

        failures = []

        for name, capability in sorted(
            CRITICAL_BINARY_MODULES.items()
        ):

            try:
                importlib.import_module(name)

            except Exception as error:
                failures.append(
                    f"{name} ({capability}): "
                    f"{type(error).__name__}: {error}"
                )

        self.assertEqual(
            failures,
            [],
            msg=(
                "compiled dependencies failed to import, so the "
                "listed JARVIS capabilities are silently unavailable: "
                + " | ".join(failures)
            ),
        )

    def test_test_runner_is_declared_as_a_dependency(self):
        """pytest is configured in pyproject and must be declared.

        ``[tool.pytest.ini_options]`` existed while pytest was absent
        from every requirements file and from all five virtualenvs, so
        the documented regression suite could not be executed at all.
        """

        root = Path(__file__).resolve().parent.parent

        declared = ""

        for candidate in (
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-nautilus.txt",
        ):

            manifest = root / candidate

            if manifest.exists():
                declared += manifest.read_text(
                    encoding="utf-8"
                ).lower()

        self.assertIn(
            "pytest",
            declared,
            msg=(
                "pyproject.toml configures pytest but no requirements "
                "file declares it; the suite is not reproducible"
            ),
        )


if __name__ == "__main__":
    unittest.main()
