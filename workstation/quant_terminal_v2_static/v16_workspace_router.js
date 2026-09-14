(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  const $ = id => document.getElementById(id);
  const CAPITAL_WORKSPACES = ["INTRADAY", "SWING", "INVESTMENT"];
  const EXTRA_OPTION_UNDERLYINGS = [
    ["CRUDEOIL", "CRUDEOIL · MCX CHAIN"],
    ["GOLD", "GOLD · MCX CHAIN"],
    ["SILVER", "SILVER · MCX CHAIN"],
    ["NATURALGAS", "NAT GAS · MCX CHAIN"],
    ["BTC", "BTC · DERIBIT CHAIN"],
    ["ETH", "ETH · DERIBIT CHAIN"],
  ];
  const hiddenBeforeOptions = new WeakMap();
  let latestState = null;
  let pollTimer = null;
  let busy = false;

  function activeMode() {
    return String(document.querySelector(".workspace-modes button.active")?.dataset.workspace || "INTRADAY").toUpperCase();
  }

  function optionCapitalWorkspace() {
    const value = String($("v16OptionCapital")?.value || $("v16OptionsSideCapital")?.value || "INTRADAY").toUpperCase();
    return CAPITAL_WORKSPACES.includes(value) ? value : "INTRADAY";
  }

  function selectedUnderlying() {
    return String($("v16OptionUnderlying")?.value || "NIFTY").toUpperCase();
  }

  function capability(underlying) {
    const value = String(underlying || "").toUpperCase();
    if (["NIFTY", "BANKNIFTY"].includes(value)) {
      return {
        tier: "AUTO PAPER",
        kind: "auto",
        source: "FYERS VERIFIED CHAIN + CANONICAL PAPER DESK",
        detail: "Automatic long CALL/PUT expression is permitted after verified signal, contract, quote, risk and Paper Desk gates pass."
      };
    }
    if (value === "SENSEX") {
      return {
        tier: "AUTO GATED",
        kind: "gated",
        source: "BSE/FYERS CONTRACT PATH",
        detail: "The V16 autonomous bridge knows SENSEX, but execution remains fail-closed unless the current provider chain and exact BSE contract verify."
      };
    }
    if (["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"].includes(value)) {
      return {
        tier: "CHAIN / RESEARCH",
        kind: "research",
        source: "FYERS MCX OPTION CHAIN V3",
        detail: "Verified MCX option-chain intelligence is available. Canonical V16 automated option execution is not yet audited for MCX, so no automatic paper entry is created."
      };
    }
    if (["BTC", "ETH"].includes(value)) {
      return {
        tier: "PUBLIC RESEARCH",
        kind: "research",
        source: "DERIBIT PUBLIC OPTIONS",
        detail: "Verified public option-chain research is available. The older crypto paper-intent journal is not used because V16 requires the single canonical Paper Desk ledger."
      };
    }
    return {tier: "UNVERIFIED", kind: "blocked", source: "NO VERIFIED ROUTE", detail: "No verified V16 option route is enabled for this underlying."};
  }

  function ensureStyle() {
    if ($("v16WorkspaceRouterStyle")) return;
    const style = document.createElement("style");
    style.id = "v16WorkspaceRouterStyle";
    style.textContent = `
      .v16-options-sidebar{border-color:#1e6479!important;background:linear-gradient(180deg,#071b25,#06121a)!important}
      .v16-options-side-head{display:flex;justify-content:space-between;gap:7px;align-items:flex-start}.v16-options-side-head b{font-size:16px;color:#e5f9ff}.v16-options-side-head span{font-size:8px;padding:4px 6px;border:1px solid #32596c;border-radius:999px;white-space:nowrap}
      .v16-options-side-head span[data-kind="auto"]{color:#7df1ad;border-color:#287a56}.v16-options-side-head span[data-kind="research"]{color:#ffd166;border-color:#7d6727}.v16-options-side-head span[data-kind="gated"]{color:#ffc66e;border-color:#805e2f}
      .v16-options-side-note{font-size:8px;line-height:1.45;color:#8fb5c4;margin:6px 0}.v16-options-side-note strong{color:#d7f4ff}
      .v16-options-side-select{display:grid;grid-template-columns:1fr;gap:4px;margin:7px 0}.v16-options-side-select label{font-size:7px;color:#6f94a4;letter-spacing:.08em}.v16-options-side-select select{width:100%;background:#071820;border:1px solid #285266;color:#d9f5ff;padding:6px;border-radius:5px}
      .v16-options-session{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:7px 0}.v16-options-session div{border:1px solid #173949;background:#06131a;padding:6px;border-radius:5px}.v16-options-session small{display:block;color:#6d94a4;font-size:7px}.v16-options-session b{font-size:10px;color:#d7f4ff}
      .v16-options-controls{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:7px 0}.v16-options-controls button{font-size:8px;min-height:29px;padding:5px}.v16-options-controls button:first-child{border-color:#2e8b61;color:#83f2b1;background:#08251a}
      .v16-options-pipeline{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;margin:7px 0}.v16-options-pipeline span{border:1px solid #173849;background:#07131b;padding:5px;min-width:0}.v16-options-pipeline small{display:block;color:#678d9c;font-size:7px}.v16-options-pipeline b{display:block;color:#ccecf7;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .v16-options-capabilities{border-top:1px solid #173849;margin-top:8px;padding-top:7px}.v16-options-capabilities>b{font-size:8px;color:#9fd8ec;letter-spacing:.08em}.v16-cap-row{margin-top:5px;padding:5px;border-left:2px solid #315368;background:#061219}.v16-cap-row strong{display:block;font-size:8px;color:#d8f5ff}.v16-cap-row span{display:block;margin-top:2px;font-size:7px;color:#7fa3b1;line-height:1.35}.v16-cap-row.auto{border-color:#2e8b61}.v16-cap-row.research{border-color:#99772f}.v16-cap-row.gated{border-color:#a46b34}
      .v16-options-side-msg{margin-top:7px;padding:6px;border-left:2px solid #337d99;background:#061219;color:#9fc4d2;font-size:8px;line-height:1.4}.v16-options-side-msg[data-kind="error"]{border-color:#ff647d;color:#ff9aad}.v16-options-side-msg[data-kind="ok"]{border-color:#45d68b;color:#8cedb4}
      .v16-options-open{border-top:1px solid #173849;margin-top:7px;padding-top:6px;font-size:8px;color:#8fb1be}.v16-options-open b{color:#dff7ff}
      html.v16-options-workspace .intel-panel>#v16OptionsSidebar{display:block!important}
    `;
    document.head.appendChild(style);
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

  function ensureExtraOptionUnderlyings() {
    const select = $("v16OptionUnderlying");
    if (!select) return;
    const existing = new Set([...select.options].map(option => String(option.value).toUpperCase()));
    EXTRA_OPTION_UNDERLYINGS.forEach(([value, label]) => {
      if (existing.has(value)) return;
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    });
  }

  function syncCapital(value) {
    const canonical = $("v16OptionCapital");
    const side = $("v16OptionsSideCapital");
    const next = CAPITAL_WORKSPACES.includes(String(value || "").toUpperCase()) ? String(value).toUpperCase() : "INTRADAY";
    if (canonical && canonical.value !== next) {
      canonical.value = next;
      canonical.dispatchEvent(new Event("change", {bubbles: true}));
    }
    if (side && side.value !== next) side.value = next;
  }

  function ensureOptionsSidebar() {
    const intel = document.querySelector(".intel-panel");
    if (!intel) return null;
    let card = $("v16OptionsSidebar");
    if (card) return card;
    card = document.createElement("section");
    card.id = "v16OptionsSidebar";
    card.className = "intel-card v16-options-sidebar";
    card.innerHTML = `
      <div class="eyebrow">OPTIONS WORKSPACE · CANONICAL V16</div>
      <div class="v16-options-side-head"><b>OPTIONS AUTOPILOT</b><span id="v16OptionsTier">WAITING</span></div>
      <div class="v16-options-side-note"><strong id="v16OptionsUnderlyingLabel">NIFTY</strong> · <span id="v16OptionsSource">provider check</span><br><span id="v16OptionsCapabilityText">Loading capability state…</span></div>
      <div class="v16-options-side-select"><label>CAPITAL MANDATE</label><select id="v16OptionsSideCapital"><option>INTRADAY</option><option>SWING</option><option>INVESTMENT</option></select></div>
      <div class="v16-options-session"><div><small>ENTRY SESSION</small><b id="v16OptionsSessionState">—</b></div><div><small>SCANNER</small><b id="v16OptionsScannerState">—</b></div><div><small>RECONCILIATION</small><b id="v16OptionsReconState">—</b></div><div><small>LIVE BROKER</small><b>LOCKED</b></div></div>
      <div class="v16-options-controls"><button data-v16-option-control="start">START SESSION</button><button data-v16-option-control="pause_new_entries">PAUSE NEW ENTRIES</button><button data-v16-option-control="resume">RESUME</button><button data-v16-option-control="stop_scanner">STOP SCANNER</button></div>
      <div class="v16-options-pipeline"><span><small>CHAIN</small><b id="v16OptionsPipeChain">VERIFY</b></span><span><small>CONTRACT</small><b id="v16OptionsPipeContract">AUTO</b></span><span><small>RISK</small><b id="v16OptionsPipeRisk">AUTO</b></span><span><small>SIZE</small><b id="v16OptionsPipeSize">PAPER DESK</b></span><span><small>MANAGE</small><b>AUTO</b></span><span><small>JOURNAL</small><b>CANONICAL</b></span></div>
      <div class="v16-options-open" id="v16OptionsOpenPosition"><b>POSITION</b><br>No open canonical option position in this mandate.</div>
      <div class="v16-options-capabilities"><b>MARKET CAPABILITY</b>
        <div class="v16-cap-row auto"><strong>NIFTY / BANKNIFTY · AUTO PAPER</strong><span>Verified FYERS chain → auto CALL/PUT → canonical Paper Desk.</span></div>
        <div class="v16-cap-row gated"><strong>SENSEX · AUTO GATED</strong><span>Autonomous bridge exists; provider chain and exact BSE contract must verify or it fails closed.</span></div>
        <div class="v16-cap-row research"><strong>CRUDEOIL / GOLD / SILVER / NAT GAS · CHAIN / RESEARCH</strong><span>Verified FYERS MCX option-chain data is exposed. Canonical auto execution is not yet audited.</span></div>
        <div class="v16-cap-row research"><strong>BTC / ETH · PUBLIC RESEARCH</strong><span>Verified Deribit public option chain. No separate crypto paper ledger is used in V16.</span></div>
      </div>
      <div class="v16-options-side-msg" id="v16OptionsSideMessage">Select OPTIONS and start the selected capital mandate. New entries remain fail-closed on stale data, closed sessions or failed risk gates.</div>
    `;
    intel.prepend(card);
    $("v16OptionsSideCapital")?.addEventListener("change", event => {
      syncCapital(event.target.value);
      refreshState(true);
    });
    card.querySelectorAll("[data-v16-option-control]").forEach(button => {
      button.addEventListener("click", () => controlSession(button.dataset.v16OptionControl, button));
    });
    return card;
  }

  function movePrimaryToTop() {
    const intel = document.querySelector(".intel-panel");
    const primary = $("v16AutonomyPrimary");
    if (!intel || !primary || activeMode() === "OPTIONS") return;
    primary.classList.add("intel-card");
    if (primary.parentElement !== intel || intel.firstElementChild !== primary) intel.prepend(primary);
  }

  function setOptionsVisibility(enabled) {
    const intel = document.querySelector(".intel-panel");
    const optionsCard = ensureOptionsSidebar();
    if (!intel || !optionsCard) return;
    document.documentElement.classList.toggle("v16-options-workspace", enabled);
    [...intel.children].forEach(node => {
      if (node === optionsCard) {
        node.hidden = !enabled;
        return;
      }
      if (enabled) {
        if (!hiddenBeforeOptions.has(node)) hiddenBeforeOptions.set(node, Boolean(node.hidden));
        node.hidden = true;
      } else if (hiddenBeforeOptions.has(node)) {
        node.hidden = hiddenBeforeOptions.get(node);
        hiddenBeforeOptions.delete(node);
      }
    });
    if (enabled) intel.prepend(optionsCard);
  }

  function renderCapability() {
    const underlying = selectedUnderlying();
    const cap = capability(underlying);
    const tier = $("v16OptionsTier");
    if (tier) { tier.textContent = cap.tier; tier.dataset.kind = cap.kind; }
    if ($("v16OptionsUnderlyingLabel")) $("v16OptionsUnderlyingLabel").textContent = underlying;
    if ($("v16OptionsSource")) $("v16OptionsSource").textContent = cap.source;
    if ($("v16OptionsCapabilityText")) $("v16OptionsCapabilityText").textContent = cap.detail;
    if ($("v16OptionsPipeContract")) $("v16OptionsPipeContract").textContent = cap.kind === "auto" || cap.kind === "gated" ? "AUTO" : "RESEARCH";
    if ($("v16OptionsPipeRisk")) $("v16OptionsPipeRisk").textContent = cap.kind === "auto" ? "AUTO" : cap.kind === "gated" ? "GATED" : "NO ENTRY";
    if ($("v16OptionsPipeSize")) $("v16OptionsPipeSize").textContent = cap.kind === "auto" ? "PAPER DESK" : "N/A";

    const banner = $("v16AutoOptionsBanner");
    if (banner) {
      banner.innerHTML = cap.kind === "auto"
        ? `<b>AUTONOMOUS OPTIONS ENABLED</b><span>${underlying}: qualified long CALL/PUT plans can flow to the canonical Paper Desk automatically. No manual contract/lot/SL/target/BUY click is required.</span>`
        : `<b>${cap.tier}</b><span>${underlying}: ${cap.detail}</span>`;
    }
    const manualToggle = $("v16ManualOptionToggle");
    if (manualToggle) manualToggle.hidden = cap.kind === "research" || cap.kind === "blocked";
    const order = $("v16OptionOrder");
    if (order && (cap.kind === "research" || cap.kind === "blocked")) order.hidden = true;
  }

  function renderState(state) {
    latestState = state;
    const session = state?.session || {};
    const running = String(session.entry_session || "PAUSED").toUpperCase();
    if ($("v16OptionsSessionState")) $("v16OptionsSessionState").textContent = running;
    if ($("v16OptionsScannerState")) $("v16OptionsScannerState").textContent = session.scanning ? "RUNNING" : "IDLE";
    if ($("v16OptionsReconState")) $("v16OptionsReconState").textContent = session.reconciliation_ok === false ? "BLOCKED" : "CLEAN";
    if ($("v16OptionsPipeChain")) {
      const providers = Object.values(state?.market_data?.providers || {});
      const bad = providers.some(item => ["DEGRADED", "RATE_LIMITED", "LOGIN_REQUIRED"].includes(String(item?.state || "").toUpperCase()));
      $("v16OptionsPipeChain").textContent = bad ? "DEGRADED" : "VERIFIED";
    }
    const positions = Array.isArray(state?.positions) ? state.positions : [];
    const option = positions.find(item => {
      const metadata = item?.metadata || {};
      return String(item?.asset_type || metadata.asset_type || "").toUpperCase() === "OPTION" || Boolean(metadata.option_type);
    });
    const host = $("v16OptionsOpenPosition");
    if (host) {
      if (!option) host.innerHTML = "<b>POSITION</b><br>No open canonical option position in this mandate.";
      else {
        const meta = option.metadata || {};
        host.innerHTML = `<b>POSITION OPEN</b><br>${String(option.symbol || "OPTION")} · ${String(meta.option_type || "LONG")} · qty ${String(option.quantity ?? "—")}<br>entry ${String(option.entry ?? option.entry_price ?? "—")} · SL ${String(option.stop ?? "—")} · target ${String(option.target ?? "—")}`;
      }
    }
  }

  async function refreshState(force = false) {
    if (activeMode() !== "OPTIONS" && !force) return;
    try {
      const workspace = optionCapitalWorkspace();
      const state = await requestJson(`/api/v16/trading/workspace-state?workspace=${encodeURIComponent(workspace)}`);
      renderState(state);
    } catch (error) {
      const msg = $("v16OptionsSideMessage");
      if (msg) { msg.textContent = `Canonical option state unavailable: ${error.message}`; msg.dataset.kind = "error"; }
    }
  }

  async function controlSession(action, button) {
    if (busy) return;
    busy = true;
    const old = button?.textContent;
    if (button) { button.disabled = true; button.textContent = "WORKING…"; }
    try {
      const workspace = optionCapitalWorkspace();
      const payload = await requestJson("/api/terminal/session", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({workspace, action}),
      });
      if (payload.state) renderState(payload.state);
      const msg = $("v16OptionsSideMessage");
      if (msg) {
        msg.textContent = `${workspace}: ${payload.message || action}. Existing positions remain governed by the canonical Paper Desk. Live broker execution remains locked.`;
        msg.dataset.kind = "ok";
      }
      await refreshState(true);
    } catch (error) {
      const msg = $("v16OptionsSideMessage");
      if (msg) { msg.textContent = `${action} failed: ${error.message}`; msg.dataset.kind = "error"; }
    } finally {
      busy = false;
      if (button) { button.disabled = false; button.textContent = old; }
    }
  }

  function route() {
    ensureStyle();
    ensureExtraOptionUnderlyings();
    ensureOptionsSidebar();
    const options = activeMode() === "OPTIONS";
    setOptionsVisibility(options);
    if (options) {
      syncCapital(optionCapitalWorkspace());
      renderCapability();
      refreshState(true);
    } else {
      movePrimaryToTop();
    }
  }

  function boot() {
    route();
    document.querySelector(".workspace-modes")?.addEventListener("click", event => {
      if (!event.target.closest("button[data-workspace]")) return;
      setTimeout(route, 0);
    });
    $("v16OptionUnderlying")?.addEventListener("change", () => {
      renderCapability();
      refreshState(true);
    });
    $("v16OptionCapital")?.addEventListener("change", event => {
      const side = $("v16OptionsSideCapital");
      if (side) side.value = event.target.value;
      refreshState(true);
    });

    const intel = document.querySelector(".intel-panel");
    if (intel) {
      new MutationObserver(() => {
        if (activeMode() === "OPTIONS") setOptionsVisibility(true);
        else movePrimaryToTop();
      }).observe(intel, {childList: true});
    }

    pollTimer = setInterval(() => {
      ensureExtraOptionUnderlyings();
      if (activeMode() === "OPTIONS") {
        renderCapability();
        refreshState(false);
      } else movePrimaryToTop();
    }, 2500);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => setTimeout(boot, 0), {once: true});
  else setTimeout(boot, 0);

  window.addEventListener("beforeunload", () => { if (pollTimer) clearInterval(pollTimer); }, {once: true});
})();
