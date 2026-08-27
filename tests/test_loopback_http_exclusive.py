from __future__ import annotations

import unittest
from http.server import BaseHTTPRequestHandler

from omni.loopback_http import exclusive_server


class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        return


class ExclusiveLoopbackServerTests(unittest.TestCase):
    def test_second_server_cannot_share_an_active_port(self):
        first = exclusive_server("127.0.0.1", 0, QuietHandler)
        try:
            port = int(first.server_address[1])
            with self.assertRaises(OSError):
                exclusive_server("127.0.0.1", port, QuietHandler)
        finally:
            first.server_close()

    def test_server_contract_disables_address_and_port_reuse(self):
        server = exclusive_server("127.0.0.1", 0, QuietHandler)
        try:
            self.assertFalse(server.allow_reuse_address)
            self.assertFalse(server.allow_reuse_port)
            self.assertTrue(server.daemon_threads)
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()
