(() => {
  let scanSequence = 0;
  let scanController = null;

  const originalSelectMarket = selectMarket;

  function cancelActiveScan() {
    scanSequence += 1;
    if (scanController) {
      try { scanController.abort(); } catch {}
      scanController = null;
    }
  }

  function clearSetupForSelection() {
    const meta = marketMeta(selectedSymbol);
    $("scanSymbol").textContent = meta.label;
    $("scanRegime").textContent = "READY";
    $("scanBias").textContent = "NOT SCANNED";
    $("scanAlignment").textContent = "—";
    $("setupState").textContent = "NO SETUP";
    $("entryRef").textContent = "—";
    $("stopRef").textContent = "—";
    $("targetRef").textContent = "—";
    $("rrRef").textContent = "—";
    $("evidenceList").innerHTML = `<p>${escapeHtml(meta.label)} has not been scanned in the current selection.</p>`;
  }

  selectMarket = function(symbol) {
    cancelActiveScan();
    const pending = originalSelectMarket(symbol);
    clearSetupForSelection();
    return pending;
  };

  async function safeScanSelected() {
    const symbol = selectedSymbol;
    const requestId = ++scanSequence;
    if (scanController) {
      try { scanController.abort(); } catch {}
    }
    scanController = new AbortController();

    $("scanSymbol").textContent = marketMeta(symbol).label;
    $("scanRegime").textContent = "SCANNING";
    $("scanBias").textContent = "WORKING";
    $("scanAlignment").textContent = "—";
    $("setupState").textContent = "WAITING";
    $("entryRef").textContent = "—";
    $("stopRef").textContent = "—";
    $("targetRef").textContent = "—";
    $("rrRef").textContent = "—";
    $("evidenceList").innerHTML = "<p>Loading verified 5m / 15m / 1h evidence…</p>";

    try {
      const response = await fetch(`/api/scan?${new URLSearchParams({ symbol })}`, {
        signal: scanController.signal,
      });
      const payload = await response.json();
      const decision = payload;

      if (requestId !== scanSequence || symbol !== selectedSymbol) return;

      const payloadSymbol = String(payload.symbol || "").toUpperCase().replaceAll(" ", "");
      if (payloadSymbol && payloadSymbol !== symbol) {
        throw new Error(`Discarded mismatched scan response for ${payloadSymbol}.`);
      }

      $("scanSymbol").textContent = marketMeta(symbol).label;
      $("scanRegime").textContent = payload.regime || "UNAVAILABLE";
      $("scanBias").textContent = payload.qualified
        ? (payload.bias || "QUALIFIED")
        : `WAIT · ${payload.bias || "NO BIAS"}`;
      $("scanAlignment").textContent = `${Number(payload.alignment || 0)}% ALIGN`;

      const setup = payload.setup;
      $("setupState").textContent = setup ? `${setup.side} · ${setup.status}` : "NO QUALIFIED SETUP";
      $("entryRef").textContent = setup ? fmt(setup.entry_reference) : "—";
      $("stopRef").textContent = setup ? fmt(setup.stop_reference) : "—";
      $("targetRef").textContent = setup ? fmt(setup.target_reference) : "—";
      $("rrRef").textContent = setup ? `${setup.risk_reward_reference}:1` : "—";

      const evidence = Array.isArray(payload.evidence) ? payload.evidence : [];
      $("evidenceList").innerHTML = evidence.map(row => {
        if (!row.available) {
          return `<div class="evidence-row"><div class="topline"><b>${escapeHtml(row.timeframe)}</b><span>NO DATA</span></div><p>${escapeHtml(row.message || "")}</p></div>`;
        }
        const cls = row.trend === "BULLISH" ? "bull" : row.trend === "BEARISH" ? "bear" : "";
        const decision = row.decision || {};
        return `<div class="evidence-row ${cls}"><div class="topline"><b>${escapeHtml(row.timeframe)} · ${escapeHtml(row.trend)}</b><span>${escapeHtml(decision.side || "WAIT")} ${Number(decision.score || 0).toFixed(1)}</span></div><p>Close ${fmt(row.close)} · EMA20 ${fmt(row.ema20)} · EMA50 ${fmt(row.ema50)} · RSI ${fmt(row.rsi14, 1)} · ATR ${fmt(row.atr14)} · Vol× ${row.volume_ratio == null ? "—" : fmt(row.volume_ratio, 2)}</p></div>`;
      }).join("") || "<p>No timeframe evidence.</p>";

      const slot = chartSlots[selectedSlot];
      if (slot && slot.symbol === symbol) applyDecision(slot, decision);

      $("commandReply").textContent = payload.message || "Scan complete.";
    } catch (error) {
      if (error?.name === "AbortError") return;
      if (requestId !== scanSequence || symbol !== selectedSymbol) return;
      $("scanRegime").textContent = "DATA ERROR";
      $("scanBias").textContent = "NO SCAN";
      $("setupState").textContent = "NO SETUP";
      $("evidenceList").innerHTML = `<p>${escapeHtml(error.message || "Scan failed.")}</p>`;
      applyDecision(chartSlots[selectedSlot], {
        success: false,
        side: "WAIT",
        score: 0,
        message: error.message || "Scan failed.",
      });
    } finally {
      if (requestId === scanSequence) scanController = null;
    }
  }

  scanSelected = safeScanSelected;

  const oldButton = $("scanButton");
  if (oldButton) {
    const replacement = oldButton.cloneNode(true);
    oldButton.replaceWith(replacement);
    replacement.addEventListener("click", scanSelected);
  }

  const chartGrid = $("chartGrid");
  if (chartGrid) {
    chartGrid.addEventListener("click", event => {
      const cell = event.target.closest(".chart-cell");
      if (!cell || Number(cell.dataset.slot) === selectedSlot) return;
      cancelActiveScan();
      setTimeout(clearSetupForSelection, 0);
    }, true);
  }

  window.jarvisScanConsistency = {
    cancelActiveScan,
    clearSetupForSelection,
    get sequence() { return scanSequence; },
  };
})();
