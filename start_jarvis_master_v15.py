from __future__ import annotations


def main() -> int:
    """Install V12 through V15 paper intelligence before protected V8 Master."""

    from workstation.v12_runtime_bridges import install_v12_runtime_bridges
    from workstation.v13_runtime_bridges import install_v13_runtime_bridges
    from workstation.v14_runtime_bridges import install_v14_runtime_bridges
    from workstation.v141_runtime_bridges import install_v141_runtime_bridges
    from workstation.v15_runtime_bridges import install_v15_runtime_bridges

    v12 = install_v12_runtime_bridges()
    v13 = install_v13_runtime_bridges()
    v14 = install_v14_runtime_bridges()
    v141 = install_v141_runtime_bridges()
    v15 = install_v15_runtime_bridges()

    from workstation import jarvis_os_v8
    from workstation.jarvis_os_v15_bridge import create_server as create_v15_bridge_server

    jarvis_os_v8.create_server = create_v15_bridge_server

    print("JARVIS V15 Master autonomous market reasoning bridge:", "READY" if v15.get("installed") else "DEGRADED")
    print("V14.1 verified risk geometry bridge:", "READY" if v141.get("installed") else "DEGRADED")
    print("V14 continuous execution bridge:", "READY" if v14.get("installed") else "DEGRADED")
    print("V13 contextual compatibility bridge:", "READY" if v13.get("installed") else "DEGRADED")
    print("V12 adaptive compatibility bridge:", "READY" if v12.get("installed") else "DEGRADED")
    print("Paper decision authority: PORTFOLIO-ADJUSTED CONTEXTUAL UTILITY / CONTINUOUS RISK")
    print("Protected Master identity: V8 UNIFIED INTELLIGENCE")
    print("V15 authority endpoint: /api/v15/paper-authority")
    print("Live broker execution: LOCKED")

    from start_jarvis_v3 import main as protected_master_main

    result = protected_master_main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
