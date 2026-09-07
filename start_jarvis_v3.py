from __future__ import annotations

import socket
import os
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from pathlib import (
    Path,
)


ROOT = Path(
    __file__
).resolve().parent

MASTER_HOST = "127.0.0.1"
MASTER_PORT = 8797


def browser_enabled():
    return str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}


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


def existing_jarvis_master(
    host=MASTER_HOST,
    port=MASTER_PORT,
):
    """Verify that an occupied port belongs to the local Master dashboard."""

    try:
        request = urllib.request.Request(
            f"http://{host}:{int(port)}/",
            headers={"Accept": "text/html"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=1.5) as response:
            if response.status != 200:
                return False
            source = response.read(256_000).decode("utf-8", errors="replace")
    except (OSError, ValueError, urllib.error.URLError):
        return False

    return (
        "JARVIS" in source
        and "OMNI OPERATING COMMAND CENTER" in source
        and "window.JARVIS_TOKEN" in source
    )


def open_existing_master(
    host=MASTER_HOST,
    port=MASTER_PORT,
):
    url = f"http://{host}:{int(port)}"
    print("Master JARVIS is already running. Opening the existing dashboard.")
    print("JARVIS OS:", url)
    if browser_enabled():
        webbrowser.open(url)


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
    print("JARVIS OS V8 - UNIFIED INTELLIGENCE OS")
    print("=" * 76)

    if port_open(MASTER_PORT):
        if existing_jarvis_master():
            open_existing_master()
            return
        raise RuntimeError(
            "Port 8797 is occupied by an unrecognized process. "
            "JARVIS will not stop or replace it automatically."
        )


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
    print("Unified executive control plane: READY")
    print("Adaptive workspace: READY")
    print("Native chart terminal: READY")
    print("Live broker execution: LOCKED")


    from workstation.jarvis_os_v8 import (
        HOST,
        PORT,
        create_server,
    )

    # Preserve the profiler contract name while the imported server is V8.
    stage("workspace server import")


    if port_open(
        PORT
    ):
        if existing_jarvis_master(HOST, PORT):
            open_existing_master(HOST, PORT)
            return
        raise RuntimeError(
            "JARVIS OS port 8797 became occupied by an unrecognized process."
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


    if browser_enabled():
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
