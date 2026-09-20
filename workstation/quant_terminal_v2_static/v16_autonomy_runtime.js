(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  const WORKSPACES = ["INTRADAY", "SWING", "INVESTMENT"];
  const INDEX_OPTION_UNDERLYINGS = new Set(["NIFTY", "BANKNIFTY", "SENSEX"]);
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
  const finite = value => {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const fmt = (value, digits = 2) => {
    const n = finite(value);
    return n === null ? "—" : n.toLocaleString("en-IN", {maximumFractionDigits: digits, minimumFractionDigits: digits});
  };

  let latestState = null;
  let pollTimer = null;
  let busy = false;

  function activeCapitalWorkspace() {
    try {
      const mode = String(activeWorkspace || "INTRADAY").toUpperCase();
      if (WORKSPACES.includes(mode)) return mode;
    } catch {}
    const optionCapital = $("v16OptionCapital")?.value;
    return WORKSPACES.includes(optionCapital) ? optionCapital : "INTRADAY";
  }

  async function requestJson(url, options = {}, timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {...options, signal: controller.signal, cache: "no-store"});
      let payload = {};
      try { payload = await response.json(); } catch {}
      if (!response.ok) throw new Error(payload.message || payload.reason || `HTTP ${response.status}`);
      return payload;
    } catch (error) {
      if (error?.name === "AbortError") throw new Error("Request timed out");
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  async function workspaceState(workspace) {
    return requestJson(`/api/v16/trading/workspace-state?workspace=${encodeURIComponent(workspace)}`);
  }

  function ensureStyles() {
    if ($("v16AutonomyConvergenceStyle")) return;
    const style = document.createElement("style");
    style.id = "v16AutonomyConvergenceStyle";
    style.textContent = `
      .v16-autonomy-primary{border:1px solid #1f5a6f;border-radius:9px;background:linear-gradient(180deg,#071a23,#07131b);padding:9px;margin:7px 0}
      .v16-auto-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.v16-auto-head>div{display:flex;flex-direction:column;gap:3px}.v16-auto-head b{font-size:17px;color:#e8faff}.v16-auto-head>span{border:1px solid #35566a;border-radius:999px;padding:5px 7px;font-size:8px;white-space:nowrap}.v16-auto-head>span[data-state="running"]{border-color:#2e8b61;color:#7cf0ad}.v16-auto-head>span[data-state="degraded"]{border-color:#7d6727;color:#ffd166}.v16-auto-sub{font-size:9px;line-height:1.45;color:#9bc0d0;margin:5px 0 7px}.v16-auto-pipeline{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px}.v16-auto-pipeline span{border:1px solid #183b4d;background:#061219;padding:5px;min-width:0}.v16-auto-pipeline small{display:block;color:#6e96a8;font-size:7px}.v16-auto-pipeline b{font-size:8px;color:#aee9ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v16-auto-actions{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:5px;margin-top:7px}.v16-auto-actions button{font-size:9px;padding:7px}.v16-auto-actions button:first-child{border-color:#42d98b;color:#8ff6ba;background:#0a281e;font-weight:700}.v16-auto-message{margin-top:6px;border-left:2px solid #4a8aa6;background:#061219;padding:6px;font-size:9px;line-height:1.4;color:#a9cddd}.v16-auto-message[data-kind="ok"]{border-color:#58d894;color:#8cecb5}.v16-auto-message[data-kind="warn"]{border-color:#ffd166;color:#dfcb82}.v16-auto-message[data-kind="error"]{border-color:#ff6f83;color:#ff9baa}.v16-auto-advanced{margin-top:6px;border:1px solid #153647;border-radius:6px}.v16-auto-advanced summary{padding:6px!important;font-size:8px!important}.v16-auto-advanced .v16-controls{display:flex!important;margin:0;padding:6px}.v16-auto-decision{margin:6px 0 8px;border:1px solid #205069;border-radius:7px;background:#06151d;padding:7px}.v16-auto-decision-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.v16-auto-decision-head strong{font-size:12px}.v16-auto-decision-head b{font-size:10px;padding:4px 6px;border-radius:5px;border:1px solid #66572d;color:#ffd166}.v16-auto-decision-head b.actionable,.v16-auto-decision-head b.open{border-color:#2c7d58;color:#78f2aa}.v16-auto-decision-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;margin-top:6px}.v16-auto-decision-grid span{border:1px solid #163746;background:#07131b;padding:5px;min-width:0}.v16-auto-decision-grid small{display:block;color:#6f94a4;font-size:7px}.v16-auto-decision-grid b{display:block;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v16-auto-why{margin-top:6px;font-size:8px;color:#9ec3d3;line-height:1.4}.v16-auto-why b{color:#d9f4ff}.v16-auto-why ul{margin:4px 0 0 15px;padding:0}.v16-auto-why li{margin:2px 0}.v16-auto-options-banner{display:flex;gap:8px;align-items:center;border:1px solid #246d4b;background:#082117;padding:6px 8px;margin-bottom:6px;border-radius:5px}.v16-auto-options-banner b{font-size:9px;color:#78f2aa}.v16-auto-options-banner span{font-size:8px;color:#a7cfc0}.v16-manual-override-toggle{width:100%;margin:5px 0;padding:5px!important;font-size:8px!important;border-style:dashed!important;color:#7997a5!important;background:#07131b!important}.v16-evidence-deck{border:1px solid #173849;border-radius:8px;margin:6px 0}.v16-evidence-deck>summary{padding:8px;font-size:9px;color:#9dcde2;cursor:pointer;letter-spacing:.06em}.v16-evidence-deck-body>.intel-card{margin:5px;border-color:#142f3e}.v16-evidence-deck-body .hero-card button{display:none}.v16-autonomy-converged #v16Canonical>.v16-controls{display:none!important}
      @media(max-width:1200px){.v16-auto-decision-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.v16-auto-pipeline{grid-template-columns:repeat(2,minmax(0,1fr))}}
    `;
    document.head.appendChild(style);
    document.documentElement.classList.add("v16-autonomy-converged");
  }

  function setMessage(text, kind = "") {
    const node = $("v16AutoMessage");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
  }

  function providerState(state, symbol = "") {
    const wanted = String(symbol || "").trim().toUpperCase();
    if (wanted) {
      const mark = state?.market_data?.marks?.[wanted];
      if (mark && typeof mark === "object") {
        if (mark.eligible_for_entry === true) return {degraded: false, label: "VERIFIED", symbol: wanted};
        const reason = String(mark.reason || "").toUpperCase();
        if (reason.includes("LOGIN")) return {degraded: true, label: "LOGIN REQUIRED", symbol: wanted};
        if (reason.includes("RATE") || reason.includes("429")) return {degraded: true, label: "RATE LIMITED", symbol: wanted};
        if (reason) return {degraded: true, label: reason.replaceAll("_", " "), symbol: wanted};
      }
      const row = (Array.isArray(state?.watchlist) ? state.watchlist : []).find(item => String(item?.symbol || "").toUpperCase() === wanted);
      if (row) {
        if (row.eligible_for_entry === true) return {degraded: false, label: "VERIFIED", symbol: wanted};
        const reason = String(row.reason || "").toUpperCase();
        if (reason.includes("LOGIN")) return {degraded: true, label: "LOGIN REQUIRED", symbol: wanted};
        if (reason.includes("RATE") || reason.includes("429")) return {degraded: true, label: "RATE LIMITED", symbol: wanted};
        if (reason) return {degraded: true, label: reason.replaceAll("_", " "), symbol: wanted};
      }
      return {degraded: false, label: "CANDIDATE VERIFIED", symbol: wanted};
    }
    const providers = Object.values(state?.market_data?.providers || {});
    if (!providers.length) return {degraded: false, label: "WAITING"};
    if (providers.some(item => String(item.state || "").toUpperCase() === "LOGIN_REQUIRED")) return {degraded: true, label: "LOGIN REQUIRED"};
    if (providers.some(item => String(item.state || "").toUpperCase() === "RATE_LIMITED")) return {degraded: true, label: "RATE LIMITED"};
    if (providers.some(item => String(item.state || "").toUpperCase() === "DEGRADED")) return {degraded: true, label: "DEGRADED"};
    return {degraded: false, label: "VERIFIED"};
  }

  function normalizedDirection(candidate) {
    const side = String(candidate?.side || "").toUpperCase();
    if (["LONG", "BUY", "BULLISH"].includes(side)) return "BULLISH";
    if (["SHORT", "SELL", "BEARISH"].includes(side)) return "BEARISH";
    return "—";
  }

  function optionPositionFor(state, underlying) {
    const positions = Array.isArray(state?.positions) ? state.positions : [];
    return positions.find(position => {
      const metadata = position?.metadata || {};
      const asset = String(position?.asset_type || metadata.asset_type || "").toUpperCase();
      if (asset !== "OPTION" && !metadata.option_type) return false;
      const explicit = String(metadata.underlying || "").toUpperCase();
      if (explicit) return explicit === underlying;
      const symbol = String(position?.symbol || "").toUpperCase();
      return underlying === "BANKNIFTY" ? symbol.includes("BANKNIFTY") : underlying === "SENSEX" ? symbol.includes("SENSEX") : symbol.includes("NIFTY") && !symbol.includes("BANKNIFTY");
    });
  }

  function decisionModel(state) {
    const session = state?.session || {};
    const candidates = Array.isArray(state?.scan_decisions?.candidates) ? state.scan_decisions.candidates : [];
    const actionable = candidates.find(item => String(item.stage || "").toUpperCase() === "ACTIONABLE");
    const candidate = actionable || candidates[0] || null;
    const candidateSymbol = String(candidate?.symbol || "").toUpperCase();
    const selectedUnderlying = String($("v16OptionUnderlying")?.value || "NIFTY").toUpperCase();
    const underlying = String(candidateSymbol || selectedUnderlying || "—").toUpperCase();
    const optionPosition = INDEX_OPTION_UNDERLYINGS.has(underlying) ? optionPositionFor(state, underlying) : null;
    const market = providerState(state, candidateSymbol || underlying);
    const running = String(session.entry_session || "").toUpperCase() === "RUNNING";
    const direction = normalizedDirection(candidate);
    const metadata = optionPosition?.metadata || {};
    const blockers = [];

    if (!running) blockers.push("Autonomous entry session is paused");
    if (session.reconciliation_ok === false) blockers.push("Canonical ledger reconciliation is not clean");
    if (market.degraded) blockers.push(`Market data is ${market.label.toLowerCase()}`);
    if (!candidate && !optionPosition) blockers.push("No verified candidate has reached strategy evaluation yet");
    if (candidate && !actionable) blockers.push(String(candidate.reason || candidate.stage || "Strategy evidence has not reached ACTIONABLE"));
    if (String(candidate?.reason || "").toUpperCase().includes("MARKET_SESSION_CLOSED")) blockers.push("Market session is closed");

    const status = optionPosition ? "POSITION OPEN" : actionable ? "ACTIONABLE" : "WAIT";
    const expression = optionPosition
      ? `LONG ${String(metadata.option_type || "OPTION").toUpperCase().replace("CE", "CALL").replace("PE", "PUT")}`
      : INDEX_OPTION_UNDERLYINGS.has(underlying)
        ? direction === "BULLISH" ? "LONG CALL" : direction === "BEARISH" ? "LONG PUT" : "AUTO"
        : direction;

    return {
      status,
      underlying,
      direction,
      expression,
      contract: optionPosition?.symbol || (actionable && INDEX_OPTION_UNDERLYINGS.has(underlying) ? "AUTO SELECT" : "—"),
      expiry: metadata.expiry || "AUTO",
      strike: metadata.strike ?? "AUTO",
      entry: optionPosition?.entry ?? (INDEX_OPTION_UNDERLYINGS.has(underlying) ? null : candidate?.entry),
      stop: optionPosition?.stop ?? (INDEX_OPTION_UNDERLYINGS.has(underlying) ? null : candidate?.stop),
      target: optionPosition?.target ?? (INDEX_OPTION_UNDERLYINGS.has(underlying) ? null : candidate?.target),
      size: optionPosition?.quantity ?? "PAPER DESK",
      ev: candidate?.expected_value_r,
      blockers: [...new Set(blockers)].slice(0, 5),
      actionable: Boolean(actionable),
      open: Boolean(optionPosition)
    };
  }

  function renderDecision(state) {
    const model = decisionModel(state);
    const host = $("v16AutoDecision");
    if (!host) return;
    const level = value => value === null || value === undefined ? "AUTO" : typeof value === "number" ? fmt(value) : String(value);
    host.innerHTML = `
      <div class="v16-auto-decision-head"><strong>AUTONOMOUS DECISION</strong><b class="${model.open ? "open" : model.actionable ? "actionable" : ""}">${esc(model.status)}</b></div>
      <div class="v16-auto-decision-grid">
        <span><small>UNDERLYING</small><b>${esc(model.underlying)}</b></span>
        <span><small>DIRECTION</small><b>${esc(model.direction)}</b></span>
        <span><small>EXPRESSION</small><b>${esc(model.expression)}</b></span>
        <span><small>CONTRACT</small><b>${esc(model.contract)}</b></span>
        <span><small>EXPIRY</small><b>${esc(model.expiry)}</b></span>
        <span><small>STRIKE</small><b>${esc(model.strike)}</b></span>
        <span><small>ENTRY</small><b>${esc(level(model.entry))}</b></span>
        <span><small>STOP</small><b>${esc(level(model.stop))}</b></span>
        <span><small>TARGET</small><b>${esc(level(model.target))}</b></span>
        <span><small>SIZE</small><b>${esc(model.size)}</b></span>
      </div>
      <div class="v16-auto-why"><b>${model.blockers.length ? "WHY NO TRADE" : model.open ? "POSITION MANAGEMENT" : "READY FOR FINAL SERVER GATES"}</b>${model.blockers.length ? `<ul>${model.blockers.map(item => `<li>${esc(item)}</li>`).join("")}</ul>` : `<p>EV ${model.ev == null ? "—" : esc(fmt(model.ev, 3))} · final quote, instrument, capital and Paper Desk gates remain authoritative.</p>`}</div>`;
  }

  function render(state) {
    latestState = state;
    const session = state?.session || {};
    const workspace = state?.workspace || activeCapitalWorkspace();
    const running = String(session.entry_session || "").toUpperCase() === "RUNNING";
    const scanning = Boolean(session.scanning);
    const reconciliation = session.reconciliation_ok !== false;
    const candidates = Array.isArray(state?.scan_decisions?.candidates) ? state.scan_decisions.candidates : [];
    const actionable = candidates.find(item => String(item.stage || "").toUpperCase() === "ACTIONABLE");
    const market = providerState(state, actionable?.symbol || candidates[0]?.symbol || "");

    const badge = $("v16AutoBadge");
    if (badge) {
      badge.textContent = running ? (scanning ? "AUTO · SCANNING" : "AUTO · ARMED") : "AUTO · PAUSED";
      badge.dataset.state = running ? (market.degraded ? "degraded" : "running") : "paused";
    }
    if ($("v16AutoWorkspace")) $("v16AutoWorkspace").textContent = workspace;

    const stages = [
      ["SCAN", running ? (scanning ? "ACTIVE" : "ARMED") : "PAUSED"],
      ["VERIFY", market.degraded ? market.label : "READY"],
      ["STRATEGY", actionable ? "ACTIONABLE" : "WAITING"],
      ["CONTRACT", workspace === "INVESTMENT" ? "N/A" : "AUTO"],
      ["RISK", reconciliation ? "AUTO" : "BLOCKED"],
      ["SIZE", reconciliation ? "PAPER DESK" : "BLOCKED"],
      ["MANAGE", "AUTO"],
      ["JOURNAL", "AUTO"]
    ];
    const pipeline = $("v16AutoPipeline");
    if (pipeline) pipeline.innerHTML = stages.map(([name, value]) => `<span><small>${esc(name)}</small><b>${esc(value)}</b></span>`).join("");

    renderDecision(state);

    if (!running) {
      setMessage("JARVIS is paused for new entries. Existing PAPER positions remain automatically monitored.");
    } else if (!reconciliation) {
      setMessage("Autonomous entries blocked by canonical ledger reconciliation. Position management continues.", "error");
    } else if (market.degraded) {
      setMessage("JARVIS is armed, but degraded market data blocks new entries until verified evidence recovers.", "warn");
    } else if (actionable) {
      setMessage(`${actionable.symbol || "Candidate"} reached ACTIONABLE. JARVIS now handles final contract, quote, risk, sizing and PAPER entry gates automatically.`, "ok");
    } else {
      setMessage("JARVIS is running autonomously. WAIT means the evidence rejected a trade; no user action is required.", "ok");
    }

    document.querySelectorAll("[data-v16-auto-control]").forEach(button => { button.disabled = busy; });
  }

  async function refresh() {
    try {
      render(await workspaceState(activeCapitalWorkspace()));
    } catch (error) {
      setMessage(error.message || "Autonomous state unavailable.", "error");
    }
  }

  async function controlWorkspace(workspace, action, token) {
    const state = token ? null : await workspaceState(workspace);
    const csrf = token || state?.csrf_token;
    if (!csrf) throw new Error("Local paper-session token unavailable; refresh the terminal.");
    return requestJson("/api/terminal/session", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Jarvis-Token": csrf},
      body: JSON.stringify({workspace, action})
    }, 15000);
  }

  async function controlAll(action) {
    const workspace = activeCapitalWorkspace();
    const state = latestState?.csrf_token ? latestState : await workspaceState(workspace);
    if (!state?.csrf_token) throw new Error("Local paper-session token unavailable.");
    const results = [];
    for (const name of WORKSPACES) results.push(await controlWorkspace(name, action, state.csrf_token));
    return results;
  }

  async function handleControl(action) {
    if (busy) return;
    busy = true;
    document.querySelectorAll("[data-v16-auto-control]").forEach(button => button.disabled = true);
    try {
      const workspace = activeCapitalWorkspace();
      if (action === "start_all") {
        await controlAll("start");
        setMessage("JARVIS autonomous PAPER trading requested for Intraday / Swing / Investment. Options are expressed automatically from qualified index signals.", "ok");
      } else if (action === "pause_all") {
        await controlAll("pause_new_entries");
        setMessage("All new entries paused. Existing PAPER positions continue automatic risk management.", "warn");
      } else if (action === "stop_day") {
        await controlAll("stop_scanner");
        setMessage("Trading stopped for the day: all entry scanners are paused; existing positions remain monitored until resolved by canonical risk rules.", "warn");
      } else {
        const mapped = action === "resume_current" ? "resume" : action === "pause_current" ? "pause_new_entries" : action === "start_current" ? "start" : action;
        await controlWorkspace(workspace, mapped);
        setMessage(`${workspace}: ${mapped.replaceAll("_", " ").toUpperCase()}.`, "ok");
      }
    } catch (error) {
      setMessage(error.message || "Autonomous control failed.", "error");
    } finally {
      busy = false;
      await refresh();
    }
  }

  function convergeLegacyEvidence() {
    const intel = document.querySelector(".intel-panel");
    if (!intel || $("v16EvidenceDeck")) return;
    const cards = [$("scanButton"), $("liveSignal"), $("setupState"), $("evidenceList")]
      .map(node => node?.closest(".intel-card"))
      .filter((node, index, arr) => node && arr.indexOf(node) === index);
    if (!cards.length) return;
    const details = document.createElement("details");
    details.id = "v16EvidenceDeck";
    details.className = "v16-evidence-deck";
    details.innerHTML = `<summary>EVIDENCE & RESEARCH · supporting diagnostics</summary><div class="v16-evidence-deck-body"></div>`;
    const canonical = $("v16Canonical");
    if (canonical?.nextSibling) intel.insertBefore(details, canonical.nextSibling);
    else intel.prepend(details);
    const body = details.querySelector(".v16-evidence-deck-body");
    cards.forEach(card => body.appendChild(card));
  }

  function makePrimaryPanel() {
    const canonical = $("v16Canonical");
    if (!canonical || $("v16AutonomyPrimary")) return false;
    const block = document.createElement("div");
    block.id = "v16AutonomyPrimary";
    block.className = "v16-autonomy-primary";
    block.innerHTML = `
      <div class="v16-auto-head">
        <div><span class="eyebrow">PRIMARY WORKFLOW</span><b>JARVIS AUTONOMOUS PAPER TRADING</b></div>
        <span id="v16AutoBadge" data-state="paused">AUTO · PAUSED</span>
      </div>
      <div class="v16-auto-sub">One normal workflow: JARVIS scans, verifies, chooses the strategy expression, derives risk, lets the canonical Paper Desk size the position, manages it, and journals the result. WAIT is an autonomous decision—not a request for manual input.</div>
      <div id="v16AutoPipeline" class="v16-auto-pipeline"></div>
      <div id="v16AutoDecision" class="v16-auto-decision"></div>
      <div class="v16-auto-actions">
        <button type="button" data-v16-auto-control="start_all">START JARVIS</button>
        <button type="button" data-v16-auto-control="pause_all">PAUSE NEW ENTRIES</button>
        <button type="button" data-v16-auto-control="stop_day">STOP FOR DAY</button>
      </div>
      <div id="v16AutoMessage" class="v16-auto-message">Loading autonomous state…</div>
      <details class="v16-auto-advanced"><summary>ADVANCED · individual workspace session controls</summary><div class="v16-auto-actions"><button data-v16-auto-control="start_current">START CURRENT</button><button data-v16-auto-control="pause_current">PAUSE CURRENT</button><button data-v16-auto-control="resume_current">RESUME CURRENT</button></div></details>
      <small>Verified completed-bar evidence only · long-premium options only · PAPER ONLY · LIVE BROKER EXECUTION LOCKED</small>`;
    const controls = canonical.querySelector(".v16-controls");
    if (controls) {
      controls.hidden = true;
      controls.insertAdjacentElement("beforebegin", block);
    } else canonical.prepend(block);
    block.querySelectorAll("[data-v16-auto-control]").forEach(button => button.addEventListener("click", () => handleControl(button.dataset.v16AutoControl)));
    return true;
  }

  function enhanceOptions() {
    const options = $("v16Options");
    if (!options) return;
    if (!$("v16AutoOptionsBanner")) {
      const banner = document.createElement("div");
      banner.id = "v16AutoOptionsBanner";
      banner.className = "v16-auto-options-banner";
      banner.innerHTML = `<b>AUTONOMOUS OPTIONS</b><span>No contract click, lot input, stop/target input or BUY click is required for the normal workflow. Qualified index signals are converted into verified long CALL/PUT PAPER expressions automatically.</span>`;
      options.prepend(banner);
    }
    const manual = $("v16OptionOrder");
    if (manual && !$("v16ManualOverrideToggle")) {
      manual.hidden = true;
      const toggle = document.createElement("button");
      toggle.id = "v16ManualOverrideToggle";
      toggle.type = "button";
      toggle.className = "v16-manual-override-toggle";
      toggle.textContent = "MANUAL PAPER OVERRIDE · OPTIONAL / DEBUG";
      toggle.addEventListener("click", () => {
        manual.hidden = !manual.hidden;
        toggle.textContent = manual.hidden ? "MANUAL PAPER OVERRIDE · OPTIONAL / DEBUG" : "HIDE MANUAL OVERRIDE";
      });
      manual.insertAdjacentElement("beforebegin", toggle);
    }
  }

  function boot() {
    ensureStyles();
    makePrimaryPanel();
    enhanceOptions();
    convergeLegacyEvidence();
    if (!$("v16AutonomyPrimary")) return setTimeout(boot, 150);
    refresh();
    pollTimer = setInterval(() => {
      enhanceOptions();
      convergeLegacyEvidence();
      refresh();
    }, 3000);
    window.addEventListener("jarvis:workspace", () => setTimeout(refresh, 100));
    $("v16OptionCapital")?.addEventListener("change", () => setTimeout(refresh, 50));
    $("v16OptionUnderlying")?.addEventListener("change", () => setTimeout(refresh, 50));
    window.addEventListener("beforeunload", () => { if (pollTimer) clearInterval(pollTimer); }, {once: true});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, {once: true});
  else boot();
})();
