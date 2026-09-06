(() => {
  "use strict";

  const allowedLoopback = new Set(["127.0.0.1", "localhost"]);

  function safeWorkspaceUrl(value) {
    try {
      const url = new URL(String(value || ""), window.location.origin);
      if (url.origin === window.location.origin) return url.href;
      if (allowedLoopback.has(url.hostname)) return url.href;
    } catch (_) {}
    return null;
  }

  const previousExecuteWorkspaceActions = window.executeWorkspaceActions;
  window.executeWorkspaceActions = function executeWorkspaceActionsV8(actions) {
    const normal = [];
    for (const action of (actions || [])) {
      if (action && action.type === "open_url") {
        const target = safeWorkspaceUrl(action.url);
        if (target) {
          window.open(target, action.target || "_blank", "noopener");
        }
        continue;
      }
      normal.push(action);
    }
    if (typeof previousExecuteWorkspaceActions === "function") {
      previousExecuteWorkspaceActions(normal);
    }
  };

  async function refreshExecutiveStatus() {
    try {
      const payload = await window.api("/api/executive/status");
      const last = payload.last_plan || null;
      const route = document.getElementById("activeRoute");
      if (route && last && last.domain) {
        route.title = `V8 Executive · ${last.domain} · ${last.mode}`;
      }
      document.documentElement.dataset.jarvisExecutive = "ready";
    } catch (_) {
      document.documentElement.dataset.jarvisExecutive = "degraded";
    }
  }

  const masterState = document.getElementById("masterState");
  if (masterState) masterState.title = "JARVIS V8 Unified Executive Control Plane";

  refreshExecutiveStatus();
  setInterval(refreshExecutiveStatus, 15000);
})();
