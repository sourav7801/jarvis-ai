(() => {
  "use strict";

  if (!window.JARVIS_V17_RUNTIME || window.__JARVIS_V17_CRYPTO_PAPER_RUNTIME__) return;
  window.__JARVIS_V17_CRYPTO_PAPER_RUNTIME__ = true;

  const $ = id => document.getElementById(id);
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const first = (...values) => values.find(value => value !== undefined && value !== null && value !== "");
  const INDIA = ["NIFTY", "BANKNIFTY", "SENSEX"];
  const MCX = ["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"];
  const CRYPTO = ["BTC", "ETH", "SOL"];

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
      #v17CryptoPaperCard .v17-market-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin:3px 0 8px}
      #v17CryptoPaperCard .v17-market-head strong{font-size:15px;letter-spacing:.03em;color:#e5f8ff}
      #v17CryptoPaperCard .v17-market-state{font-size:8px;border:1px solid #385f72;border-radius:999px;padding:5px 7px;color:#bad9e8;white-space:nowrap}
      #v17CryptoPaperCard .v17-market-state[data-state="running"],#v17CryptoPaperCard .v17-market-state[data-state="actionable"]{border-color:#2f8c61;color:#84f3b3}
      #v17CryptoPaperCard .v17-market-state[data-state="problem"],#v17CryptoPaperCard .v17-market-state[data-state="blocked"]{border-color:#8a3b4d;color:#ff91a4}
      #v17CryptoPaperCard .v17-authority{font-size:8px;line-height:1.45;color:#7fa9ba;margin-bottom:8px}
      #v17CryptoPaperCard .v17-authority b{color:#8cf1b4}
      #v17CryptoPaperCard .v17-section{border-top:1px solid #143747;padding-top:8px;margin-top:8px}
      #v17CryptoPaperCard .v17-section-title{display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:8px;letter-spacing:.08em;color:#8bc8da;margin-bottom:5px}
      #v17CryptoPaperCard .v17-market-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;margin:0 0 7px}
      #v17CryptoPaperCard .v17-market-grid.four{grid-template-columns:repeat(2,minmax(0,1fr))}
      #v17CryptoPaperCard .v17-market-row{border:1px solid #163f4f;background:#06151d;padding:6px;min-width:0}
      #v17CryptoPaperCard .v17-market-row .top{display:flex;justify-content:space-between;gap:4px;align-items:center}
      #v17CryptoPaperCard .v17-market-row b{font-size:9px;color:#dff8ff}.v17-action{font-size:8px;color:#ffd166}
      #v17CryptoPaperCard .v17-market-row[data-action="primary"] .v17-action,#v17CryptoPaperCard .v17-market-row[data-action="probe"] .v17-action,#v17CryptoPaperCard .v17-market-row[data-action="actionable"] .v17-action,#v17CryptoPaperCard .v17-market-row[data-action="position_open"] .v17-action{color:#82efae}
      #v17CryptoPaperCard .v17-market-row small{display:block;margin-top:4px;color:#7fa8b8;font-size:7px;line-height:1.35;overflow-wrap:anywhere}
      #v17CryptoPaperCard .v17-position-title{margin:7px 0 5px;font-size:8px;letter-spacing:.09em;color:#85bfd3}
      #v17CryptoPaperCard .v17-position{border:1px solid #2b6f59;background:#071d19;padding:7px;margin-top:5px}
      #v17CryptoPaperCard .v17-position .symbol{display:flex;justify-content:space-between;gap:6px;color:#8bf2b4;font-size:10px;font-weight:700}
      #v17CryptoPaperCard .v17-position-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;margin-top:6px}
      #v17CryptoPaperCard .v17-position-grid div{border:1px solid #174051;padding:5px;min-width:0}
      #v17CryptoPaperCard .v17-position-grid span{display:block;font-size:6px;color:#6f9dad;text-transform:uppercase}.v17-position-grid b{font-size:8px!important;color:#e3f8ff!important;overflow-wrap:anywhere}
      #v17CryptoPaperCard .v17-empty{border:1px dashed #305367;padding:7px;color:#82aaba;font-size:8px;line-height:1.45}
      @media(max-width:1250px){#v17CryptoPaperCard .v17-market-grid,#v17CryptoPaperCard .v17-market-grid.four{grid-template-columns:1fr}}
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
      <div class="eyebrow">V17 CROSS-MARKET · CANONICAL PAPER</div>
      <div class="v17-market-head"><strong>INDIA · MCX · CRYPTO</strong><span id="v17CrossMarketState" class="v17-market-state">CHECKING</span></div>
      <div id="v17CrossMarketAuthority" class="v17-authority">Reading canonical execution authorities…</div>

      <div class="v17-section">
        <div class="v17-section-title"><span>INDIAN INDEX OPTIONS · NIFTY / BANKNIFTY / SENSEX</span><span id="v17IndiaState">CHECKING</span></div>
        <div id="v17IndiaRows" class="v17-market-grid"></div>
        <div class="v17-position-title">OPEN INDEX OPTION PAPER POSITIONS</div>
        <div id="v17IndiaPositions"></div>
      </div>

      <div class="v17-section">
        <div class="v17-section-title"><span>MCX UNDERLYING/FUTURES PAPER</span><span id="v17McxState">CHECKING</span></div>
        <div id="v17McxRows" class="v17-market-grid four"></div>
        <div class="v17-position-title">OPEN MCX PAPER POSITIONS</div>
        <div id="v17McxPositions"></div>
      </div>

      <div class="v17-section">
        <div class="v17-section-title"><span>CRYPTO UNDERLYING PAPER · BTC / ETH / SOL</span><span id="v17CryptoLaneState">CHECKING</span></div>
        <div id="v17CryptoRows" class="v17-market-grid"></div>
        <div class="v17-position-title">OPEN CRYPTO PAPER POSITIONS</div>
        <div id="v17CryptoPositions"></div>
      </div>`;
    const primary = $("v16AutonomyPrimary");
    const evidence = $("v16EvidenceDeck");
    if (evidence?.parentElement === intel) evidence.insertAdjacentElement("afterend", card);
    else if (primary?.parentElement === intel) primary.insertAdjacentElement("afterend", card);
    else intel.prepend(card);
    return card;
  }

  function rowReason(row) {
    const option = row?.option_decision || {};
    const result = first(
      row?.reason,
      option?.primary_reason,
      option?.reason,
      row?.execution_result?.reason,
      row?.adaptive_reason,
      Array.isArray(row?.hard_blockers) ? row.hard_blockers.join(", ") : null,
      Array.isArray(row?.reasons_not_to_trade) ? row.reasons_not_to_trade.join(", ") : null,
      row?.message
    );
    return String(result || "Waiting for a complete scanner row.");
  }

  function rowAction(row, mode) {
    const option = row?.option_decision || {};
    if (mode === "INDIA") return String(first(option.status, option.execution_stage, row?.stage, row?.adaptive_action, "WAIT")).toUpperCase();
    return String(first(row?.adaptive_action, row?.action, "WAIT")).toUpperCase();
  }

  function rowSide(row, mode) {
    const option = row?.option_decision || {};
    if (mode === "INDIA") return String(first(option.bias, option.direction, row?.adaptive_side, row?.candidate_side, row?.side, "—")).toUpperCase();
    return String(first(row?.adaptive_side, row?.candidate_side, row?.side, "—")).toUpperCase();
  }

  function rowEv(row, mode) {
    const option = row?.option_decision || {};
    return first(option.expected_value_r, row?.adaptive_expected_value_r, row?.expected_value_r);
  }

  function rowConfidence(row, mode) {
    const option = row?.option_decision || {};
    return first(option.confidence, row?.adaptive_confidence, row?.confidence);
  }

  function renderRows(hostId, symbols, rows, mode) {
    const host = $(hostId);
    if (!host) return;
    const list = Array.isArray(rows) ? rows : [];
    const bySymbol = new Map();
    for (const row of list) {
      const option = row?.option_decision || {};
      const raw = String(first(option.underlying, row?.underlying, row?.symbol, "")).toUpperCase();
      const symbol = INDIA.find(name => raw.includes(name)) || MCX.find(name => raw.includes(name)) || CRYPTO.find(name => raw.includes(name)) || raw;
      if (symbol) bySymbol.set(symbol, row || {});
    }
    host.innerHTML = symbols.map(symbol => {
      const row = bySymbol.get(symbol) || {};
      const action = rowAction(row, mode);
      const side = rowSide(row, mode);
      return `<div class="v17-market-row" data-action="${escapeHtml(action.toLowerCase())}">
        <div class="top"><b>${escapeHtml(symbol)}</b><span class="v17-action">${escapeHtml(action)}</span></div>
        <small>${escapeHtml(side)} · EV ${escapeHtml(number(rowEv(row, mode), 3))}R · CONF ${escapeHtml(percent(rowConfidence(row, mode)))}</small>
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

  function renderPositions(hostId, positions, emptyText) {
    const host = $(hostId);
    if (!host) return;
    const rows = Array.isArray(positions) ? positions : [];
    if (!rows.length) {
      host.innerHTML = `<div class="v17-empty">${escapeHtml(emptyText)}</div>`;
      return;
    }
    host.innerHTML = rows.map(position => {
      const symbol = String(positionValue(position, "symbol") || "POSITION").toUpperCase();
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

  function indiaPositions(state) {
    return (Array.isArray(state?.positions) ? state.positions : []).filter(position => {
      const meta = position?.metadata || {};
      const text = `${position?.symbol || ""} ${meta?.underlying || ""}`.toUpperCase();
      const asset = String(first(position?.asset_type, meta?.asset_type, "")).toUpperCase();
      return asset === "OPTION" && INDIA.some(symbol => text.includes(symbol));
    });
  }

  function renderIndia(state) {
    const session = state?.session || {};
    const scan = state?.scan_decisions || {};
    const rows = scan?.candidates || [];
    const stateText = String(session?.entry_session || session?.state || "PAUSED").toUpperCase();
    const node = $("v17IndiaState");
    if (node) node.textContent = stateText;
    renderRows("v17IndiaRows", INDIA, rows, "INDIA");
    renderPositions(
      "v17IndiaPositions",
      indiaPositions(state),
      "No open NIFTY/BANKNIFTY/SENSEX option PAPER position. Exact-contract execution remains quality-gated and session-aware."
    );
  }

  function renderMcx(lane) {
    const state = String(lane?.state || (lane?.running ? "RUNNING" : "PAUSED")).toUpperCase();
    const node = $("v17McxState");
    if (node) node.textContent = state;
    renderRows("v17McxRows", MCX, lane?.last_rows_summary || [], "MCX");
    renderPositions(
      "v17McxPositions",
      lane?.positions || [],
      state === "WAITING_FOR_MCX_SESSION"
        ? "MCX is closed. The lane will start scanning automatically when the MCX session opens; MCX option execution remains disabled."
        : "No open MCX PAPER position. JARVIS requires an adaptive executable setup plus verified FYERS FUTURE specs, live mark, risk geometry and capital approval."
    );
  }

  function renderCrypto(lane) {
    const state = String(lane?.state || (lane?.running ? "RUNNING" : "PAUSED")).toUpperCase();
    const node = $("v17CryptoLaneState");
    if (node) node.textContent = state;
    renderRows("v17CryptoRows", CRYPTO, lane?.last_rows_summary || [], "CRYPTO");
    renderPositions(
      "v17CryptoPositions",
      lane?.positions || [],
      "No open BTC/ETH/SOL PAPER position. JARVIS will populate this automatically after a PRIMARY/PROBE decision clears the hard safety gates."
    );
  }

  function renderAuthority(v17, india) {
    const crypto = v17?.crypto_underlying_paper || {};
    const mcx = crypto?.mcx_underlying_paper || {};
    const authority = $("v17CrossMarketAuthority");
    if (authority) {
      authority.innerHTML = `<b>${escapeHtml(crypto?.qualification_authority || "ADAPTIVE PAPER")}</b><br>` +
        `Crypto ${escapeHtml(crypto?.adaptive_policy_version || "—")} · MCX ${escapeHtml(mcx?.adaptive_policy_version || "—")} · ` +
        `India exact-option contracts: NIFTY / BANKNIFTY / SENSEX · MCX options disabled · live broker execution locked.`;
    }
    const cross = $("v17CrossMarketState");
    if (cross) {
      const problem = v17?.success === false || india?.success === false || crypto?.success === false || mcx?.success === false;
      const open = Number(crypto?.open_positions || 0) + Number(mcx?.open_positions || 0) + indiaPositions(india).length;
      cross.textContent = problem ? "PROBLEM" : open ? `${open} OPEN` : "MONITORING";
      cross.dataset.state = problem ? "problem" : open ? "actionable" : "running";
    }
  }

  function renderProblem(message) {
    ensureCard();
    const cross = $("v17CrossMarketState");
    if (cross) {
      cross.textContent = "PROBLEM";
      cross.dataset.state = "problem";
    }
    const authority = $("v17CrossMarketAuthority");
    if (authority) authority.textContent = message || "Cross-market PAPER status unavailable.";
  }

  async function refresh() {
    if (document.hidden) return;
    ensureCard();
    try {
      const [v17Response, indiaResponse] = await Promise.all([
        fetch("/api/v17/trading/status?workspace=OPTIONS", {cache: "no-store"}),
        fetch("/api/v16/trading/workspace-state?workspace=INTRADAY", {cache: "no-store"})
      ]);
      const [v17, india] = await Promise.all([v17Response.json(), indiaResponse.json()]);
      if (!v17Response.ok || !v17?.crypto_underlying_paper) throw new Error(v17?.reason || `V17 HTTP ${v17Response.status}`);
      if (!indiaResponse.ok || !india?.session) throw new Error(india?.reason || `India HTTP ${indiaResponse.status}`);
      renderAuthority(v17, india);
      renderIndia(india);
      renderMcx(v17.crypto_underlying_paper.mcx_underlying_paper || {});
      renderCrypto(v17.crypto_underlying_paper);
    } catch (error) {
      renderProblem(`Cross-market PAPER monitor unavailable: ${error?.message || error}`);
    }
  }

  const observer = new MutationObserver(() => ensureCard());
  observer.observe(document.documentElement, {childList: true, subtree: true});
  setTimeout(refresh, 900);
  setInterval(refresh, 7500);
})();
