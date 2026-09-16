(() => {
  "use strict";

  // V17 UI-only transport governor. It does not touch server-side scanners,
  // strategy cadence, or execution logic; it only prevents the browser from
  // bursting many identical /api/live reads at the local market-data bridge.
  if (!window.JARVIS_V17_RUNTIME || window.JARVIS_V17_LIVE_FETCH_SCHEDULER) return;

  const nativeFetch = window.fetch.bind(window);
  const MAX_CONCURRENT_LIVE_READS = 2;
  const LIVE_CACHE_MS = 2200;
  const queue = [];
  const pending = new Map();
  const cache = new Map();
  let active = 0;

  function liveKey(input, init = {}) {
    const method = String(init.method || (input && input.method) || "GET").toUpperCase();
    if (method !== "GET") return null;
    let raw = typeof input === "string" ? input : input?.url;
    if (!raw) return null;
    try {
      const url = new URL(raw, window.location.href);
      if (url.origin !== window.location.origin || url.pathname !== "/api/live") return null;
      return `${url.pathname}?${url.searchParams.toString()}`;
    } catch {
      return null;
    }
  }

  function cachedResponse(entry) {
    return new Response(entry.body, {
      status: entry.status,
      statusText: entry.statusText,
      headers: entry.headers,
    });
  }

  function pump() {
    while (active < MAX_CONCURRENT_LIVE_READS && queue.length) {
      const task = queue.shift();
      if (task.signal?.aborted) {
        pending.delete(task.key);
        task.reject(new DOMException("The operation was aborted.", "AbortError"));
        continue;
      }
      active += 1;
      nativeFetch(task.input, task.init)
        .then(async response => {
          const body = await response.clone().text();
          cache.set(task.key, {
            at: Date.now(),
            body,
            status: response.status,
            statusText: response.statusText,
            headers: [...response.headers.entries()],
          });
          task.resolve(response);
        })
        .catch(task.reject)
        .finally(() => {
          active -= 1;
          pending.delete(task.key);
          pump();
        });
    }
  }

  window.fetch = function v17BoundedFetch(input, init = {}) {
    const key = liveKey(input, init);
    if (!key) return nativeFetch(input, init);

    const cached = cache.get(key);
    if (cached && Date.now() - cached.at < LIVE_CACHE_MS) {
      return Promise.resolve(cachedResponse(cached));
    }

    const existing = pending.get(key);
    if (existing) return existing.then(response => response.clone());

    const task = new Promise((resolve, reject) => {
      queue.push({ input, init, key, signal: init?.signal || input?.signal, resolve, reject });
      pump();
    });
    pending.set(key, task);
    return task.then(response => response.clone());
  };

  window.JARVIS_V17_LIVE_FETCH_SCHEDULER = Object.freeze({
    maxConcurrent: MAX_CONCURRENT_LIVE_READS,
    cacheMs: LIVE_CACHE_MS,
    scope: "/api/live",
  });
})();
