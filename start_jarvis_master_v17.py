from __future__ import annotations

"""Launch protected JARVIS Master with the V17 unified workstation bridge."""

import os

# Autonomous option selection starts only after a paper workspace is explicitly
# armed. Existing positions remain monitorable from process boot.
os.environ["JARVIS_AUTO_PAPER_START"] = "0"
os.environ["JARVIS_V12_AUTO_PAPER_START"] = "0"
os.environ["JARVIS_V17_AUTONOMOUS_OPTIONS"] = "1"
os.environ["JARVIS_LIVE_EXECUTION"] = "0"


def main() -> int:
    from workstation.v12_runtime_bridges import install_v12_runtime_bridges
    from workstation.v13_runtime_bridges import install_v13_runtime_bridges
    from workstation.v14_runtime_bridges import install_v14_runtime_bridges
    from workstation.v141_runtime_bridges import install_v141_runtime_bridges
    from workstation.v15_runtime_bridges import install_v15_runtime_bridges
    from omni.v16_capability_registry import install_v16_capabilities

    v12 = install_v12_runtime_bridges()
    v13 = install_v13_runtime_bridges()
    v14 = install_v14_runtime_bridges()
    v141 = install_v141_runtime_bridges()
    v15 = install_v15_runtime_bridges()
    capabilities = install_v16_capabilities()

    # Protected start_jarvis_v3 still owns core verification and the Master
    # lifecycle. V17 changes only the workstation server factory.
    from workstation import jarvis_os_v8
    from workstation.jarvis_os_v17_bridge import create_server as create_v17_bridge_server

    jarvis_os_v8.create_server = create_v17_bridge_server

    print("JARVIS V17 unified workstation bridge: READY")
    print(f"Canonical tools: {capabilities['registry']['tool_count']}")
    print("Protected Master identity: V8 UNIFIED INTELLIGENCE")
    print("V15 autonomous market reasoning:", "READY" if v15.get("installed") else "DEGRADED")
    print("V14.1 verified risk geometry:", "READY" if v141.get("installed") else "DEGRADED")
    print("V14 continuous execution:", "READY" if v14.get("installed") else "DEGRADED")
    print("V13 contextual bridge:", "READY" if v13.get("installed") else "DEGRADED")
    print("V12 adaptive bridge:", "READY" if v12.get("installed") else "DEGRADED")
    print("Trading gateway: V17 supervised professional PAPER terminal")
    print("Autonomous option selection: ENABLED after paper session START")
    print("Live broker execution: LOCKED")

    from start_jarvis_v3 import main as protected_master_main

    result = protected_master_main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
