(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  const $ = id => document.getElementById(id);
  const CAPITAL_WORKSPACES = ["INTRADAY", "SWING", "INVESTMENT"];
  const EXTRA_OPTION_UNDERLYINGS = [
    ["CRUDEOIL", "CRUDEOIL · MCX"],
    ["GOLD", "GOLD · MCX"],
    ["SILVER", "SILVER · MCX"],
    ["NATURALGAS", "NAT GAS · MCX"],
    ["BTC", "BTC · DERIBIT"],
    ["ETH", "ETH · DERIBIT"],
  ];
  const hiddenBeforeOptions = new WeakMap();
  let latestState = null;
  let latestStateAt = 0;
  let pollTimer = null;
  let busy = false;
  let chainSerial = 0;
  let selectedContract = null;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
  const num = value => {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const fmt = (value, digits = 2) => {
    const n = num(value);
    return n === null ? "—" : n.toLocaleString("en-IN", {maximumFractionDigits: digits, minimumFractionDigits: digits});
  };

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
        detail: "Automatic long CALL/PUT expression is permitted after verified signal, exact contract, fresh quote, risk and Paper Desk gates pass."
      };
    }
    if (value === "SENSEX") {
      return {
        tier: "AUTO GATED",
        kind: "gated",
        source: "BSE/FYERS CONTRACT PATH",
        detail: "Autonomous expression remains fail-closed until the current provider chain and exact BSE contract verify."
      };
    }
    if (["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"].includes(value)) {
      return {
        tier: "CHAIN / RESEARCH",
        kind: "research",
        source: "FYERS MCX OPTION CHAIN V3",
        detail: "Verified MCX option-chain intelligence is available. Canonical V16 automated option execution is not yet audited for MCX."
      };
    }
    if (["BTC", "ETH"].includes(value)) {
      return {
        tier: "PUBLIC RESEARCH",
        kind: "research",
        source: "DERIBIT PUBLIC OPTIONS",
        detail: "Verified Deribit public option-chain research is available. V16 does not use the older separate crypto paper-intent ledger."
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
      .v16-options-controls{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:7px 0}.v16-options-controls button{font-size:8px;min-height:29px;padding:5px}.v16-options-controls button:first-child{border-color:#2e8b61;color:#83f2b1;background:#08251a}.v16-options-controls button:disabled{opacity:.38;cursor:not-allowed}
      .v16-options-pipeline{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;margin:7px 0}.v16-options-pipeline span{border:1px solid #173849;background:#07131b;padding:5px;min-width:0}.v16-options-pipeline small{display:block;color:#678d9c;font-size:7px}.v16-options-pipeline b{display:block;color:#ccecf7;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .v16-options-capabilities{border-top:1px solid #173849;margin-top:8px;padding-top:7px}.v16-options-capabilities>b{font-size:8px;color:#9fd8ec;letter-spacing:.08em}.v16-cap-row{margin-top:5px;padding:5px;border-left:2px solid #315368;background:#061219}.v16-cap-row strong{display:block;font-size:8px;color:#d8f5ff}.v16-cap-row span{display:block;margin-top:2px;font-size:7px;color:#7fa3b1;line-height:1.35}.v16-cap-row.auto{border-color:#2e8b61}.v16-cap-row.research{border-color:#99772f}.v16-cap-row.gated{border-color:#a46b34}
      .v16-options-side-msg{margin-top:7px;padding:6px;border-left:2px solid #337d99;background:#061219;color:#9fc4d2;font-size:8px;line-height:1.4}.v16-options-side-msg[data-kind="error"]{border-color:#ff647d;color:#ff9aad}.v16-options-side-msg[data-kind="ok"]{border-color:#45d68b;color:#8cedb4}.v16-options-side-msg[data-kind="warn"]{border-color:#ffd166;color:#e7d18a}
      .v16-options-open{border-top:1px solid #173849;margin-top:7px;padding-top:6px;font-size:8px;color:#8fb1be;line-height:1.45}.v16-options-open b{color:#dff7ff}
      html.v16-options-workspace .intel-panel>#v16OptionsSidebar{display:block!important}
      html.v16-options-workspace #v16Options{display:block!important;max-height:none!important;min-height:250px;border-color:#2a657d;background:#06151d}
      html.v16-options-workspace #v16Options .v16-option-table-wrap{max-height:275px}
      html.v16-options-workspace #chartGrid{min-height:330px}
      html.v16-options-workspace .workspace-toolbar{border-color:#1e4c60}
      .v16-option-domain-bar{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:6px 0}.v16-option-domain-bar>div{border:1px solid #1a4152;background:#07151d;padding:6px;border-radius:5px}.v16-option-domain-bar small{display:block;color:#6f94a4;font-size:7px;letter-spacing:.08em}.v16-option-domain-bar b{display:block;color:#d7f4ff;font-size:10px;margin-top:2px}.v16-option-domain-bar span{display:block;color:#82a9b7;font-size:8px;margin-top:2px;line-height:1.35}
      .v16-option-provenance{margin-top:5px;color:#87aebb;font-size:8px}.v16-option-provenance strong{color:#ccecf7}
    `;
    document.head.appendChild(style);
  }

  async function requestJson(url, options = {}, timeoutMs = 12000) {
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
    if (canonical && canonical.value !== next) canonical.value = next;
    if (side && side.value !== next) side.value = next;
  }

  function ensureDomainBar() {
    const panel = $("v16Options");
    if (!panel || $("v16OptionDomainBar")) return;
    const bar = document.createElement("div");
    bar.id = "v16OptionDomainBar";
    bar.className = "v16-option-domain-bar";
    bar.innerHTML = `
      <div><small>UNDERLYING DOMAIN</small><b id="v16DomainUnderlying">NIFTY · —</b><span>Structure, support/resistance, regime and directional thesis belong to the underlying only.</span></div>
      <div><small>OPTION PREMIUM DOMAIN</small><b id="v16DomainContract">NO CONTRACT SELECTED</b><span>Premium chart receives only option-contract indicators plus canonical option entry/SL/target geometry.</span></div>`;
    const head = panel.querySelector(".v16-option-head");
    if (head?.nextSibling) panel.insertBefore(bar, head.nextSibling);
    else panel.prepend(bar);
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
      <div class="v16-options-session"><div><small>ENTRY SESSION</small><b id="v16OptionsSessionState">—</b></div><div><small>SCANNER</small><b id="v16OptionsScannerState">—</b></div><div><small>RECONCILIATION</small><b id="v16OptionsReconState">—</b></div><div><small>STATE AGE</small><b id="v16OptionsStateAge">—</b></div></div>
      <div class="v16-options-controls"><button data-v16-option-control="start">START SESSION</button><button data-v16-option-control="pause_new_entries">PAUSE NEW ENTRIES</button><button data-v16-option-control="resume">RESUME</button><button data-v16-option-control="stop_scanner">STOP SCANNER</button></div>
      <div class="v16-options-pipeline"><span><small>CHAIN</small><b id="v16OptionsPipeChain">VERIFY</b></span><span><small>CONTRACT</small><b id="v16OptionsPipeContract">AUTO</b></span><span><small>RISK</small><b id="v16OptionsPipeRisk">AUTO</b></span><span><small>SIZE</small><b id="v16OptionsPipeSize">PAPER DESK</b></span><span><small>MANAGE</small><b>AUTO</b></span><span><small>LIVE BROKER</small><b>LOCKED</b></span></div>
      <div class="v16-options-open" id="v16OptionsOpenPosition"><b>POSITION</b><br>No open canonical option position in this mandate.</div>
      <div class="v16-options-capabilities"><b>MARKET CAPABILITY</b>
        <div class="v16-cap-row auto"><strong>NIFTY / BANKNIFTY · AUTO PAPER</strong><span>Verified FYERS chain → auto CALL/PUT → canonical Paper Desk.</span></div>
        <div class="v16-cap-row gated"><strong>SENSEX · AUTO GATED</strong><span>Provider chain and exact BSE contract must verify or the route fails closed.</span></div>
        <div class="v16-cap-row research"><strong>CRUDEOIL / GOLD / SILVER / NAT GAS · CHAIN / RESEARCH</strong><span>Verified FYERS MCX option-chain data is selectable in the center workspace. Canonical auto execution is not yet audited.</span></div>
        <div class="v16-cap-row research"><strong>BTC / ETH · PUBLIC RESEARCH</strong><span>Verified Deribit public option chain is selectable. No separate crypto paper ledger is used in V16.</span></div>
      </div>
      <div class="v16-options-side-msg" id="v16OptionsSideMessage">Loading canonical option state…</div>`;
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
    if (enabled && intel.firstElementChild !== optionsCard) intel.prepend(optionsCard);
  }

  function setCenterOptionsVisibility(enabled) {
    const panel = $("v16Options");
    if (!panel) return false;
    panel.hidden = !enabled;
    if (enabled) {
      ensureDomainBar();
      const grid = $("chartGrid");
      if (grid?.parentElement && panel.nextElementSibling !== grid) grid.parentElement.insertBefore(panel, grid);
    }
    return true;
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
    if ($("v16DomainUnderlying")) $("v16DomainUnderlying").textContent = `${underlying} · UNDERLYING LEVELS ONLY`;

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

  function optionUnderlyingFromPosition(item) {
    const meta = item?.metadata || {};
    const explicit = String(meta.underlying || "").toUpperCase();
    if (explicit) return explicit;
    const symbol = String(item?.symbol || "").toUpperCase();
    if (symbol.includes("BANKNIFTY") || symbol.includes("NIFTYBANK")) return "BANKNIFTY";
    for (const token of ["SENSEX", "CRUDEOIL", "NATURALGAS", "SILVER", "GOLD", "BTC", "ETH", "NIFTY"]) {
      if (symbol.includes(token)) return token;
    }
    return null;
  }

  function positionProvenance(item) {
    const meta = item?.metadata || {};
    if (meta.legacy_fingerprint || meta.legacy_source) return "LEGACY → CANONICAL MIGRATION";
    if (meta.v16_autonomous_option || meta.autonomous_paper) return "V16 AUTONOMOUS PAPER";
    if (meta.manual_option_order || meta.manual_paper) return "V16 MANUAL PAPER";
    return String(item?.source || meta.source || "CANONICAL · PROVENANCE NOT TAGGED");
  }

  function isOptionPosition(item) {
    const meta = item?.metadata || {};
    return String(item?.asset_type || meta.asset_type || "").toUpperCase() === "OPTION" || Boolean(meta.option_type) || /(?:CE|PE)$/.test(String(item?.symbol || "").toUpperCase());
  }

  function renderPositionContext(state) {
    const positions = Array.isArray(state?.positions) ? state.positions.filter(isOptionPosition) : [];
    const underlying = selectedUnderlying();
    const matching = positions.filter(item => optionUnderlyingFromPosition(item) === underlying);
    const other = positions.filter(item => optionUnderlyingFromPosition(item) !== underlying);
    const host = $("v16OptionsOpenPosition");
    if (!host) return;
    if (matching.length) {
      const item = matching[0];
      const meta = item.metadata || {};
      host.innerHTML = `<b>${esc(underlying)} POSITION OPEN</b><br>${esc(item.symbol || "OPTION")} · ${esc(meta.option_type || item.side || "LONG")} · qty ${esc(item.quantity ?? "—")}<br>entry ${esc(item.entry ?? item.entry_price ?? "—")} · SL ${esc(item.stop ?? "—")} · target ${esc(item.target ?? "—")}<div class="v16-option-provenance"><strong>PROVENANCE</strong> · ${esc(positionProvenance(item))}</div>`;
      return;
    }
    const others = other.slice(0, 3).map(item => `${optionUnderlyingFromPosition(item) || "OTHER"}: ${item.symbol} [${positionProvenance(item)}]`);
    host.innerHTML = `<b>${esc(underlying)} POSITION</b><br>No open canonical ${esc(underlying)} option position in this mandate.${others.length ? `<div class="v16-option-provenance"><strong>OTHER CANONICAL OPTION EXPOSURE</strong><br>${others.map(esc).join("<br>")}</div>` : ""}`;
  }

  function syncSessionButtons(session) {
    const running = String(session?.entry_session || "PAUSED").toUpperCase() === "RUNNING";
    const scanning = Boolean(session?.scanning);
    document.querySelectorAll("[data-v16-option-control]").forEach(button => {
      const action = button.dataset.v16OptionControl;
      if (action === "start" || action === "resume") button.disabled = running || busy;
      else if (action === "pause_new_entries") button.disabled = !running || busy;
      else if (action === "stop_scanner") button.disabled = !scanning || busy;
    });
  }

  function renderState(state) {
    latestState = state;
    latestStateAt = Date.now();
    const session = state?.session || {};
    const running = String(session.entry_session || "PAUSED").toUpperCase();
    if ($("v16OptionsSessionState")) $("v16OptionsSessionState").textContent = running;
    if ($("v16OptionsScannerState")) $("v16OptionsScannerState").textContent = session.scanning ? "RUNNING" : "IDLE";
    if ($("v16OptionsReconState")) $("v16OptionsReconState").textContent = session.reconciliation_ok === false ? "BLOCKED" : "CLEAN";
    if ($("v16OptionsStateAge")) $("v16OptionsStateAge").textContent = "FRESH";
    if ($("v16OptionsPipeChain")) {
      const providers = Object.values(state?.market_data?.providers || {});
      const bad = providers.some(item => ["DEGRADED", "RATE_LIMITED", "LOGIN_REQUIRED"].includes(String(item?.state || "").toUpperCase()));
      $("v16OptionsPipeChain").textContent = bad ? "DEGRADED" : "VERIFIED";
      const msg = $("v16OptionsSideMessage");
      if (msg && bad) {
        msg.textContent = "NEW OPTION ENTRIES BLOCKED · provider/chain health is degraded. Existing canonical positions remain managed.";
        msg.dataset.kind = "warn";
      } else if (msg) {
        msg.textContent = "Canonical option state is fresh. New entries still require session, signal, contract, quote, risk and capital gates.";
        msg.dataset.kind = "ok";
      }
    }
    renderPositionContext(state);
    syncSessionButtons(session);
  }

  function markStateStale(error) {
    for (const id of ["v16OptionsSessionState", "v16OptionsScannerState", "v16OptionsReconState"]) {
      if ($(id)) $(id).textContent = "STALE";
    }
    if ($("v16OptionsStateAge")) $("v16OptionsStateAge").textContent = latestStateAt ? `${Math.max(1, Math.round((Date.now() - latestStateAt) / 1000))}s+` : "NO STATE";
    if ($("v16OptionsPipeChain")) $("v16OptionsPipeChain").textContent = "DEGRADED";
    const msg = $("v16OptionsSideMessage");
    if (msg) {
      msg.textContent = `NEW OPTION ENTRIES BLOCKED · canonical state unavailable: ${error.message}. Existing positions remain managed by the server.`;
      msg.dataset.kind = "error";
    }
    syncSessionButtons({entry_session: "PAUSED", scanning: false});
  }

  async function refreshState(force = false) {
    if (activeMode() !== "OPTIONS" && !force) return null;
    try {
      const workspace = optionCapitalWorkspace();
      const state = await requestJson(`/api/v16/trading/workspace-state?workspace=${encodeURIComponent(workspace)}`, {}, 10000);
      if (!state?.success) throw new Error(state?.message || "Canonical state unavailable");
      renderState(state);
      return state;
    } catch (error) {
      markStateStale(error);
      return null;
    }
  }

  async function controlSession(action, button) {
    if (busy) return;
    busy = true;
    const old = button?.textContent;
    if (button) { button.disabled = true; button.textContent = "WORKING…"; }
    try {
      const workspace = optionCapitalWorkspace();
      if (!latestState?.csrf_token || String(latestState?.workspace || "").toUpperCase() !== workspace) await refreshState(true);
      const token = String(latestState?.csrf_token || "");
      if (!token) throw new Error("Local V16 session token is unavailable; refresh the terminal.");
      const payload = await requestJson("/api/terminal/session", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Jarvis-Token": token},
        body: JSON.stringify({workspace, action}),
      });
      const msg = $("v16OptionsSideMessage");
      if (msg) {
        msg.textContent = `${workspace}: ${payload.message || action}. Existing positions remain governed by the canonical Paper Desk.`;
        msg.dataset.kind = "ok";
      }
      await refreshState(true);
    } catch (error) {
      const msg = $("v16OptionsSideMessage");
      if (msg) { msg.textContent = `${action} failed: ${error.message}`; msg.dataset.kind = "error"; }
    } finally {
      busy = false;
      if (button) button.textContent = old;
      syncSessionButtons(latestState?.session || {});
    }
  }

  async function resolveModule(url, serial) {
    for (let attempt = 0; attempt < 16; attempt++) {
      if (serial !== chainSerial) return null;
      const payload = await requestJson(url, {}, 15000);
      if (!payload?.pending) return payload?.result ?? payload;
      await new Promise(resolve => setTimeout(resolve, 400));
    }
    throw new Error("Verified option-chain analysis is still busy; retry shortly.");
  }

  function updateExpiryChoices(payload) {
    const select = $("v16OptionExpiry");
    if (!select) return;
    const current = select.value;
    const expiries = Array.isArray(payload?.available_expiries) ? payload.available_expiries.filter(Boolean) : [];
    select.innerHTML = `<option value="">NEAREST</option>` + expiries.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join("");
    if (current && expiries.includes(current)) select.value = current;
  }

  function renderChain(payload) {
    const underlying = selectedUnderlying();
    const rows = Array.isArray(payload?.chain) ? payload.chain : [];
    const analytics = payload?.chain_analytics || {};
    if ($("v16OptionTitle")) $("v16OptionTitle").textContent = `${underlying} OPTION CHAIN`;
    if ($("v16OptionMessage")) $("v16OptionMessage").textContent = payload?.message || (rows.length ? `Loaded ${rows.length} verified contracts.` : "No verified contracts returned.");
    updateExpiryChoices(payload);
    if ($("v16OptionStats")) {
      const stats = [
        ["SPOT", payload?.spot],
        ["PCR OI", payload?.pcr_oi ?? analytics.pcr_oi],
        ["CALL WALL", analytics.call_oi_wall?.strike],
        ["PUT WALL", analytics.put_oi_wall?.strike],
        ["MAX PAIN", analytics.max_pain?.strike],
      ];
      $("v16OptionStats").innerHTML = stats.map(([name, value]) => `<span><small>${esc(name)}</small><b>${fmt(value)}</b></span>`).join("");
    }
    if ($("v16DomainUnderlying")) $("v16DomainUnderlying").textContent = `${underlying} · ${payload?.spot == null ? "SPOT —" : `SPOT ${fmt(payload.spot)}`}`;
    const body = $("v16OptionRows");
    if (!body) return;
    body.innerHTML = rows.map((contract, index) => {
      const symbol = String(contract.symbol || contract.instrument_name || "");
      const selected = selectedContract && String(selectedContract.symbol || selectedContract.instrument_name || "") === symbol ? " selected" : "";
      return `<tr data-v16-contract="${index}" class="${selected}"><td>${esc(contract.option_type || "—")}</td><td>${fmt(contract.strike, 0)}</td><td>${fmt(contract.ltp)}</td><td>${fmt(contract.bid)}</td><td>${fmt(contract.ask)}</td><td>${fmt(contract.volume, 0)}</td><td>${fmt(contract.open_interest, 0)}</td><td>${fmt(contract.change_in_oi, 0)}</td><td>${fmt(contract.iv)}</td><td>${fmt(contract.delta, 3)}</td><td>${fmt(contract.gamma, 4)}</td><td>${fmt(contract.theta, 3)}</td><td>${fmt(contract.vega, 3)}</td></tr>`;
    }).join("");
    body.querySelectorAll("[data-v16-contract]").forEach(row => {
      row.addEventListener("click", () => selectContract(rows[Number(row.dataset.v16Contract)], payload));
    });
  }

  function selectContract(contract, payload) {
    const symbol = String(contract?.symbol || contract?.instrument_name || "").trim();
    if (!symbol) return;
    selectedContract = contract;
    const underlying = selectedUnderlying();
    const provider = String(payload?.provider || "FYERS_READ_ONLY").toUpperCase();
    if ($("v16SelectedOption")) {
      $("v16SelectedOption").innerHTML = `<b>${esc(symbol)}</b> · ${esc(contract.option_type || "OPTION")} ${fmt(contract.strike, 0)} · LTP ${fmt(contract.ltp)} · IV ${fmt(contract.iv)} · OI ${fmt(contract.open_interest, 0)}<br><span>Selected contract premium chart is isolated from ${esc(underlying)} underlying price levels.</span>`;
    }
    if ($("v16DomainContract")) $("v16DomainContract").textContent = `${symbol} · PREMIUM ${fmt(contract.ltp)}`;
    try {
      window.JARVIS_OPTION_CHART?.open({
        kind: "OPTION",
        provider,
        instrument_name: symbol,
        label: symbol,
        underlying,
        strike: contract.strike,
        option_type: contract.option_type,
        expiry: contract.expiry || payload?.expiry?.date || payload?.expiry || $("v16OptionExpiry")?.value || null,
      });
    } catch {}
    renderChain(payload);
  }

  async function loadChain() {
    if (activeMode() !== "OPTIONS") return;
    const serial = ++chainSerial;
    selectedContract = null;
    if ($("v16OptionMessage")) $("v16OptionMessage").textContent = "Loading verified option chain…";
    const query = new URLSearchParams({workspace: optionCapitalWorkspace(), symbol: selectedUnderlying(), module: "option-chain"});
    const expiry = $("v16OptionExpiry")?.value || "";
    if (expiry) query.set("expiry", expiry);
    try {
      const payload = await resolveModule(`/api/terminal/module?${query}`, serial);
      if (!payload || serial !== chainSerial) return;
      renderChain(payload);
      const chain = $("v16OptionsPipeChain");
      if (chain) chain.textContent = payload.success ? "VERIFIED" : "UNAVAILABLE";
    } catch (error) {
      if (serial !== chainSerial) return;
      renderChain({success: false, message: error.message, chain: []});
      if ($("v16OptionsPipeChain")) $("v16OptionsPipeChain").textContent = "DEGRADED";
    }
  }

  function bindCenterControls() {
    const underlying = $("v16OptionUnderlying");
    if (underlying && !underlying.dataset.v16RouterBound) {
      underlying.dataset.v16RouterBound = "1";
      underlying.addEventListener("change", () => {
        selectedContract = null;
        const expiry = $("v16OptionExpiry");
        if (expiry) expiry.value = "";
        renderCapability();
        loadChain();
        refreshState(true);
      });
    }
    const expiry = $("v16OptionExpiry");
    if (expiry && !expiry.dataset.v16RouterBound) {
      expiry.dataset.v16RouterBound = "1";
      expiry.addEventListener("change", () => { selectedContract = null; loadChain(); });
    }
    const reload = $("v16OptionReload");
    if (reload && !reload.dataset.v16RouterBound) {
      reload.dataset.v16RouterBound = "1";
      reload.addEventListener("click", loadChain);
    }
    const capital = $("v16OptionCapital");
    if (capital && !capital.dataset.v16RouterBound) {
      capital.dataset.v16RouterBound = "1";
      capital.addEventListener("change", event => {
        syncCapital(event.target.value);
        refreshState(true);
      });
    }
  }

  function route() {
    ensureStyle();
    ensureExtraOptionUnderlyings();
    ensureOptionsSidebar();
    bindCenterControls();
    const options = activeMode() === "OPTIONS";
    setOptionsVisibility(options);
    setCenterOptionsVisibility(options);
    if (options) {
      syncCapital(optionCapitalWorkspace());
      renderCapability();
      refreshState(true);
      loadChain();
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

    const intel = document.querySelector(".intel-panel");
    if (intel) {
      new MutationObserver(() => {
        if (activeMode() === "OPTIONS") setOptionsVisibility(true);
        else movePrimaryToTop();
      }).observe(intel, {childList: true});
    }

    pollTimer = setInterval(() => {
      ensureExtraOptionUnderlyings();
      bindCenterControls();
      if (activeMode() === "OPTIONS") {
        setCenterOptionsVisibility(true);
        renderCapability();
        refreshState(false);
        if ($("v16OptionsStateAge") && latestStateAt) $("v16OptionsStateAge").textContent = `${Math.max(0, Math.round((Date.now() - latestStateAt) / 1000))}s`;
      } else movePrimaryToTop();
    }, 2500);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => setTimeout(boot, 0), {once: true});
  else setTimeout(boot, 0);

  window.addEventListener("beforeunload", () => { if (pollTimer) clearInterval(pollTimer); }, {once: true});
})();
