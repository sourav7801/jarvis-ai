(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  const WORKSPACES = ["INTRADAY", "SWING", "INVESTMENT"];
  const $ = id => document.getElementById(id);
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
      const response = await fetch(url, {...options, signal: controller.signal});
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

  function setMessage(text, kind = "") {
    const node = $("v16AutoMessage");
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
  }

  function render(state) {
    latestState = state;
    const session = state?.session || {};
    const workspace = state?.workspace || activeCapitalWorkspace();
    const running = String(session.entry_session || "").toUpperCase() === "RUNNING";
    const scanning = Boolean(session.scanning);
    const reconciliation = session.reconciliation_ok !== false;
    const market = state?.market_data || {};
    const providers = Object.values(market.providers || {});
    const dataDegraded = providers.some(item => ["DEGRADED", "RATE_LIMITED", "LOGIN_REQUIRED"].includes(String(item.state || "").toUpperCase()));
    const candidates = Array.isArray(state?.scan_decisions?.candidates) ? state.scan_decisions.candidates : [];
    const actionable = candidates.find(item => String(item.stage || "").toUpperCase() === "ACTIONABLE");

    const badge = $("v16AutoBadge");
    if (badge) {
      badge.textContent = running ? (scanning ? "AUTO · SCANNING" : "AUTO · ARMED") : "AUTO · PAUSED";
      badge.dataset.state = running ? (dataDegraded ? "degraded" : "running") : "paused";
    }
    const workspaceNode = $("v16AutoWorkspace");
    if (workspaceNode) workspaceNode.textContent = workspace;

    const stages = [
      ["SCAN", running ? (scanning ? "ACTIVE" : "ARMED") : "PAUSED"],
      ["VERIFY", dataDegraded ? "DEGRADED" : "READY"],
      ["STRATEGY", actionable ? "ACTIONABLE" : "WAITING"],
      ["CONTRACT", workspace === "INVESTMENT" ? "N/A" : "AUTO"],
      ["RISK", reconciliation ? "AUTO" : "BLOCKED"],
      ["SIZE", reconciliation ? "PAPER DESK" : "BLOCKED"],
      ["MANAGE", "AUTO"],
      ["JOURNAL", "AUTO"]
    ];
    const pipeline = $("v16AutoPipeline");
    if (pipeline) pipeline.innerHTML = stages.map(([name, value]) => `<span><small>${name}</small><b>${value}</b></span>`).join("");

    if (!running) {
      setMessage(`${workspace} autonomous entries are paused. Existing paper positions remain monitored.`);
    } else if (!reconciliation) {
      setMessage("Autonomous entries blocked by canonical ledger reconciliation. Position management continues.", "error");
    } else if (dataDegraded) {
      setMessage("Autonomous engine is armed, but degraded market data blocks new entries until verified evidence recovers.", "warn");
    } else if (actionable) {
      setMessage(`${actionable.symbol || "Candidate"} reached ACTIONABLE. Final fresh quote, option economics and Paper Desk risk gates still decide the paper fill.`, "ok");
    } else {
      setMessage("Autonomous engine is running: scan → verify → strategy → contract/risk → Paper Desk size → manage → journal.", "ok");
    }

    document.querySelectorAll("[data-v16-auto-control]").forEach(button => {
      button.disabled = busy;
    });
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

  async function handleControl(action) {
    if (busy) return;
    busy = true;
    document.querySelectorAll("[data-v16-auto-control]").forEach(button => button.disabled = true);
    try {
      const workspace = activeCapitalWorkspace();
      if (action === "start_all") {
        const state = latestState?.csrf_token ? latestState : await workspaceState(workspace);
        if (!state?.csrf_token) throw new Error("Local paper-session token unavailable.");
        const results = [];
        for (const name of WORKSPACES) {
          results.push(await controlWorkspace(name, "start", state.csrf_token));
        }
        setMessage(`Autonomous PAPER requested for ${WORKSPACES.join(" / ")}. Each mandate remains independently risk-gated.`, "ok");
      } else {
        const mapped = action === "resume" ? "resume" : action === "pause" ? "pause_new_entries" : action;
        await controlWorkspace(workspace, mapped);
        setMessage(`${workspace} autonomous control: ${mapped.replaceAll("_", " ").toUpperCase()}.`, "ok");
      }
    } catch (error) {
      setMessage(error.message || "Autonomous control failed.", "error");
    } finally {
      busy = false;
      await refresh();
    }
  }

  function makePrimaryPanel() {
    const canonical = $("v16Canonical");
    if (!canonical || $("v16AutonomyPrimary")) return false;
    const block = document.createElement("div");
    block.id = "v16AutonomyPrimary";
    block.className = "v16-autonomy-primary";
    block.innerHTML = `
      <div class="v16-auto-head">
        <div><span class="eyebrow">PRIMARY WORKFLOW</span><b>AUTONOMOUS PAPER TRADING</b></div>
        <span id="v16AutoBadge" data-state="paused">AUTO · PAUSED</span>
      </div>
      <div class="v16-auto-sub">Workspace <b id="v16AutoWorkspace">INTRADAY</b> · JARVIS selects setups automatically. For qualified NIFTY/BANKNIFTY/SENSEX signals it can select CALL/PUT + exact contract + stop/target; the canonical Paper Desk sizes and manages the position.</div>
      <div id="v16AutoPipeline" class="v16-auto-pipeline"></div>
      <div class="v16-auto-actions">
        <button type="button" data-v16-auto-control="start">START AUTONOMOUS PAPER</button>
        <button type="button" data-v16-auto-control="start_all">START ALL 3 MANDATES</button>
        <button type="button" data-v16-auto-control="pause">PAUSE NEW ENTRIES</button>
        <button type="button" data-v16-auto-control="resume">RESUME AUTO</button>
      </div>
      <div id="v16AutoMessage" class="v16-auto-message">Loading autonomous state…</div>
      <small>Verified completed-bar evidence only · long-premium options only · PAPER ONLY · LIVE BROKER EXECUTION LOCKED</small>`;
    const controls = canonical.querySelector(".v16-controls");
    if (controls) {
      controls.hidden = true;
      controls.insertAdjacentElement("beforebegin", block);
    } else {
      canonical.prepend(block);
    }
    block.querySelectorAll("[data-v16-auto-control]").forEach(button => {
      button.addEventListener("click", () => handleControl(button.dataset.v16AutoControl));
    });
    return true;
  }

  function enhanceOptions() {
    const options = $("v16Options");
    if (!options) return;
    if (!$("v16AutoOptionsBanner")) {
      const banner = document.createElement("div");
      banner.id = "v16AutoOptionsBanner";
      banner.className = "v16-auto-options-banner";
      banner.innerHTML = `<b>AUTONOMOUS OPTIONS ENABLED</b><span>No manual contract/SL/target input is required for qualified paper signals. JARVIS selects CALL/PUT, verifies the listed contract, derives premium risk geometry and lets Paper Desk size the trade.</span>`;
      options.prepend(banner);
    }
    const manual = $("v16OptionOrder");
    if (manual && !$("v16ManualOverrideToggle")) {
      manual.hidden = true;
      const toggle = document.createElement("button");
      toggle.id = "v16ManualOverrideToggle";
      toggle.type = "button";
      toggle.className = "v16-manual-override-toggle";
      toggle.textContent = "MANUAL PAPER OVERRIDE · OPTIONAL";
      toggle.addEventListener("click", () => {
        manual.hidden = !manual.hidden;
        toggle.textContent = manual.hidden ? "MANUAL PAPER OVERRIDE · OPTIONAL" : "HIDE MANUAL OVERRIDE";
      });
      manual.insertAdjacentElement("beforebegin", toggle);
    }
  }

  function boot() {
    makePrimaryPanel();
    enhanceOptions();
    if (!$("v16AutonomyPrimary")) return setTimeout(boot, 150);
    refresh();
    pollTimer = setInterval(() => {
      enhanceOptions();
      refresh();
    }, 3000);
    window.addEventListener("jarvis:workspace", () => setTimeout(refresh, 100));
    $("v16OptionCapital")?.addEventListener("change", () => setTimeout(refresh, 50));
    window.addEventListener("beforeunload", () => {
      if (pollTimer) clearInterval(pollTimer);
    }, {once: true});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, {once: true});
  else boot();
})();
