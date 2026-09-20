from pathlib import Path
import unittest


class V17UnifiedDataPlaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.scheduler_js = (
            cls.project_root
            / "workstation"
            / "quant_terminal_v2_static"
            / "v17_live_fetch_scheduler.js"
        ).read_text(encoding="utf-8")
        cls.app_js = (
            cls.project_root
            / "workstation"
            / "quant_terminal_v2_static"
            / "app.js"
        ).read_text(encoding="utf-8")
        cls.router_js = (
            cls.project_root
            / "workstation"
            / "quant_terminal_v2_static"
            / "v16_workspace_router.js"
        ).read_text(encoding="utf-8")
        cls.terminal_http = (
            cls.project_root / "workstation" / "v17_terminal_http.py"
        ).read_text(encoding="utf-8")

    def test_scheduler_only_governs_read_only_local_requests(self):
        self.assertIn("method !== \"GET\"", self.scheduler_js)
        self.assertIn("if (url.origin !== window.location.origin) return null;", self.scheduler_js)
        self.assertIn("writesIntercepted: false", self.scheduler_js)
        self.assertIn("return nativeFetch(input, sanitizeInit", self.scheduler_js)

    def test_scheduler_bounds_history_live_and_module_reads(self):
        self.assertIn("const limits = Object.freeze({ live: 2, history: 2, module: 1 });", self.scheduler_js)
        self.assertIn('if (info.path === "/api/candles") return "history";', self.scheduler_js)
        self.assertIn('if (info.path === "/api/live") return "live";', self.scheduler_js)
        self.assertIn('if (info.path === "/api/terminal/module") return "module";', self.scheduler_js)
        self.assertIn("metrics.singleFlightHits += 1", self.scheduler_js)
        self.assertIn("window.JARVIS_V17_DATA_PLANE = api", self.scheduler_js)

    def test_canonical_state_reads_are_deduplicated_and_not_queued_behind_live(self):
        self.assertIn('"/api/v16/trading/workspace-state"', self.scheduler_js)
        self.assertIn('"/api/v17/trading/status"', self.scheduler_js)
        self.assertIn('if (kind === "canonical") return canonicalFetch', self.scheduler_js)
        self.assertIn("caches.canonical.set", self.scheduler_js)

    def test_module_pending_responses_are_not_cached(self):
        self.assertIn("A module response can legitimately be {pending:true}", self.scheduler_js)
        self.assertIn('if (cacheResponse && kind === "module")', self.scheduler_js)
        self.assertIn("cacheResponse = parsed?.pending !== true", self.scheduler_js)

    def test_workspace_generation_supersedes_obsolete_requests(self):
        self.assertIn("function beginWorkspace(workspace, generation)", self.scheduler_js)
        self.assertIn("task.generation < currentGeneration", self.scheduler_js)
        self.assertIn("REQUEST_SUPERSEDED", self.scheduler_js)
        self.assertIn("controller?.abort()", self.scheduler_js)
        self.assertIn("beginWorkspaceTransition(name)", self.app_js)
        self.assertIn("workspaceAbortController.abort", self.app_js)

    def test_app_preserves_workspace_chart_runtime(self):
        self.assertIn("const workspaceRuntimes=new Map()", self.app_js)
        self.assertIn("function stashWorkspaceRuntime()", self.app_js)
        self.assertIn("function restoreWorkspaceRuntime(name,generation)", self.app_js)
        self.assertIn("void mountCharts(generation,{progressive:true})", self.app_js)
        self.assertIn("await loadSlot(order[0],generation,1)", self.app_js)

    def test_options_chain_is_lazy_cancellable_and_cached(self):
        self.assertIn("const chainCache = new Map()", self.router_js)
        self.assertIn("const CHAIN_CACHE_MS = 15000", self.router_js)
        self.assertIn("chainAbortController.abort()", self.router_js)
        self.assertIn("queueMicrotask(()=>void refreshState(true))", self.router_js)
        self.assertIn("setTimeout(()=>void loadChain(),25)", self.router_js)
        self.assertIn("for (let attempt = 0; attempt < 30; attempt++)", self.router_js)
        self.assertIn("},10000);", self.router_js)

    def test_options_runtime_does_not_own_generic_autonomy_poll(self):
        autonomy_js = (self.project_root / "workstation" / "quant_terminal_v2_static" / "v16_autonomy_runtime.js").read_text(encoding="utf-8")
        self.assertIn('=== "OPTIONS") return;', autonomy_js)

    def test_options_selection_does_not_reload_generic_chart(self):
        self.assertNotIn("syncUnderlyingChartContext(); renderCapability();", self.router_js)
        self.assertIn("loadChain({force:true}); refreshState(true);", self.router_js)

    def test_v17_runtime_does_not_observe_entire_document(self):
        runtime_js = (self.project_root / "workstation" / "quant_terminal_v2_static" / "v17_runtime.js").read_text(encoding="utf-8")
        self.assertNotIn("observer.observe(document.body", runtime_js)
        self.assertIn("observerHost", runtime_js)

    def test_v17_http_cache_busts_v174_assets_and_has_diagnostics(self):
        self.assertIn('/app.js?v=170403', self.terminal_http)
        self.assertIn('/v17_live_fetch_scheduler.js?v=170403', self.terminal_http)
        self.assertIn('/v16_workspace_router.js?v=170403', self.terminal_http)
        self.assertIn('/v17_runtime.js?v=170403', self.terminal_http)
        self.assertIn('/api/v17/diagnostics/performance', self.terminal_http)
        self.assertIn('"version": "17.4.1"', self.terminal_http)


if __name__ == "__main__":
    unittest.main()
