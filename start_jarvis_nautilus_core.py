from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "data" / "logs" / "nautilus_core_v52_launcher.log"


def _write_failure(text: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(text, encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    try:
        from workstation.nautilus_core_service import main as service_main

        service_main()
    except Exception:
        detail = traceback.format_exc()
        _write_failure(detail)
        print(detail, file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
