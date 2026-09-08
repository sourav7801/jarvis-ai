from __future__ import annotations


def main() -> int:
    """Install V12/V13/V14/V14.1 paper intelligence before protected V8 Master."""

    from workstation.v12_runtime_bridges import install_v12_runtime_bridges
    from workstation.v13_runtime_bridges import install_v13_runtime_bridges
    from workstation.v14_runtime_bridges import install_v14_runtime_bridges
    from workstation.v141_runtime_bridges import install_v141_runtime_bridges

    v12 = install_v12_runtime_bridges()
    v13 = install_v13_runtime_bridges()
    v14 = install_v14_runtime_bridges()
    v141 = install_v141_runtime_bridges()

    from workstation import jarvis_os_v8
    from workstation.jarvis_os_v141_bridge import create_server as create_v141_bridge_server

    jarvis_os_v8.create_server = create_v141_bridge_server

    print("JARVIS V14.1 Master risk-geometry bridge:", "READY" if v141.get("installed") else "DEGRADED")
    print("V14 continuous execution bridge:", "READY" if v14.get("installed") else "DEGRADED")
    print("V13 contextual compatibility bridge:", "READY" if v13.get("installed") else "DEGRADED")
    print("V12 adaptive compatibility bridge:", "READY" if v12.get("installed") else "DEGRADED")
    print("Risk geometry: VERIFIED COMPLETED-BAR EVIDENCE / LEGACY QUALIFICATION NOT REQUIRED")
    print("Paper decision authority: POSITIVE CONTEXTUAL EXPECTED VALUE / CONTINUOUS RISK")
    print("Protected Master identity: V8 UNIFIED INTELLIGENCE")
    print("V12 authority endpoint: /api/v12/paper-authority")
    print("V13 authority endpoint: /api/v13/paper-authority")
    print("V14 authority endpoint: /api/v14/paper-authority")
    print("V14.1 authority endpoint: /api/v14.1/paper-authority")
    print("Live broker execution: LOCKED")

    from start_jarvis_v3 import main as protected_master_main

    result = protected_master_main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
