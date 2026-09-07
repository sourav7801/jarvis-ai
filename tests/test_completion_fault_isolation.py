from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch

from omni.loopback_http import exclusive_server
from workstation import completion_console as console


class CompletionFaultIsolationTests(unittest.TestCase):
    def collector(self):
        from omni.subsystem_snapshot import SubsystemSnapshotCollector
        return SubsystemSnapshotCollector(max_inflight=4)

    def test_failure_does_not_hide_healthy_subsystem(self):
        def broken():
            raise RuntimeError('provider failed')
        result = self.collector().collect({'good': lambda: {'count': 9}, 'bad': broken}, timeout=1)
        self.assertEqual(result['good']['data']['count'], 9)
        self.assertTrue(result['good']['healthy'])
        self.assertEqual(result['bad']['state'], 'FAILED')
        self.assertFalse(result['bad']['healthy'])
        self.assertIsNone(result['bad']['data'])
        self.assertTrue(result['bad']['last_updated'])

    def test_timeout_reuses_inflight_work_and_recovers(self):
        release = threading.Event()
        calls = []
        def slow():
            calls.append(1)
            release.wait(3)
            return {'done': True}
        collector = self.collector()
        try:
            started = time.monotonic()
            for _ in range(3):
                result = collector.collect({'slow': slow, 'good': lambda: {'count': 2}}, timeout=.03)
                self.assertEqual(result['slow']['state'], 'TIMEOUT')
                self.assertIsNone(result['slow']['last_updated'])
                self.assertEqual(result['good']['data']['count'], 2)
            self.assertLess(time.monotonic() - started, .75)
            self.assertEqual(len(calls), 1)
            release.set()
            result = collector.collect({'slow': slow}, timeout=1)
            self.assertEqual(result['slow']['state'], 'READY')
            self.assertTrue(result['slow']['data']['done'])
        finally:
            release.set()

    def test_explicit_unhealthy_payload_is_not_ready(self):
        result = self.collector().collect({'service': lambda: {'success': False, 'error': 'offline'}}, timeout=1)
        self.assertFalse(result['service']['healthy'])
        self.assertEqual(result['service']['state'], 'DEGRADED')

    def test_overview_http_survives_failed_import_and_preserves_safety(self):
        def missing():
            raise ModuleNotFoundError('optional subsystem')
        providers = {'completion': lambda: {'items': []}, 'executive': missing,
                     'memory': lambda: {'records': 3}}
        server = exclusive_server('127.0.0.1', 0, console.CompletionHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        with patch.object(console, '_overview_providers', return_value=providers), \
             patch.object(console, 'SNAPSHOTS', self.collector()):
            thread.start()
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_address[1]}/api/overview', timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    result = json.load(response)
                self.assertTrue(result['success'])
                self.assertEqual(result['overall'], 'DEGRADED')
                self.assertFalse(result['subsystems']['executive']['healthy'])
                self.assertIsNone(result['executive'])
                self.assertEqual(result['memory']['data']['records'], 3)
                self.assertTrue(result['safety']['paper_only'])
                self.assertFalse(result['safety']['live_execution'])
                self.assertFalse(result['safety']['automatic_broker_order'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)


if __name__ == '__main__':
    unittest.main()
