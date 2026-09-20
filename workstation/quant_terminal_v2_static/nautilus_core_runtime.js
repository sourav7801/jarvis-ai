(() => {
  const CORE_URL = "http://127.0.0.1:8792/health";
  let badge = null;

  function ensureBadge() {
    if (badge) return badge;
    const topbar = document.querySelector("header") || document.querySelector(".topbar") || document.body;
    badge = document.createElement("div");
    badge.id = "nautilus-core-badge";
    badge.textContent = "NAUTILUS · CHECKING";
    badge.style.cssText = [
      "position:fixed",
      "top:12px",
      "right:430px",
      "z-index:9999",
      "padding:7px 11px",
      "border:1px solid #315064",
      "border-radius:16px",
      "background:#07131b",
      "color:#79cfff",
      "font:11px/1.2 monospace",
      "letter-spacing:.06em",
      "pointer-events:none"
    ].join(";");
    topbar.appendChild(badge);
    return badge;
  }

  async function refresh() {
    const el = ensureBadge();
    try {
      const response = await fetch(CORE_URL, { cache: "no-store" });
      const payload = await response.json();
      if (payload.engine_ready) {
        el.textContent = `NAUTILUS · ${payload.nautilus_version || "READY"}`;
        el.style.color = "#77f7aa";
        el.style.borderColor = "#2f6f50";
      } else if (["STARTING", "PROBING"].includes(String(payload.phase || "").toUpperCase())) {
        el.textContent = `NAUTILUS · ${String(payload.phase).toUpperCase()}`;
        el.style.color = "#ffd166";
        el.style.borderColor = "#7a662b";
      } else {
        el.textContent = "NAUTILUS · OFFLINE";
        el.style.color = "#ffb35c";
        el.style.borderColor = "#7a5730";
        el.title = payload.error || "NautilusTrader engine is unavailable.";
      }
    } catch (_error) {
      el.textContent = "NAUTILUS · OFFLINE";
      el.style.color = "#ff6f7d";
      el.style.borderColor = "#7d3440";
    }
  }

  window.JARVIS_NAUTILUS_CORE = {
    refresh,
    statusUrl: CORE_URL,
  };

  window.addEventListener("DOMContentLoaded", () => {
    ensureBadge();
    refresh();
    setInterval(refresh, 3000);
  });
})();
