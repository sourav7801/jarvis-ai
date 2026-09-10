from __future__ import annotations

"""One-command acceptance launcher for the full JARVIS V16 workstation.

This is intentionally separate from JARVIS.bat until the local Windows
acceptance gate passes. It starts the supervised 8797 Master + internal 8787
professional paper terminal as one product.
"""

from scripts.jarvis_runtime_supervisor_v16 import main


if __name__ == "__main__":
    raise SystemExit(main())
