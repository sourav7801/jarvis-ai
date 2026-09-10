from __future__ import annotations

"""Launch the protected V8 Master with the V16 unified workstation bridge.

V16 adds workstation services and the internal professional trading gateway,
but preserves the verified V12->V15 intelligence lineage first. Paper entry
sessions remain explicit and live broker execution remains locked.
"""

import os
import webbrowser

# Workstation boot may restore/monitor paper positions, but it may not arm new
# entries without an explicit paper-session action.
os.environ["JARVIS_AUTO_PAPER_START"] = "0"
os.environ["JARVIS_V12_AUTO_PAPER_START"] = "0"


def main() -> int:
    from workstation.v12_runtime_bridges import install_v12_runtime_bridges
    from workstation.v13_runtime_bridges import install_v13_runtime_bridges
    from workstation.v14_runtime_bridges import install_v14_runtime_bridges
    from workstation.v141_runtime_bridges import install_v141_runtime_bridges
    from workstation.v15_runtime_bridges import install_v15_runtime_bridges
    from omni.v16_capability_registry import install_v16_capabilities
    from workstation.jarvis_os_v16_bridge import HOST, PORT, create_server

    v12 = install_v12_runtime_bridges()
    v13 = install_v13_runtime_bridges()
    v14 = install_v14_runtime_bridges()
    v141 = install_v141_runtime_bridges()
    v15 = install_v15_runtime_bridges()
    capabilities = install_v16_capabilities()

    server = create_server(HOST, PORT)
    url = f"http://{HOST}:{PORT}"
    print("=" * 76)
    print("JARVIS V16 - UNIFIED AUTONOMOUS WORKSTATION")
    print("=" * 76)
    print(f"Master: {url}")
    print(f"Canonical tools: {capabilities['registry']['tool_count']}")
    print("Managed Files + Verified Artifacts + Projects: ENABLED")
    print("Protected Master identity: V8 UNIFIED INTELLIGENCE")
    print("V15 autonomous market reasoning:", "READY" if v15.get("installed") else "DEGRADED")
    print("V14.1 verified risk geometry:", "READY" if v141.get("installed") else "DEGRADED")
    print("V14 continuous execution:", "READY" if v14.get("installed") else "DEGRADED")
    print("V13 contextual bridge:", "READY" if v13.get("installed") else "DEGRADED")
    print("V12 adaptive bridge:", "READY" if v12.get("installed") else "DEGRADED")
    print("Trading gateway: SAME-ORIGIN /api/v16/trading/*")
    print("Paper entry sessions: EXPLICIT START ONLY")
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
