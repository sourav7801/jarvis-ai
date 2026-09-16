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

    def test_scheduler_only_governs_live_get_requests(self):
        self.assertIn(
            "if (!window.JARVIS_V17_RUNTIME || window.JARVIS_V17_LIVE_FETCH_SCHEDULER) return;",
            self.scheduler_js,
        )
        self.assertIn('method !== "GET"', self.scheduler_js)
        self.assertIn('url.pathname !== "/api/live"', self.scheduler_js)
        self.assertIn("if (!key) return nativeFetch(input, init);", self.scheduler_js)

    def test_scheduler_bounds_concurrency_and_coalesces_duplicates(self):
        self.assertIn("const MAX_CONCURRENT_LIVE_READS = 2;", self.scheduler_js)
        self.assertIn("const LIVE_CACHE_MS = 2200;", self.scheduler_js)
        self.assertIn(
            "while (active < MAX_CONCURRENT_LIVE_READS && queue.length)",
            self.scheduler_js,
        )
        self.assertIn("const existing = pending.get(key);", self.scheduler_js)
        self.assertIn("if (existing) return existing.then", self.scheduler_js)
        self.assertIn("cache.set(task.key", self.scheduler_js)
        self.assertIn(
            "window.fetch = function v17BoundedFetch", self.scheduler_js
        )

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
