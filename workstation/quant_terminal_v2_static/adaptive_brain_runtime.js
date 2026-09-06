(() => {
  "use strict";

  const DECISION_REFRESH_MS = 5000;
  const STATUS_REFRESH_MS = 10000;
  let decisionTimer = null;
  let statusTimer = null;

  function clearLines(slot) {
    if (!slot || !Array.isArray(slot.adaptiveLines) || !slot.candles) return;
    for (const line of slot.adaptiveLines) {
      try { slot.candles.removePriceLine(line); } catch (_) {}
    }
    slot.adaptiveLines = [];
  }

  function addLine(slot, price, title, lineStyle = 2, lineWidth = 1) {
    const numeric = Number(price);
    if (!slot?.candles || !Number.isFinite(numeric) || numeric <= 0) return;
    try {
      const line = slot.candles.createPriceLine({
        price: numeric,
        title,
        axisLabelVisible: true,
        lineStyle,
        lineWidth,
      });
      slot.adaptiveLines = slot.adaptiveLines || [];
      slot.adaptiveLines.push(line);
    } catch (_) {}
  }

  function selectedChartSlot() {
    try {
      if (!Array.isArray(chartSlots) || !chartSlots.length) return null;
      return chartSlots[selectedSlot] || chartSlots[0] || null;
    } catch (_) {
      return null;
    }
  }

  function renderBrainState(slot, payload) {
    if (!slot || !payload?.success || !payload?.decision) return;
    const decision = payload.decision;
    const structure = decision.structure || {};
    clearLines(slot);

    for (const support of (structure.supports || []).slice(0, 3)) {
      addLine(slot, support, "SUPPORT", 2, 1);
    }
    for (const resistance of (structure.resistances || []).slice(0, 3)) {
      addLine(slot, resistance, "RESIST", 2, 1);
    }
    addLine(slot, decision.entry, "ENTRY", 0, 2);
    addLine(slot, decision.stop, "STOP", 1, 2);
    addLine(slot, decision.target, "TARGET", 0, 2);

    try {
      const regime = decision.regime || "UNKNOWN";
      const side = decision.side || "WAIT";
      const score = Number(decision.score || 0).toFixed(1);
      const bos = structure.bos || "NONE";
      const choch = structure.choch || "NONE";
      const sweep = structure.liquidity_sweep || "NONE";
      slot.status.textContent = `ADAPTIVE BRAIN · ${regime} · ${side} ${score} · BOS ${bos} · CHOCH ${choch} · ${sweep}`;
      slot.status.className = "chart-status live";
    } catch (_) {}
  }

  function currentProfile() {
    let tf = "15m";
    try { tf = timeframe || "15m"; } catch (_) {}
    return {
      "1m": "1m_only",
      "5m": "5m_only",
      "15m": "15m_only",
      "1h": "1h_only",
      "1d": "swing",
    }[tf] || "adaptive_intraday";
  }

  function openDeck(module) {
    const slot = selectedChartSlot();
    const symbol = slot?.symbol || "NIFTY";
    const query = new URLSearchParams({
      module,
      symbol,
      profile: currentProfile(),
    });
    location.href = `/intelligence.html?${query}`;
  }

  function mountBrainCard() {
    if (document.getElementById("adaptiveBrainLiveCard")) return;
    const host = document.querySelector(".intel-panel");
    if (!host) return;
    const card = document.createElement("section");
    card.className = "intel-card";
    card.id = "adaptiveBrainLiveCard";
    card.innerHTML = `
      <div class="eyebrow">ADAPTIVE BRAIN V6.3 · LIVE RESEARCH TELEMETRY</div>
      <div class="hero-row">
        <b id="adaptiveBrainState">ONLINE</b>
        <span id="adaptiveBrainLearning">LEARNING · 0 OUTCOMES</span>
      </div>
      <div class="gate-summary" style="margin-top:8px">
        <div><b id="adaptiveTopStrategy">NO LEADERBOARD YET</b><small>TOP STRATEGY RELIABILITY</small></div>
        <div><b id="adaptiveResearchState">RESEARCH IDLE</b><small>SELF-IMPROVEMENT LOOP</small></div>
      </div>
      <div class="module-grid" style="margin-top:8px">
        <button type="button" data-v63-module="adaptive-brain">BRAIN</button>
        <button type="button" data-v63-module="strategy-lab">STRATEGY LAB</button>
        <button type="button" data-v63-module="learning">LEARNING</button>
        <button type="button" data-v63-module="self-improvement">RESEARCH</button>
      </div>
      <small>Bounded paper learning only. No automatic production rewrite or broker-order surface.</small>
    `;
    host.prepend(card);
    card.querySelectorAll("[data-v63-module]").forEach(button => {
      button.addEventListener("click", () => openDeck(button.dataset.v63Module));
    });
  }

  async function refreshAdaptiveBrain() {
    const slot = selectedChartSlot();
    if (!slot?.symbol || !slot?.candles) return;
    let tf = "15m";
    try { tf = timeframe || "15m"; } catch (_) {}
    try {
      const params = new URLSearchParams({ symbol: slot.symbol, timeframe: tf });
      const response = await fetch(`/api/intelligence/decision?${params}`);
      const payload = await response.json();
      if (payload?.success) renderBrainState(slot, payload);
    } catch (_) {}
  }

  async function refreshLearningStatus() {
    try {
      const response = await fetch("/api/intelligence/status");
      const payload = await response.json();
      if (!payload?.success) return;
      const learning = payload.learning || {};
      const recent = Array.isArray(learning.recent_outcomes) ? learning.recent_outcomes : [];
      const board = Array.isArray(learning.strategy_leaderboard) ? learning.strategy_leaderboard : [];
      const improvement = payload.self_improvement || {};
      const top = board[0];

      const learningNode = document.getElementById("adaptiveBrainLearning");
      const strategyNode = document.getElementById("adaptiveTopStrategy");
      const researchNode = document.getElementById("adaptiveResearchState");
      const stateNode = document.getElementById("adaptiveBrainState");

      if (learningNode) learningNode.textContent = `LEARNING · ${recent.length} OUTCOMES`;
      if (strategyNode) {
        strategyNode.textContent = top
          ? `${top.strategy} · W ${Number(top.weight || 1).toFixed(3)} · ${top.trades || 0} TRADES`
          : "NO LEADERBOARD YET";
      }
      if (researchNode) {
        researchNode.textContent = improvement.running
          ? `RUNNING · ${improvement.cycles || 0} CYCLES`
          : `IDLE · ${improvement.cycles || 0} CYCLES`;
      }
      if (stateNode) stateNode.textContent = "ONLINE";
    } catch (_) {
      const stateNode = document.getElementById("adaptiveBrainState");
      if (stateNode) stateNode.textContent = "DEGRADED";
    }
  }

  function install() {
    mountBrainCard();
    if (decisionTimer) clearInterval(decisionTimer);
    if (statusTimer) clearInterval(statusTimer);
    decisionTimer = setInterval(refreshAdaptiveBrain, DECISION_REFRESH_MS);
    statusTimer = setInterval(refreshLearningStatus, STATUS_REFRESH_MS);
    setTimeout(refreshAdaptiveBrain, 1200);
    setTimeout(refreshLearningStatus, 1500);
    window.addEventListener("beforeunload", () => {
      if (decisionTimer) clearInterval(decisionTimer);
      if (statusTimer) clearInterval(statusTimer);
    }, { once: true });
  }

  install();
})();
