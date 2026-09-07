from __future__ import annotations


def main() -> int:
    """Install V12 process-local paper intelligence before protected V8 Master.

    The Master surface itself remains the verified V8 Unified Intelligence OS on
    port 8797. This wrapper changes only process-local paper-command authority;
    it does not alter the protected Master HTTP identity and never enables live
    broker execution.
    """

    from workstation.v12_runtime_bridges import install_v12_runtime_bridges

    bridges = install_v12_runtime_bridges()
    print("JARVIS V12 Master adaptive bridge:", "READY" if bridges.get("success") else "DEGRADED")
    print("Paper decision authority: ADAPTIVE EXPECTED VALUE / OUTCOME LEARNING")
    print("Protected Master identity: V8 UNIFIED INTELLIGENCE")
    print("Live broker execution: LOCKED")

    from start_jarvis_v3 import main as protected_master_main

    result = protected_master_main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
