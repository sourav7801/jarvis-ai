from __future__ import annotations

import socket
import threading
import time
import webbrowser

from pathlib import (
    Path,
)


ROOT = Path(
    __file__
).resolve().parent


def port_open(
    port,
):

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    sock.settimeout(
        .25
    )


    try:

        return (
            sock.connect_ex(
                (
                    "127.0.0.1",
                    int(
                        port
                    ),
                )
            )
            == 0
        )


    finally:

        sock.close()


def main():

    started = time.perf_counter()
    last_stage = started

    def stage(name):
        nonlocal last_stage
        now = time.perf_counter()
        print(
            f"STARTUP > {name}: "
            f"+{now - last_stage:.3f}s "
            f"(total {now - started:.3f}s)"
        )
        last_stage = now

    print("=" * 76)
    print("JARVIS OS V3.2 — ADAPTIVE WORKSPACE")
    print("=" * 76)


    import main as jarvis_main

    stage("main import")

    from omni.core_integrity import (
        verify_protected_core,
    )


    core = verify_protected_core()

    stage("protected core verification")


    if not core.ok:

        raise RuntimeError(
            "Protected Core validation failed."
        )


    trading = (
        jarvis_main
        .jarvis_trading_v8_status()
    )

    stage("trading safety status")


    if trading[
        "live_execution"
    ] is not False:

        raise RuntimeError(
            "Live execution safety invariant failed."
        )


    if trading[
        "automatic_broker_order"
    ] is not False:

        raise RuntimeError(
            "Broker-order safety invariant failed."
        )


    print("Protected Core: PASS")
    print("Master JARVIS: READY")
    print("Adaptive workspace: READY")
    print("Native chart terminal: READY")
    print("Live broker execution: LOCKED")


    from workstation.jarvis_os_v3 import (
        HOST,
        PORT,
        create_server,
    )

    stage("workspace server import")


    if port_open(
        PORT
    ):

        raise RuntimeError(
            "JARVIS OS port 8797 is already in use. "
            "Close the previous JARVIS process first."
        )


    server = create_server(
        HOST,
        PORT,
    )

    stage("HTTP server creation")


    url = (
        f"http://{HOST}:{PORT}"
    )


    print(
        "JARVIS OS:",
        url
    )

    stage("CORE READY")


    def open_browser():

        time.sleep(
            .7
        )


        webbrowser.open(
            url
        )


    threading.Thread(
        target=open_browser,
        daemon=True,
    ).start()


    try:

        server.serve_forever()


    except KeyboardInterrupt:

        print()
        print(
            "Stopping JARVIS..."
        )


    finally:

        server.server_close()


    print(
        "JARVIS stopped."
    )


if __name__ == "__main__":

    main()
