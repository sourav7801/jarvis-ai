(() => {
  "use strict";

  if (!window.JARVIS_V16_CANONICAL) return;

  const ENDPOINT = "/api/v16/trading/option-readiness";
  const $ = id => document.getElementById(id);
  const money = value => Number.isFinite(Number(value))
    ? `₹${Number(value).toLocaleString("en-IN", {maximumFractionDigits: 0})}`
    : "—";
  const number = value => {
    const parsed = Number(String(value ?? "").replaceAll(",", "").trim());
    return Number.isFinite(parsed) ? parsed : null;
  };

  let latest = {execution_ready: false, reason: "SERVER_READINESS_PENDING"};
  let debounceTimer = null;
  let refreshTimer = null;
  let controller = null;
  let serial = 0;
  let nudgingLocalGate = false;

  function ticket() {
    const label = $("v16OptionOrderContract")?.textContent?.trim() || "";
    if (!label || label.startsWith("SELECT")) return null;
    const pieces = label.split("·").map(value => value.trim());
    const symbol = pieces[0] || "";
    const optionType = String(pieces[1] || "").split(/\s+/)[0].toUpperCase();
    if (!symbol || !["CE", "PE"].includes(optionType)) return null;
    return {
      execution_mode: "PAPER",
      workspace: $("v16OptionCapital")?.value || "INTRADAY",
      symbol,
      option_type: optionType,
      lots: $("v16OptionLots")?.value || "",
      stop: $("v16OptionStop")?.value || "",
      target: $("v16OptionTarget")?.value || "",
      underlying: $("v16OptionUnderlying")?.value || "",
      expiry: $("v16OptionExpiry")?.value || "",
    };
  }

  function host() {
    let node = $("v16OptionServerReadiness");
    if (node) return node;
    const gates = $("v16OptionGates");
    if (!gates) return null;
    node = document.createElement("div");
    node.id = "v16OptionServerReadiness";
    node.className = "v16-option-order-status";
    node.setAttribute("role", "status");
    node.textContent = "SERVER READINESS · waiting for a complete paper ticket…";
    gates.insertAdjacentElement("afterend", node);
    return node;
  }

  function blockerText(payload) {
    const blocks = Array.isArray(payload?.block_reasons) ? payload.block_reasons : [];
    return blocks.map(item => item?.message || item?.code).filter(Boolean).join(" · ")
      || String(payload?.reason || "SERVER READINESS REQUIRED").replaceAll("_", " ");
  }

  function render(payload) {
    const node = host();
    if (!node) return;
    const quote = payload?.quote || {};
    const risk = payload?.risk || {};
    const age = Number.isFinite(Number(quote.age_seconds)) ? `${Number(quote.age_seconds).toFixed(1)}s old` : "age unavailable";
    const requested = risk.requested_lots ?? "—";
    const safe = risk.recommended_lots ?? "—";
    const riskLine = safe !== "—"
      ? `SAFE LOTS ${safe}/${requested} · RISK ${money(risk.capital_at_risk)} / BUDGET ${money(risk.risk_budget)} · CAPITAL ${money(risk.available_capital_before)}`
      : `REQUESTED LOTS ${requested}`;
    if (payload?.execution_ready === true) {
      node.dataset.kind = "ok";
      node.textContent = `SERVER READY · EXACT QUOTE ${age} · ${riskLine} · ${risk.limiting_constraint || "within canonical limits"}`;
    } else {
      node.dataset.kind = "error";
      node.textContent = `SERVER BLOCKED · ${blockerText(payload)} · QUOTE ${age} · ${riskLine}`;
    }
  }

  function nudgeLocalGate() {
    const lots = $("v16OptionLots");
    if (!lots) return;
    nudgingLocalGate = true;
    try {
      lots.dispatchEvent(new Event("input", {bubbles: false}));
    } finally {
      nudgingLocalGate = false;
    }
  }

  function enforce() {
    const buy = $("v16OptionBuy");
    if (!buy) return;
    buy.dataset.serverReadiness = latest.execution_ready === true ? "READY" : "BLOCKED";
    if (latest.execution_ready !== true) {
      buy.disabled = true;
      buy.title = `Server readiness blocked: ${blockerText(latest)}`;
      return;
    }
    // Let the existing local gate remain authoritative for UI/pending state.
    // Re-run it after a server-ready transition instead of blindly enabling.
    nudgeLocalGate();
  }

  function failClosed(reason, message) {
    latest = {
      success: false,
      execution_ready: false,
      reason,
      block_reasons: [{code: reason, message}],
      quote: {},
      risk: {},
      paper_only: true,
      live_execution: false,
    };
    render(latest);
    enforce();
  }

  async function refresh({invalidate = false} = {}) {
    const current = ticket();
    if (!current) {
      failClosed("SELECT_CONTRACT", "Select an exact CE/PE option contract first.");
      return;
    }
    if (invalidate) {
      latest = {
        success: true,
        execution_ready: false,
        reason: "SERVER_READINESS_PENDING",
        block_reasons: [{code: "SERVER_READINESS_PENDING", message: "Revalidating exact quote, session, capital and risk…"}],
        quote: {},
        risk: {requested_lots: number(current.lots)},
        paper_only: true,
        live_execution: false,
      };
      render(latest);
      enforce();
    }

    const requestSerial = ++serial;
    controller?.abort();
    const requestController = new AbortController();
    controller = requestController;
    const timeout = setTimeout(() => requestController.abort(), 5000);
    try {
      const query = new URLSearchParams(current);
      const response = await fetch(`${ENDPOINT}?${query.toString()}`, {
        method: "GET",
        cache: "no-store",
        signal: requestController.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (requestSerial !== serial) return;
      if (!response.ok || payload?.success !== true) {
        throw new Error(payload?.message || `HTTP ${response.status}`);
      }
      if (payload.paper_only !== true || payload.live_execution !== false || payload.execution_mode !== "PAPER") {
        throw new Error("Server did not return a PAPER-only readiness certificate.");
      }
      latest = payload;
      render(payload);
      enforce();
    } catch (error) {
      if (requestSerial !== serial) return;
      failClosed(
        "SERVER_READINESS_UNAVAILABLE",
        `Authoritative readiness unavailable: ${error?.name === "AbortError" ? "request timed out" : error?.message || "unknown error"}. Paper BUY remains locked.`,
      );
    } finally {
      clearTimeout(timeout);
      if (controller === requestController) controller = null;
    }
  }

  function schedule(invalidate = true) {
    clearTimeout(debounceTimer);
    if (invalidate) {
      latest = {
        success: true,
        execution_ready: false,
        reason: "SERVER_READINESS_PENDING",
        block_reasons: [{code: "SERVER_READINESS_PENDING", message: "Ticket changed; server revalidation required."}],
        quote: {},
        risk: {},
        paper_only: true,
        live_execution: false,
      };
      enforce();
    }
    debounceTimer = setTimeout(() => refresh({invalidate: false}), 250);
  }

  function mount() {
    if (!$("v16OptionOrder")) {
      setTimeout(mount, 100);
      return;
    }
    host();
    failClosed("SERVER_READINESS_PENDING", "Waiting for authoritative quote, session, capital and risk validation.");

    document.addEventListener("click", event => {
      const buy = event.target?.closest?.("#v16OptionBuy");
      if (!buy || latest.execution_ready === true) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      render(latest);
      enforce();
    }, true);

    document.addEventListener("input", event => {
      if (nudgingLocalGate) return;
      if (["v16OptionLots", "v16OptionStop", "v16OptionTarget"].includes(event.target?.id)) schedule(true);
    }, true);
    document.addEventListener("change", event => {
      if (["v16OptionCapital", "v16OptionUnderlying", "v16OptionExpiry"].includes(event.target?.id)) schedule(true);
    }, true);

    const contract = $("v16OptionOrderContract");
    const contractObserver = new MutationObserver(() => schedule(true));
    if (contract) contractObserver.observe(contract, {childList: true, subtree: true, characterData: true});

    const buy = $("v16OptionBuy");
    const buttonObserver = new MutationObserver(() => {
      if (latest.execution_ready !== true && buy && !buy.disabled) buy.disabled = true;
    });
    if (buy) buttonObserver.observe(buy, {attributes: true, attributeFilter: ["disabled"]});

    schedule(true);
    refreshTimer = setInterval(() => refresh({invalidate: false}), 4000);
    window.addEventListener("beforeunload", () => {
      clearTimeout(debounceTimer);
      if (refreshTimer) clearInterval(refreshTimer);
      controller?.abort();
      contractObserver.disconnect();
      buttonObserver.disconnect();
    }, {once: true});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount, {once: true});
  else mount();
})();
