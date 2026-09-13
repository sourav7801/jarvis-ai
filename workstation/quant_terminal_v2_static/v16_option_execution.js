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
  let diagnosticsTimer = null;

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

  function readSelection() {
    const row = selectedRow();
    const summary = $("v16SelectedOption");
    const symbol = summary?.querySelector("b")?.textContent?.trim() || "";
    if (!row || !symbol) return null;
    const cells = [...row.querySelectorAll("td")].map(cell => cell.textContent.trim());
    if (cells.length < 5) return null;
    return {
      symbol,
      option_type: String(cells[0] || "").toUpperCase(),
      strike: parseNumber(cells[1]),
      ltp: parseNumber(cells[2]),
      bid: parseNumber(cells[3]),
      ask: parseNumber(cells[4]),
      underlying: $("v16OptionUnderlying")?.value || "NIFTY",
      expiry: $("v16OptionExpiry")?.value || "",
      workspace: $("v16OptionCapital")?.value || "INTRADAY",
    };
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
      <div class="v16-option-order-grid">
        <label>Lots<input id="v16OptionLots" type="number" min="1" max="100" step="1" value="1"></label>
        <label>Stop<input id="v16OptionStop" inputmode="decimal" placeholder="required"></label>
        <label>Target<input id="v16OptionTarget" inputmode="decimal" placeholder="required"></label>
        <button id="v16OptionBuy" type="button" disabled>BUY SELECTED OPTION</button>
        <button id="v16OptionClose" type="button" disabled>CLOSE LONG POSITION</button>
      </div>
      <div id="v16OptionOrderStatus" class="v16-option-order-status">Select a listed CE/PE contract. Stop and target are mandatory; JARVIS will not invent risk levels.</div>
      <details id="v16LedgerDiagnostics">
        <summary>LEDGER / EXECUTION DIAGNOSTICS</summary>
        <div id="v16LedgerIssues">Checking canonical ledger…</div>
        <button id="v16RepairLedger" type="button" hidden>REPAIR UNAMBIGUOUS LEGACY LINKS</button>
      </details>
      <small>Long CALL/PUT paper positions only. No naked shorts. No broker-order API. Live execution remains locked.</small>`;
    const selectedSummary = $("v16SelectedOption");
    if (selectedSummary?.parentElement) selectedSummary.insertAdjacentElement("afterend", panel);
    else options.appendChild(panel);

    $("v16OptionBuy")?.addEventListener("click", buySelected);
    $("v16OptionClose")?.addEventListener("click", closeSelected);
    $("v16RepairLedger")?.addEventListener("click", repairLedger);

    const rows = $("v16OptionRows");
    rows?.addEventListener("click", () => setTimeout(syncSelection, 0));
    $("v16OptionUnderlying")?.addEventListener("change", clearSelection);
    $("v16OptionExpiry")?.addEventListener("change", clearSelection);
    $("v16OptionCapital")?.addEventListener("change", () => {
      if (selected) selected.workspace = $("v16OptionCapital")?.value || "INTRADAY";
      syncOpenPosition();
    });

    const observer = new MutationObserver(() => syncSelection());
    if (selectedSummary) observer.observe(selectedSummary, {childList: true, subtree: true, characterData: true});
    syncSelection();
    refreshDiagnostics();
    diagnosticsTimer = setInterval(refreshDiagnostics, 5000);
    window.addEventListener("beforeunload", () => {
      observer.disconnect();
      if (diagnosticsTimer) clearInterval(diagnosticsTimer);
    }, {once: true});
  }

  function clearSelection() {
    selected = null;
    const label = $("v16OptionOrderContract");
    if (label) label.textContent = "SELECT A CONTRACT";
    const buy = $("v16OptionBuy");
    const close = $("v16OptionClose");
    if (buy) buy.disabled = true;
    if (close) close.disabled = true;
    setStatus("Select a listed CE/PE contract. Stop and target are mandatory; JARVIS will not invent risk levels.");
  }

  function syncSelection() {
    const contract = readSelection();
    if (!contract) return clearSelection();
    selected = contract;
    const label = $("v16OptionOrderContract");
    if (label) label.textContent = `${contract.symbol} · ${contract.option_type} ${contract.strike ?? "—"}`;
    const buy = $("v16OptionBuy");
    if (buy) {
      buy.disabled = pending || !["CE", "PE"].includes(contract.option_type);
      buy.textContent = contract.option_type === "CE" ? "BUY CALL · PAPER" : "BUY PUT · PAPER";
    }
    setStatus(`Selected ${contract.symbol}. Enter STOP < live entry < TARGET, then submit the paper order.`);
    syncOpenPosition();
  }

  async function stateFor(workspace) {
    return requestJson(`/api/v16/trading/workspace-state?workspace=${encodeURIComponent(workspace)}`);
  }

  async function syncOpenPosition() {
    const close = $("v16OptionClose");
    if (!close) return;
    close.disabled = true;
    close.dataset.positionId = "";
    if (!selected?.symbol) return;
    try {
      const state = await stateFor(selected.workspace || "INTRADAY");
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
    const state = await stateFor(workspace);
    if (!state?.csrf_token) throw new Error("Local V16 session token unavailable; refresh the terminal.");
    return state;
  }

  function riskInputs() {
    return {
      lots: parseNumber($("v16OptionLots")?.value),
      stop: parseNumber($("v16OptionStop")?.value),
      target: parseNumber($("v16OptionTarget")?.value),
    };
  }

  async function buySelected() {
    syncSelection();
    if (!selected || pending) return;
    const risk = riskInputs();
    if (!Number.isInteger(risk.lots) || risk.lots < 1) {
      return setStatus("Enter a positive whole number of lots.", "error");
    }
    const reference = selected.ask ?? selected.ltp;
    if (risk.stop === null || risk.target === null) {
      return setStatus("STOP and TARGET are required. JARVIS will not fabricate option risk geometry.", "error");
    }
    if (reference !== null && !(risk.stop > 0 && risk.stop < reference && risk.target > reference)) {
      return setStatus(`For a long option require STOP < current ask/LTP (${reference}) < TARGET.`, "error");
    }

    pending = true;
    const buy = $("v16OptionBuy");
    const close = $("v16OptionClose");
    if (buy) buy.disabled = true;
    if (close) close.disabled = true;
    setStatus("Validating fresh quote, symbol master, capital and risk gates…", "working");
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
        setStatus(
          `${payload.action || "LONG OPTION"} filled in PAPER ledger · position ${payload.position_id ?? "recorded"} · live broker execution LOCKED.`,
          "ok",
        );
      }
      await refreshDiagnostics();
      await syncOpenPosition();
    } catch (error) {
      setStatus(error.message || "Paper option order failed.", "error");
    } finally {
      pending = false;
      if (buy) buy.disabled = !selected;
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
      await syncOpenPosition();
    } catch (error) {
      setStatus(error.message || "Paper option close failed.", "error");
    } finally {
      pending = false;
      if ($("v16OptionBuy")) $("v16OptionBuy").disabled = !selected;
      await refreshDiagnostics();
    }
  }

  function issueText(issue) {
    if (typeof issue === "string") return issue;
    if (issue && typeof issue === "object") {
      return `${issue.book || "LEGACY_RECORD"}${issue.open_count ? ` · ${issue.open_count} open` : ""}${issue.error ? ` · ${issue.error}` : ""}`;
    }
    return String(issue ?? "UNKNOWN");
  }

  async function refreshDiagnostics() {
    const host = $("v16LedgerIssues");
    const repair = $("v16RepairLedger");
    if (!host) return;
    try {
      const payload = await requestJson("/api/v16/trading/reconciliation");
      const issues = Array.isArray(payload.issues) ? payload.issues : [];
      const legacy = Array.isArray(payload.legacy_exposure) ? payload.legacy_exposure : [];
      const all = [...issues, ...legacy];
      if (payload.success && !all.length) {
        host.innerHTML = "<span class=\"state-ready\">CLEAN · new paper exposure may pass to normal risk gates.</span>";
        if (repair) repair.hidden = true;
      } else {
        host.innerHTML = `<b class="state-blocked">NEW ENTRIES BLOCKED</b>${all.slice(0, 8).map(item => `<p>${escapeHtml(issueText(item))}</p>`).join("")}`;
        if (repair) repair.hidden = false;
      }
    } catch (error) {
      host.textContent = error.message || "Ledger diagnostics unavailable.";
    }
  }

  async function repairLedger() {
    const repair = $("v16RepairLedger");
    if (!repair || pending) return;
    pending = true;
    repair.disabled = true;
    setStatus("Backfilling only unambiguous missing legacy links; no trade is deleted or rewritten…", "working");
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
      await refreshDiagnostics();
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
