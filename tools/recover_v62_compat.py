from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "tools" / "recover_v62_from_adaptive.py"
COMPAT_INTEGRATOR = ROOT / "tools" / "integrate_quant_v6_adaptive_v62.py"

spec = importlib.util.spec_from_file_location("jarvis_v62_recovery", RECOVERY)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load recovery module: {RECOVERY}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def run_compat_integrator(py: Path) -> None:
    print("PATCH > V6.2 compatibility integration preserving the complete V6.1 system")
    module.run(str(py), str(COMPAT_INTEGRATOR))


# The original recovery driver still owns branch checks, additive file copying,
# backup creation, validation, targeted/full regressions, commit, push and
# automatic rollback. We replace only its obsolete V5-era anchor integrator.
module.run_integrators = run_compat_integrator

if __name__ == "__main__":
    raise SystemExit(module.main())
