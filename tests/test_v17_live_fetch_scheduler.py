from pathlib import Path
import unittest


class V17LiveFetchSchedulerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.scheduler_js = (
            cls.project_root
            / "workstation"
            / "quant_terminal_v2_static"
            / "v17_live_fetch_scheduler.js"
        ).read_text(encoding="utf-8")
        cls.terminal_http = (
            cls.project_root / "workstation" / "v17_terminal_http.py"
        ).read_text(encoding="utf-8")

    def test_scheduler_only_governs_read_only_local_requests(self):
        self.assertIn(
            "if (!window.JARVIS_V17_RUNTIME || window.JARVIS_V17_LIVE_FETCH_SCHEDULER) return;",
            self.scheduler_js,
        )
        self.assertIn('method !== "GET"', self.scheduler_js)
        self.assertIn('if (url.origin !== window.location.origin) return null;', self.scheduler_js)
        self.assertIn('if (info.path !== "/api/live")', self.scheduler_js)
        self.assertIn("return nativeFetch(input, init);", self.scheduler_js)
        self.assertIn("writesIntercepted: false", self.scheduler_js)

    def test_scheduler_bounds_live_reads_and_coalesces_duplicates(self):
        self.assertIn("const MAX_CONCURRENT_LIVE_READS = 2;", self.scheduler_js)
        self.assertIn("const LIVE_CACHE_MS = 4000;", self.scheduler_js)
        self.assertIn(
            "while (activeLive < MAX_CONCURRENT_LIVE_READS && liveQueue.length)",
            self.scheduler_js,
        )
        self.assertIn("const existing = livePending.get(info.key);", self.scheduler_js)
        self.assertIn("if (existing) return existing.then", self.scheduler_js)
        self.assertIn("liveCache.set(task.key", self.scheduler_js)
        self.assertIn(
            "window.fetch = function v17BoundedFetch", self.scheduler_js
        )

    def test_canonical_state_reads_bypass_live_queue_and_are_deduplicated(self):
        self.assertIn("const CANONICAL_CACHE_MS = 1200;", self.scheduler_js)
        self.assertIn('"/api/v16/trading/workspace-state"', self.scheduler_js)
        self.assertIn('"/api/v17/trading/status"', self.scheduler_js)
        self.assertIn("const existing = canonicalPending.get(key);", self.scheduler_js)
        self.assertIn("return canonicalFetch(input, init, info.key);", self.scheduler_js)
        self.assertIn("canonicalPending.set(key, task);", self.scheduler_js)

    def test_v17_http_injects_scheduler_before_runtime(self):
        self.assertIn(
            '<script>window.JARVIS_V16_CANONICAL=true;window.JARVIS_V17_RUNTIME=true;window.JARVIS_V17_SINGLE_OPTION_CONTROLLER=true;</script>',
            self.terminal_http,
        )
        scheduler_injection = self.terminal_http.index("/v17_live_fetch_scheduler.js")
        runtime_injection = self.terminal_http.index("/v17_runtime.js")
        self.assertLess(scheduler_injection, runtime_injection)
        self.assertIn(
            "window.JARVIS_V17_SINGLE_OPTION_CONTROLLER=true", self.terminal_http
        )


if __name__ == "__main__":
    unittest.main()
