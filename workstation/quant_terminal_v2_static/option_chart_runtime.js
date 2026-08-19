(() => {
  const originalSendCommand = sendCommand;
  const originalLoadSlot = loadSlot;
  const originalSelectMarket = selectMarket;

  function optionLabel(spec) {
    return String(spec?.label || spec?.instrument_name || "OPTION");
  }

  function clearOptionMode(slot) {
    if (!slot) return;
    slot.kind = "MARKET";
    slot.optionChart = null;
    slot.optionSocket = null;
  }

  selectMarket = function enhancedSelectMarket(symbol) {
    const slot = chartSlots[selectedSlot];
    if (slot) clearOptionMode(slot);
    return originalSelectMarket(symbol);
  };

  function applyOptionLivePrice(slot, snapshot) {
    if (!slot?.candles || !snapshot) return;
    const price = Number(snapshot.ltp ?? snapshot.mark_price);
    if (!Number.isFinite(price)) return;
    const now = bucketTime(currentEpoch(snapshot), timeframe);
    const last = slot.data[slot.data.length - 1];
    let candle;
    if (last && Number(last.time) === now) {
      candle = {
        ...last,
        high: Math.max(Number(last.high), price),
        low: Math.min(Number(last.low), price),
        close: price,
      };
      slot.data[slot.data.length - 1] = candle;
    } else {
      const open = last ? Number(last.close) : price;
      candle = {
        time: now,
        open,
        high: Math.max(open, price),
        low: Math.min(open, price),
        close: price,
        volume: 0,
      };
      slot.data.push(candle);
    }
    slot.candles.update({
      time: candle.time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    });
    slot.head.querySelector("span").textContent = `${timeframe} · LIVE ${fmt(price, 4)}`;
    const iv = Number(snapshot.mark_iv);
    const oi = Number(snapshot.open_interest);
    const parts = [slot.optionChart?.provider || "OPTION", `price ${fmt(price, 4)}`];
    if (Number.isFinite(iv)) parts.push(`IV ${iv.toFixed(2)}`);
    if (Number.isFinite(oi)) parts.push(`OI ${fmt(oi, 0)}`);
    setStatus(slot, parts.join(" · "), "live");
  }

  function connectDeribitOptionSocket(slot) {
    const spec = slot?.optionChart;
    if (!spec || spec.provider !== "DERIBIT_PUBLIC" || !spec.instrument_name) return;
    try {
      const socket = new WebSocket(spec.websocket_url || "wss://www.deribit.com/ws/api/v2");
      slot.cryptoSocket = socket;
      socket.onopen = () => {
        socket.send(JSON.stringify({
          jsonrpc: "2.0",
          id: Date.now(),
          method: "public/subscribe",
          params: {channels: [spec.realtime_channel || `ticker.${spec.instrument_name}.100ms`]},
        }));
      };
      socket.onmessage = event => {
        try {
          const message = JSON.parse(event.data);
          const data = message?.params?.data;
          if (!data || data.instrument_name !== spec.instrument_name) return;
          applyOptionLivePrice(slot, {
            ltp: data.last_price ?? data.mark_price,
            mark_price: data.mark_price,
            mark_iv: data.mark_iv,
            open_interest: data.open_interest,
            underlying_price: data.underlying_price ?? data.index_price,
            greeks: data.greeks || {},
            exchange_timestamp: data.timestamp ? Math.floor(Number(data.timestamp) / 1000) : undefined,
          });
        } catch {}
      };
      socket.onerror = () => {
        setStatus(slot, "Deribit option WebSocket unavailable; REST option ticker fallback remains available.", "error");
      };
    } catch (error) {
      setStatus(slot, error.message || "Unable to start Deribit option stream.", "error");
    }
  }

  async function pollOptionLive(slot) {
    const spec = slot?.optionChart;
    if (!spec || !spec.instrument_name) return;
    try {
      const params = new URLSearchParams({
        provider: spec.provider,
        instrument: spec.instrument_name,
      });
      const response = await fetch(`/api/option-live?${params}`);
      const payload = await response.json();
      if (payload.success && payload.snapshot) applyOptionLivePrice(slot, payload.snapshot);
    } catch {}
  }

  async function loadOptionSlot(index) {
    const slot = chartSlots[index];
    const spec = slot?.optionChart;
    if (!slot || !spec?.instrument_name) return originalLoadSlot(index);
    if (slot.cryptoSocket) {
      try { slot.cryptoSocket.close(); } catch {}
      slot.cryptoSocket = null;
    }
    const label = optionLabel(spec);
    slot.head.querySelector("strong").textContent = label;
    slot.head.querySelector("span").textContent = `${timeframe} · OPTION LOADING`;
    setStatus(slot, `Loading verified option candles for ${label}…`);
    try {
      const params = new URLSearchParams({
        provider: spec.provider,
        instrument: spec.instrument_name,
        timeframe,
        bars: "700",
      });
      const response = await fetch(`/api/option-candles?${params}`);
      const payload = await response.json();
      if (!payload.success || !payload.candles?.length) {
        throw new Error(payload.message || "Verified option candles unavailable.");
      }
      createSeries(slot, payload);
      slot.head.querySelector("strong").textContent = label;
      slot.head.querySelector("span").textContent = `${timeframe} · ${payload.source}`;
      setStatus(
        slot,
        `${payload.source} · ${payload.provider_symbol} · ${payload.bars} bars · ${payload.data_quality || "OPTION DATA"}`,
        "live",
      );
      if (spec.provider === "DERIBIT_PUBLIC") connectDeribitOptionSocket(slot);
      else pollOptionLive(slot);
    } catch (error) {
      setStatus(slot, error.message || "Option chart data unavailable.", "error");
      slot.head.querySelector("span").textContent = `${timeframe} · OPTION DATA UNAVAILABLE`;
    }
  }

  loadSlot = async function enhancedLoadSlot(index) {
    const slot = chartSlots[index];
    if (slot?.kind === "OPTION" && slot.optionChart) return loadOptionSlot(index);
    return originalLoadSlot(index);
  };

  function openOptionChart(spec) {
    if (!spec?.instrument_name) return;
    const underlying = String(spec.underlying || "").toUpperCase();
    let index = chartSlots.findIndex(slot => String(slot.symbol || "").toUpperCase() === underlying);
    if (index < 0) index = selectedSlot;
    const slot = chartSlots[index];
    if (!slot) return;
    selectedSlot = index;
    if (underlying) selectedSymbol = underlying;
    slot.kind = "OPTION";
    slot.optionChart = {...spec};
    if (underlying) slot.symbol = underlying;
    document.querySelectorAll(".chart-cell").forEach((node, i) => node.classList.toggle("selected", i === index));
    loadSlot(index);
  }

  async function enhancedSendCommand() {
    const input = $("commandInput");
    const text = input.value.trim();
    if (!text) return;
    $("commandReply").textContent = "JARVIS is routing the trading command…";
    try {
      const response = await fetch("/api/agent", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text}),
      });
      const result = await response.json();
      $("commandReply").textContent = result.speech || result.message || "Command processed.";
      if (result.action === "set_layout" && Number(result.layout)) {
        layout = [1, 2, 4, 6, 8].includes(Number(result.layout)) ? Number(result.layout) : layout;
        selectedSlot = 0;
        syncControls();
        mountCharts();
      }
      if (result.action === "set_chart" && result.chart) {
        const raw = String(result.chart.label || result.chart.symbol || "").toUpperCase().replaceAll(" ", "");
        const found = MARKETS.find(item => item.symbol === raw || item.label.toUpperCase().replaceAll(" ", "") === raw);
        if (found) selectMarket(found.symbol);
      }
      if (result.action === "open_quant" && result.symbol) {
        const raw = String(result.symbol).toUpperCase().replaceAll(" ", "");
        const found = MARKETS.find(item => item.symbol === raw || item.label.toUpperCase().replaceAll(" ", "") === raw);
        if (found) {
          selectMarket(found.symbol);
          scanSelected();
        }
      }
      if ((result.action === "option_analysis" || result.action === "india_option_analysis") && result.chart) {
        openOptionChart(result.chart);
      }
    } catch (error) {
      $("commandReply").textContent = error.message;
    }
  }

  sendCommand = enhancedSendCommand;
  const button = $("sendCommand");
  if (button) {
    button.removeEventListener("click", originalSendCommand);
    button.addEventListener("click", enhancedSendCommand);
  }

  window.JARVIS_OPTION_CHART = {
    open: openOptionChart,
    load: loadOptionSlot,
  };
})();
