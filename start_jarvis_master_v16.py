"""Launch protected V8 Master with the V16 unified workstation bridge."""
from __future__ import annotations

import os
import webbrowser

from omni.v16_capability_registry import install_v16_capabilities
from workstation.jarvis_os_v16_bridge import HOST, PORT, create_server


# V16 preserves the V8 Master identity and layers workstation services above it.
# Trading remains PAPER / RESEARCH; live broker execution is locked.

def main() -> int:
    capabilities = install_v16_capabilities()
    server = create_server(HOST, PORT)
    url = f"http://{HOST}:{PORT}"
    print("=" * 76)
    print("JARVIS V16 - UNIFIED AUTONOMOUS WORKSTATION")
    print("=" * 76)
    print(f"Master: {url}")
    print(f"Canonical tools: {capabilities['registry']['tool_count']}")
    print("Managed Files + Verified Artifacts + Projects: ENABLED")
    print("Protected V8 Master + verified V15 reasoning: PRESERVED")
    print("Live broker execution: LOCKED")
    if str(os.getenv("JARVIS_NO_BROWSER", "")).strip().lower() not in {"1", "true", "yes"}:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
