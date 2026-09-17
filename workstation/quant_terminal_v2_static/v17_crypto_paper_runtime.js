(() => {
  "use strict";

  if (!window.JARVIS_V17_RUNTIME || window.__JARVIS_V17_CRYPTO_PAPER_RUNTIME__) return;
  window.__JARVIS_V17_CRYPTO_PAPER_RUNTIME__ = true;

  const $ = id => document.getElementById(id);
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const first = (...values) => values.find(value => value !== undefined && value !== null && value !== "");

  function number(value, digits = 2) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits) : "—";
  }

  function percent(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return `${(Math.abs(n) <= 1 ? n * 100 : n).toFixed(1)}%`;
  }

  function ensureStyle() {
    if ($("v17CryptoPaperStyle")) return;
    const style = document.createElement("style");
    style.id = "v17CryptoPaperStyle";
    style.textContent = `
      #v17CryptoPaperCard{border-color:#365f79;background:linear-gradient(180deg,#071923,#06131b)}
      #v17CryptoPaperCard .v17-crypto-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin:3px 0 8px}
      #v17CryptoPaperCard .v17-crypto-head strong{font-size:18px;letter-spacing:.03em;color:#e5f8ff}
      #v17CryptoPaperCard .v17-crypto-state{font-size:8px;border:1px solid #385f72;border-radius:999px;padding:5px 7px;color:#bad9e8;white-space:nowrap}
      #v17CryptoPaperCard .v17-crypto-state[data-state="running"]{border-color:#2f8c61;color:#84f3b3}
      #v17CryptoPaperCard .v17-crypto-state[data-state="problem"]{border-color:#8a3b4d;color:#ff91a4}
      #v17CryptoPaperCard .v17-crypto-authority{font-size:8px;line-height:1.45;color:#7fa9ba;margin-bottom:8px}
      #v17CryptoPaperCard .v17-crypto-authority b{color:#8cf1b4}
      #v17CryptoPaperCard .v17-crypto-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;margin:0 0 8px}
      #v17CryptoPaperCard .v17-crypto-row{border:1px solid #163f4f;background:#06151d;padding:6px;min-width:0}
      #v17CryptoPaperCard .v17-crypto-row .top{display:flex;justify-content:space-between;gap:4px;align-items:center}
      #v17CryptoPaperCard .v17-crypto-row b{font-size:9px;color:#dff8ff}.v17-crypto-action{font-size:8px;color:#ffd166}
      #v17CryptoPaperCard .v17-crypto-row[data-action="primary"] .v17-crypto-action,#v17CryptoPaperCard .v17-crypto-row[data-action="probe"] .v17-crypto-action{color:#82efae}
      #v17CryptoPaperCard .v17-crypto-row small{display:block;margin-top:4px;color:#7fa8b8;font-size:7px;line-height:1.35;overflow-wrap:anywhere}
      #v17CryptoPaperCard .v17-position-title{margin:7px 0 5px;font-size:8px;letter-spacing:.09em;color:#85bfd3}
      #v17CryptoPaperCard .v17-position{border:1px solid #2b6f59;background:#071d19;padding:7px;margin-top:5px}
      #v17CryptoPaperCard .v17-position .symbol{display:flex;justify-content:space-between;gap:6px;color:#8bf2b4;font-size:10px;font-weight:700}
      #v17CryptoPaperCard .v17-position-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;margin-top:6px}
      #v17CryptoPaperCard .v17-position-grid div{border:1px solid #174051;padding:5px;min-width:0}
      #v17CryptoPaperCard .v17-position-grid span{display:block;font-size:6px;color:#6f9dad;text-transform:uppercase}.v17-position-grid b{font-size:8px!important;color:#e3f8ff!important;overflow-wrap:anywhere}
      #v17CryptoPaperCard .v17-empty{border:1px dashed #305367;padding:7px;color:#82aaba;font-size:8px;line-height:1.45}
      @media(max-width:1250px){#v17CryptoPaperCard .v17-crypto-grid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function ensureCard() {
    ensureStyle();
    let card = $("v17CryptoPaperCard");
    if (card) return card;
    const intel = document.querySelector(".intel-panel");
    if (!intel) return null;
    card = document.createElement("section");
    card.id = "v17CryptoPaperCard";
    card.className = "intel-card";
    card.innerHTML = `
      <div class="eyebrow">V17 CRYPTO UNDERLYING · CANONICAL PAPER</div>
      <div class="v17-crypto-head"><strong>BTC · ETH · SOL</strong><span id="v17CryptoLaneState" class="v17-crypto-state">CHECKING</span></div>
      <div id="v17CryptoAuthority" class="v17-crypto-authority">Reading adaptive execution authority…</div>
      <div id="v17CryptoRows" class="v17-crypto-grid"></div>
      <div class="v17-position-title">OPEN CRYPTO PAPER POSITIONS</div>
      <div id="v17CryptoPositions"></div>`;
    const primary = $("v16AutonomyPrimary");
    const evidence = $("v16EvidenceDeck");
    if (evidence?.parentElement === intel) evidence.insertAdjacentElement("afterend", card);
    else if (primary?.parentElement === intel) primary.insertAdjacentElement("afterend", card);
    else intel.prepend(card);
    return card;
  }

  function rowReason(row) {
    const result = first(
      row.reason,
      row.execution_result?.reason,
      row.adaptive_reason,
      Array.isArray(row.hard_blockers) ? row.hard_blockers.join(", ") : null,
      Array.isArray(row.reasons_not_to_trade) ? row.reasons_not_to_trade.join(", ") : null
    );
    return String(result || "Waiting for a complete adaptive scanner row.");
  }

  function renderRows(rows) {
    const host = $("v17CryptoRows");
    if (!host) return;
    const bySymbol = new Map((Array.isArray(rows) ? rows : []).map(row => [String(row?.symbol || "").toUpperCase(), row || {}]));
    host.innerHTML = ["BTC", "ETH", "SOL"].map(symbol => {
      const row = bySymbol.get(symbol) || {};
      const action = String(first(row.adaptive_action, row.action, "WAIT")).toUpperCase();
      const side = String(first(row.adaptive_side, row.candidate_side, row.side, "—")).toUpperCase();
      const ev = first(row.adaptive_expected_value_r, row.expected_value_r);
      const confidence = first(row.adaptive_confidence, row.confidence);
      return `<div class="v17-crypto-row" data-action="${escapeHtml(action.toLowerCase())}">
        <div class="top"><b>${symbol}</b><span class="v17-crypto-action">${escapeHtml(action)}</span></div>
        <small>${escapeHtml(side)} · EV ${escapeHtml(number(ev, 3))}R · CONF ${escapeHtml(percent(confidence))}</small>
        <small>${escapeHtml(rowReason(row))}</small>
      </div>`;
    }).join("");
  }

  function positionValue(position, ...keys) {
    for (const key of keys) {
      if (position?.[key] !== undefined && position?.[key] !== null && position?.[key] !== "") return position[key];
    }
    return null;
  }

  function renderPositions(positions) {
    const host = $("v17CryptoPositions");
    if (!host) return;
    const rows = Array.isArray(positions) ? positions : [];
    if (!rows.length) {
      host.innerHTML = '<div class="v17-empty">No open BTC/ETH/SOL PAPER position. JARVIS will populate this automatically after a PRIMARY/PROBE decision clears fresh-data, risk-geometry, reconciliation, capital and duplicate-exposure gates.</div>';
      return;
    }
    host.innerHTML = rows.map(position => {
      const symbol = String(positionValue(position, "symbol") || "CRYPTO").toUpperCase();
      const side = String(positionValue(position, "side", "direction") || "—").toUpperCase();
      const qty = positionValue(position, "quantity", "qty", "size");
      const entry = positionValue(position, "entry", "entry_price", "average_price");
      const mark = positionValue(position, "mark", "current_price", "last_price", "ltp");
      const stop = positionValue(position, "stop", "stop_loss", "sl");
      const target = positionValue(position, "target", "take_profit", "tp");
      const pnl = positionValue(position, "unrealized_pnl", "pnl", "unrealized");
      const strategy = positionValue(position, "strategy", "source");
      return `<div class="v17-position">
        <div class="symbol"><span>${escapeHtml(symbol)} · ${escapeHtml(side)}</span><span>PAPER</span></div>
        <div class="v17-position-grid">
          <div><span>Quantity</span><b>${escapeHtml(qty ?? "—")}</b></div>
          <div><span>Entry</span><b>${escapeHtml(entry ?? "—")}</b></div>
          <div><span>Mark</span><b>${escapeHtml(mark ?? "—")}</b></div>
          <div><span>P&L</span><b>${escapeHtml(pnl ?? "—")}</b></div>
          <div><span>Stop</span><b>${escapeHtml(stop ?? "—")}</b></div>
          <div><span>Target</span><b>${escapeHtml(target ?? "—")}</b></div>
        </div>
        ${strategy ? `<small>${escapeHtml(strategy)}</small>` : ""}
      </div>`;
    }).join("");
  }

  function renderLane(lane) {
    ensureCard();
    const state = String(lane?.state || (lane?.running ? "RUNNING" : "PAUSED")).toUpperCase();
    const stateNode = $("v17CryptoLaneState");
    if (stateNode) {
      stateNode.textContent = state;
      stateNode.dataset.state = state.toLowerCase() === "running" ? "running" : state.toLowerCase() === "problem" ? "problem" : "paused";
    }
    const authority = $("v17CryptoAuthority");
    if (authority) {
      const policy = lane?.adaptive_policy_version || "—";
      const executionAuthority = lane?.decision_authority || lane?.qualification_authority || "—";
      authority.innerHTML = `<b>${escapeHtml(executionAuthority)}</b><br>Policy ${escapeHtml(policy)} · ${Number(lane?.open_positions || 0)} open · Deribit options research-only · live broker execution locked.`;
    }
    renderRows(lane?.last_rows_summary || []);
    renderPositions(lane?.positions || []);
  }

  function renderProblem(message) {
    ensureCard();
    const stateNode = $("v17CryptoLaneState");
    if (stateNode) {
      stateNode.textContent = "PROBLEM";
      stateNode.dataset.state = "problem";
    }
    const authority = $("v17CryptoAuthority");
    if (authority) authority.textContent = message || "Crypto PAPER status unavailable.";
    renderRows([]);
    renderPositions([]);
  }

  async function refresh() {
    if (document.hidden) return;
    ensureCard();
    try {
      const response = await fetch("/api/v17/trading/status?workspace=OPTIONS", {cache: "no-store"});
      const payload = await response.json();
      if (!response.ok || !payload?.crypto_underlying_paper) throw new Error(payload?.reason || `HTTP ${response.status}`);
      renderLane(payload.crypto_underlying_paper);
    } catch (error) {
      renderProblem(`Crypto PAPER monitor unavailable: ${error?.message || error}`);
    }
  }

  const observer = new MutationObserver(() => ensureCard());
  observer.observe(document.documentElement, {childList: true, subtree: true});
  setTimeout(refresh, 900);
  setInterval(refresh, 7500);
})();
