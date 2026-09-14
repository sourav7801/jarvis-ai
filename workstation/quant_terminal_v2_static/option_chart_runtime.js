(() => {
  const originalSendCommand = sendCommand;
  const originalLoadSlot = loadSlot;
  const originalSelectMarket = selectMarket;

  function optionLabel(spec) {
    return String(spec?.label || spec?.instrument_name || "OPTION");
  }

  function abortOptionLoad(slot) {
    if (!slot) return;
    slot.optionLoadVersion = Number(slot.optionLoadVersion || 0) + 1;
    if (slot.optionAbortController) {
      try { slot.optionAbortController.abort(); } catch {}
      slot.optionAbortController = null;
    }
    if (slot.cryptoSocket) {
      try { slot.cryptoSocket.close(); } catch {}
      slot.cryptoSocket = null;
    }
  }

  function clearOptionMode(slot) {
    if (!slot) return;
    abortOptionLoad(slot);
    slot.kind = "MARKET";
    slot.optionChart = null;
    slot.optionSocket = null;
  }

  selectMarket = function enhancedSelectMarket(symbol) {
    const slot = chartSlots[selectedSlot];
    if (slot) clearOptionMode(slot);
    return originalSelectMarket(symbol);
  };

  function sameOptionRequest(slot, spec, version) {
    return Boolean(
      slot
      && Number(slot.optionLoadVersion || 0) === Number(version)
      && slot.kind === "OPTION"
      && slot.optionChart
      && String(slot.optionChart.instrument_name || "") === String(spec?.instrument_name || "")
      && String(slot.optionChart.provider || "") === String(spec?.provider || "")
    );
  }

  function applyOptionLivePrice(slot, snapshot) {
    if (!slot?.candles || !snapshot) return;
    const price = Number(snapshot.ltp ?? snapshot.mark_price);
    if (!Number.isFinite(price)) return;
    const slotFrame = slot.timeframe || timeframe;
    const now = bucketTime(currentEpoch(snapshot), slotFrame);
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
    slot.head.querySelector("span").textContent = `${slotFrame} · LIVE ${fmt(price, 4)}`;
    const iv = Number(snapshot.mark_iv);
    const oi = Number(snapshot.open_interest);
    const parts = [slot.optionChart?.provider || "OPTION", `price ${fmt(price, 4)}`];
    if (Number.isFinite(iv)) parts.push(`IV ${iv.toFixed(2)}`);
    if (Number.isFinite(oi)) parts.push(`OI ${fmt(oi, 0)}`);
    setStatus(slot, parts.join(" · "), "live");
  }

  function connectDeribitOptionSocket(slot, spec, version) {
    if (!spec || spec.provider !== "DERIBIT_PUBLIC" || !spec.instrument_name) return;
    try {
      const socket = new WebSocket(spec.websocket_url || "wss://www.deribit.com/ws/api/v2");
      slot.cryptoSocket = socket;
      socket.onopen = () => {
        if (!sameOptionRequest(slot, spec, version)) {
          try { socket.close(); } catch {}
          return;
        }
        socket.send(JSON.stringify({
          jsonrpc: "2.0",
          id: Date.now(),
          method: "public/subscribe",
          params: {channels: [spec.realtime_channel || `ticker.${spec.instrument_name}.100ms`]},
        }));
      };
      socket.onmessage = event => {
        if (!sameOptionRequest(slot, spec, version)) return;
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
        if (sameOptionRequest(slot, spec, version)) {
          setStatus(slot, "Deribit option WebSocket unavailable; REST option ticker fallback remains available.", "error");
        }
      };
    } catch (error) {
      if (sameOptionRequest(slot, spec, version)) {
        setStatus(slot, error.message || "Unable to start Deribit option stream.", "error");
      }
    }
  }

  async function pollOptionLive(slot, spec, version) {
    if (!spec || !spec.instrument_name || !sameOptionRequest(slot, spec, version)) return;
    try {
      const params = new URLSearchParams({
        provider: spec.provider,
        instrument: spec.instrument_name,
      });
      const response = await fetch(`/api/option-live?${params}`);
      const payload = await response.json();
      if (!sameOptionRequest(slot, spec, version)) return;
      if (payload.success && payload.snapshot) applyOptionLivePrice(slot, payload.snapshot);
    } catch {}
  }

  async function loadOptionSlot(index) {
    const slot = chartSlots[index];
    const currentSpec = slot?.optionChart;
    if (!slot || !currentSpec?.instrument_name) return originalLoadSlot(index);

    if (slot.optionAbortController) {
      try { slot.optionAbortController.abort(); } catch {}
    }
    if (slot.cryptoSocket) {
      try { slot.cryptoSocket.close(); } catch {}
      slot.cryptoSocket = null;
    }

    const spec = {...currentSpec};
    const version = Number(slot.optionLoadVersion || 0) + 1;
    slot.optionLoadVersion = version;
    const controller = new AbortController();
    slot.optionAbortController = controller;

    const slotFrame = slot.timeframe || timeframe;
    const label = optionLabel(spec);
    slot.head.querySelector("strong").textContent = label;
    slot.head.querySelector("span").textContent = `${slotFrame} · OPTION LOADING`;
    setStatus(slot, `Loading verified option candles for ${label}…`);

    try {
      const params = new URLSearchParams({
        provider: spec.provider,
        instrument: spec.instrument_name,
        timeframe: slotFrame,
        bars: "700",
      });
      const response = await fetch(`/api/option-candles?${params}`, {signal: controller.signal, cache: "no-store"});
      const payload = await response.json();
      if (!sameOptionRequest(slot, spec, version)) return;
      if (!payload.success || !payload.candles?.length) {
        throw new Error(payload.message || "Verified option candles unavailable.");
      }
      createSeries(slot, payload);
      if (!sameOptionRequest(slot, spec, version)) return;
      slot.head.querySelector("strong").textContent = label;
      slot.head.querySelector("span").textContent = `${slotFrame} · ${payload.source}`;
      setStatus(
        slot,
        `${payload.source} · ${payload.provider_symbol} · ${payload.bars} bars · ${payload.data_quality || "OPTION DATA"}`,
        "live",
      );
      if (spec.provider === "DERIBIT_PUBLIC") connectDeribitOptionSocket(slot, spec, version);
      else void pollOptionLive(slot, spec, version);
    } catch (error) {
      if (error?.name === "AbortError" || !sameOptionRequest(slot, spec, version)) return;
      setStatus(slot, error.message || "Option chart data unavailable.", "error");
      slot.head.querySelector("span").textContent = `${slotFrame} · OPTION DATA UNAVAILABLE`;
    } finally {
      if (slot.optionAbortController === controller) slot.optionAbortController = null;
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

    // Update the visible contract immediately.  The async candle load below is
    // generation-guarded so an older request can never repaint a newer click.
    const label = optionLabel(slot.optionChart);
    if (slot.head) {
      slot.head.querySelector("strong").textContent = label;
      slot.head.querySelector("span").textContent = `${slot.timeframe || timeframe} · OPTION SELECTED`;
    }
    document.querySelectorAll(".chart-cell").forEach((node, i) => node.classList.toggle("selected", i === index));
    try { persistCharts(); } catch {}
    void loadSlot(index);
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
      if (result.action === "open_master_chat") {
        const handoff = String(result.text || text).slice(0, 1000);
        window.open(
          `http://127.0.0.1:8797/?workspace=chat&command=${encodeURIComponent(handoff)}`,
          "_blank",
          "noopener",
        );
      }
      else if (result.action === "set_layout" && Number(result.layout)) {
        layout = chartCount(Number(result.layout));
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