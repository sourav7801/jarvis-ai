(() => {
  "use strict";

  if (!window.JARVIS_V17_RUNTIME || window.__JARVIS_V17_RUNTIME__) return;
  window.__JARVIS_V17_RUNTIME__ = true;

  const $ = id => document.getElementById(id);

  function ensureStyle() {
    if ($("v17RuntimeStyle")) return;
    const style = document.createElement("style");
    style.id = "v17RuntimeStyle";
    style.textContent = `
      .v17-runtime-pill{font-size:10px;letter-spacing:.08em;padding:7px 10px;border-radius:999px;border:1px solid #2c8b63;color:#84f3b3;background:linear-gradient(135deg,rgba(20,87,62,.78),rgba(16,57,80,.72));box-shadow:0 0 18px rgba(84,242,173,.10)}
      .v17-runtime-pill[data-state="degraded"]{border-color:#7a662b;color:#ffd166;background:rgba(77,58,14,.6)}
      .v17-runtime-pill[data-state="error"]{border-color:#7a3141;color:#ff8da0;background:rgba(89,27,42,.55)}
      .v17-runtime-banner{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;border:1px solid #2d7b59;background:linear-gradient(90deg,#071b1d,#081725);padding:7px 9px;border-radius:7px;margin:0 0 6px}
      .v17-runtime-banner strong{font-size:10px;color:#8af2b6;letter-spacing:.08em}.v17-runtime-banner span{display:block;margin-top:2px;font-size:8px;color:#8fb7c5}
      .v17-runtime-badges{display:flex;gap:5px;align-items:center;justify-content:flex-end;flex-wrap:wrap}.v17-runtime-badges b{font-size:9px;color:#dffaff;border:1px solid #24576d;border-radius:999px;padding:5px 7px;white-space:nowrap}
      .v17-runtime-badges b[data-state="connected"]{border-color:#2c8b63;color:#84f3b3}.v17-runtime-badges b[data-state="stale"],.v17-runtime-badges b[data-state="reconnecting"]{border-color:#7a662b;color:#ffd166}.v17-runtime-badges b[data-state="failed"],.v17-runtime-badges b[data-state="unavailable"]{border-color:#7a3141;color:#ff8da0}
    `;
    document.head.appendChild(style);
  }

  function setText(node, value) {
    if (node && node.textContent !== value) node.textContent = value;
  }

  function brandStaticSurface() {
    if (document.title !== "JARVIS Quant V17 · Autonomous Options") {
      document.title = "JARVIS Quant V17 · Autonomous Options";
    }
    setText(document.querySelector(".brand span"), "V17 AUTONOMOUS OPTIONS RUNTIME · PAPER / RESEARCH");

    const status = document.querySelector(".top-status");
    if (status && !$("v17RuntimePill")) {
      const pill = document.createElement("span");
      pill.id = "v17RuntimePill";
      pill.className = "v17-runtime-pill";
      pill.dataset.state = "degraded";
      pill.textContent = "V17 · VERIFYING";
      status.prepend(pill);
    }

    const workspace = document.querySelector(".workspace");
    if (workspace && !$("v17RuntimeBanner")) {
      const banner = document.createElement("section");
      banner.id = "v17RuntimeBanner";
      banner.className = "v17-runtime-banner";
      banner.innerHTML = `
        <div><strong>JARVIS V17 · AUTONOMOUS OPTIONS CONVERGENCE</strong><span id="v17RuntimeSummary">Verifying route, provider freshness, strategy and canonical Paper Desk.</span></div>
        <div class="v17-runtime-badges">
          <b id="v17RuntimeMode">PAPER ONLY</b>
          <b id="v17RouteState">INTRADAY</b>
          <b id="v17FeedState" data-state="disconnected">FYERS · DISCONNECTED</b>
        </div>`;
      const modes = document.querySelector(".workspace-modes");
      if (modes) modes.insertAdjacentElement("afterend", banner);
      else workspace.prepend(banner);
    }

    const footer = document.querySelector("footer span");
    if (footer && !String(footer.textContent || "").includes("V17")) {
      footer.textContent = "JARVIS Quant V17 · route-aware provider health · V15 reasoning core · V14.1 verified risk geometry · canonical Paper Desk · live execution locked";
    }
  }

  function relabelInheritedLineage() {
    const card = $("v15ReasoningCard");
    const eyebrow = card?.querySelector(".eyebrow");
    if (eyebrow) {
      const raw = String(eyebrow.textContent || "");
      let symbol = "";
      if (raw.startsWith("V15 AUTONOMOUS MARKET REASONING ·")) {
        symbol = raw.split("·").pop().trim();
      } else if (raw.startsWith("V17 AUTONOMOUS OPTIONS · V15 REASONING CORE ·")) {
        symbol = raw.split("·").pop().trim();
      }
      const desired = `V17 AUTONOMOUS OPTIONS · V15 REASONING CORE${symbol ? ` · ${symbol}` : ""}`;
      setText(eyebrow, desired);
    }

    const reason = $("signalReason");
    if (reason && /^V15\s/i.test(String(reason.textContent || ""))) {
      setText(reason, String(reason.textContent).replace(/^V15\s/i, "V17 · V15 reasoning core · "));
    }

    const autoPrimary = $("v16AutonomyPrimary");
    if (autoPrimary) {
      const eyebrowNode = autoPrimary.querySelector(".eyebrow");
      if (eyebrowNode && !String(eyebrowNode.textContent || "").includes("V17")) {
        setText(eyebrowNode, "PRIMARY WORKFLOW · JARVIS V17");
      }
      setText(autoPrimary.querySelector(".v16-auto-head b"), "AUTONOMOUS OPTIONS PAPER TRADING");
    }
  }

  function activeWorkspace() {
    return String(document.querySelector(".workspace-modes button.active")?.dataset.workspace || "INTRADAY").toUpperCase();
  }

  async function readStatus() {
    const workspace = activeWorkspace();
    const response = await fetch(`/api/v17/trading/status?workspace=${encodeURIComponent(workspace)}`, {cache: "no-store"});
    let payload = {};
    try { payload = await response.json(); } catch {}
    if (!response.ok || payload.success !== true) throw new Error(payload.reason || `HTTP ${response.status}`);
    return payload;
  }

  function normalizeFeedState(status) {
    const stream = status?.market_data?.stream || {};
    if (stream.state) return String(stream.state).toUpperCase();
    if (stream.connected === true) return stream.fresh === false ? "STALE" : "CONNECTED";
    return stream.running ? "RECONNECTING" : "DISCONNECTED";
  }

  function renderStatus(status) {
    const pill = $("v17RuntimePill");
    if (pill) {
      pill.dataset.state = "ok";
      setText(pill, "V17 · ACTIVE");
      pill.title = `${status.service || "JARVIS V17"} · ${status.decision_source || "VERIFIED DATA"}`;
    }

    const route = status.route || {};
    const requested = String(route.requested_workspace || status.workspace || activeWorkspace()).toUpperCase();
    const execution = String(route.execution_workspace || status.execution_workspace || requested).toUpperCase();
    const feedState = normalizeFeedState(status);
    const feed = status?.market_data?.stream || {};

    setText($("v17RouteState"), requested);
    const feedNode = $("v17FeedState");
    if (feedNode) {
      feedNode.dataset.state = feedState.toLowerCase();
      setText(feedNode, `FYERS · ${feedState}`);
      const retry = Number(feed.retry_in_seconds);
      feedNode.title = Number.isFinite(retry) && retry > 0
        ? `Read-only market data · reconnect in ~${retry.toFixed(1)}s`
        : "Read-only FYERS market-data WebSocket · broker orders disabled";
    }

    const summary = $("v17RuntimeSummary");
    if (summary) {
      const underlyings = Array.isArray(status.verified_auto_option_underlyings)
        ? status.verified_auto_option_underlyings.join(" / ")
        : "NIFTY / BANKNIFTY / SENSEX";
      const routeText = requested === execution ? requested : `${requested} → ${execution} execution`;
      const feedText = feedState === "CONNECTED"
        ? "FYERS stream fresh"
        : feedState === "STALE"
          ? "FYERS stream stale — new autonomous entries stay fail-closed"
          : `FYERS stream ${feedState.toLowerCase()} — REST/history paths may still be available`;
      setText(summary, `${routeText} · ${feedText}. Automatic verified PAPER options: ${underlyings}.`);
    }

    setText($("v17RuntimeMode"), status.live_execution ? "LIVE" : "PAPER ONLY");
    window.JARVIS_V17_STATUS = status;
    relabelInheritedLineage();
  }

  function renderFailure(error) {
    const pill = $("v17RuntimePill");
    if (pill) {
      pill.dataset.state = "error";
      setText(pill, "V17 · STATUS ERROR");
      pill.title = String(error?.message || error || "V17 status unavailable");
    }
    const feedNode = $("v17FeedState");
    if (feedNode) {
      feedNode.dataset.state = "unavailable";
      setText(feedNode, "FYERS · UNKNOWN");
    }
    setText($("v17RuntimeSummary"), "V17 shell loaded, but the runtime-status endpoint is unavailable. Trading gates remain fail-closed.");
  }

  async function refresh() {
    try {
      renderStatus(await readStatus());
    } catch (error) {
      renderFailure(error);
    }
  }

  function boot() {
    ensureStyle();
    brandStaticSurface();
    relabelInheritedLineage();
    refresh();
    setInterval(refresh, 5000);

    const observer = new MutationObserver(() => relabelInheritedLineage());
    observer.observe(document.body, {subtree: true, childList: true, characterData: true});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
