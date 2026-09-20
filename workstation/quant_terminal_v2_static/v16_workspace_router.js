(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  const $ = id => document.getElementById(id);
  const CAPITAL_WORKSPACES = ["INTRADAY", "SWING", "INVESTMENT"];
  const OPTION_UNDERLYINGS = [
    ["NIFTY", "NIFTY"],
    ["BANKNIFTY", "BANKNIFTY"],
    ["SENSEX", "SENSEX"],
    ["CRUDEOIL", "CRUDEOIL · MCX"],
    ["GOLD", "GOLD · MCX"],
    ["SILVER", "SILVER · MCX"],
    ["NATURALGAS", "NAT GAS · MCX"],
    ["BTC", "BTC · DERIBIT"],
    ["ETH", "ETH · DERIBIT"],
  ];
  const OPTION_SET = new Set(OPTION_UNDERLYINGS.map(([value]) => value));
  const hiddenBeforeOptions = new WeakMap();
  let latestState = null;
  let latestStateAt = 0;
  let latestChain = null;
  let pollTimer = null;
  let busy = false;
  let chainSerial = 0;
  let chainAbortController = null;
  const chainCache = new Map();
  const CHAIN_CACHE_MS = 15000;
  let selectedContract = null;
  let selectedContractPayload = null;
  let chartFocus = false;
  let lastMode = null;

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
  const fmtMoney = value => {
    const n = num(value);
    return n === null ? "—" : n.toLocaleString("en-IN", {style: "currency", currency: "INR", maximumFractionDigits: 0});
  };
  const fmtAllocation = value => {
    const n = num(value);
    if (n === null) return "—";
    const pct = Math.abs(n) <= 1 ? n * 100 : n;
    return `${pct.toFixed(pct % 1 ? 1 : 0)}%`;
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

  function marketContextSymbol() {
    let raw = "";
    try { raw = String(selectedSymbol || "").toUpperCase(); } catch {}
    if (!raw) raw = String($("scanSymbol")?.textContent || "").trim().toUpperCase();
    const aliases = {
      "NIFTY 50": "NIFTY", "NIFTY50": "NIFTY",
      "BANK NIFTY": "BANKNIFTY", "BANKNIFTY": "BANKNIFTY",
      "NAT GAS": "NATURALGAS", "NATURAL GAS": "NATURALGAS",
      "BITCOIN": "BTC", "ETHEREUM": "ETH",
    };
    return aliases[raw] || raw.replaceAll(" ", "");
  }

  function capability(underlying) {
    const value = String(underlying || "").toUpperCase();
    if (["NIFTY", "BANKNIFTY"].includes(value)) {
      return {tier: "AUTO PAPER", kind: "auto", source: "FYERS VERIFIED CHAIN + CANONICAL PAPER DESK", detail: "Automatic long CALL/PUT expression is permitted after verified signal, exact contract, fresh quote, risk and Paper Desk gates pass."};
    }
    if (value === "SENSEX") {
      return {tier: "AUTO GATED", kind: "gated", source: "BSE/FYERS CONTRACT PATH", detail: "Autonomous expression remains fail-closed until the current provider chain and exact BSE contract verify."};
    }
    if (["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"].includes(value)) {
      return {tier: "CHAIN / RESEARCH", kind: "research", source: "FYERS MCX OPTION CHAIN V3", detail: "Verified MCX option-chain intelligence is available. Canonical V16 automated option execution is not yet audited for MCX."};
    }
    if (["BTC", "ETH"].includes(value)) {
      return {tier: "OPTIONS RESEARCH + UNDERLYING AUTO PAPER", kind: "auto", source: "DERIBIT RESEARCH + CANONICAL PAPER DESK", detail: "Deribit option contracts remain research-only. BTC/ETH underlying paper entries are autonomous through the canonical Paper Desk after fresh strategy, risk and capital gates pass."};
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
      .v16-options-capital-head{margin:7px 0 4px;color:#8fcde1;font-size:7px;letter-spacing:.09em}.v16-options-capital{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;margin-bottom:7px}.v16-options-capital div{border:1px solid #1c4556;background:#07161e;padding:5px;min-width:0}.v16-options-capital small{display:block;color:#6d94a4;font-size:6px;letter-spacing:.07em}.v16-options-capital b{display:block;margin-top:2px;color:#dff7ff;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v16-options-capital b[data-kind="available"]{color:#7ee9ae}.v16-options-capital b[data-kind="risk"]{color:#ffd166}
      .v16-options-session{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:7px 0}.v16-options-session div{border:1px solid #173949;background:#06131a;padding:6px;border-radius:5px}.v16-options-session small{display:block;color:#6d94a4;font-size:7px}.v16-options-session b{font-size:10px;color:#d7f4ff}
      .v16-options-controls{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:7px 0}.v16-options-controls button{font-size:8px;min-height:29px;padding:5px}.v16-options-controls button:first-child{border-color:#2e8b61;color:#83f2b1;background:#08251a}.v16-options-controls button:disabled{opacity:.38;cursor:not-allowed}
      .v16-options-pipeline{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;margin:7px 0}.v16-options-pipeline span{border:1px solid #173849;background:#07131b;padding:5px;min-width:0}.v16-options-pipeline small{display:block;color:#678d9c;font-size:7px}.v16-options-pipeline b{display:block;color:#ccecf7;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .v16-options-capabilities{border-top:1px solid #173849;margin-top:8px;padding-top:7px}.v16-options-capabilities>b{font-size:8px;color:#9fd8ec;letter-spacing:.08em}.v16-cap-row{margin-top:5px;padding:5px;border-left:2px solid #315368;background:#061219}.v16-cap-row strong{display:block;font-size:8px;color:#d8f5ff}.v16-cap-row span{display:block;margin-top:2px;font-size:7px;color:#7fa3b1;line-height:1.35}.v16-cap-row.auto{border-color:#2e8b61}.v16-cap-row.research{border-color:#99772f}.v16-cap-row.gated{border-color:#a46b34}
      .v16-options-side-msg{margin-top:7px;padding:6px;border-left:2px solid #337d99;background:#061219;color:#9fc4d2;font-size:8px;line-height:1.4}.v16-options-side-msg[data-kind="error"]{border-color:#ff647d;color:#ff9aad}.v16-options-side-msg[data-kind="ok"]{border-color:#45d68b;color:#8cedb4}.v16-options-side-msg[data-kind="warn"]{border-color:#ffd166;color:#e7d18a}
      .v16-options-open{border-top:1px solid #173849;margin-top:7px;padding-top:6px;font-size:8px;color:#8fb1be;line-height:1.45}.v16-options-open b{color:#dff7ff}
      .v16-option-chart-actions{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:6px;align-items:center;margin:7px 0;padding:7px;border:1px solid #24566a;background:#071922}.v16-option-chart-actions span{min-width:0}.v16-option-chart-actions small{display:block;color:#6e9cad;font-size:7px;letter-spacing:.09em}.v16-option-chart-actions b{display:block;margin-top:2px;color:#d8f5ff;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v16-option-chart-actions button{min-height:30px;padding:5px 9px;font-size:8px;white-space:nowrap}.v16-option-chart-actions button:disabled{opacity:.4;cursor:not-allowed}.v16-option-chart-actions #v16OpenOptionChart{border-color:#2d8b61;color:#83f2b1;background:#08251a}.v16-option-chart-actions #v16BackToOptionChain{border-color:#4b7589;color:#caefff;background:#0a202b}
      html.v16-options-workspace .intel-panel>#v16OptionsSidebar{display:block!important}
      html.v16-options-workspace #v16Options{display:block!important;max-height:none!important;min-height:250px;border-color:#2a657d;background:#06151d}
      html.v16-options-workspace #v16Options .v16-option-table-wrap{max-height:275px}
      html.v16-options-workspace #chartGrid{min-height:330px}
      html.v16-options-workspace .workspace-toolbar{border-color:#1e4c60}
      html.v16-options-workspace.v16-option-chart-focus #v16Options{min-height:0!important;padding-top:5px!important;padding-bottom:5px!important}
      html.v16-options-workspace.v16-option-chart-focus #v16Options>:not(#v16SelectedOption):not(#v16OptionChartActions){display:none!important}
      html.v16-options-workspace.v16-option-chart-focus #v16SelectedOption{margin-top:0!important}
      html.v16-options-workspace.v16-option-chart-focus #v16OptionChartActions{margin-bottom:0!important}
      html.v16-options-workspace.v16-option-chart-focus #chartGrid{min-height:560px!important}
      .v16-option-domain-bar{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:6px 0}.v16-option-domain-bar>div{border:1px solid #1a4152;background:#07151d;padding:6px;border-radius:5px}.v16-option-domain-bar small{display:block;color:#6f94a4;font-size:7px;letter-spacing:.08em}.v16-option-domain-bar b{display:block;color:#d7f4ff;font-size:10px;margin-top:2px}.v16-option-domain-bar span{display:block;color:#82a9b7;font-size:8px;margin-top:2px;line-height:1.35}
      .v16-option-provenance{margin-top:5px;color:#87aebb;font-size:8px}.v16-option-provenance strong{color:#ccecf7}
    `;
    document.head.appendChild(style);
  }

  function requestSuperseded() {
    const error = new Error("REQUEST_SUPERSEDED");
    error.code = "REQUEST_SUPERSEDED";
    return error;
  }

  async function requestJson(url, options = {}, timeoutMs = 12000) {
    const externalSignal = options.signal || null;
    const controller = new AbortController();
    const onAbort = () => controller.abort();
    if (externalSignal) {
      if (externalSignal.aborted) onAbort();
      else externalSignal.addEventListener("abort", onAbort, {once:true});
    }
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {...options, signal: controller.signal, cache: "no-store"});
      let payload = {};
      try { payload = await response.json(); } catch {}
      if (!response.ok) throw new Error(payload.message || payload.reason || `HTTP ${response.status}`);
      return payload;
    } catch (error) {
      if (error?.name === "AbortError") {
        if (externalSignal?.aborted) throw requestSuperseded();
        const timeout = new Error("Request timed out");
        timeout.code = "MARKET_DATA_TIMEOUT";
        throw timeout;
      }
      throw error;
    } finally {
      clearTimeout(timer);
      if (externalSignal) externalSignal.removeEventListener("abort", onAbort);
    }
  }

  function ensureOptionsCenter() {
    let panel = $("v16Options");
    if (panel) return panel;
    const grid = $("chartGrid");
    if (!grid?.parentElement) return null;
    panel = document.createElement("section");
    panel.id = "v16Options";
    panel.hidden = true;
    panel.innerHTML = `
      <div class="v16-option-head">
        <div><div class="eyebrow">OPTIONS WORKSPACE · VERIFIED PROVIDER DATA</div><strong id="v16OptionTitle">NIFTY OPTION CHAIN</strong></div>
        <div class="v16-option-controls">
          <label>Underlying<select id="v16OptionUnderlying">${OPTION_UNDERLYINGS.map(([value,label])=>`<option value="${value}">${label}</option>`).join("")}</select></label>
          <label>Expiry<select id="v16OptionExpiry"><option value="">NEAREST</option></select></label>
          <label>Capital<select id="v16OptionCapital">${CAPITAL_WORKSPACES.map(value=>`<option value="${value}">${value}</option>`).join("")}</select></label>
          <button id="v16OptionReload" type="button">RELOAD CHAIN</button>
        </div>
      </div>
      <div id="v16OptionStats" class="v16-option-stats"></div>
      <div id="v16OptionMessage" class="v16-option-message">Select OPTIONS to load the verified chain.</div>
      <div class="v16-option-table-wrap"><table><thead><tr><th>TYPE</th><th>STRIKE</th><th>LTP</th><th>BID</th><th>ASK</th><th>VOL</th><th>OI</th><th>ΔOI</th><th>IV</th><th>DELTA</th><th>GAMMA</th><th>THETA</th><th>VEGA</th></tr></thead><tbody id="v16OptionRows"></tbody></table></div>
      <div id="v16SelectedOption" class="v16-selected-option">No contract selected.</div>
      <small class="v16-option-safety">PAPER / RESEARCH ONLY · LIVE BROKER EXECUTION LOCKED · NAKED OPTION SELLING BLOCKED</small>`;
    grid.parentElement.insertBefore(panel, grid);
    return panel;
  }

  function ensureExtraOptionUnderlyings() {
    const select = $("v16OptionUnderlying");
    if (!select) return;
    const existing = new Set([...select.options].map(option => String(option.value).toUpperCase()));
    OPTION_UNDERLYINGS.forEach(([value, label]) => {
      if (existing.has(value)) return;
      const option = document.createElement("option"); option.value = value; option.textContent = label; select.appendChild(option);
    });
  }

  function syncCapital(value) {
    const canonical = $("v16OptionCapital");
    const side = $("v16OptionsSideCapital");
    const next = CAPITAL_WORKSPACES.includes(String(value || "").toUpperCase()) ? String(value).toUpperCase() : "INTRADAY";
    if (canonical && canonical.value !== next) canonical.value = next;
    if (side && side.value !== next) side.value = next;
  }

  function syncUnderlyingFromMarketContext() {
    const select = $("v16OptionUnderlying");
    if (!select || select.dataset.userChosen === "1") return;
    const context = marketContextSymbol();
    if (OPTION_SET.has(context)) select.value = context;
  }

  function syncUnderlyingChartContext() {
    const underlying = selectedUnderlying();
    try {
      const slot = Array.isArray(chartSlots) ? (chartSlots[selectedSlot] || chartSlots[0]) : null;
      if (slot?.kind === "OPTION" && slot.optionChart) return;
      if (String(slot?.symbol || "").toUpperCase() !== underlying && typeof selectMarket === "function") selectMarket(underlying);
    } catch {}
  }

  function ensureDomainBar() {
    const panel = $("v16Options");
    if (!panel || $("v16OptionDomainBar")) return;
    const bar = document.createElement("div"); bar.id = "v16OptionDomainBar"; bar.className = "v16-option-domain-bar";
    bar.innerHTML = `<div><small>UNDERLYING DOMAIN</small><b id="v16DomainUnderlying">NIFTY · —</b><span>Structure, support/resistance, regime and directional thesis belong to the underlying only.</span></div><div><small>OPTION PREMIUM DOMAIN</small><b id="v16DomainContract">NO CONTRACT SELECTED</b><span>Premium chart receives only option-contract indicators plus canonical option entry/SL/target geometry.</span></div>`;
    const head = panel.querySelector(".v16-option-head");
    if (head?.nextSibling) panel.insertBefore(bar, head.nextSibling); else panel.prepend(bar);
  }

  function syncOptionChartActions() {
    const symbol = String(selectedContract?.symbol || selectedContract?.instrument_name || "").trim();
    const open = $("v16OpenOptionChart"); const back = $("v16BackToOptionChain"); const label = $("v16OptionChartSelection");
    if (open) { open.disabled = !symbol; open.hidden = chartFocus; }
    if (back) back.hidden = !chartFocus;
    if (label) label.textContent = symbol || "Select a chain row first.";
  }

  function setOptionChartFocus(enabled) {
    chartFocus = Boolean(enabled && selectedContract);
    document.documentElement.classList.toggle("v16-option-chart-focus", chartFocus);
    syncOptionChartActions();
    if (chartFocus) {
      requestAnimationFrame(() => $("chartGrid")?.scrollIntoView({behavior: "smooth", block: "start"}));
    }
  }

  function openSelectedOptionChart() {
    const contract = selectedContract; const payload = selectedContractPayload || {};
    const symbol = String(contract?.symbol || contract?.instrument_name || "").trim();
    if (!symbol) return;
    const provider = String(payload?.provider || "FYERS_READ_ONLY").toUpperCase(); const underlying = selectedUnderlying();
    if (typeof window.JARVIS_OPTION_CHART?.open !== "function") {
      if ($("v16OptionMessage")) $("v16OptionMessage").textContent = "Option chart runtime is unavailable. The selected contract remains viewing-only.";
      return;
    }
    try {
      window.JARVIS_OPTION_CHART.open({kind:"OPTION", provider, instrument_name:symbol, label:symbol, underlying, strike:contract.strike, option_type:contract.option_type, expiry:contract.expiry || payload?.expiry?.date || payload?.expiry || $("v16OptionExpiry")?.value || null});
      setOptionChartFocus(true);
    } catch (error) {
      if ($("v16OptionMessage")) $("v16OptionMessage").textContent = `Option chart could not be opened: ${error?.message || "unknown error"}`;
    }
  }

  function ensureOptionChartActions() {
    const panel = $("v16Options"); if (!panel) return null;
    let actions = $("v16OptionChartActions"); if (actions) { syncOptionChartActions(); return actions; }
    actions = document.createElement("div"); actions.id = "v16OptionChartActions"; actions.className = "v16-option-chart-actions";
    actions.innerHTML = `<span><small>VIEWING CONTRACT · MANUAL RESEARCH CONTROL</small><b id="v16OptionChartSelection">Select a chain row first.</b></span><button id="v16OpenOptionChart" type="button" disabled>OPEN OPTION CHART</button><button id="v16BackToOptionChain" type="button" hidden>BACK TO CHAIN</button>`;
    const selected = $("v16SelectedOption");
    if (selected?.parentElement === panel) selected.insertAdjacentElement("afterend", actions); else panel.appendChild(actions);
    $("v16OpenOptionChart")?.addEventListener("click", openSelectedOptionChart);
    $("v16BackToOptionChain")?.addEventListener("click", () => { setOptionChartFocus(false); requestAnimationFrame(() => $("v16Options")?.scrollIntoView({behavior: "smooth", block: "start"})); });
    syncOptionChartActions();
    return actions;
  }

  function ensureOptionsSidebar() {
    const intel = document.querySelector(".intel-panel");
    if (!intel) return null;
    let card = $("v16OptionsSidebar");
    if (card) return card;
    card = document.createElement("section"); card.id = "v16OptionsSidebar"; card.className = "intel-card v16-options-sidebar";
    card.innerHTML = `<div class="eyebrow">OPTIONS WORKSPACE · CANONICAL V16</div><div class="v16-options-side-head"><b>OPTIONS AUTOPILOT</b><span id="v16OptionsTier">WAITING</span></div><div class="v16-options-side-note"><strong id="v16OptionsUnderlyingLabel">NIFTY</strong> · <span id="v16OptionsSource">provider check</span><br><span id="v16OptionsCapabilityText">Loading capability state…</span></div><div class="v16-options-side-select"><label>CAPITAL MANDATE</label><select id="v16OptionsSideCapital"><option>INTRADAY</option><option>SWING</option><option>INVESTMENT</option></select></div><div class="v16-options-capital-head">CAPITAL ALLOCATION · CANONICAL PAPER DESK</div><div class="v16-options-capital"><div><small>MANDATE</small><b id="v16OptionsCapitalMandate">—</b></div><div><small>ALLOCATED</small><b id="v16OptionsCapitalAllocated">—</b></div><div><small>AVAILABLE</small><b id="v16OptionsCapitalAvailable" data-kind="available">—</b></div><div><small>COMMITTED</small><b id="v16OptionsCapitalCommitted">—</b></div><div><small>OPEN RISK</small><b id="v16OptionsCapitalRisk" data-kind="risk">—</b></div><div><small>EQUITY</small><b id="v16OptionsCapitalEquity">—</b></div></div><div class="v16-options-session"><div><small>ENTRY SESSION</small><b id="v16OptionsSessionState">—</b></div><div><small>SCANNER</small><b id="v16OptionsScannerState">—</b></div><div><small>RECONCILIATION</small><b id="v16OptionsReconState">—</b></div><div><small>STATE AGE</small><b id="v16OptionsStateAge">—</b></div></div><div class="v16-options-controls"><button data-v16-option-control="start">START SESSION</button><button data-v16-option-control="pause_new_entries">PAUSE NEW ENTRIES</button><button data-v16-option-control="resume">RESUME</button><button data-v16-option-control="stop_scanner">STOP SCANNER</button></div><div class="v16-options-pipeline"><span><small>CHAIN</small><b id="v16OptionsPipeChain">VERIFY</b></span><span><small>CONTRACT</small><b id="v16OptionsPipeContract">AUTO</b></span><span><small>RISK</small><b id="v16OptionsPipeRisk">AUTO</b></span><span><small>SIZE</small><b id="v16OptionsPipeSize">PAPER DESK</b></span><span><small>MANAGE</small><b>AUTO</b></span><span><small>LIVE BROKER</small><b>LOCKED</b></span></div><div class="v16-options-open" id="v16OptionsOpenPosition"><b>POSITION</b><br>No open canonical option position in this mandate.</div><div class="v16-options-capabilities"><b>MARKET CAPABILITY</b><div class="v16-cap-row auto"><strong>NIFTY / BANKNIFTY · AUTO PAPER</strong><span>Verified FYERS chain → auto CALL/PUT → canonical Paper Desk.</span></div><div class="v16-cap-row gated"><strong>SENSEX · AUTO GATED</strong><span>Provider chain and exact BSE contract must verify or the route fails closed.</span></div><div class="v16-cap-row research"><strong>CRUDEOIL / GOLD / SILVER / NAT GAS · CHAIN / RESEARCH</strong><span>Verified FYERS MCX option-chain data is selectable in the center workspace. Canonical V16 auto execution is not yet audited.</span></div><div class="v16-cap-row auto"><strong>BTC / ETH / SOL · UNDERLYING AUTO PAPER</strong><span>Canonical Paper Desk can autonomously open and manage verified crypto underlying PAPER positions. Deribit options remain research-only.</span></div></div><div class="v16-options-side-msg" id="v16OptionsSideMessage">Loading canonical option state…</div>`;
    intel.prepend(card);
    $("v16OptionsSideCapital")?.addEventListener("change", event => { syncCapital(event.target.value); refreshState(true); });
    card.querySelectorAll("[data-v16-option-control]").forEach(button => button.addEventListener("click", () => controlSession(button.dataset.v16OptionControl, button)));
    return card;
  }

  function movePrimaryToTop() {
    const intel = document.querySelector(".intel-panel"); const primary = $("v16AutonomyPrimary");
    if (!intel || !primary || activeMode() === "OPTIONS") return;
    primary.classList.add("intel-card"); if (primary.parentElement !== intel || intel.firstElementChild !== primary) intel.prepend(primary);
  }

  function setOptionsVisibility(enabled) {
    const intel = document.querySelector(".intel-panel"); const optionsCard = ensureOptionsSidebar();
    if (!intel || !optionsCard) return;
    document.documentElement.classList.toggle("v16-options-workspace", enabled);
    [...intel.children].forEach(node => {
      if (node === optionsCard) { node.hidden = !enabled; return; }
      if (node.id === "v17CryptoPaperCard") { node.hidden = false; return; }
      if (enabled) { if (!hiddenBeforeOptions.has(node)) hiddenBeforeOptions.set(node, Boolean(node.hidden)); node.hidden = true; }
      else if (hiddenBeforeOptions.has(node)) { node.hidden = hiddenBeforeOptions.get(node); hiddenBeforeOptions.delete(node); }
    });
    if (enabled) {
      if (intel.firstElementChild !== optionsCard) intel.prepend(optionsCard);
      const unified = $("v17CryptoPaperCard");
      if (unified?.parentElement === intel) intel.prepend(unified);
    }
  }

  function setCenterOptionsVisibility(enabled) {
    const panel = ensureOptionsCenter();
    if (!panel) return false;
    panel.hidden = !enabled;
    if (enabled) {
      ensureDomainBar(); ensureOptionChartActions();
      const grid = $("chartGrid");
      if (grid?.parentElement && panel.nextElementSibling !== grid) grid.parentElement.insertBefore(panel, grid);
    } else {
      setOptionChartFocus(false);
    }
    return true;
  }

  function renderCapability() {
    const underlying = selectedUnderlying(); const cap = capability(underlying); const tier = $("v16OptionsTier");
    if (tier) { tier.textContent = cap.tier; tier.dataset.kind = cap.kind; }
    if ($("v16OptionsUnderlyingLabel")) $("v16OptionsUnderlyingLabel").textContent = underlying;
    if ($("v16OptionsSource")) $("v16OptionsSource").textContent = cap.source;
    if ($("v16OptionsCapabilityText")) $("v16OptionsCapabilityText").textContent = cap.detail;
    if ($("v16OptionsPipeContract")) $("v16OptionsPipeContract").textContent = cap.kind === "auto" || cap.kind === "gated" ? "AUTO" : "RESEARCH";
    if ($("v16OptionsPipeRisk")) $("v16OptionsPipeRisk").textContent = cap.kind === "auto" ? "AUTO" : cap.kind === "gated" ? "GATED" : "NO ENTRY";
    if ($("v16OptionsPipeSize")) $("v16OptionsPipeSize").textContent = cap.kind === "auto" ? "PAPER DESK" : "N/A";
    if ($("v16DomainUnderlying")) $("v16DomainUnderlying").textContent = `${underlying} · UNDERLYING LEVELS ONLY`;
  }

  function optionUnderlyingFromPosition(item) {
    const meta = item?.metadata || {}; const explicit = String(meta.underlying || "").toUpperCase(); if (explicit) return explicit;
    const symbol = String(item?.symbol || "").toUpperCase();
    if (symbol.includes("BANKNIFTY") || symbol.includes("NIFTYBANK")) return "BANKNIFTY";
    for (const token of ["SENSEX", "CRUDEOIL", "NATURALGAS", "SILVER", "GOLD", "BTC", "ETH", "NIFTY"]) if (symbol.includes(token)) return token;
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
    const allPositions = Array.isArray(state?.positions) ? state.positions : [];
    const positions = allPositions.filter(isOptionPosition);
    const underlying = selectedUnderlying(); const matching = positions.filter(item => optionUnderlyingFromPosition(item) === underlying); const other = positions.filter(item => optionUnderlyingFromPosition(item) !== underlying); const host = $("v16OptionsOpenPosition");
    if (!host) return;
    const cryptoUnderlying = ["BTC", "ETH", "SOL"].includes(underlying)
      ? allPositions.find(item => String(item?.symbol || "").toUpperCase() === underlying && !isOptionPosition(item))
      : null;
    if (cryptoUnderlying) {
      host.innerHTML = `<b>${esc(underlying)} UNDERLYING PAPER POSITION OPEN</b><br>${esc(cryptoUnderlying.side || "—")} · qty ${esc(cryptoUnderlying.quantity ?? "—")}<br>entry ${esc(cryptoUnderlying.entry ?? cryptoUnderlying.entry_price ?? "—")} · mark ${esc(cryptoUnderlying.mark ?? "—")}<br>SL ${esc(cryptoUnderlying.stop ?? "—")} · target ${esc(cryptoUnderlying.target ?? "—")}<div class="v16-option-provenance"><strong>CANONICAL PAPER DESK</strong> · autonomous crypto underlying; Deribit options remain research-only.</div>`;
      return;
    }
    if (matching.length) {
      const item = matching[0]; const meta = item.metadata || {};
      host.innerHTML = `<b>${esc(underlying)} POSITION OPEN</b><br>${esc(item.symbol || "OPTION")} · ${esc(meta.option_type || item.side || "LONG")} · qty ${esc(item.quantity ?? "—")}<br>entry ${esc(item.entry ?? item.entry_price ?? "—")} · SL ${esc(item.stop ?? "—")} · target ${esc(item.target ?? "—")}<div class="v16-option-provenance"><strong>PROVENANCE</strong> · ${esc(positionProvenance(item))}</div>`; return;
    }
    const others = other.slice(0, 3).map(item => `${optionUnderlyingFromPosition(item) || "OTHER"}: ${item.symbol} [${positionProvenance(item)}]`);
    host.innerHTML = `<b>${esc(underlying)} POSITION</b><br>No open canonical ${esc(underlying)} option position in this mandate.${others.length ? `<div class="v16-option-provenance"><strong>OTHER CANONICAL OPTION EXPOSURE</strong><br>${others.map(esc).join("<br>")}</div>` : ""}`;
  }

  function renderCapitalAccount(state) {
    const account = state?.account || {};
    const workspace = String(state?.workspace || optionCapitalWorkspace()).toUpperCase();
    if ($("v16OptionsCapitalMandate")) $("v16OptionsCapitalMandate").textContent = `${workspace} · ${fmtAllocation(account.allocation)}`;
    if ($("v16OptionsCapitalAllocated")) $("v16OptionsCapitalAllocated").textContent = fmtMoney(account.starting_capital);
    if ($("v16OptionsCapitalAvailable")) $("v16OptionsCapitalAvailable").textContent = fmtMoney(account.available_capital);
    if ($("v16OptionsCapitalCommitted")) $("v16OptionsCapitalCommitted").textContent = fmtMoney(account.committed_capital);
    if ($("v16OptionsCapitalRisk")) $("v16OptionsCapitalRisk").textContent = fmtMoney(account.open_risk);
    if ($("v16OptionsCapitalEquity")) $("v16OptionsCapitalEquity").textContent = fmtMoney(account.equity);
  }

  function syncSessionButtons(session) {
    const running = String(session?.entry_session || "PAUSED").toUpperCase() === "RUNNING"; const scanning = Boolean(session?.scanning);
    document.querySelectorAll("[data-v16-option-control]").forEach(button => {
      const action = button.dataset.v16OptionControl;
      if (action === "start" || action === "resume") button.disabled = running || busy;
      else if (action === "pause_new_entries") button.disabled = !running || busy;
      else if (action === "stop_scanner") button.disabled = !scanning || busy;
    });
  }

  function selectedChainHealth() {
    const underlying = selectedUnderlying();
    if (!latestChain || latestChain.underlying !== underlying) return {status: "WAITING", reason: "chain not loaded for selected underlying"};
    const ageMs = Date.now() - latestChain.receivedAt;
    if (ageMs > 30000) return {status: "DEGRADED", reason: "selected option chain is stale"};
    if (latestChain.status !== "VERIFIED") return {status: latestChain.status, reason: latestChain.message || "selected option chain is unavailable"};
    return {status: "VERIFIED", reason: `${latestChain.provider || "provider"} · ${latestChain.rows} contracts · fresh`};
  }

  function applyChainGateMessage(stateFresh = true) {
    const cap = capability(selectedUnderlying());
    const chain = selectedChainHealth();
    const node = $("v16OptionsPipeChain");
    if (node) node.textContent = chain.status;
    const msg = $("v16OptionsSideMessage");
    if (!msg) return;
    if (!stateFresh) return;
    if (cap.kind === "research" || cap.kind === "blocked") {
      msg.textContent = `${cap.tier} · ${cap.detail} No automatic paper entry is permitted for this underlying.`;
      msg.dataset.kind = "warn";
      return;
    }
    if (chain.status !== "VERIFIED") {
      msg.textContent = `NEW OPTION ENTRIES BLOCKED · ${chain.reason}. Existing canonical positions remain managed.`;
      msg.dataset.kind = "warn";
      return;
    }
    msg.textContent = `SELECTED CHAIN VERIFIED · ${chain.reason}. New entries still require session, signal, exact contract, fresh quote, risk and capital gates.`;
    msg.dataset.kind = "ok";
  }

  function renderState(state) {
    latestState = state; latestStateAt = Date.now(); const session = state?.session || {}; const running = String(session.entry_session || "PAUSED").toUpperCase();
    if ($("v16OptionsSessionState")) $("v16OptionsSessionState").textContent = running;
    if ($("v16OptionsScannerState")) $("v16OptionsScannerState").textContent = session.scanning ? "RUNNING" : "IDLE";
    if ($("v16OptionsReconState")) $("v16OptionsReconState").textContent = session.reconciliation_ok === false ? "BLOCKED" : "CLEAN";
    if ($("v16OptionsStateAge")) $("v16OptionsStateAge").textContent = "FRESH";
    renderCapitalAccount(state); applyChainGateMessage(true);
    renderPositionContext(state); syncSessionButtons(session);
  }

  function markStateStale(error) {
    for (const id of ["v16OptionsSessionState", "v16OptionsScannerState", "v16OptionsReconState"]) if ($(id)) $(id).textContent = "STALE";
    if ($("v16OptionsStateAge")) $("v16OptionsStateAge").textContent = latestStateAt ? `${Math.max(1, Math.round((Date.now() - latestStateAt) / 1000))}s+` : "NO STATE";
    if ($("v16OptionsPipeChain")) $("v16OptionsPipeChain").textContent = "DEGRADED";
    const msg = $("v16OptionsSideMessage"); if (msg) { msg.textContent = `NEW OPTION ENTRIES BLOCKED · canonical state unavailable: ${error.message}. Existing positions remain managed by the server.`; msg.dataset.kind = "error"; }
    syncSessionButtons({entry_session: "PAUSED", scanning: false});
  }

  async function refreshState(force = false) {
    if (activeMode() !== "OPTIONS" && !force) return null;
    try { const workspace = optionCapitalWorkspace(); const state = await requestJson(`/api/v16/trading/workspace-state?workspace=${encodeURIComponent(workspace)}`, {}, 10000); if (!state?.success) throw new Error(state?.message || "Canonical state unavailable"); renderState(state); return state; }
    catch (error) { markStateStale(error); return null; }
  }

  async function controlSession(action, button) {
    if (busy) return; busy = true; const old = button?.textContent; if (button) { button.disabled = true; button.textContent = "WORKING…"; }
    try {
      const workspace = optionCapitalWorkspace(); if (!latestState?.csrf_token || String(latestState?.workspace || "").toUpperCase() !== workspace) await refreshState(true);
      const token = String(latestState?.csrf_token || ""); if (!token) throw new Error("Local V16 session token is unavailable; refresh the terminal.");
      const payload = await requestJson("/api/terminal/session", {method: "POST", headers: {"Content-Type": "application/json", "X-Jarvis-Token": token}, body: JSON.stringify({workspace, action})});
      const msg = $("v16OptionsSideMessage"); if (msg) { msg.textContent = `${workspace}: ${payload.message || action}. Existing positions remain governed by the canonical Paper Desk.`; msg.dataset.kind = "ok"; }
      await refreshState(true);
    } catch (error) { const msg = $("v16OptionsSideMessage"); if (msg) { msg.textContent = `${action} failed: ${error.message}`; msg.dataset.kind = "error"; } }
    finally { busy = false; if (button) button.textContent = old; syncSessionButtons(latestState?.session || {}); }
  }

  async function resolveModule(url, serial, signal) {
    // Provider-backed option chains can take several seconds (and a selected
    // expiry may require two read-only FYERS calls). Keep the UI asynchronous,
    // but give the bounded server-side job enough time to finish.
    for (let attempt = 0; attempt < 30; attempt++) {
      if (serial !== chainSerial || signal?.aborted) throw requestSuperseded();
      const plane = window.JARVIS_V17_DATA_PLANE?.snapshot?.();
      const payload = await requestJson(url, {
        signal,
        jarvisPriority: 4,
        jarvisGeneration: plane?.generation,
        jarvisScope: "workspace",
      }, 12000);
      if (!payload?.pending) return payload?.result ?? payload;
      await new Promise((resolve,reject) => {
        const timer=setTimeout(resolve,500);
        signal?.addEventListener("abort",()=>{clearTimeout(timer);reject(requestSuperseded())},{once:true});
      });
    }
    throw new Error("Verified option-chain analysis is still busy; retry shortly.");
  }

  function updateExpiryChoices(payload) {
    const select = $("v16OptionExpiry"); if (!select) return; const current = select.value; const expiries = Array.isArray(payload?.available_expiries) ? payload.available_expiries.filter(Boolean) : [];
    select.innerHTML = `<option value="">NEAREST</option>` + expiries.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join(""); if (current && expiries.includes(current)) select.value = current;
  }

  function renderChain(payload) {
    const underlying = selectedUnderlying(); const rows = Array.isArray(payload?.chain) ? payload.chain : []; const analytics = payload?.chain_analytics || {};
    if ($("v16OptionTitle")) $("v16OptionTitle").textContent = `${underlying} OPTION CHAIN`;
    if ($("v16OptionMessage")) $("v16OptionMessage").textContent = payload?.message || (rows.length ? `Loaded ${rows.length} verified contracts.` : "No verified contracts returned.");
    updateExpiryChoices(payload);
    if ($("v16OptionStats")) {
      const stats = [["SPOT", payload?.spot], ["PCR OI", payload?.pcr_oi ?? analytics.pcr_oi], ["CALL WALL", analytics.call_oi_wall?.strike], ["PUT WALL", analytics.put_oi_wall?.strike], ["MAX PAIN", analytics.max_pain?.strike]];
      $("v16OptionStats").innerHTML = stats.map(([name,value]) => `<span><small>${esc(name)}</small><b>${fmt(value)}</b></span>`).join("");
    }
    if ($("v16DomainUnderlying")) $("v16DomainUnderlying").textContent = `${underlying} · ${payload?.spot == null ? "SPOT —" : `SPOT ${fmt(payload.spot)}`}`;
    const body = $("v16OptionRows"); if (!body) return;
    body.innerHTML = rows.map((contract,index) => { const symbol = String(contract.symbol || contract.instrument_name || ""); const selected = selectedContract && String(selectedContract.symbol || selectedContract.instrument_name || "") === symbol ? " selected" : ""; return `<tr data-v16-contract="${index}" class="${selected}"><td>${esc(contract.option_type || "—")}</td><td>${fmt(contract.strike,0)}</td><td>${fmt(contract.ltp)}</td><td>${fmt(contract.bid)}</td><td>${fmt(contract.ask)}</td><td>${fmt(contract.volume,0)}</td><td>${fmt(contract.open_interest,0)}</td><td>${fmt(contract.change_in_oi,0)}</td><td>${fmt(contract.iv)}</td><td>${fmt(contract.delta,3)}</td><td>${fmt(contract.gamma,4)}</td><td>${fmt(contract.theta,3)}</td><td>${fmt(contract.vega,3)}</td></tr>`; }).join("");
    body.querySelectorAll("[data-v16-contract]").forEach(row => row.addEventListener("click", () => selectContract(rows[Number(row.dataset.v16Contract)], payload)));
    syncOptionChartActions();
  }

  function selectContract(contract, payload) {
    const symbol = String(contract?.symbol || contract?.instrument_name || "").trim(); if (!symbol) return; selectedContract = contract; selectedContractPayload = payload; setOptionChartFocus(false);
    const underlying = selectedUnderlying();
    if ($("v16SelectedOption")) $("v16SelectedOption").innerHTML = `<span class="v16-viewing-contract-label">VIEWING CONTRACT · NOT EXECUTION AUTHORITY</span><b>${esc(symbol)}</b> · ${esc(contract.option_type || "OPTION")} ${fmt(contract.strike,0)} · LTP ${fmt(contract.ltp)} · IV ${fmt(contract.iv)} · OI ${fmt(contract.open_interest,0)}<br><span>Row selection no longer opens the chart. Use OPEN OPTION CHART when you want a focused premium chart. The premium chart is isolated from ${esc(underlying)} underlying price levels.</span>`;
    if ($("v16DomainContract")) $("v16DomainContract").textContent = `${symbol} · PREMIUM ${fmt(contract.ltp)}`;
    renderChain(payload); syncOptionChartActions();
  }

  async function loadChain({force=false} = {}) {
    if (activeMode() !== "OPTIONS") return;
    const underlying = selectedUnderlying();
    const expiryValue = $("v16OptionExpiry")?.value || "";
    const workspace = optionCapitalWorkspace();
    const key = [workspace,underlying,expiryValue].join("|");
    const cached = chainCache.get(key);
    if (!force && cached && Date.now() - cached.at < CHAIN_CACHE_MS) {
      latestChain = cached.latestChain;
      renderChain(cached.payload);
      applyChainGateMessage(Boolean(latestState));
      return cached.payload;
    }

    if (chainAbortController) {
      try { chainAbortController.abort(); } catch {}
    }
    chainAbortController = new AbortController();
    const signal = chainAbortController.signal;
    const serial = ++chainSerial;
    selectedContract = null;
    selectedContractPayload = null;
    setOptionChartFocus(false);
    latestChain = {underlying,status:"LOADING",provider:"",rows:0,receivedAt:Date.now(),message:"loading selected option chain"};
    if ($("v16SelectedOption")) $("v16SelectedOption").textContent = "No contract selected. Click a row to select it, then use OPEN OPTION CHART.";
    if ($("v16DomainContract")) $("v16DomainContract").textContent = "NO CONTRACT SELECTED";
    syncOptionChartActions();
    if ($("v16OptionMessage")) $("v16OptionMessage").textContent = "Loading verified option chain in background…";
    if ($("v16OptionsPipeChain")) $("v16OptionsPipeChain").textContent = "LOADING";

    const query = new URLSearchParams({workspace, symbol:underlying, module:"option-chain"});
    if (expiryValue) query.set("expiry",expiryValue);

    try {
      const payload = await resolveModule(`/api/terminal/module?${query}`,serial,signal);
      if (!payload || serial !== chainSerial || signal.aborted || activeMode() !== "OPTIONS") return null;
      const rows = Array.isArray(payload?.chain) ? payload.chain : [];
      const verified = payload?.success !== false && payload?.stale !== true && payload?.verified !== false && rows.length > 0;
      latestChain = {underlying,status:verified?"VERIFIED":"UNAVAILABLE",provider:String(payload?.provider || payload?.source || "OPTION_PROVIDER"),rows:rows.length,receivedAt:Date.now(),message:payload?.message || (verified?"verified selected option chain":"no verified contracts returned")};
      chainCache.set(key,{at:Date.now(),payload,latestChain:{...latestChain}});
      while(chainCache.size>16)chainCache.delete(chainCache.keys().next().value);
      renderChain(payload);
      applyChainGateMessage(Boolean(latestState));
      return payload;
    } catch (error) {
      if (error?.code === "REQUEST_SUPERSEDED" || signal.aborted || serial !== chainSerial) return null;
      latestChain = {underlying,status:"DEGRADED",provider:"",rows:0,receivedAt:Date.now(),message:error.message};
      renderChain({success:false,message:error.message,chain:[]});
      applyChainGateMessage(Boolean(latestState));
      return null;
    }
  }

  function bindCenterControls() {
    ensureOptionChartActions();
    const underlying = $("v16OptionUnderlying");
    if (underlying && !underlying.dataset.v16RouterBound) { underlying.dataset.v16RouterBound = "1"; underlying.addEventListener("change", () => { underlying.dataset.userChosen = "1"; selectedContract = null; selectedContractPayload = null; setOptionChartFocus(false); latestChain=null; const expiry=$("v16OptionExpiry"); if(expiry)expiry.value=""; renderCapability(); loadChain({force:true}); refreshState(true); }); }
    const expiry = $("v16OptionExpiry"); if (expiry && !expiry.dataset.v16RouterBound) { expiry.dataset.v16RouterBound="1"; expiry.addEventListener("change",()=>{selectedContract=null;selectedContractPayload=null;setOptionChartFocus(false);latestChain=null;loadChain({force:true});}); }
    const reload = $("v16OptionReload"); if (reload && !reload.dataset.v16RouterBound) { reload.dataset.v16RouterBound="1"; reload.addEventListener("click",()=>loadChain({force:true})); }
    const capital = $("v16OptionCapital"); if (capital && !capital.dataset.v16RouterBound) { capital.dataset.v16RouterBound="1"; capital.addEventListener("change",event=>{syncCapital(event.target.value);refreshState(true);}); }
  }

  function route() {
    ensureStyle(); ensureOptionsCenter(); ensureOptionChartActions(); ensureExtraOptionUnderlyings(); ensureOptionsSidebar(); bindCenterControls();
    const mode = activeMode(); const options = mode === "OPTIONS"; const entering = options && lastMode !== "OPTIONS"; lastMode = mode;
    if (entering) { const select=$("v16OptionUnderlying"); if(select)select.dataset.userChosen=""; syncUnderlyingFromMarketContext(); selectedContract=null; selectedContractPayload=null; setOptionChartFocus(false); latestChain=null; }
    setOptionsVisibility(options); setCenterOptionsVisibility(options);
    if (options) {
      syncCapital(optionCapitalWorkspace());
      renderCapability();
      if (entering) {
        // OPTIONS shell is already visible. Hydrate canonical state and chain
        // asynchronously instead of blocking the workspace click.
        queueMicrotask(()=>void refreshState(true));
        setTimeout(()=>void loadChain(),25);
      }
    } else {
      if (chainAbortController) { try { chainAbortController.abort(); } catch {} }
      setOptionChartFocus(false); movePrimaryToTop();
    }
  }

  function boot() {
    route();
    document.querySelector(".workspace-modes")?.addEventListener("click",event=>{if(!event.target.closest("button[data-workspace]"))return;setTimeout(route,0);});
    const intel=document.querySelector(".intel-panel"); if(intel)new MutationObserver(()=>{if(activeMode()==="OPTIONS")setOptionsVisibility(true);else movePrimaryToTop();}).observe(intel,{childList:true});
    pollTimer=setInterval(()=>{ensureOptionsCenter();ensureOptionChartActions();ensureExtraOptionUnderlyings();bindCenterControls();if(activeMode()==="OPTIONS"){setCenterOptionsVisibility(true);renderCapability();void refreshState(false);if($("v16OptionsStateAge")&&latestStateAt)$("v16OptionsStateAge").textContent=`${Math.max(0,Math.round((Date.now()-latestStateAt)/1000))}s`;}else movePrimaryToTop();},10000);
  }

  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",()=>setTimeout(boot,0),{once:true});else setTimeout(boot,0);
  window.addEventListener("beforeunload",()=>{if(pollTimer)clearInterval(pollTimer);},{once:true});
})();
