(() => {
  "use strict";

  // V17 browser transport governor.
  // - /api/live stays bounded so market-data polling cannot consume every
  //   localhost connection.
  // - canonical read-only trading state is deduplicated briefly but bypasses
  //   the live queue entirely, so safety/control observers keep a free lane.
  // This file never intercepts POSTs or changes execution authority.
  if (!window.JARVIS_V17_RUNTIME || window.JARVIS_V17_LIVE_FETCH_SCHEDULER) return;

  const nativeFetch = window.fetch.bind(window);
  const MAX_CONCURRENT_LIVE_READS = 2;
  const LIVE_CACHE_MS = 4000;
  const CANONICAL_CACHE_MS = 1200;
  const CANONICAL_PATHS = new Set([
    "/api/v16/trading/workspace-state",
    "/api/v17/trading/status",
  ]);

  const liveQueue = [];
  const livePending = new Map();
  const liveCache = new Map();
  const canonicalPending = new Map();
  const canonicalCache = new Map();
  let activeLive = 0;

  function requestInfo(input, init = {}) {
    const method = String(init.method || (input && input.method) || "GET").toUpperCase();
    if (method !== "GET") return null;
    const raw = typeof input === "string" ? input : input?.url;
    if (!raw) return null;
    try {
      const url = new URL(raw, window.location.href);
      if (url.origin !== window.location.origin) return null;
      return {
        path: url.pathname,
        key: `${url.pathname}?${url.searchParams.toString()}`,
      };
    } catch {
      return null;
    }
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

  function pumpLive() {
    while (activeLive < MAX_CONCURRENT_LIVE_READS && liveQueue.length) {
      const task = liveQueue.shift();
      if (task.signal?.aborted) {
        livePending.delete(task.key);
        task.reject(new DOMException("The operation was aborted.", "AbortError"));
        continue;
      }
      activeLive += 1;
      nativeFetch(task.input, task.init)
        .then(async response => {
          const body = await response.clone().text();
          if (response.ok) liveCache.set(task.key, responseEntry(response, body));
          task.resolve(response);
        })
        .catch(task.reject)
        .finally(() => {
          activeLive -= 1;
          livePending.delete(task.key);
          pumpLive();
        });
    }
  }

  function canonicalFetch(input, init, key) {
    const cached = canonicalCache.get(key);
    if (cached && Date.now() - cached.at < CANONICAL_CACHE_MS) {
      return Promise.resolve(cachedResponse(cached));
    }
    const existing = canonicalPending.get(key);
    if (existing) return existing.then(response => response.clone());

    // Canonical state is intentionally not queued behind /api/live.  Multiple
    // observers share one in-flight GET, but writes/control POSTs never enter
    // this path.
    const task = nativeFetch(input, init)
      .then(async response => {
        const body = await response.clone().text();
        if (response.ok) canonicalCache.set(key, responseEntry(response, body));
        return response;
      })
      .finally(() => canonicalPending.delete(key));
    canonicalPending.set(key, task);
    return task.then(response => response.clone());
  }

  window.fetch = function v17BoundedFetch(input, init = {}) {
    const info = requestInfo(input, init);
    if (!info) return nativeFetch(input, init);

    if (CANONICAL_PATHS.has(info.path)) {
      return canonicalFetch(input, init, info.key);
    }
    if (info.path !== "/api/live") {
      return nativeFetch(input, init);
    }

    const cached = liveCache.get(info.key);
    if (cached && Date.now() - cached.at < LIVE_CACHE_MS) {
      return Promise.resolve(cachedResponse(cached));
    }

    const existing = livePending.get(info.key);
    if (existing) return existing.then(response => response.clone());

    const task = new Promise((resolve, reject) => {
      liveQueue.push({
        input,
        init,
        key: info.key,
        signal: init?.signal || input?.signal,
        resolve,
        reject,
      });
      pumpLive();
    });
    livePending.set(info.key, task);
    return task.then(response => response.clone());
  };

  window.JARVIS_V17_LIVE_FETCH_SCHEDULER = Object.freeze({
    maxConcurrentLive: MAX_CONCURRENT_LIVE_READS,
    liveCacheMs: LIVE_CACHE_MS,
    canonicalCacheMs: CANONICAL_CACHE_MS,
    liveScope: "/api/live",
    canonicalReadScopes: [...CANONICAL_PATHS],
    writesIntercepted: false,
  });
})();
