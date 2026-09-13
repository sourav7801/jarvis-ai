(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  const $ = id => document.getElementById(id);
  const parseNumber = value => {
    const n = Number(String(value ?? "").replaceAll(",", "").replace("₹", "").trim());
    return Number.isFinite(n) ? n : null;
  };
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));

  let selected = null;
  let pending = false;
  let latestState = null;
  let latestReconciliation = null;
  let diagnosticsTimer = null;
  let stateTimer = null;

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    let payload = {};
    try { payload = await response.json(); } catch {}
    if (!response.ok) throw new Error(payload.message || `HTTP ${response.status}`);
    return payload;
  }

  function selectedRow() {
    return document.querySelector("#v16OptionRows tr.selected");
  }

  function contractFromRow(row, symbol = "", spec = {}) {
    if (!row) return null;
    const cells = [...row.querySelectorAll("td")].map(cell => cell.textContent.trim());
    if (cells.length < 5) return null;
    return {
      symbol: String(symbol || spec.instrument_name || "").trim().toUpperCase(),
      option_type: String(cells[0] || spec.option_type || "").toUpperCase(),
      strike: parseNumber(cells[1]) ?? parseNumber(spec.strike),
      ltp: parseNumber(cells[2]),
      bid: parseNumber(cells[3]),
      ask: parseNumber(cells[4]),
      underlying: String(spec.underlying || $("v16OptionUnderlying")?.value || "NIFTY").toUpperCase(),
      expiry: spec.expiry || $("v16OptionExpiry")?.value || "",
      workspace: $("v16OptionCapital")?.value || "INTRADAY",
    };
  }

  function readDomSelection() {
    const row = selectedRow();
    const summary = $("v16SelectedOption");
    const symbol = summary?.querySelector("b")?.textContent?.trim() || "";
    if (!row || !symbol) return null;
    return contractFromRow(row, symbol);
  }

  function optionChartSpec() {
    try {
      if (typeof chartSlots === "undefined" || !Array.isArray(chartSlots)) return null;
      const preferred = typeof selectedSlot === "number" ? chartSlots[selectedSlot] : null;
      const slot = preferred?.kind === "OPTION" && preferred?.optionChart
        ? preferred
        : chartSlots.find(item => item?.kind === "OPTION" && item?.optionChart);
      return slot?.optionChart || null;
    } catch {
      return null;
    }
  }

  function readChartSelection() {
    const spec = optionChartSpec();
    if (!spec?.instrument_name) return null;
    const currentUnderlying = String($("v16OptionUnderlying")?.value || "NIFTY").toUpperCase();
    const specUnderlying = String(spec.underlying || currentUnderlying).toUpperCase();
    if (specUnderlying !== currentUnderlying) return null;
    const exactExpiry = String($("v16OptionExpiry")?.value || "").trim();
    if (exactExpiry && spec.expiry && String(spec.expiry) !== exactExpiry) return null;

    const wantedType = String(spec.option_type || "").toUpperCase();
    const wantedStrike = parseNumber(spec.strike);
    let match = null;
    document.querySelectorAll("#v16OptionRows tr[data-contract]").forEach(row => {
      if (match) return;
      const cells = [...row.querySelectorAll("td")].map(cell => cell.textContent.trim());
      const rowType = String(cells[0] || "").toUpperCase();
      const rowStrike = parseNumber(cells[1]);
      if (rowType === wantedType && wantedStrike !== null && rowStrike === wantedStrike) match = row;
    });
    if (match) {
      document.querySelectorAll("#v16OptionRows tr").forEach(row => row.classList.toggle("selected", row === match));
      return contractFromRow(match, spec.instrument_name, spec);
    }
    return {
      symbol: String(spec.instrument_name).trim().toUpperCase(),
      option_type: wantedType,
      strike: wantedStrike,
      ltp: null,
      bid: null,
      ask: null,
      underlying: specUnderlying,
      expiry: spec.expiry || exactExpiry,
      workspace: $("v16OptionCapital")?.value || "INTRADAY",
    };
  }

  function readSelection() {
    return readDomSelection() || readChartSelection();
  }

  function currentTimeframe() {
    try {
      if (typeof chartSlots !== "undefined" && typeof selectedSlot !== "undefined") {
        return chartSlots[selectedSlot]?.timeframe || "5m";
      }
    } catch {}
    return "5m";
  }

  function setStatus(message, kind = "") {
    const node = $("v16OptionOrderStatus");
    if (!node) return;
    node.textContent = message;
    node.dataset.kind = kind;
  }

  function riskInputs() {
    return {
      lots: parseNumber($("v16OptionLots")?.value),
      stop: parseNumber($("v16OptionStop")?.value),
      target: parseNumber($("v16OptionTarget")?.value),
    };
  }

  function reconciliationClean() {
    if (!latestReconciliation) return null;
    const issues = Array.isArray(latestReconciliation.issues) ? latestReconciliation.issues : [];
    const legacy = Array.isArray(latestReconciliation.legacy_exposure) ? latestReconciliation.legacy_exposure : [];
    return latestReconciliation.success === true && !issues.length && !legacy.length;
  }

  function sessionState() {
    return String(latestState?.session?.state || latestState?.session?.entry_session || "").toUpperCase();
  }

  function riskGate() {
    if (!selected) return {ready: false, state: "WAITING", detail: "SELECT CONTRACT"};
    const risk = riskInputs();
    if (!Number.isInteger(risk.lots) || risk.lots < 1) return {ready: false, state: "BLOCKED", detail: "VALID LOTS REQUIRED"};
    if (risk.stop === null || risk.target === null) return {ready: false, state: "WAITING", detail: "STOP + TARGET REQUIRED"};
    const reference = selected.ask ?? selected.ltp;
    if (!(risk.stop > 0 && risk.target > risk.stop)) return {ready: false, state: "BLOCKED", detail: "INVALID RISK LEVELS"};
    if (reference !== null && !(risk.stop < reference && risk.target > reference)) {
      return {ready: false, state: "BLOCKED", detail: `STOP < ${reference} < TARGET`};
    }
    return {ready: true, state: "READY", detail: reference === null ? "SERVER WILL VERIFY LIVE ENTRY" : "LOCAL GEOMETRY VALID"};
  }

  function gateMarkup(name, state, detail) {
    const cls = String(state || "WAITING").toLowerCase();
    return `<span class="v16-option-gate gate-${cls}"><small>${escapeHtml(name)}</small><b>${escapeHtml(state)}</b><em>${escapeHtml(detail || "")}</em></span>`;
  }

  function refreshGatePresentation({preserveStatus = false} = {}) {
    const contractReady = Boolean(selected?.symbol && ["CE", "PE"].includes(selected.option_type));
    const ledger = reconciliationClean();
    const session = sessionState();
    const risk = riskGate();
    const gates = [
      ["CONTRACT", contractReady ? "READY" : "BLOCKED", contractReady ? selected.symbol : "SELECT CE / PE"],
      ["LEDGER", ledger === null ? "CHECKING" : ledger ? "READY" : "BLOCKED", ledger === false ? "RECONCILIATION REQUIRED" : ledger === true ? "CANONICAL" : "LOADING"],
      ["SESSION", !latestState ? "CHECKING" : session === "RUNNING" ? "READY" : "BLOCKED", latestState ? (session || "PAUSED") : "LOADING"],
      ["RISK", risk.state, risk.detail],
      ["MARKET", contractReady ? "SERVER CHECK" : "WAITING", contractReady ? "FRESH QUOTE + SESSION AT SUBMIT" : "SELECT CONTRACT"],
    ];
    const host = $("v16OptionGates");
    if (host) host.innerHTML = gates.map(item => gateMarkup(...item)).join("");

    const canBuy = Boolean(contractReady && ledger === true && session === "RUNNING" && risk.ready && !pending);
    const buy = $("v16OptionBuy");
    if (buy) {
      buy.disabled = !canBuy;
      buy.title = canBuy ? "Final fresh-quote/session validation runs on submit." : "Resolve the highlighted execution gates first.";
    }

    if (preserveStatus || pending) return;
    if (!contractReady) setStatus("BUY disabled · select a listed CE/PE contract. A contract already loaded in a chart is now detected automatically.");
    else if (ledger === null) setStatus("BUY disabled · checking canonical ledger reconciliation…", "working");
    else if (!ledger) setStatus("BUY disabled · canonical ledger reconciliation is not clean. Existing/legacy exposure must be resolved first.", "error");
    else if (!latestState) setStatus("BUY disabled · checking paper workspace session…", "working");
    else if (session !== "RUNNING") setStatus(`BUY disabled · ${selected.workspace} paper session is ${session || "PAUSED"}. Start the session first.`, "error");
    else if (!risk.ready) setStatus(`BUY disabled · ${risk.detail}.`, risk.state === "BLOCKED" ? "error" : "");
    else setStatus("READY FOR PAPER SUBMIT · final fresh option quote and exchange-session validation will run on the server before any paper fill.", "ok");
  }

  function mount() {
    const options = $("v16Options");
    if (!options || $("v16OptionOrder")) return;
    const panel = document.createElement("div");
    panel.id = "v16OptionOrder";
    panel.className = "v16-option-order";
    panel.innerHTML = `
      <div class="v16-option-order-head">
        <div><span class="eyebrow">CANONICAL PAPER OPTION ORDER</span><b id="v16OptionOrderContract">SELECT A CONTRACT</b></div>
        <span id="v16OptionOrderState">PAPER ONLY</span>
      </div>
      <div id="v16OptionGates" class="v16-option-gates"></div>
      <div class="v16-option-order-grid">
        <label>Lots<input id="v16OptionLots" type="number" min="1" max="100" step="1" value="1"></label>
        <label>Stop<input id="v16OptionStop" inputmode="decimal" placeholder="required"></label>
        <label>Target<input id="v16OptionTarget" inputmode="decimal" placeholder="required"></label>
        <button id="v16OptionBuy" type="button" disabled>BUY SELECTED OPTION</button>
        <button id="v16OptionClose" type="button" disabled>CLOSE LONG POSITION</button>
      </div>
      <div id="v16OptionOrderStatus" class="v16-option-order-status">Checking execution gates…</div>
      <details id="v16LedgerDiagnostics">
        <summary>LEDGER / EXECUTION DIAGNOSTICS</summary>
        <div id="v16LedgerIssues">Checking canonical ledger…</div>
        <button id="v16RepairLedger" type="button" hidden>REPAIR UNAMBIGUOUS CANONICAL LINKS</button>
      </details>
      <small>Long CALL/PUT paper positions only. No naked shorts. No broker-order API. Live execution remains locked.</small>`;
    const selectedSummary = $("v16SelectedOption");
    if (selectedSummary?.parentElement) selectedSummary.insertAdjacentElement("afterend", panel);
    else options.appendChild(panel);

    $("v16OptionBuy")?.addEventListener("click", buySelected);
    $("v16OptionClose")?.addEventListener("click", closeSelected);
    $("v16RepairLedger")?.addEventListener("click", repairLedger);
    ["v16OptionLots", "v16OptionStop", "v16OptionTarget"].forEach(id => {
      $(id)?.addEventListener("input", () => refreshGatePresentation());
    });

    const rows = $("v16OptionRows");
    rows?.addEventListener("click", () => setTimeout(() => syncSelection(), 0));
    $("v16OptionUnderlying")?.addEventListener("change", clearSelection);
    $("v16OptionExpiry")?.addEventListener("change", clearSelection);
    $("v16OptionCapital")?.addEventListener("change", () => {
      if (selected) selected.workspace = $("v16OptionCapital")?.value || "INTRADAY";
      latestState = null;
      refreshWorkspaceState();
      syncOpenPosition();
    });

    const observer = new MutationObserver(() => setTimeout(() => syncSelection(), 0));
    if (selectedSummary) observer.observe(selectedSummary, {childList: true, subtree: true, characterData: true});
    if (rows) observer.observe(rows, {childList: true, subtree: true});
    window.addEventListener("jarvis:workspace", () => setTimeout(() => syncSelection(), 80));

    syncSelection();
    refreshDiagnostics();
    refreshWorkspaceState();
    diagnosticsTimer = setInterval(refreshDiagnostics, 5000);
    stateTimer = setInterval(refreshWorkspaceState, 3000);
    window.addEventListener("beforeunload", () => {
      observer.disconnect();
      if (diagnosticsTimer) clearInterval(diagnosticsTimer);
      if (stateTimer) clearInterval(stateTimer);
    }, {once: true});
  }

  function clearSelection() {
    selected = null;
    const label = $("v16OptionOrderContract");
    if (label) label.textContent = "SELECT A CONTRACT";
    const buy = $("v16OptionBuy");
    const close = $("v16OptionClose");
    if (buy) {
      buy.disabled = true;
      buy.textContent = "BUY SELECTED OPTION";
    }
    if (close) {
      close.disabled = true;
      close.textContent = "CLOSE LONG POSITION";
      close.dataset.positionId = "";
    }
    refreshGatePresentation();
  }

  function syncSelection() {
    const contract = readSelection();
    if (!contract?.symbol) return clearSelection();
    const changed = !selected || selected.symbol !== contract.symbol || selected.workspace !== contract.workspace;
    selected = contract;
    const label = $("v16OptionOrderContract");
    if (label) label.textContent = `${contract.symbol} · ${contract.option_type} ${contract.strike ?? "—"}`;
    const buy = $("v16OptionBuy");
    if (buy) buy.textContent = contract.option_type === "CE" ? "BUY CALL · PAPER" : "BUY PUT · PAPER";
    if (changed) {
      latestState = null;
      refreshWorkspaceState();
    }
    syncOpenPosition();
    refreshGatePresentation();
  }

  async function stateFor(workspace) {
    return requestJson(`/api/v16/trading/workspace-state?workspace=${encodeURIComponent(workspace)}`);
  }

  async function refreshWorkspaceState() {
    const workspace = selected?.workspace || $("v16OptionCapital")?.value || "INTRADAY";
    try {
      latestState = await stateFor(workspace);
    } catch {
      latestState = null;
    }
    refreshGatePresentation();
  }

  async function syncOpenPosition() {
    const close = $("v16OptionClose");
    if (!close) return;
    close.disabled = true;
    close.dataset.positionId = "";
    if (!selected?.symbol) return;
    try {
      const state = latestState?.workspace === selected.workspace ? latestState : await stateFor(selected.workspace || "INTRADAY");
      latestState = state;
      const position = (state.positions || []).find(item => String(item.symbol || "").toUpperCase() === selected.symbol.toUpperCase());
      if (position) {
        close.dataset.positionId = String(position.id);
        close.disabled = pending;
        close.textContent = `CLOSE LONG · ${position.quantity ?? "—"} LOT${Number(position.quantity) === 1 ? "" : "S"}`;
      } else {
        close.textContent = "CLOSE LONG POSITION";
      }
    } catch {}
  }

  async function csrfState(workspace) {
    const state = latestState?.workspace === workspace ? latestState : await stateFor(workspace);
    latestState = state;
    if (!state?.csrf_token) throw new Error("Local V16 session token unavailable; refresh the terminal.");
    return state;
  }

  async function buySelected() {
    syncSelection();
    if (!selected || pending) return;
    const risk = riskInputs();
    refreshGatePresentation();
    if (!Number.isInteger(risk.lots) || risk.lots < 1) return setStatus("Enter a positive whole number of lots.", "error");
    const reference = selected.ask ?? selected.ltp;
    if (risk.stop === null || risk.target === null) return setStatus("STOP and TARGET are required. JARVIS will not fabricate option risk geometry.", "error");
    if (reference !== null && !(risk.stop > 0 && risk.stop < reference && risk.target > reference)) {
      return setStatus(`For a long option require STOP < current ask/LTP (${reference}) < TARGET.`, "error");
    }

    pending = true;
    refreshGatePresentation({preserveStatus: true});
    const buy = $("v16OptionBuy");
    const close = $("v16OptionClose");
    if (buy) buy.disabled = true;
    if (close) close.disabled = true;
    setStatus("FINAL SERVER GATE · validating fresh quote, exchange session, exact contract, capital and Paper Desk risk…", "working");
    try {
      const state = await csrfState(selected.workspace);
      const body = {
        action: "BUY",
        workspace: selected.workspace,
        symbol: selected.symbol,
        option_type: selected.option_type,
        strike: selected.strike,
        underlying: selected.underlying,
        expiry: selected.expiry,
        lots: risk.lots,
        stop: risk.stop,
        target: risk.target,
        timeframe: currentTimeframe(),
        client_order_id: `ui:${selected.workspace}:${selected.symbol}:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`,
      };
      const payload = await requestJson("/api/v16/trading/option-order", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Jarvis-Token": state.csrf_token},
        body: JSON.stringify(body),
      });
      if (!payload.success) {
        const reason = payload.reason ? ` [${payload.reason}]` : "";
        setStatus(`${payload.message || "Paper order blocked."}${reason}`, "error");
      } else {
        setStatus(`${payload.action || "LONG OPTION"} filled in PAPER ledger · position ${payload.position_id ?? "recorded"} · live broker execution LOCKED.`, "ok");
      }
      await Promise.all([refreshDiagnostics(), refreshWorkspaceState()]);
      await syncOpenPosition();
    } catch (error) {
      setStatus(error.message || "Paper option order failed.", "error");
    } finally {
      pending = false;
      refreshGatePresentation({preserveStatus: true});
      await syncOpenPosition();
    }
  }

  async function closeSelected() {
    if (!selected || pending) return;
    const button = $("v16OptionClose");
    const positionId = button?.dataset.positionId;
    if (!positionId) return setStatus("No matching open paper position exists for the selected contract.", "error");
    pending = true;
    if (button) button.disabled = true;
    if ($("v16OptionBuy")) $("v16OptionBuy").disabled = true;
    setStatus("Validating a fresh exit quote…", "working");
    try {
      const state = await csrfState(selected.workspace);
      const payload = await requestJson("/api/v16/trading/option-order", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Jarvis-Token": state.csrf_token},
        body: JSON.stringify({
          action: "CLOSE",
          workspace: selected.workspace,
          position_id: Number(positionId),
          symbol: selected.symbol,
          option_type: selected.option_type,
        }),
      });
      if (!payload.success) setStatus(`${payload.message || "Paper close blocked."} [${payload.reason || "BLOCKED"}]`, "error");
      else setStatus(`Long option closed in PAPER ledger at ${payload.exit_price ?? "verified mark"}. Live execution remains locked.`, "ok");
      await Promise.all([refreshDiagnostics(), refreshWorkspaceState()]);
      await syncOpenPosition();
    } catch (error) {
      setStatus(error.message || "Paper option close failed.", "error");
    } finally {
      pending = false;
      refreshGatePresentation({preserveStatus: true});
      await syncOpenPosition();
    }
  }

  function issueText(issue) {
    if (typeof issue === "string") return issue;
    if (issue && typeof issue === "object") {
      const parts = [issue.book || "LEGACY_RECORD"];
      if (issue.open_count) parts.push(`${issue.open_count} open`);
      if (issue.error) parts.push(issue.error);
      if (issue.path) parts.push(issue.path);
      return parts.join(" · ");
    }
    return String(issue ?? "UNKNOWN");
  }

  async function refreshDiagnostics() {
    const host = $("v16LedgerIssues");
    const repair = $("v16RepairLedger");
    if (!host) return;
    try {
      const payload = await requestJson("/api/v16/trading/reconciliation");
      latestReconciliation = payload;
      const issues = Array.isArray(payload.issues) ? payload.issues : [];
      const legacy = Array.isArray(payload.legacy_exposure) ? payload.legacy_exposure : [];
      const all = [...issues, ...legacy];
      if (payload.success && !all.length) {
        host.innerHTML = "<span class=\"state-ready\">CLEAN · new paper exposure may pass to normal risk gates.</span>";
        if (repair) repair.hidden = true;
      } else {
        const legacyExposure = legacy.some(item => item && typeof item === "object" && (item.open_count || item.error));
        const note = legacyExposure
          ? "<p class=\"v16-ledger-note\">Legacy open exposure must be migrated or closed deliberately. Automatic link repair is hidden because it must never delete, duplicate, or silently import a position.</p>"
          : "";
        host.innerHTML = `<b class="state-blocked">NEW ENTRIES BLOCKED</b>${all.slice(0, 8).map(item => `<p>${escapeHtml(issueText(item))}</p>`).join("")}${note}`;
        if (repair) repair.hidden = legacyExposure || !issues.length;
      }
    } catch (error) {
      latestReconciliation = null;
      host.textContent = error.message || "Ledger diagnostics unavailable.";
    }
    refreshGatePresentation();
  }

  async function repairLedger() {
    const repair = $("v16RepairLedger");
    if (!repair || repair.hidden || pending) return;
    pending = true;
    repair.disabled = true;
    setStatus("Backfilling only unambiguous canonical event/order links; no trade is deleted, closed, or imported…", "working");
    try {
      const workspace = selected?.workspace || $("v16OptionCapital")?.value || "INTRADAY";
      const state = await csrfState(workspace);
      const payload = await requestJson("/api/v16/trading/reconcile", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Jarvis-Token": state.csrf_token},
        body: JSON.stringify({action: "repair_legacy_links"}),
      });
      const remaining = payload.reconciliation?.issues || [];
      if (payload.success) setStatus("Canonical ledger reconciliation is clean. Start the paper session before a new option entry.", "ok");
      else setStatus(`${payload.message || "Unresolved ledger issues remain."}${remaining.length ? ` ${remaining.join(" · ")}` : ""}`, "error");
      await Promise.all([refreshDiagnostics(), refreshWorkspaceState()]);
    } catch (error) {
      setStatus(error.message || "Ledger repair failed.", "error");
    } finally {
      pending = false;
      repair.disabled = false;
      syncSelection();
    }
  }

  function boot() {
    mount();
    if (!$("v16OptionOrder")) setTimeout(boot, 150);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, {once: true});
  else boot();
})();