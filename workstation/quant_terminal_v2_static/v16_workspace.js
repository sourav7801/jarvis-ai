(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  const SINGLE_OPTION_CONTROLLER = window.JARVIS_V17_SINGLE_OPTION_CONTROLLER === true;
  const CAPITAL_WORKSPACES = ["INTRADAY", "SWING", "INVESTMENT"];
  const OPTION_UNDERLYINGS = ["NIFTY", "BANKNIFTY", "SENSEX"];
  const POLL_MS = 2500;

  let canonicalState = null;
  let capitalWorkspace = "INTRADAY";
  let optionUnderlying = "NIFTY";
  let optionExpiry = "";
  let optionPayload = null;
  let selectedOption = null;
  let refreshTimer = null;
  let optionRequestSerial = 0;

  document.documentElement.classList.add("v16-canonical");

  const el = id => document.getElementById(id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
  const num = value => {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const fmt = (value, digits = 2) => {
    const n = num(value);
    return n === null ? "—" : n.toLocaleString("en-IN", {
      maximumFractionDigits: digits,
      minimumFractionDigits: digits
    });
  };
  const money = value => {
    const n = num(value);
    return n === null ? "—" : `₹${n.toLocaleString("en-IN", {maximumFractionDigits: 0})}`;
  };

  function currentMode() {
    try {
      return String(activeWorkspace || "INTRADAY").toUpperCase();
    } catch {
      return "INTRADAY";
    }
  }

  function stateWorkspace() {
    const mode = currentMode();
    return CAPITAL_WORKSPACES.includes(mode) ? mode : capitalWorkspace;
  }

  async function jsonRequest(url, options = {}, timeoutMs = 12000) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {...options, signal: controller.signal});
      let payload = {};
      try { payload = await response.json(); } catch {}
      if (!response.ok) {
        throw new Error(payload.message || payload.reason || `Request failed (${response.status})`);
      }
      return payload;
    } catch (error) {
      if (error?.name === "AbortError") throw new Error("Request timed out");
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  function mountCanonicalPanel() {
    if (el("v16Canonical")) return;
    const intel = document.querySelector(".intel-panel");
    if (!intel) return;
    const panel = document.createElement("section");
    panel.id = "v16Canonical";
    panel.className = "intel-card";
    panel.innerHTML = `
      <div class="eyebrow">V16 CANONICAL PAPER DESK</div>
      <div class="hero-row"><b id="v16WorkspaceLabel">INTRADAY</b><span id="v16SessionState">CONNECTING</span></div>
      <p id="v16SessionReason">Loading canonical workspace state…</p>
      <div class="v16-controls">
        <button type="button" data-v16-action="start">START SESSION</button>
        <button type="button" data-v16-action="pause_new_entries">PAUSE NEW ENTRIES</button>
        <button type="button" data-v16-action="resume">RESUME</button>
        <button type="button" data-v16-action="stop_scanner">STOP SCANNER</button>
      </div>
      <div id="v16Metrics" class="v16-metrics"></div>
      <details open>
        <summary>AGENT OPERATIONS</summary>
        <div id="v16Agents" class="v16-agents"></div>
      </details>
      <details>
        <summary>OPEN PAPER POSITIONS</summary>
        <div id="v16Positions" class="v16-scroll"></div>
      </details>
      <details>
        <summary>EXECUTION PIPELINE</summary>
        <div id="v16Trace" class="v16-scroll"></div>
      </details>
      <details>
        <summary>CANONICAL JOURNAL</summary>
        <div id="v16Journal" class="v16-scroll"></div>
      </details>`;
    const firstCard = intel.querySelector(".intel-card");
    if (firstCard?.nextSibling) intel.insertBefore(panel, firstCard.nextSibling);
    else intel.prepend(panel);
    panel.querySelectorAll("[data-v16-action]").forEach(button => {
      button.addEventListener("click", () => sessionAction(button.dataset.v16Action));
    });
  }

  function mountOptionsPanel() {
    if (el("v16Options")) return;
    const grid = el("chartGrid");
    if (!grid?.parentElement) return;
    const panel = document.createElement("section");
    panel.id = "v16Options";
    panel.hidden = true;
    panel.innerHTML = `
      <div class="v16-option-head">
        <div>
          <div class="eyebrow">OPTIONS WORKSPACE · VERIFIED PROVIDER DATA</div>
          <strong id="v16OptionTitle">NIFTY OPTION CHAIN</strong>
        </div>
        <div class="v16-option-controls">
          <label>Underlying
            <select id="v16OptionUnderlying">
              ${OPTION_UNDERLYINGS.map(item => `<option value="${item}">${item}</option>`).join("")}
            </select>
          </label>
          <label>Expiry
            <select id="v16OptionExpiry"><option value="">NEAREST</option></select>
          </label>
          <label>Capital
            <select id="v16OptionCapital">
              ${CAPITAL_WORKSPACES.map(item => `<option value="${item}">${item}</option>`).join("")}
            </select>
          </label>
          <button id="v16OptionReload" type="button">RELOAD CHAIN</button>
        </div>
      </div>
      <div id="v16OptionStats" class="v16-option-stats"></div>
      <div id="v16OptionMessage" class="v16-option-message">Select OPTIONS to load the verified chain.</div>
      <div class="v16-option-table-wrap"><table>
        <thead><tr>
          <th>TYPE</th><th>STRIKE</th><th>LTP</th><th>BID</th><th>ASK</th>
          <th>VOL</th><th>OI</th><th>ΔOI</th><th>IV</th><th>DELTA</th>
          <th>GAMMA</th><th>THETA</th><th>VEGA</th>
        </tr></thead>
        <tbody id="v16OptionRows"></tbody>
      </table></div>
      <div id="v16SelectedOption" class="v16-selected-option">No contract selected.</div>
      <small class="v16-option-safety">PAPER / RESEARCH ONLY · LIVE BROKER EXECUTION LOCKED · NAKED OPTION SELLING BLOCKED</small>`;
    grid.parentElement.insertBefore(panel, grid);

    // V17 keeps this canonical DOM surface so the V16 Paper Desk/order gate can
    // mount normally, but the old NIFTY-only chain owner must not bind. The
    // route-aware v16_workspace_router.js is the single option-chain controller.
    if (SINGLE_OPTION_CONTROLLER) return;

    el("v16OptionUnderlying")?.addEventListener("change", event => {
      optionUnderlying = event.target.value;
      optionExpiry = "";
      selectedOption = null;
      loadOptionChain(true);
    });
    el("v16OptionExpiry")?.addEventListener("change", event => {
      optionExpiry = event.target.value;
      selectedOption = null;
      loadOptionChain(false);
    });
    el("v16OptionCapital")?.addEventListener("change", event => {
      capitalWorkspace = CAPITAL_WORKSPACES.includes(event.target.value) ? event.target.value : "INTRADAY";
      refreshCanonicalState(true);
    });
    el("v16OptionReload")?.addEventListener("click", () => loadOptionChain(false));
  }

  function providerState(state) {
    const providers = Object.values(state?.market_data?.providers || {});
    if (!providers.length) return "WAITING";
    if (providers.some(item => item.state === "LOGIN_REQUIRED")) return "BLOCKED";
    if (providers.some(item => item.state === "RATE_LIMITED" || item.state === "DEGRADED")) return "DEGRADED";
    return providers.every(item => item.state === "LIVE") ? "READY" : "WAITING";
  }

  function renderCanonical(state) {
    canonicalState = state;
    const workspace = state?.workspace || stateWorkspace();
    const session = state?.session || {};
    const capital = state?.capital || {};
    const risk = state?.risk || {};
    const positions = Array.isArray(state?.positions) ? state.positions : [];
    const history = Array.isArray(state?.history) ? state.history : [];
    const trace = Array.isArray(state?.execution_trace?.rows) ? state.execution_trace.rows : [];
    const candidates = Array.isArray(state?.scan_decisions?.candidates) ? state.scan_decisions.candidates : [];

    if (el("v16WorkspaceLabel")) el("v16WorkspaceLabel").textContent = workspace;
    if (el("v16SessionState")) el("v16SessionState").textContent = session.state || session.entry_session || "PAUSED";
    if (el("v16SessionReason")) el("v16SessionReason").textContent =
      session.reason || "Entry scanning is paused; existing paper positions remain monitored.";

    if (el("v16Metrics")) {
      el("v16Metrics").innerHTML = `
        <div><span>EQUITY</span><b>${money(capital.equity)}</b></div>
        <div><span>AVAILABLE</span><b>${money(capital.available_capital)}</b></div>
        <div><span>OPEN RISK</span><b>${money(capital.open_risk)}</b></div>
        <div><span>DAILY P&L</span><b>${money(capital.daily_pnl)}</b></div>`;
    }

    const dataState = providerState(state);
    const scannerState = session.scanning ? "SCANNING" :
      session.entry_session === "RUNNING" ? "WAITING" : "IDLE";
    const strategyState = candidates.some(item => item.stage === "ACTIONABLE") ? "READY" :
      candidates.length ? "ANALYZING" : "WAITING";
    const riskState = session.reconciliation_ok === false ? "BLOCKED" :
      num(risk.open_risk) > 0 ? "MANAGING" : "READY";
    const executionState = positions.length ? "MANAGING" :
      (state?.orders?.length ? "READY" : "IDLE");
    const journalState = history.length ? "READY" : "IDLE";
    const optionsState = optionPayload?.success ? "READY" :
      currentMode() === "OPTIONS" ? "WAITING" : "IDLE";

    if (el("v16Agents")) {
      const agents = [
        ["Market Data", dataState], ["Scanner", scannerState],
        ["Strategy", strategyState], ["Risk", riskState],
        ["Execution", executionState], ["Position Manager", positions.length ? "MANAGING" : "IDLE"],
        ["Journal", journalState], ["Options", optionsState]
      ];
      el("v16Agents").innerHTML = agents.map(([name, value]) =>
        `<span><b>${esc(name)}</b><em class="state-${String(value).toLowerCase()}">${esc(value)}</em></span>`
      ).join("");
    }

    if (el("v16Positions")) {
      el("v16Positions").innerHTML = positions.length ? positions.map(position => `
        <article>
          <b>${esc(position.symbol)} · ${esc(position.side)}</b>
          <p>Qty ${fmt(position.quantity, 0)} · Entry ${fmt(position.entry)} · Mark ${fmt(position.mark)}</p>
          <p>SL ${fmt(position.stop)} · T1 ${fmt(position.target)} · ${esc(position.stage || "POSITION_MANAGED")}</p>
        </article>`).join("") : "<p>No open paper positions in this capital workspace.</p>";
    }

    if (el("v16Trace")) {
      el("v16Trace").innerHTML = trace.length ? trace.slice(0, 12).map(row => `
        <article>
          <b>${esc(row.symbol || "—")} · ${esc(row.stage || "WAITING")}</b>
          <p>${esc(row.reason || row.rejection || row.message || "")}</p>
        </article>`).join("") : "<p>No canonical execution-stage rows yet.</p>";
    }

    if (el("v16Journal")) {
      el("v16Journal").innerHTML = history.length ? history.slice(0, 12).map(row => `
        <article>
          <b>${esc(row.symbol)} · ${esc(row.side || "")}</b>
          <p>P&L ${money(row.realized_pnl)} · ${esc(row.closed_at || "")}</p>
        </article>`).join("") : "<p>No closed paper trades in this workspace.</p>";
    }

    renderGeometry(state);
  }

  async function refreshCanonicalState(force = false) {
    const workspace = stateWorkspace();
    try {
      const state = await jsonRequest(`/api/v16/trading/workspace-state?workspace=${encodeURIComponent(workspace)}`, {}, 10000);
      if (!state?.success) throw new Error(state?.message || "Canonical state unavailable");
      renderCanonical(state);
    } catch (error) {
      if (el("v16SessionState")) el("v16SessionState").textContent = "DEGRADED";
      if (el("v16SessionReason")) el("v16SessionReason").textContent = error.message;
    } finally {
      if (force) scheduleRefresh();
    }
  }

  async function sessionAction(action) {
    if (!canonicalState?.csrf_token) return refreshCanonicalState(true);
    const workspace = stateWorkspace();
    const buttons = document.querySelectorAll("[data-v16-action]");
    buttons.forEach(button => button.disabled = true);
    try {
      const payload = await jsonRequest("/api/terminal/session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Jarvis-Token": canonicalState.csrf_token
        },
        body: JSON.stringify({workspace, action})
      }, 12000);
      if (el("v16SessionReason")) {
        el("v16SessionReason").textContent = payload.message ||
          `${payload.state || action}. Existing positions remain monitored by the canonical Paper Desk.`;
      }
      await refreshCanonicalState();
    } catch (error) {
      if (el("v16SessionReason")) el("v16SessionReason").textContent = error.message;
    } finally {
      buttons.forEach(button => button.disabled = false);
    }
  }

  function clearGeometry(slot) {
    for (const line of slot?.v16GeometryLines || []) {
      try { slot.candles?.removePriceLine(line); } catch {}
    }
    for (const node of slot?.v16GeometryNodes || []) {
      try { node.remove(); } catch {}
    }
    if (slot) {
      slot.v16GeometryLines = [];
      slot.v16GeometryNodes = [];
    }
  }

  function setupForSlot(state, slot) {
    if (!slot) return null;
    const symbol = String(slot.optionChart?.instrument_name || slot.symbol || "").toUpperCase();
    const positions = Array.isArray(state?.positions) ? state.positions : [];
    const position = positions.find(item => String(item.symbol || "").toUpperCase() === symbol);
    if (position) return {item: position, executed: true};
    const proposed = state?.proposed_setup;
    if (proposed && String(proposed.symbol || "").toUpperCase() === symbol) {
      return {item: proposed, executed: false};
    }
    return null;
  }

  function addGeometryBand(slot, entry, price, kind, label) {
    const host = slot?.cell || slot?.host?.parentElement;
    if (!host || !slot?.candles?.priceToCoordinate) return;
    const y1 = slot.candles.priceToCoordinate(entry);
    const y2 = slot.candles.priceToCoordinate(price);
    if (!Number.isFinite(y1) || !Number.isFinite(y2)) return;
    const band = document.createElement("div");
    band.className = `v16-risk-band ${kind}`;
    band.style.top = `${Math.min(y1, y2) + 56}px`;
    band.style.height = `${Math.max(2, Math.abs(y2 - y1))}px`;
    band.title = label;
    host.appendChild(band);
    slot.v16GeometryNodes.push(band);
  }

  function renderGeometryForSlot(slot, state) {
    clearGeometry(slot);
    const selected = setupForSlot(state, slot);
    if (!selected || !slot?.candles) return;
    const item = selected.item || {};
    const entry = num(item.entry);
    const stop = num(item.stop);
    const target1 = num(item.target ?? item.target1 ?? item.t1);
    const metadata = item.metadata || {};
    const target2 = num(item.target2 ?? item.t2 ?? metadata.target2 ?? metadata.t2);
    if (entry === null) return;

    const style = selected.executed ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed;
    const levels = [
      [entry, "ENTRY", "#5cdbff"],
      [stop, "SL", "#ff6f83"],
      [target1, "T1", "#78f2aa"],
      [target2, "T2", "#78f2aa"]
    ];
    for (const [price, title, color] of levels) {
      if (price === null) continue;
      try {
        slot.v16GeometryLines.push(slot.candles.createPriceLine({
          price, color, lineWidth: selected.executed ? 2 : 1,
          lineStyle: style, axisLabelVisible: true, title
        }));
      } catch {}
    }
    if (stop !== null) addGeometryBand(slot, entry, stop, "risk", `Risk ${fmt(entry)} → ${fmt(stop)}`);
    if (target1 !== null) addGeometryBand(slot, entry, target1, "reward", `Reward ${fmt(entry)} → ${fmt(target1)}`);

    const host = slot.cell || slot.host?.parentElement;
    if (host) {
      const label = document.createElement("div");
      label.className = "v16-trade-label";
      const rr = num(item.risk_reward ?? metadata.risk_reward);
      const qty = num(item.quantity ?? item.planned_quantity ?? metadata.quantity);
      label.textContent = `${selected.executed ? "PAPER FILLED" : "PROPOSED"} · RR ${rr === null ? "—" : rr.toFixed(2)} · QTY ${qty === null ? "—" : fmt(qty, 0)}`;
      host.appendChild(label);
      slot.v16GeometryNodes.push(label);
    }
  }

  function renderGeometry(state = canonicalState) {
    if (!state) return;
    try {
      chartSlots.forEach(slot => renderGeometryForSlot(slot, state));
    } catch {}
  }

  function optionStats(payload) {
    const analytics = payload?.chain_analytics || {};
    const maxPain = analytics.max_pain?.strike;
    return [
      ["SPOT", fmt(payload?.spot)],
      ["PCR OI", fmt(payload?.pcr_oi ?? analytics.pcr_oi)],
      ["CALL WALL", fmt(analytics.call_oi_wall?.strike)],
      ["PUT WALL", fmt(analytics.put_oi_wall?.strike)],
      ["MAX PAIN", fmt(maxPain)]
    ];
  }

  function updateExpiryChoices(payload) {
    const select = el("v16OptionExpiry");
    if (!select) return;
    const expiries = Array.isArray(payload?.available_expiries) ? payload.available_expiries : [];
    const current = optionExpiry;
    select.innerHTML = `<option value="">NEAREST</option>` + expiries.map(value =>
      `<option value="${esc(value)}">${esc(value)}</option>`
    ).join("");
    if (current && expiries.includes(current)) select.value = current;
  }

  function renderOptionChain(payload) {
    optionPayload = payload;
    const rows = Array.isArray(payload?.chain) ? payload.chain : [];
    if (el("v16OptionTitle")) {
      el("v16OptionTitle").textContent = `${optionUnderlying} OPTION CHAIN`;
    }
    updateExpiryChoices(payload);
    if (el("v16OptionStats")) {
      el("v16OptionStats").innerHTML = optionStats(payload).map(([name, value]) =>
        `<span><small>${esc(name)}</small><b>${esc(value)}</b></span>`
      ).join("");
    }
    if (el("v16OptionMessage")) {
      el("v16OptionMessage").textContent = payload?.message ||
        (rows.length ? `Loaded ${rows.length} listed contracts.` : "No verified contracts returned.");
    }
    if (el("v16OptionRows")) {
      el("v16OptionRows").innerHTML = rows.map((contract, index) => {
        const selected = selectedOption?.symbol && selectedOption.symbol === contract.symbol ? " selected" : "";
        return `<tr data-contract="${index}" class="${selected}">
          <td>${esc(contract.option_type || "—")}</td>
          <td>${fmt(contract.strike, 0)}</td>
          <td>${fmt(contract.ltp)}</td>
          <td>${fmt(contract.bid)}</td>
          <td>${fmt(contract.ask)}</td>
          <td>${fmt(contract.volume, 0)}</td>
          <td>${fmt(contract.open_interest, 0)}</td>
          <td>${fmt(contract.change_in_oi, 0)}</td>
          <td>${fmt(contract.iv)}</td>
          <td>${fmt(contract.delta, 3)}</td>
          <td>${fmt(contract.gamma, 4)}</td>
          <td>${fmt(contract.theta, 3)}</td>
          <td>${fmt(contract.vega, 3)}</td>
        </tr>`;
      }).join("");
      el("v16OptionRows").querySelectorAll("[data-contract]").forEach(row => {
        row.addEventListener("click", () => selectOption(rows[Number(row.dataset.contract)]));
      });
    }
  }

  function selectOption(contract) {
    if (!contract?.symbol) return;
    selectedOption = contract;
    if (el("v16SelectedOption")) {
      el("v16SelectedOption").innerHTML =
        `<b>${esc(contract.symbol)}</b> · ${esc(contract.option_type)} ${fmt(contract.strike, 0)} · LTP ${fmt(contract.ltp)} · ` +
        `IV ${fmt(contract.iv)} · OI ${fmt(contract.open_interest, 0)}<br>` +
        `<span>Contract loaded into the selected chart. Paper execution remains behind the canonical risk gate.</span>`;
    }
    document.querySelectorAll("#v16OptionRows tr").forEach(row => row.classList.remove("selected"));
    const spec = {
      kind: "OPTION",
      provider: String(optionPayload?.provider || "FYERS_READ_ONLY").toUpperCase().includes("FYERS") ? "FYERS_READ_ONLY" : optionPayload?.provider,
      instrument_name: contract.symbol,
      label: contract.symbol,
      underlying: optionUnderlying,
      strike: contract.strike,
      option_type: contract.option_type,
      expiry: contract.expiry || optionPayload?.expiry?.date || optionExpiry || null
    };
    try { window.JARVIS_OPTION_CHART?.open(spec); } catch {}
    try { persistCharts(); } catch {}
    renderOptionChain(optionPayload);
  }

  async function resolveModuleResult(url, serial) {
    for (let attempt = 0; attempt < 12; attempt++) {
      if (serial !== optionRequestSerial) return null;
      const payload = await jsonRequest(url, {}, 12000);
      if (!payload?.pending) return payload?.result ?? payload;
      await new Promise(resolve => setTimeout(resolve, 350));
    }
    throw new Error("Option-chain analysis is still busy; retry shortly.");
  }

  async function loadOptionChain(resetExpiry = false) {
    if (SINGLE_OPTION_CONTROLLER || currentMode() !== "OPTIONS") return;
    if (resetExpiry) optionExpiry = "";
    const serial = ++optionRequestSerial;
    if (el("v16OptionMessage")) el("v16OptionMessage").textContent = "Loading verified listed contracts…";
    if (el("v16OptionRows")) el("v16OptionRows").innerHTML = "";
    const query = new URLSearchParams({
      workspace: capitalWorkspace,
      symbol: optionUnderlying,
      module: "option-chain"
    });
    if (optionExpiry) query.set("expiry", optionExpiry);
    try {
      const payload = await resolveModuleResult(`/api/terminal/module?${query}`, serial);
      if (!payload || serial !== optionRequestSerial) return;
      renderOptionChain(payload);
    } catch (error) {
      optionPayload = {success: false, message: error.message, chain: []};
      renderOptionChain(optionPayload);
    }
  }

  function workspaceChanged() {
    const mode = currentMode();
    document.querySelectorAll("[data-workspace]").forEach(button => {
      button.classList.toggle("active", button.dataset.workspace === mode);
    });
    const options = el("v16Options");
    if (options) options.hidden = mode !== "OPTIONS";
    if (mode === "OPTIONS" && !SINGLE_OPTION_CONTROLLER) {
      el("v16OptionCapital").value = capitalWorkspace;
      loadOptionChain(false);
    }
    refreshCanonicalState(true);
  }

  function scheduleRefresh() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(async () => {
      await refreshCanonicalState();
      scheduleRefresh();
    }, POLL_MS);
  }

  function installChartHook() {
    try {
      const original = loadSlot;
      loadSlot = async function v16CanonicalLoadSlot(index) {
        const result = await original(index);
        setTimeout(() => {
          try { renderGeometryForSlot(chartSlots[index], canonicalState); } catch {}
        }, 40);
        return result;
      };
    } catch {}
  }

  function boot() {
    mountCanonicalPanel();
    mountOptionsPanel();
    installChartHook();
    window.addEventListener("jarvis:workspace", workspaceChanged);
    document.querySelectorAll("[data-workspace]").forEach(button => {
      button.addEventListener("click", () => setTimeout(workspaceChanged, 0));
    });
    refreshCanonicalState(true);
    workspaceChanged();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, {once: true});
  } else {
    boot();
  }
})();