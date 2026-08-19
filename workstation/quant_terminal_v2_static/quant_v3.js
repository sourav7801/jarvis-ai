(() => {
  "use strict";

  const q = id => document.getElementById(id);
  const post = async (path, body = {}) => {
    const response = await fetch(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok && !payload.success) throw new Error(payload.message || `HTTP ${response.status}`);
    return payload;
  };

  const style = document.createElement("style");
  style.textContent = `
    .v3-pill{border:1px solid #23536b;border-radius:999px;padding:7px 10px;font-size:10px;letter-spacing:.7px;color:#78dfff;background:#07151d}
    .v3-pill.running{border-color:#2c8b62;color:#82f4b2}.v3-pill.kill{border-color:#a43d4c;color:#ff7185}
    .v3-card{border:1px solid #173d4f;background:#07131a;border-radius:10px;padding:12px;margin-bottom:10px}
    .v3-title{font-size:10px;letter-spacing:2px;color:#62dfff;margin-bottom:8px}
    .v3-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.v3-grid>div{border:1px solid #173747;border-radius:7px;padding:7px}
    .v3-grid span{display:block;color:#6f919f;font-size:9px}.v3-grid strong{display:block;color:#e8faff;font-size:13px;margin-top:3px}
    .v3-actions{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}.v3-actions button{min-height:31px}
    .v3-actions .danger{border-color:#8d3342;color:#ff7185}.v3-actions .go{border-color:#287b5a;color:#7af0ad}
    .v3-drivers{margin-top:8px;display:flex;flex-direction:column;gap:4px}.v3-driver{display:flex;justify-content:space-between;gap:8px;font-size:10px;border-top:1px solid #102b37;padding-top:4px}.v3-driver b{color:#dff8ff}.v3-driver em{font-style:normal;color:#7fa5b4}
    .v3-note{font-size:9px;color:#6f919f;margin-top:7px;line-height:1.35}
  `;
  document.head.appendChild(style);

  function mount() {
    const top = document.querySelector(".top-status");
    if (top && !q("v3TopStatus")) {
      const status = document.createElement("span");
      status.id = "v3TopStatus";
      status.className = "v3-pill";
      status.textContent = "QUANT V3 · READY";
      top.prepend(status);
    }

    const panel = document.querySelector(".intel-panel");
    if (!panel || q("v3AutopilotCard")) return;

    const card = document.createElement("section");
    card.id = "v3AutopilotCard";
    card.className = "v3-card";
    card.innerHTML = `
      <div class="v3-title">AUTONOMOUS PAPER QUANT</div>
      <div class="v3-grid">
        <div><span>STATE</span><strong id="v3State">OFF</strong></div>
        <div><span>LOCAL CYCLE</span><strong id="v3Latency">—</strong></div>
        <div><span>EQUITY</span><strong id="v3Equity">—</strong></div>
        <div><span>REALIZED P&L</span><strong id="v3Pnl">—</strong></div>
        <div><span>POSITIONS</span><strong id="v3Positions">0</strong></div>
        <div><span>STRATEGIES</span><strong id="v3Strategies">—</strong></div>
      </div>
      <div class="v3-actions">
        <button class="go" id="v3Start">START PAPER AUTOPILOT</button>
        <button id="v3Stop">STOP</button>
        <button id="v3Decision">RUN V3 DECISION</button>
        <button id="v3Options">OPTIONS INTEL</button>
        <button class="danger" id="v3Kill">KILL PAPER ENGINE</button>
        <button id="v3Resume">RESUME</button>
      </div>
      <div class="v3-note" id="v3Message">Regime-aware ensemble. No broker-order authority.</div>
      <div class="v3-drivers" id="v3Drivers"></div>
    `;
    panel.prepend(card);

    q("v3Start").addEventListener("click", async () => {
      try {
        const result = await post("/api/v3/autopilot/start", {
          symbols: ["NIFTY", "BANKNIFTY", "SENSEX", "CRUDEOIL", "GOLD", "BTC", "ETH"],
        });
        q("v3Message").textContent = `Paper autopilot started for ${result.symbols?.join(", ") || "configured markets"}.`;
        refreshStatus();
      } catch (error) { q("v3Message").textContent = error.message; }
    });
    q("v3Stop").addEventListener("click", async () => {
      try { await post("/api/v3/autopilot/stop"); q("v3Message").textContent = "Paper autopilot stopped."; refreshStatus(); }
      catch (error) { q("v3Message").textContent = error.message; }
    });
    q("v3Kill").addEventListener("click", async () => {
      try { await post("/api/v3/autopilot/kill", {reason: "manual_terminal_kill"}); q("v3Message").textContent = "Paper engine kill switch engaged."; refreshStatus(); }
      catch (error) { q("v3Message").textContent = error.message; }
    });
    q("v3Resume").addEventListener("click", async () => {
      try { await post("/api/v3/autopilot/resume"); q("v3Message").textContent = "Paper engine resumed. Live execution remains locked."; refreshStatus(); }
      catch (error) { q("v3Message").textContent = error.message; }
    });
    q("v3Decision").addEventListener("click", runDecision);
    q("v3Options").addEventListener("click", runOptions);
  }

  function currentSymbol() {
    try { return String(selectedSymbol || "NIFTY"); } catch { return "NIFTY"; }
  }

  function money(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString("en-IN", {maximumFractionDigits: 2, minimumFractionDigits: 2}) : "—";
  }

  async function refreshStatus() {
    if (!q("v3State")) return;
    try {
      const response = await fetch("/api/v3/status");
      const payload = await response.json();
      const state = payload.autopilot || {};
      const risk = state.risk || {};
      const latency = state.latency || {};
      q("v3State").textContent = state.kill_switch ? "KILLED" : state.running ? "RUNNING" : "OFF";
      q("v3Latency").textContent = latency.last_ms == null ? "—" : `${latency.last_ms} ms`;
      q("v3Equity").textContent = money(risk.equity);
      q("v3Pnl").textContent = money(risk.realized_pnl);
      q("v3Positions").textContent = String(risk.open_positions ?? 0);
      q("v3Strategies").textContent = String(payload.strategies?.strategies?.length ?? "—");
      const top = q("v3TopStatus");
      if (top) {
        top.textContent = state.kill_switch ? "QUANT V3 · KILLED" : state.running ? "QUANT V3 · AUTOPILOT PAPER" : "QUANT V3 · READY";
        top.className = `v3-pill ${state.kill_switch ? "kill" : state.running ? "running" : ""}`;
      }
    } catch (error) {
      q("v3State").textContent = "UNAVAILABLE";
    }
  }

  function renderDrivers(anchor) {
    const host = q("v3Drivers");
    if (!host) return;
    const rows = anchor?.top_drivers || [];
    host.innerHTML = rows.slice(0, 6).map(row => `
      <div class="v3-driver">
        <b>${escapeHtml(row.strategy_id || "strategy")}</b>
        <em>${escapeHtml(row.signal || "FLAT")} · ${(Number(row.strength || 0) * 100).toFixed(0)}%</em>
      </div>
    `).join("") || '<div class="v3-driver"><em>No active strategy votes.</em></div>';
  }

  async function runDecision() {
    const symbol = currentSymbol();
    q("v3Message").textContent = `Running Quant V3 ensemble on ${symbol}…`;
    try {
      const response = await fetch(`/api/v3/decision?${new URLSearchParams({symbol})}`);
      const payload = await response.json();
      if (!payload.success) throw new Error(payload.message || "Quant V3 decision unavailable.");
      q("v3Message").textContent = `${symbol}: ${payload.consensus} · ${(Number(payload.timeframe_agreement || 0) * 100).toFixed(0)}% timeframe agreement · regime ${payload.regime} · local engine ${payload.engine_latency_ms} ms. This is a paper/research decision, not a win probability.`;
      renderDrivers(payload.anchor);
    } catch (error) { q("v3Message").textContent = error.message; }
  }

  async function runOptions() {
    const symbol = currentSymbol();
    q("v3Message").textContent = `Loading ${symbol} option intelligence…`;
    try {
      const response = await fetch(`/api/v3/options?${new URLSearchParams({symbol})}`);
      const payload = await response.json();
      if (!payload.success) throw new Error(payload.message || "Verified options data unavailable for this market.");
      const analysis = payload.analysis || {};
      const confirmation = payload.confirmation || {};
      const pcr = analysis.pcr_oi ?? analysis.put_call_oi_ratio ?? payload.pcr_oi;
      const iv = analysis.atm_iv ?? payload.atm_iv;
      const liquidity = confirmation.liquidity_score ?? analysis.liquidity_score;
      q("v3Message").textContent = `${symbol} OPTIONS · provider ${payload.provider} · PCR ${pcr == null ? "—" : Number(pcr).toFixed(2)} · ATM IV ${iv == null ? "—" : Number(iv).toFixed(2)} · liquidity ${liquidity == null ? "—" : Number(liquidity).toFixed(1)} · defined-risk paper options only.`;
      q("v3Drivers").innerHTML = '<div class="v3-driver"><b>OPTION SAFETY</b><em>NAKED SHORT DISABLED</em></div>';
    } catch (error) { q("v3Message").textContent = error.message; }
  }

  mount();
  refreshStatus();
  setInterval(refreshStatus, 1200);
})();
