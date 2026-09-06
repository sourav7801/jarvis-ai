(() => {
  "use strict";

  const REFRESH_MS = 5000;
  let timer = null;

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

  function install() {
    if (timer) clearInterval(timer);
    timer = setInterval(refreshAdaptiveBrain, REFRESH_MS);
    setTimeout(refreshAdaptiveBrain, 1200);
  }

  install();
})();
