from __future__ import annotations


def main() -> int:
    """Install V12 paper intelligence before launching the protected V8 Master.

    The Master home/UI and deterministic V8 command contract are preserved. A
    read-only V12 authority endpoint is installed so the supervisor can prove
    this process has adaptive paper-command routing instead of adopting an older
    V8 listener. Live broker execution remains unavailable.
    """

    from workstation.v12_runtime_bridges import install_v12_runtime_bridges

    bridges = install_v12_runtime_bridges()

    # start_jarvis_v3 imports create_server from this module inside main().
    # Rebinding only that factory preserves the V8 handler behavior and home
    # identity while adding /api/v12/paper-authority for runtime ownership.
    from workstation import jarvis_os_v8
    from workstation.jarvis_os_v12_bridge import create_server as create_v12_bridge_server

    jarvis_os_v8.create_server = create_v12_bridge_server

    print("JARVIS V12 Master adaptive bridge:", "READY" if bridges.get("success") else "DEGRADED")
    print("Paper decision authority: ADAPTIVE EXPECTED VALUE / OUTCOME LEARNING")
    print("Protected Master identity: V8 UNIFIED INTELLIGENCE")
    print("V12 authority endpoint: /api/v12/paper-authority")
    print("Live broker execution: LOCKED")

    from start_jarvis_v3 import main as protected_master_main

    result = protected_master_main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
