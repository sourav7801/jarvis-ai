(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL || window.__JARVIS_V16_OPTION_DECISION_RUNTIME__) return;
  window.__JARVIS_V16_OPTION_DECISION_RUNTIME__ = true;

  const $ = id => document.getElementById(id);
  let latestState = null;
  let latestAt = 0;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
  const number = value => {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const fmt = (value, digits = 2) => {
    const n = number(value);
    return n === null || n <= 0 ? "—" : n.toLocaleString("en-IN", {maximumFractionDigits: digits});
  };
  const fmtSigned = (value, digits = 3) => {
    const n = number(value);
    return n === null ? "—" : n.toLocaleString("en-IN", {maximumFractionDigits: digits});
  };
  const percent = value => {
    const n = number(value);
    if (n === null) return "—";
    return `${(Math.abs(n) <= 1 ? n * 100 : n).toFixed(1)}%`;
  };
  const formatTime = value => {
    if (value == null || value === "") return "—";
    let date = null;
    const n = Number(value);
    if (Number.isFinite(n)) date = new Date(n > 1e12 ? n : n * 1000);
    else {
      const parsed = Date.parse(String(value));
      if (Number.isFinite(parsed)) date = new Date(parsed);
    }
    if (!date || Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("en-IN", {hour12: false, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit"});
  };

  function activeOptions() {
    return String(document.querySelector(".workspace-modes button.active")?.dataset.workspace || "").toUpperCase() === "OPTIONS";
  }

  function selectedUnderlying() {
    return String($("v16OptionUnderlying")?.value || "NIFTY").toUpperCase();
  }

  function viewingChainState() {
    const raw = String($("v16OptionsPipeChain")?.textContent || "WAITING").trim().toUpperCase();
    if (raw === "VERIFIED") return {state: "VERIFIED", kind: "ok"};
    if (["DEGRADED", "UNAVAILABLE"].includes(raw)) return {state: raw, kind: "blocked"};
    return {state: raw || "WAITING", kind: "wait"};
  }

  function ensureStyle() {
    if ($("v16OptionDecisionStyle")) return;
    const style = document.createElement("style");
    style.id = "v16OptionDecisionStyle";
    style.textContent = `
      .v16-auto-decision{border-top:1px solid #1d4252;border-bottom:1px solid #1d4252;margin:7px 0;padding:7px 0}
      .v16-auto-decision-head{display:flex;justify-content:space-between;align-items:center;gap:6px}.v16-auto-decision-head strong{font-size:10px;color:#dcf6ff;letter-spacing:.06em}.v16-auto-decision-head span{font-size:8px;border:1px solid #355b6b;border-radius:999px;padding:3px 6px;color:#cfefff}
      .v16-auto-decision-head span[data-state="ACTIONABLE"],.v16-auto-decision-head span[data-state="POSITION_OPEN"],.v16-auto-decision-head span[data-state="MANAGING"]{color:#7ef0ac;border-color:#2f7f59}.v16-auto-decision-head span[data-state="BLOCKED"]{color:#ff8196;border-color:#8a4051}.v16-auto-decision-head span[data-state="WAIT"]{color:#ffd166;border-color:#7b652f}
      .v16-auto-grid{display:grid;grid-template-columns:1fr 1fr;gap:3px;margin-top:5px}.v16-auto-grid div{background:#06151d;border:1px solid #173b4b;padding:4px;min-width:0}.v16-auto-grid small{display:block;font-size:6px;color:#6d94a4;letter-spacing:.07em}.v16-auto-grid b{display:block;font-size:8px;color:#d8f5ff;line-height:1.2;overflow-wrap:anywhere;max-height:2.4em;overflow:hidden}
      .v16-auto-contract{margin-top:5px;border-left:2px solid #2f7591;background:#06151d;padding:5px}.v16-auto-contract small{display:block;color:#6d94a4;font-size:7px;letter-spacing:.08em}.v16-auto-contract b{display:block;color:#dff7ff;font-size:9px;margin-top:2px;overflow-wrap:anywhere}.v16-auto-contract[data-active="1"]{border-color:#38d486}.v16-auto-contract[data-active="1"] small{color:#79e7a7}
      .v16-view-context{display:grid;grid-template-columns:1fr auto;gap:5px;align-items:center;margin-top:5px;padding:5px;background:#061219;border:1px solid #173847}.v16-view-context small{display:block;color:#6d94a4;font-size:6px;letter-spacing:.08em}.v16-view-context b{font-size:8px;color:#9fd9ec}.v16-view-context b[data-kind="ok"]{color:#69dda1}.v16-view-context b[data-kind="blocked"]{color:#ff7a91}.v16-view-context span{grid-column:1/-1;color:#759ba9;font-size:7px;line-height:1.3}
      .v16-auto-gates{display:grid;grid-template-columns:1fr 1fr;gap:2px 6px;margin-top:5px}.v16-auto-gate{display:flex;justify-content:space-between;gap:4px;border-bottom:1px solid #102f3b;padding:2px 1px;font-size:7px}.v16-auto-gate span:first-child{color:#8baebb}.v16-auto-gate b{font-size:7px}.v16-auto-gate[data-state="PASS"] b{color:#61dda0}.v16-auto-gate[data-state="BLOCKED"] b{color:#ff7189}.v16-auto-gate[data-state="WAIT"] b{color:#d5b85d}
      .v16-auto-reasons{margin-top:5px;padding:5px;background:#07141b;border-left:2px solid #c59a37;color:#d8c37f;font-size:7px;line-height:1.35}.v16-auto-reasons strong{color:#f0d67f}
      .v16-viewing-contract-label{display:inline-block;margin-right:6px;padding:2px 5px;border:1px solid #2c6075;border-radius:999px;color:#81cde8;font-size:7px;letter-spacing:.08em}.v16-auto-stale{opacity:.62}
    `;
    document.head.appendChild(style);
  }

  function ensureCard() {
    ensureStyle();
    const sidebar = $("v16OptionsSidebar");
    if (!sidebar) return null;
    let card = $("v16AutonomousDecision");
    if (card) return card;
    card = document.createElement("section");
    card.id = "v16AutonomousDecision";
    card.className = "v16-auto-decision";
    card.innerHTML = `
      <div class="v16-auto-decision-head"><strong>AUTONOMOUS DECISION</strong><span id="v16AutoDecisionStatus" data-state="WAIT">WAIT</span></div>
      <div id="v16AutoDecisionGrid" class="v16-auto-grid"></div>
      <div id="v16AutoCandidate" class="v16-auto-contract"><small>AUTONOMOUS CANDIDATE</small><b>—</b></div>
      <div id="v16ViewingContext" class="v16-view-context"><div><small>VIEWING CONTEXT · NOT EXECUTION AUTHORITY</small><b id="v16ViewingUnderlying">NIFTY</b></div><b id="v16ViewingChainState" data-kind="wait">WAITING</b><span>A manually viewed chain or row does not mean JARVIS selected that contract.</span></div>
      <div id="v16AutoGates" class="v16-auto-gates"></div>
      <div id="v16AutoReasons" class="v16-auto-reasons"><strong>WAIT</strong><br>JARVIS has not produced a qualified autonomous option decision yet.</div>`;
    const pipeline = sidebar.querySelector(".v16-options-pipeline");
    if (pipeline?.nextSibling) sidebar.insertBefore(card, pipeline.nextSibling); else sidebar.appendChild(card);
    return card;
  }

  function systemGate(state, reason = null) {
    return {state, reason};
  }

  function mergedGates(decision, state) {
    const gates = {...(decision?.gates || {})};
    const session = state?.session || {};
    const running = String(session.entry_session || "PAUSED").toUpperCase() === "RUNNING";
    gates.PAPER_SESSION = systemGate(running ? "PASS" : "BLOCKED", running ? null : "ENTRY_SESSION_PAUSED");
    gates.RECONCILIATION = systemGate(session.reconciliation_ok === false ? "BLOCKED" : "PASS", session.reconciliation_ok === false ? "LEDGER_RECONCILIATION_REQUIRED" : null);
    return gates;
  }

  function decisionForState(state) {
    return state?.scan_decisions?.autonomous_options?.[selectedUnderlying()] || null;
  }

  function renderViewingContext() {
    const chain = viewingChainState();
    if ($("v16ViewingUnderlying")) $("v16ViewingUnderlying").textContent = selectedUnderlying();
    if ($("v16ViewingChainState")) {
      $("v16ViewingChainState").textContent = chain.state;
      $("v16ViewingChainState").dataset.kind = chain.kind;
    }
    const pipe = $("v16OptionsPipeChain");
    const label = pipe?.closest("span")?.querySelector("small");
    if (label) label.textContent = "VIEW CHAIN";

    // The router historically described a stale browser-viewed chain as a
    // blocker for new autonomous entries.  That is misleading: autonomous
    // admission is based on the engine proposal/server gates, not this table.
    const msg = $("v16OptionsSideMessage");
    if (msg && !String(msg.textContent || "").includes("canonical state unavailable")) {
      const text = String(msg.textContent || "");
      if (text.startsWith("NEW OPTION ENTRIES BLOCKED") && /option chain|selected option chain|chain/i.test(text)) {
        msg.textContent = `VIEWING CHAIN ${chain.state} · browser chain is research/context only. Autonomous entry authority remains the scanner proposal + exact fresh quote + canonical Paper Desk gates.`;
        msg.dataset.kind = chain.kind === "ok" ? "ok" : "warn";
      }
    }
  }

  function render(state) {
    if (!activeOptions()) return;
    const card = ensureCard();
    if (!card) return;
    const decision = decisionForState(state);
    const status = String(decision?.status || "WAIT").toUpperCase();
    const statusNode = $("v16AutoDecisionStatus");
    if (statusNode) { statusNode.textContent = status; statusNode.dataset.state = status; }

    const fields = [
      ["UNDERLYING", decision?.underlying || selectedUnderlying()],
      ["BIAS", decision?.bias || decision?.direction],
      ["CONFIDENCE", percent(decision?.confidence)],
      ["STRATEGY", decision?.strategy],
      ["EXPECTED VALUE", decision?.expected_value_r == null ? null : `${fmtSigned(decision.expected_value_r, 3)}R`],
      ["EXPRESSION", decision?.expression],
      ["ENTRY", fmt(decision?.entry)],
      ["STOP", fmt(decision?.stop)],
      ["TARGET", fmt(decision?.target)],
      ["R:R", decision?.rr == null ? null : `${fmt(decision.rr, 2)} : 1`],
      ["SIZE", decision?.quantity],
      ["RISK", decision?.risk],
      ["STAGE", decision?.execution_stage],
      ["DECISION TIME", formatTime(decision?.updated_at)],
    ];
    const grid = $("v16AutoDecisionGrid");
    if (grid) grid.innerHTML = fields.map(([label,value]) => `<div title="${esc(value == null || value === "" ? "" : value)}"><small>${esc(label)}</small><b>${esc(value == null || value === "" ? "—" : value)}</b></div>`).join("");

    const candidate = $("v16AutoCandidate");
    if (candidate) {
      const active = status === "POSITION_OPEN" || status === "MANAGING";
      candidate.dataset.active = active ? "1" : "0";
      candidate.querySelector("small").textContent = active ? "ACTIVE PAPER POSITION" : "AUTONOMOUS CANDIDATE · SELECTED BY JARVIS";
      const detail = decision?.candidate_contract ? `${decision.candidate_contract}${decision.expression ? ` · ${decision.expression}` : ""}${decision.strike != null ? ` · ${fmt(decision.strike,0)}` : ""}` : "—";
      candidate.querySelector("b").textContent = detail;
    }

    renderViewingContext();
    const gates = mergedGates(decision, state);
    const gateNode = $("v16AutoGates");
    if (gateNode) gateNode.innerHTML = Object.entries(gates).map(([name,value]) => {
      const gateState = String(value?.state || "WAIT").toUpperCase();
      return `<div class="v16-auto-gate" data-state="${esc(gateState)}"><span>${esc(name.replaceAll("_"," "))}</span><b title="${esc(value?.reason || "")}">${esc(gateState)}</b></div>`;
    }).join("");

    const reasons = Array.isArray(decision?.rejection_reasons) ? decision.rejection_reasons.filter(Boolean) : [];
    const primary = decision?.primary_reason || reasons[0] || null;
    const extras = reasons.filter(reason => reason !== primary);
    const reasonsNode = $("v16AutoReasons");
    if (reasonsNode) {
      if (["ACTIONABLE", "POSITION_OPEN", "MANAGING"].includes(status)) {
        reasonsNode.innerHTML = `<strong>${esc(status)}</strong><br>${status === "ACTIONABLE" ? "JARVIS has a qualified engine-selected contract. Final fresh-quote and Paper Desk gates remain authoritative." : "Canonical Paper Desk owns execution and position management."}`;
      } else {
        const detail = primary ? `${esc(primary)}${extras.length ? ` · also: ${extras.map(esc).join(" · ")}` : ""}` : "no qualified engine decision yet";
        reasonsNode.innerHTML = `<strong>${esc(status)}${primary ? ` · ${esc(primary)}` : ""}</strong><br>JARVIS chose not to trade · ${detail}.`;
      }
    }
    card.classList.remove("v16-auto-stale");
  }

  function labelViewingContract() {
    const host = $("v16SelectedOption");
    if (!host || host.querySelector(".v16-viewing-contract-label")) return;
    const label = document.createElement("span");
    label.className = "v16-viewing-contract-label";
    label.textContent = "VIEWING CONTRACT";
    host.prepend(label);
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    try {
      const requestUrl = String(typeof args[0] === "string" ? args[0] : args[0]?.url || "");
      if (requestUrl.includes("/api/v16/trading/workspace-state")) {
        response.clone().json().then(payload => {
          if (!payload?.success) return;
          latestState = payload;
          latestAt = Date.now();
          render(payload);
        }).catch(() => {});
      }
    } catch {}
    return response;
  };

  document.addEventListener("click", event => {
    if (event.target.closest("#v16OptionRows tr[data-v16-contract]")) setTimeout(() => { labelViewingContract(); renderViewingContext(); }, 0);
    if (event.target.closest("button[data-workspace]") || event.target.closest("#v16OptionUnderlying")) setTimeout(() => latestState && render(latestState), 20);
  });
  document.addEventListener("change", event => {
    if (event.target?.id === "v16OptionUnderlying") setTimeout(() => latestState && render(latestState), 0);
  });

  setInterval(() => {
    if (!activeOptions()) return;
    if (latestState) render(latestState);
    const card = $("v16AutonomousDecision");
    if (card && latestAt && Date.now() - latestAt > 12000) card.classList.add("v16-auto-stale");
  }, 2500);
})();