(() => {
  "use strict";

  if (!window.JARVIS_V17_RUNTIME || window.JARVIS_V17_DATA_PLANE) return;

  const nativeFetch = window.fetch.bind(window);
  const limits = Object.freeze({ live: 2, history: 2, module: 1 });
  const active = { live: 0, history: 0, module: 0 };
  const queues = { live: [], history: [], module: [] };
  const pending = new Map();
  const caches = {
    live: new Map(),
    canonical: new Map(),
    history: new Map(),
    module: new Map(),
  };
  const cacheTtl = { live: 4000, canonical: 1200, history: 15000, module: 5000 };
  const activeTasks = new Set();

  let currentGeneration = 0;
  let currentWorkspace = "INTRADAY";
  let sequence = 0;

  const metrics = {
    started: 0,
    completed: 0,
    failed: 0,
    superseded: 0,
    cacheHits: 0,
    singleFlightHits: 0,
    timeouts: 0,
    slowRequests: 0,
    workspaceTransitions: 0,
    lastWorkspaceTransitionAt: null,
    lastSlowRequest: null,
  };

  const CANONICAL_PATHS = new Set([
    "/api/v16/trading/workspace-state",
    "/api/v17/trading/status",
  ]);

  function requestInfo(input, init = {}) {
    const method = String(init.method || (input && input.method) || "GET").toUpperCase();
    if (method !== "GET") return null;
    const raw = typeof input === "string" ? input : input?.url;
    if (!raw) return null;
    try {
      const url = new URL(raw, window.location.href);
      if (url.origin !== window.location.origin) return null;
      const priority = Number(init.jarvisPriority);
      return {
        method,
        url,
        path: url.pathname,
        key: `${url.pathname}?${url.searchParams.toString()}`,
        priority: Number.isFinite(priority) ? priority : null,
        generation: Number.isFinite(Number(init.jarvisGeneration)) ? Number(init.jarvisGeneration) : null,
        scope: String(init.jarvisScope || ""),
      };
    } catch {
      return null;
    }
  }

  function classify(info) {
    if (CANONICAL_PATHS.has(info.path)) return "canonical";
    if (info.path === "/api/candles") return "history";
    if (info.path === "/api/live") return "live";
    if (info.path === "/api/terminal/module") return "module";
    return null;
  }

  function defaultPriority(kind) {
    if (kind === "canonical") return 1;
    if (kind === "history") return 2;
    if (kind === "live") return 3;
    if (kind === "module") return 4;
    return 5;
  }

  function responseEntry(response, body) {
    return {
      at: Date.now(),
      body,
      status: response.status,
      statusText: response.statusText,
      headers: [...response.headers.entries()],
    };
  }

  function cachedResponse(entry) {
    return new Response(entry.body, {
      status: entry.status,
      statusText: entry.statusText,
      headers: entry.headers,
    });
  }

  function supersededError() {
    const error = new DOMException("REQUEST_SUPERSEDED", "AbortError");
    try { error.code = "REQUEST_SUPERSEDED"; } catch {}
    return error;
  }

  function cacheFor(kind) {
    return caches[kind] || null;
  }

  function freshCache(kind, key) {
    const cache = cacheFor(kind);
    if (!cache) return null;
    const entry = cache.get(key);
    if (!entry || Date.now() - entry.at >= cacheTtl[kind]) return null;
    metrics.cacheHits += 1;
    return entry;
  }

  function sanitizeInit(init = {}, signal) {
    const clean = {...init, signal};
    delete clean.jarvisPriority;
    delete clean.jarvisGeneration;
    delete clean.jarvisScope;
    return clean;
  }

  function taskKey(kind, info) {
    return `${kind}:${info.key}`;
  }

  function shouldSupersede(task) {
    return task.scope === "workspace"
      && Number.isFinite(task.generation)
      && task.generation < currentGeneration;
  }

  function settleSuperseded(task) {
    metrics.superseded += 1;
    if (pending.get(task.pendingKey) === task) pending.delete(task.pendingKey);
    task.reject(supersededError());
  }

  function pump(kind) {
    const queue = queues[kind];
    const max = limits[kind];
    while (active[kind] < max && queue.length) {
      queue.sort((a,b) => a.priority - b.priority || a.seq - b.seq);
      const task = queue.shift();
      if (task.externalSignal?.aborted || shouldSupersede(task)) {
        settleSuperseded(task);
        continue;
      }

      active[kind] += 1;
      activeTasks.add(task);
      task.startedAt = performance.now();
      const controller = new AbortController();
      task.controller = controller;
      const onAbort = () => controller.abort();
      if (task.externalSignal) {
        if (task.externalSignal.aborted) controller.abort();
        else task.externalSignal.addEventListener("abort", onAbort, {once:true});
      }

      metrics.started += 1;
      nativeFetch(task.input, sanitizeInit(task.init, controller.signal))
        .then(async response => {
          const body = await response.clone().text();
          if (response.ok) cacheFor(kind)?.set(task.info.key, responseEntry(response, body));
          task.resolve(response);
        })
        .catch(error => {
          if (controller.signal.aborted && (shouldSupersede(task) || task.externalSignal?.aborted)) {
            metrics.superseded += 1;
            task.reject(supersededError());
          } else {
            metrics.failed += 1;
            if (error?.name === "AbortError") metrics.timeouts += 1;
            task.reject(error);
          }
        })
        .finally(() => {
          const elapsed = performance.now() - task.startedAt;
          if (elapsed > (kind === "history" ? 8000 : 2000)) {
            metrics.slowRequests += 1;
            metrics.lastSlowRequest = {
              path: task.info.path,
              key: task.info.key,
              workspace: currentWorkspace,
              generation: task.generation,
              elapsed_ms: Math.round(elapsed),
              finished_at: new Date().toISOString(),
            };
          }
          if (task.externalSignal) task.externalSignal.removeEventListener("abort", onAbort);
          activeTasks.delete(task);
          active[kind] -= 1;
          if (pending.get(task.pendingKey) === task) pending.delete(task.pendingKey);
          metrics.completed += 1;
          pump(kind);
        });
    }
  }

  function queuedFetch(kind, input, init, info) {
    const cached = freshCache(kind, info.key);
    if (cached) return Promise.resolve(cachedResponse(cached));

    const key = taskKey(kind, info);
    const existing = pending.get(key);
    if (existing && !(existing.scope === "workspace" && existing.generation < currentGeneration)) {
      metrics.singleFlightHits += 1;
      return existing.promise.then(response => response.clone());
    }

    if (existing && existing.controller) {
      try { existing.controller.abort(); } catch {}
    }

    let resolveTask, rejectTask;
    const promise = new Promise((resolve,reject) => { resolveTask=resolve; rejectTask=reject; });
    const task = {
      seq: ++sequence,
      kind,
      input,
      init,
      info,
      pendingKey: key,
      priority: info.priority ?? defaultPriority(kind),
      generation: info.generation,
      scope: info.scope,
      externalSignal: init?.signal || input?.signal || null,
      resolve: resolveTask,
      reject: rejectTask,
      promise,
      controller: null,
      startedAt: 0,
    };
    pending.set(key, task);
    queues[kind].push(task);
    pump(kind);
    return promise.then(response => response.clone());
  }

  function canonicalFetch(input, init, info) {
    const cached = freshCache("canonical", info.key);
    if (cached) return Promise.resolve(cachedResponse(cached));

    const key = taskKey("canonical", info);
    const existing = pending.get(key);
    if (existing) {
      metrics.singleFlightHits += 1;
      return existing.promise.then(response => response.clone());
    }

    const controller = new AbortController();
    const externalSignal = init?.signal || input?.signal || null;
    const onAbort = () => controller.abort();
    if (externalSignal) {
      if (externalSignal.aborted) controller.abort();
      else externalSignal.addEventListener("abort", onAbort, {once:true});
    }

    const startedAt = performance.now();
    metrics.started += 1;
    const promise = nativeFetch(input, sanitizeInit(init, controller.signal))
      .then(async response => {
        const body = await response.clone().text();
        if (response.ok) caches.canonical.set(info.key, responseEntry(response, body));
        return response;
      })
      .catch(error => {
        metrics.failed += 1;
        throw error;
      })
      .finally(() => {
        if (externalSignal) externalSignal.removeEventListener("abort", onAbort);
        const elapsed = performance.now() - startedAt;
        if (elapsed > 2000) {
          metrics.slowRequests += 1;
          metrics.lastSlowRequest = {
            path: info.path,
            key: info.key,
            workspace: currentWorkspace,
            generation: info.generation,
            elapsed_ms: Math.round(elapsed),
            finished_at: new Date().toISOString(),
          };
        }
        metrics.completed += 1;
        pending.delete(key);
      });

    pending.set(key, {promise,scope:info.scope,generation:info.generation,controller});
    return promise.then(response => response.clone());
  }

  function beginWorkspace(workspace, generation) {
    currentWorkspace = String(workspace || "INTRADAY").toUpperCase();
    currentGeneration = Number.isFinite(Number(generation)) ? Number(generation) : currentGeneration + 1;
    metrics.workspaceTransitions += 1;
    metrics.lastWorkspaceTransitionAt = new Date().toISOString();

    for (const kind of ["history","module","live"]) {
      const keep = [];
      for (const task of queues[kind]) {
        if (shouldSupersede(task)) settleSuperseded(task);
        else keep.push(task);
      }
      queues[kind].splice(0, queues[kind].length, ...keep);
    }
    for (const task of [...activeTasks]) {
      if (shouldSupersede(task)) {
        try { task.controller?.abort(); } catch {}
      }
    }
    return currentGeneration;
  }

  window.fetch = function v17UnifiedFetch(input, init = {}) {
    const info = requestInfo(input, init);
    if (!info) return nativeFetch(input, init);
    const kind = classify(info);
    if (!kind) return nativeFetch(input, sanitizeInit(init, init?.signal || input?.signal));
    if (kind === "canonical") return canonicalFetch(input, init, info);
    return queuedFetch(kind, input, init, info);
  };

  function snapshot() {
    return {
      version: "17.4",
      workspace: currentWorkspace,
      generation: currentGeneration,
      active: {...active},
      queued: {
        live: queues.live.length,
        history: queues.history.length,
        module: queues.module.length,
      },
      pending: pending.size,
      cache_entries: {
        live: caches.live.size,
        canonical: caches.canonical.size,
        history: caches.history.size,
        module: caches.module.size,
      },
      metrics: {...metrics},
      limits: {...limits},
      writesIntercepted: false,
    };
  }

  const api = Object.freeze({
    version: "17.4",
    beginWorkspace,
    snapshot,
    maxConcurrentLive: limits.live,
    maxConcurrentHistory: limits.history,
    maxConcurrentModule: limits.module,
    liveCacheMs: cacheTtl.live,
    canonicalCacheMs: cacheTtl.canonical,
    historyCacheMs: cacheTtl.history,
    liveScope: "/api/live",
    canonicalReadScopes: [...CANONICAL_PATHS],
    writesIntercepted: false,
  });

  window.JARVIS_V17_DATA_PLANE = api;
  window.JARVIS_V17_LIVE_FETCH_SCHEDULER = api;
})();
