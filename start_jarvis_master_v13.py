from __future__ import annotations


def main() -> int:
    """Install V12/V13 process-local paper intelligence before protected V8 Master.

    The Master HTTP/UI identity on 8797 remains the verified V8 Unified
    Intelligence surface. Only paper-command authority is upgraded process
    locally; no live broker execution or production rewrite capability is added.
    """

    from workstation.v12_runtime_bridges import install_v12_runtime_bridges
    from workstation.v13_runtime_bridges import install_v13_runtime_bridges
    from workstation.jarvis_os_v12_bridge import install_master_v12_bridge

    v12 = install_v12_runtime_bridges()
    v13 = install_v13_runtime_bridges()
    master_bridge = install_master_v12_bridge()
    print("JARVIS V13 Master contextual bridge:", "READY" if v13.get("installed") else "DEGRADED")
    print("V12 compatibility bridge:", "READY" if v12.get("installed") else "DEGRADED")
    print("V12 Master authority endpoint:", "READY" if master_bridge.get("installed") else "DEGRADED")
    print("Paper decision authority: CONTEXTUAL EXPECTED VALUE / OUTCOME MEMORY")
    print("Protected Master identity: V8 UNIFIED INTELLIGENCE")
    print("Live broker execution: LOCKED")

    # start_jarvis_v3 remains the protected V8 Master launcher contract.
    from start_jarvis_v3 import main as protected_master_main

    result = protected_master_main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
