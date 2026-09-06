"""JARVIS V7 runtime wrapper.

V7 preserves the V6.2 stale-Quant ownership preflight, then extends the bounded
canonical supervisor with the Project Completion Center on port 8799.  No
broker client or order API is imported here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jarvis_runtime_supervisor import (  # noqa: E402
    JarvisRuntimeSupervisor,
    ManagedService,
    default_services,
)
from scripts.jarvis_runtime_supervisor_v62 import reclaim_obsolete_quant_listener  # noqa: E402


def v7_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    existing = list(default_services(root))
    python = str(Path(sys.executable).resolve())
    completion = root / "start_jarvis_completion_console.py"
    if completion.exists():
        existing.append(
            ManagedService(
                name="completion",
                argv=(python, str(completion)),
                health_url="http://127.0.0.1:8799/api/health",
                expected_service="JARVIS_COMPLETION_CENTER",
                port=8799,
            )
        )
    return tuple(existing)


def main() -> int:
    print("JARVIS V7 runtime preflight...")
    result = reclaim_obsolete_quant_listener()
    print("Quant ownership preflight:", result.get("action"))
    print("Starting V7 supervised services including Project Completion Center.")
    print("Paper/research mode only. Live broker execution remains locked.")
    browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {
        "1", "true", "yes", "on"
    }
    return JarvisRuntimeSupervisor(
        root=ROOT,
        services=v7_services(ROOT),
        browser=browser,
    ).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
