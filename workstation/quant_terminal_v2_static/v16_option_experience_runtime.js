(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL || window.__JARVIS_V16_OPTION_EXPERIENCE_RUNTIME__) return;
  window.__JARVIS_V16_OPTION_EXPERIENCE_RUNTIME__ = true;

  const $ = id => document.getElementById(id);
  const CAPITAL_WORKSPACES = ["INTRADAY", "SWING", "INVESTMENT"];
  const AUTO_OPTION_UNDERLYINGS = new Set(["NIFTY", "BANKNIFTY", "SENSEX"]);
  let latestState = null;
  let lastAutoFocusKey = "";
  let autoFocusLock = false;
  let pendingFocusTimer = null;
  let manualFocusTimer = null;

  const number = value => {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const money = value => {
    const n = number(value);
    return n === null
      ? "—"
      : n.toLocaleString("en-IN", {style: "currency", currency: "INR", maximumFractionDigits: 0});
  };
  const allocation = value => {
    const n = number(value);
    if (n === null) return "—";
    const pct = Math.abs(n) <= 1 ? n * 100 : n;
    return `${pct.toFixed(Math.abs(pct % 1) > 0.001 ? 1 : 0)}%`;
  };
  const ev = value => {
    const n = number(value);
    return n === null ? "—" : `${n.toFixed(2)}R`;
  };
  const normalizeOptionType = value => {
    const token = String(value || "").trim().toUpperCase();
    if (["CALL", "CE", "C"].includes(token)) return "CALL";
    if (["PUT", "PE", "P"].includes(token)) return "PUT";
    return token;
  };

  function activeMode() {
    return String(document.querySelector(".workspace-modes button.active")?.dataset.workspace || "INTRADAY").toUpperCase();
  }

  function selectedUnderlying() {
    return String($("v16OptionUnderlying")?.value || "NIFTY").toUpperCase();
  }

  function optionMandate() {
    const raw = String($("v16OptionCapital")?.value || $("v16OptionsSideCapital")?.value || "INTRADAY").toUpperCase();
    return CAPITAL_WORKSPACES.includes(raw) ? raw : "INTRADAY";
  }

  function accountsFrom(state) {
    return state?.accounts && typeof state.accounts === "object" ? state.accounts : {};
  }

  function accountFor(state, workspace) {
    const key = String(workspace || state?.workspace || "INTRADAY").toUpperCase();
    if (String(state?.workspace || "").toUpperCase() === key && state?.capital) {
      return {...(state.accounts?.[key] || {}), ...state.capital};
    }
    return state?.accounts?.[key] || {};
  }

  function sumAccounts(accounts, field) {
    return CAPITAL_WORKSPACES.reduce((total, name) => total + (number(accounts?.[name]?.[field]) || 0), 0);
  }

  function ensureStyle() {
    if ($("v16OptionExperienceStyle")) return;
    const style = document.createElement("style");
    style.id = "v16OptionExperienceStyle";
    style.textContent = `
      .v16-capital-strip{display:grid;grid-template-columns:1.05fr repeat(3,1fr) 1.2fr 1.05fr;gap:5px;margin:6px 0;padding:6px;border:1px solid #1d5063;background:linear-gradient(90deg,#071922,#06131b)}
      .v16-capital-strip>div{min-width:0;border-right:1px solid #173b49;padding:2px 7px}.v16-capital-strip>div:last-child{border-right:0}.v16-capital-strip small{display:block;color:#6f98a8;font-size:7px;letter-spacing:.08em;white-space:nowrap}.v16-capital-strip b{display:block;color:#dff7ff;font-size:10px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v16-capital-strip span{display:block;color:#6fa2b4;font-size:7px;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .v16-capital-strip [data-kind="available"] b{color:#79e7a7}.v16-capital-strip [data-kind="open"] b{color:#ffd166}.v16-capital-strip [data-kind="options"]{border:1px solid #285e73;padding:3px 7px;background:#08202a}.v16-capital-strip [data-kind="options"] b{color:#7ed8f2}
      .v16-smart-option-note{display:inline-block;margin-left:7px;padding:2px 6px;border:1px solid #2d7556;border-radius:999px;color:#79e7a7;font-size:7px;letter-spacing:.07em}.v16-smart-option-note[data-kind="manual"]{border-color:#315e74;color:#8ccce1}.v16-smart-option-note[data-kind="wait"]{border-color:#7a6631;color:#d6bc68}
      @media(max-width:1250px){.v16-capital-strip{grid-template-columns:repeat(3,1fr)}.v16-capital-strip>div{border-right:0}}
    `;
    document.head.appendChild(style);
  }

  function ensureCapitalStrip() {
    ensureStyle();
    let strip = $("v16CapitalStrip");
    if (strip) return strip;
    const modes = document.querySelector(".workspace-modes");
    if (!modes?.parentElement) return null;
    strip = document.createElement("section");
    strip.id = "v16CapitalStrip";
    strip.className = "v16-capital-strip";
    strip.setAttribute("aria-label", "Canonical paper capital allocation");
    modes.insertAdjacentElement("afterend", strip);
    return strip;
  }

  function renderCapital(state) {
    if (!state?.success) return;
    latestState = state;
    const accounts = accountsFrom(state);
    const total = sumAccounts(accounts, "starting_capital");
    const committed = sumAccounts(accounts, "committed_capital");
    const openRisk = sumAccounts(accounts, "open_risk");
    const available = sumAccounts(accounts, "available_capital");
    const optionsMandate = optionMandate();
    const optionsAccount = accountFor(state, optionsMandate);
    const strip = ensureCapitalStrip();
    if (strip) {
      strip.innerHTML = `
        <div data-kind="available"><small>TOTAL PAPER CAPITAL</small><b>${money(total)}</b><span>${money(available)} available</span></div>
        ${CAPITAL_WORKSPACES.map(name => {
          const account = accountFor(state, name);
          return `<div><small>${name} · ${allocation(account.allocation)}</small><b>${money(account.starting_capital)}</b><span>${money(account.available_capital)} available</span></div>`;
        }).join("")}
        <div data-kind="options"><small>OPTIONS · SHARED MANDATE</small><b>→ ${optionsMandate} · ${money(optionsAccount.starting_capital)}</b><span>not a fourth capital pool</span></div>
        <div data-kind="open"><small>OPEN / RISK</small><b>${money(committed)} / ${money(openRisk)}</b><span>committed / stop risk</span></div>`;
    }

    // The V16 workspace-state endpoint exposes the active account as
    // state.capital, not state.account.  Override the legacy sidebar reader
    // with the canonical values so zero/blank capital cannot be displayed.
    const activeWorkspace = String(state.workspace || optionsMandate).toUpperCase();
    const capital = accountFor(state, activeWorkspace);
    const setText = (id, value) => { const node = $(id); if (node) node.textContent = value; };
    setText("v16OptionsCapitalMandate", `${activeWorkspace} · ${allocation(capital.allocation)}`);
    setText("v16OptionsCapitalAllocated", money(capital.starting_capital));
    setText("v16OptionsCapitalAvailable", money(capital.available_capital));
    setText("v16OptionsCapitalCommitted", money(capital.committed_capital));
    setText("v16OptionsCapitalRisk", money(capital.open_risk));
    setText("v16OptionsCapitalEquity", money(capital.equity));
  }

  function decisionForSelectedUnderlying(state) {
    return state?.scan_decisions?.autonomous_options?.[selectedUnderlying()] || null;
  }

  function directionMatchesOption(decision) {
    const direction = String(decision?.direction || decision?.bias || "").toUpperCase();
    const optionType = normalizeOptionType(decision?.option_type);
    if (direction === "LONG") return optionType === "CALL";
    if (direction === "SHORT") return optionType === "PUT";
    return false;
  }

  function actionableDecision(state) {
    const decision = decisionForSelectedUnderlying(state);
    if (!decision) return null;
    const status = String(decision.status || "WAIT").toUpperCase();
    if (!["ACTIONABLE", "POSITION_OPEN", "MANAGING"].includes(status)) return null;
    if (!AUTO_OPTION_UNDERLYINGS.has(String(decision.underlying || selectedUnderlying()).toUpperCase())) return null;
    if (!String(decision.candidate_contract || "").trim()) return null;
    if (decision.paper_only === false || decision.live_execution === true || decision.automatic_broker_order === true) return null;
    if (!directionMatchesOption(decision)) return null;
    return decision;
  }

  function rowForDecision(decision) {
    const wantedType = normalizeOptionType(decision?.option_type);
    const wantedStrike = number(decision?.strike);
    if (!wantedType || wantedStrike === null) return null;
    return [...document.querySelectorAll("#v16OptionRows tr[data-v16-contract]")].find(row => {
      const type = normalizeOptionType(row.cells?.[0]?.textContent);
      const strikeText = String(row.cells?.[1]?.textContent || "").replaceAll(",", "");
      const strike = number(strikeText);
      return type === wantedType && strike !== null && Math.abs(strike - wantedStrike) < 0.001;
    }) || null;
  }

  function focusLabel(decision, kind = "auto") {
    const actions = $("v16OptionChartActions");
    const small = actions?.querySelector("span small");
    if (!small) return;
    actions.querySelector(".v16-smart-option-note")?.remove();
    const note = document.createElement("em");
    note.className = "v16-smart-option-note";
    note.dataset.kind = kind;
    if (kind === "auto" && decision) {
      const direction = String(decision.direction || decision.bias || "—").toUpperCase();
      const optionType = normalizeOptionType(decision.option_type) || "OPTION";
      small.textContent = "AUTONOMOUS CANDIDATE · ENGINE SELECTED";
      note.textContent = `${direction} → ${optionType} · EV ${ev(decision.expected_value_r)}`;
      note.title = `${decision.candidate_contract || ""} · confidence ${decision.confidence ?? "—"} · entry ${decision.entry ?? "—"} · stop ${decision.stop ?? "—"} · target ${decision.target ?? "—"}`;
    } else {
      small.textContent = "VIEWING CONTRACT · MANUAL RESEARCH CONTROL";
      note.textContent = "MANUAL VIEW · NO EXECUTION AUTHORITY";
    }
    small.insertAdjacentElement("afterend", note);
  }

  function chooseDecisionExpiry(decision) {
    const expiry = String(decision?.expiry || "").trim();
    const select = $("v16OptionExpiry");
    if (!expiry || !select) return false;
    const option = [...select.options].find(item => String(item.value || "").trim() === expiry);
    if (!option || select.value === expiry) return false;
    select.value = expiry;
    select.dispatchEvent(new Event("change", {bubbles: true}));
    return true;
  }

  function autoFocusDecision(state, attempt = 0) {
    if (activeMode() !== "OPTIONS") return;
    const decision = actionableDecision(state);
    if (!decision) return;
    const key = [decision.status, decision.candidate_contract, decision.updated_at || "", decision.execution_stage || ""].join("|");
    if (key === lastAutoFocusKey && document.documentElement.classList.contains("v16-option-chart-focus")) return;

    if (attempt === 0 && chooseDecisionExpiry(decision)) {
      if (pendingFocusTimer) clearTimeout(pendingFocusTimer);
      pendingFocusTimer = setTimeout(() => autoFocusDecision(state, 1), 500);
      return;
    }

    const row = rowForDecision(decision);
    if (!row) {
      if (attempt < 20) {
        if (pendingFocusTimer) clearTimeout(pendingFocusTimer);
        pendingFocusTimer = setTimeout(() => autoFocusDecision(state, attempt + 1), 250);
      }
      return;
    }

    autoFocusLock = true;
    try {
      row.click();
      setTimeout(() => {
        const open = $("v16OpenOptionChart");
        focusLabel(decision, "auto");
        if (open && !open.disabled && !open.hidden) open.click();
        lastAutoFocusKey = key;
        autoFocusLock = false;
      }, 20);
    } catch {
      autoFocusLock = false;
    }
  }

  function handleWorkspaceState(state) {
    if (!state?.success) return;
    latestState = state;
    // Let the router finish its own render first, then place the canonical
    // capital values over the older state.account compatibility reader.
    setTimeout(() => renderCapital(state), 0);
    setTimeout(() => autoFocusDecision(state), 35);
  }

  function observeCanonicalStateResponses() {
    const upstreamFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const response = await upstreamFetch(...args);
      try {
        const requestUrl = String(typeof args[0] === "string" ? args[0] : args[0]?.url || "");
        if (requestUrl.includes("/api/v16/trading/workspace-state")) {
          response.clone().json().then(handleWorkspaceState).catch(() => {});
        }
      } catch {}
      return response;
    };
  }

  function bindManualChartFirstNavigation() {
    document.addEventListener("click", event => {
      const row = event.target.closest?.("#v16OptionRows tr[data-v16-contract]");
      if (!row || autoFocusLock) return;
      if (manualFocusTimer) clearTimeout(manualFocusTimer);
      manualFocusTimer = setTimeout(() => {
        if (activeMode() !== "OPTIONS") return;
        focusLabel(null, "manual");
        const open = $("v16OpenOptionChart");
        if (open && !open.disabled && !open.hidden) open.click();
      }, 25);
    });

    document.addEventListener("change", event => {
      if (!["v16OptionCapital", "v16OptionsSideCapital"].includes(event.target?.id)) return;
      if (latestState) setTimeout(() => renderCapital(latestState), 0);
    });

    document.addEventListener("click", event => {
      if (!event.target.closest?.("#v16BackToOptionChain")) return;
      focusLabel(null, "manual");
    });
  }

  function boot() {
    ensureCapitalStrip();
    observeCanonicalStateResponses();
    bindManualChartFirstNavigation();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, {once: true});
  else boot();
})();
