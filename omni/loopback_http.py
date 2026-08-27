from __future__ import annotations

import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Type


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """Fail closed when another local JARVIS service owns the port."""

    allow_reuse_address = False
    allow_reuse_port = False
    daemon_threads = True

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_EXCLUSIVEADDRUSE,
                1,
            )
        super().server_bind()


def exclusive_server(
    host: str,
    port: int,
    handler: Type[BaseHTTPRequestHandler],
) -> ExclusiveThreadingHTTPServer:
    return ExclusiveThreadingHTTPServer((host, int(port)), handler)
