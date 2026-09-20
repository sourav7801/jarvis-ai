(() => {
  "use strict";

  if (!window.JARVIS_V17_RUNTIME || window.__JARVIS_V17_RUNTIME__) return;
  window.__JARVIS_V17_RUNTIME__ = true;

  const $ = id => document.getElementById(id);
  const AUTO_UNDERLYINGS = new Set(["NIFTY", "BANKNIFTY", "SENSEX"]);
  let latestWorkspaceState = null;
  let latestToken = "";
  let latestPreferences = null;
  let controlBusy = false;
  let focusTimer = null;
  let lastFocusKey = "";

  const upstreamFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await upstreamFetch(...args);
    try {
      const requestUrl = String(typeof args[0] === "string" ? args[0] : args[0]?.url || "");
      if (requestUrl.includes("/api/v16/trading/workspace-state")) {
        response.clone().json().then(payload => {
          if (!payload?.success) return;
          latestWorkspaceState = payload;
          if (payload.csrf_token) latestToken = String(payload.csrf_token);
          scheduleChartFirst(payload, 45);
        }).catch(() => {});
      }
    } catch {}
    return response;
  };

  function ensureStyle() {
    if ($("v17RuntimeStyle")) return;
    const style = document.createElement("style");
    style.id = "v17RuntimeStyle";
    style.textContent = `
      .v17-runtime-pill{font-size:10px;letter-spacing:.08em;padding:7px 10px;border-radius:999px;border:1px solid #2c8b63;color:#84f3b3;background:linear-gradient(135deg,rgba(20,87,62,.78),rgba(16,57,80,.72));box-shadow:0 0 18px rgba(84,242,173,.10)}
      .v17-runtime-pill[data-state="degraded"]{border-color:#7a662b;color:#ffd166;background:rgba(77,58,14,.6)}
      .v17-runtime-pill[data-state="error"]{border-color:#7a3141;color:#ff8da0;background:rgba(89,27,42,.55)}
      .v17-runtime-banner{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;border:1px solid #2d7b59;background:linear-gradient(90deg,#071b1d,#081725);padding:8px 9px;border-radius:7px;margin:0 0 6px}
      .v17-runtime-banner strong{font-size:10px;color:#8af2b6;letter-spacing:.08em}.v17-runtime-banner span{display:block;margin-top:2px;font-size:8px;color:#8fb7c5}
      .v17-runtime-badges{display:flex;gap:5px;align-items:center;justify-content:flex-end;flex-wrap:wrap}.v17-runtime-badges b{font-size:9px;color:#dffaff;border:1px solid #24576d;border-radius:999px;padding:5px 7px;white-space:nowrap}
      .v17-runtime-badges b[data-state="connected"]{border-color:#2c8b63;color:#84f3b3}.v17-runtime-badges b[data-state="stale"],.v17-runtime-badges b[data-state="reconnecting"]{border-color:#7a662b;color:#ffd166}.v17-runtime-badges b[data-state="failed"],.v17-runtime-badges b[data-state="unavailable"]{border-color:#7a3141;color:#ff8da0}
      .v17-autopilot-controls{grid-column:1/-1;display:grid;grid-template-columns:auto minmax(170px,1fr) auto auto auto;gap:6px;align-items:center;border-top:1px solid #153c49;padding-top:7px}
      .v17-capital-input{display:flex!important;align-items:center;gap:5px;color:#8fb7c5!important;font-size:8px!important;margin:0!important}.v17-capital-input input{width:62px;background:#06151d;border:1px solid #2b6071;color:#dffaff;border-radius:5px;padding:6px;font-size:10px}.v17-capital-input em{font-style:normal;color:#8fb7c5}
      .v17-autopilot-state{min-width:0;color:#9fc5d2!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v17-autopilot-state[data-kind="ok"]{color:#83efb0!important}.v17-autopilot-state[data-kind="warn"]{color:#ffd166!important}.v17-autopilot-state[data-kind="error"]{color:#ff8da0!important}
      .v17-auto-btn{min-height:30px;padding:5px 9px;border-radius:5px;border:1px solid #2d6579;background:#071922;color:#d9f5ff;font-size:8px;letter-spacing:.04em;cursor:pointer;white-space:nowrap}.v17-auto-btn:disabled{opacity:.45;cursor:not-allowed}.v17-auto-btn.start{border-color:#2f8c61;color:#87f5b6;background:#08251a}.v17-auto-btn.stop{border-color:#74404b;color:#ff9aac;background:#251016}.v17-auto-btn.voice{border-color:#506388;color:#bed0ff;background:#10182b}
      #v17ChainEvidence{margin-top:6px;border:1px solid #1b4b5d;background:#06141c;border-radius:5px;padding:0}#v17ChainEvidence>summary{cursor:pointer;list-style:none;padding:6px 8px;color:#84b8ca;font-size:8px;letter-spacing:.07em}#v17ChainEvidence>summary::-webkit-details-marker{display:none}#v17ChainEvidence[open]>summary{border-bottom:1px solid #1b4b5d;color:#c8eaf6}
      #v17ChainEvidence .v16-option-table-wrap{margin:0!important;border:0!important}
      .v17-chart-first-note{margin:5px 0;padding:5px 7px;border-left:2px solid #2f8c61;background:#06151d;color:#8fb7c5;font-size:8px;line-height:1.4}.v17-chart-first-note b{color:#83efb0}
      @media(max-width:980px){.v17-runtime-banner{grid-template-columns:1fr}.v17-runtime-badges{justify-content:flex-start}.v17-autopilot-controls{grid-template-columns:1fr 1fr}.v17-autopilot-state{grid-column:1/-1}.v17-capital-input{grid-column:1/-1}}
    `;
    document.head.appendChild(style);
  }

  function setText(node, value) {
    if (node && node.textContent !== value) node.textContent = value;
  }

  function activeWorkspace() {
    return String(document.querySelector(".workspace-modes button.active")?.dataset.workspace || "INTRADAY").toUpperCase();
  }

  function optionsWorkspaceActive() {
    return activeWorkspace() === "OPTIONS";
  }

  function selectedUnderlying() {
    return String($("v16OptionUnderlying")?.value || "NIFTY").toUpperCase();
  }

  function normalizeOptionType(value) {
    const token = String(value || "").trim().toUpperCase();
    if (["CE", "CALL", "C"].includes(token)) return "CALL";
    if (["PE", "PUT", "P"].includes(token)) return "PUT";
    return null;
  }

  function brandStaticSurface() {
    if (document.title !== "JARVIS Quant V17 · Autonomous Options") document.title = "JARVIS Quant V17 · Autonomous Options";
    setText(document.querySelector(".brand span"), "V17 AUTONOMOUS OPTIONS RUNTIME · PAPER / RESEARCH");

    const status = document.querySelector(".top-status");
    if (status && !$("v17RuntimePill")) {
      const pill = document.createElement("span");
      pill.id = "v17RuntimePill";
      pill.className = "v17-runtime-pill";
      pill.dataset.state = "degraded";
      pill.textContent = "V17 · VERIFYING";
      status.prepend(pill);
    }

    const workspace = document.querySelector(".workspace");
    if (workspace && !$("v17RuntimeBanner")) {
      const banner = document.createElement("section");
      banner.id = "v17RuntimeBanner";
      banner.className = "v17-runtime-banner";
      banner.innerHTML = `
        <div><strong>JARVIS V17 · ONE-TOUCH AUTONOMOUS PAPER TRADING</strong><span id="v17RuntimeSummary">Verifying route, provider freshness, strategy and canonical Paper Desk.</span></div>
        <div class="v17-runtime-badges">
          <b id="v17RuntimeMode">PAPER ONLY</b>
          <b id="v17ArmedState" data-state="paused">DISARMED</b>
          <b id="v17RouteState">INTRADAY</b>
          <b id="v17FeedState" data-state="disconnected">FYERS · DISCONNECTED</b>
        </div>
        <div class="v17-autopilot-controls">
          <label class="v17-capital-input">OPTIONS CAPITAL <input id="v17OptionsCapital" type="number" min="5" max="100" step="1" value="50"><em>%</em></label>
          <span id="v17AutopilotState" class="v17-autopilot-state">One-touch PAPER autopilot ready. No forced trades.</span>
          <button id="v17StartAutopilot" class="v17-auto-btn start" type="button">START JARVIS TRADING</button>
          <button id="v17StopAutopilot" class="v17-auto-btn stop" type="button">STOP NEW ENTRIES</button>
          <button id="v17VoiceAutopilot" class="v17-auto-btn voice" type="button">VOICE</button>
        </div>`;
      const modes = document.querySelector(".workspace-modes");
      if (modes) modes.insertAdjacentElement("afterend", banner);
      else workspace.prepend(banner);
    }

    const footer = document.querySelector("footer span");
    if (footer && !String(footer.textContent || "").includes("V17")) footer.textContent = "JARVIS Quant V17 · one-touch PAPER autonomy · exact verified option contracts · canonical Paper Desk · live execution locked";
  }

  function relabelInheritedLineage() {
    const card = $("v15ReasoningCard");
    const eyebrow = card?.querySelector(".eyebrow");
    if (eyebrow) {
      const raw = String(eyebrow.textContent || "");
      let symbol = "";
      if (raw.startsWith("V15 AUTONOMOUS MARKET REASONING ·")) symbol = raw.split("·").pop().trim();
      else if (raw.startsWith("V17 AUTONOMOUS OPTIONS · V15 REASONING CORE ·")) symbol = raw.split("·").pop().trim();
      setText(eyebrow, `V17 AUTONOMOUS OPTIONS · V15 REASONING CORE${symbol ? ` · ${symbol}` : ""}`);
    }
    const reason = $("signalReason");
    if (reason && /^V15\s/i.test(String(reason.textContent || ""))) setText(reason, String(reason.textContent).replace(/^V15\s/i, "V17 · V15 reasoning core · "));
    const autoPrimary = $("v16AutonomyPrimary");
    if (autoPrimary) {
      const eyebrowNode = autoPrimary.querySelector(".eyebrow");
      if (eyebrowNode && !String(eyebrowNode.textContent || "").includes("V17")) setText(eyebrowNode, "PRIMARY WORKFLOW · JARVIS V17");
      setText(autoPrimary.querySelector(".v16-auto-head b"), "AUTONOMOUS OPTIONS PAPER TRADING");
    }
  }

  function ensureChainEvidenceMode() {
    const wrap = document.querySelector("#v16Options .v16-option-table-wrap");
    if (!wrap || $("v17ChainEvidence")) return;
    const details = document.createElement("details");
    details.id = "v17ChainEvidence";
    details.open = latestPreferences?.chart_first_options === false;
    const summary = document.createElement("summary");
    summary.textContent = "OPTION-CHAIN EVIDENCE / DEBUG · expand for manual inspection";
    wrap.parentElement.insertBefore(details, wrap);
    details.append(summary, wrap);
    const note = document.createElement("div");
    note.id = "v17ChartFirstNote";
    note.className = "v17-chart-first-note";
    note.innerHTML = "<b>CHART-FIRST</b> · underlying chart while JARVIS searches; exact option chart opens only for an engine-selected verified contract. The chain is evidence, not execution authority.";
    details.insertAdjacentElement("beforebegin", note);
  }

  function applyChartPreference() {
    ensureChainEvidenceMode();
    const details = $("v17ChainEvidence");
    if (details && latestPreferences?.chart_first_options !== false && !document.documentElement.classList.contains("v16-option-chart-focus")) details.open = false;
  }

  async function readPreferences() {
    const response = await upstreamFetch("/api/v17/autopilot/preferences", {cache: "no-store"});
    let payload = {};
    try { payload = await response.json(); } catch {}
    if (!response.ok || payload.success !== true) throw new Error(payload.message || payload.reason || `HTTP ${response.status}`);
    latestPreferences = payload.preferences || {};
    const input = $("v17OptionsCapital");
    if (input) input.value = String(Math.round(Number(latestPreferences.options_capital_fraction || 0.5) * 100));
    applyChartPreference();
    return latestPreferences;
  }

  async function ensureToken() {
    if (latestToken) return latestToken;
    const response = await fetch("/api/v16/trading/workspace-state?workspace=INTRADAY", {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok || !payload?.success || !payload.csrf_token) throw new Error("Local PAPER session token is unavailable; refresh the terminal.");
    latestWorkspaceState = payload;
    latestToken = String(payload.csrf_token);
    return latestToken;
  }

  function setAutopilotMessage(text, kind = "") {
    const node = $("v17AutopilotState");
    if (!node) return;
    node.textContent = text;
    if (kind) node.dataset.kind = kind;
    else delete node.dataset.kind;
  }

  function setControlBusy(busy) {
    controlBusy = busy;
    [$("v17StartAutopilot"), $("v17StopAutopilot"), $("v17VoiceAutopilot")].forEach(node => { if (node) node.disabled = busy; });
  }

  async function postV17(path, body) {
    const token = await ensureToken();
    const response = await fetch(path, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Jarvis-Token": token},
      body: JSON.stringify(body),
      cache: "no-store",
    });
    let payload = {};
    try { payload = await response.json(); } catch {}
    if (!response.ok || payload.success !== true) throw new Error(payload.message || payload.reason || `HTTP ${response.status}`);
    return payload;
  }

  async function controlAutopilot(action, spokenPercent = null) {
    if (controlBusy) return;
    const input = $("v17OptionsCapital");
    const percent = spokenPercent == null ? Number(input?.value || 50) : Number(spokenPercent);
    if (!Number.isFinite(percent) || percent < 5 || percent > 100) {
      setAutopilotMessage("Options capital must be between 5% and 100%.", "error");
      return;
    }
    if (input) input.value = String(percent);
    setControlBusy(true);
    setAutopilotMessage(action === "start" ? "Starting enabled PAPER scanners through the canonical runtime…" : "Pausing all new-entry PAPER sessions…", "warn");
    try {
      const payload = await postV17("/api/v17/autopilot/control", {action, options_capital_percent: percent});
      latestPreferences = payload.preferences || latestPreferences;
      const stateText = Object.entries(payload.states || {}).map(([name, state]) => `${name} ${state || "—"}`).join(" · ");
      setAutopilotMessage(`${payload.message}${stateText ? ` · ${stateText}` : ""}`, "ok");
      if (latestWorkspaceState) scheduleChartFirst(latestWorkspaceState, 80);
      setTimeout(refresh, 250);
    } catch (error) {
      setAutopilotMessage(`V17 autopilot: ${error.message}`, "error");
    } finally {
      setControlBusy(false);
    }
  }

  async function saveCapitalPreference() {
    if (controlBusy) return;
    const percent = Number($("v17OptionsCapital")?.value || 50);
    if (!Number.isFinite(percent) || percent < 5 || percent > 100) return setAutopilotMessage("Options capital must be between 5% and 100%.", "error");
    try {
      const payload = await postV17("/api/v17/autopilot/preferences", {options_capital_percent: percent});
      latestPreferences = payload.preferences || latestPreferences;
      setAutopilotMessage(`Options mandate saved at ${percent}% of funded workspace capital. No daily rebalance or cross-workspace top-up.`, "ok");
    } catch (error) {
      setAutopilotMessage(`Could not save options mandate: ${error.message}`, "error");
    }
  }

  function actionableDecision(state) {
    const decisions = state?.scan_decisions?.autonomous_options || {};
    const ordered = [selectedUnderlying(), "NIFTY", "BANKNIFTY", "SENSEX"];
    const seen = new Set();
    for (const key of ordered) {
      const underlying = String(key || "").toUpperCase();
      if (seen.has(underlying)) continue;
      seen.add(underlying);
      const decision = decisions[underlying];
      if (!decision) continue;
      const status = String(decision.status || "WAIT").toUpperCase();
      const exact = String(decision.candidate_contract || "").trim();
      const decisionUnderlying = String(decision.underlying || underlying).toUpperCase();
      if (!["ACTIONABLE", "POSITION_OPEN", "MANAGING"].includes(status)) continue;
      if (!AUTO_UNDERLYINGS.has(decisionUnderlying) || !exact) continue;
      if (decision.paper_only === false || decision.live_execution === true || decision.automatic_broker_order === true) continue;
      const direction = String(decision.direction || decision.bias || "").toUpperCase();
      const optionType = normalizeOptionType(decision.option_type);
      if (direction === "LONG" && optionType !== "CALL") continue;
      if (direction === "SHORT" && optionType !== "PUT") continue;
      return {...decision, underlying: decisionUnderlying};
    }
    return null;
  }

  function rowForDecision(decision) {
    const wantedType = normalizeOptionType(decision?.option_type);
    const wantedStrike = Number(decision?.strike);
    if (!wantedType || !Number.isFinite(wantedStrike)) return null;
    return [...document.querySelectorAll("#v16OptionRows tr[data-v16-contract]")].find(row => {
      const rowType = normalizeOptionType(row.cells?.[0]?.textContent);
      const strike = Number(String(row.cells?.[1]?.textContent || "").replaceAll(",", ""));
      return rowType === wantedType && Number.isFinite(strike) && Math.abs(strike - wantedStrike) < 0.001;
    }) || null;
  }

  function scheduleChartFirst(state, delay = 40) {
    if (focusTimer) clearTimeout(focusTimer);
    focusTimer = setTimeout(() => driveChartFirst(state, 0), delay);
  }

  function driveChartFirst(state, attempt = 0) {
    ensureChainEvidenceMode();
    if (!optionsWorkspaceActive() || latestPreferences?.chart_first_options === false) return;
    const running = String(state?.session?.entry_session || "PAUSED").toUpperCase() === "RUNNING";
    if (!running) return;
    const decision = actionableDecision(state);
    if (!decision) return;
    const key = [decision.status, decision.candidate_contract, decision.updated_at || "", decision.execution_stage || ""].join("|");
    if (key === lastFocusKey && document.documentElement.classList.contains("v16-option-chart-focus")) return;

    const underlyingSelect = $("v16OptionUnderlying");
    if (!underlyingSelect) return;
    if (String(underlyingSelect.value || "").toUpperCase() !== decision.underlying) {
      underlyingSelect.value = decision.underlying;
      underlyingSelect.dispatchEvent(new Event("change", {bubbles: true}));
      underlyingSelect.dataset.userChosen = "";
      if (attempt < 20) focusTimer = setTimeout(() => driveChartFirst(state, attempt + 1), 350);
      return;
    }

    const expiry = String(decision.expiry || "").trim();
    const expirySelect = $("v16OptionExpiry");
    if (expiry && expirySelect && expirySelect.value !== expiry) {
      const option = [...expirySelect.options].find(item => String(item.value || "").trim() === expiry);
      if (option) {
        expirySelect.value = expiry;
        expirySelect.dispatchEvent(new Event("change", {bubbles: true}));
        if (attempt < 20) focusTimer = setTimeout(() => driveChartFirst(state, attempt + 1), 350);
        return;
      }
    }

    const row = rowForDecision(decision);
    if (!row) {
      if (attempt < 20) focusTimer = setTimeout(() => driveChartFirst(state, attempt + 1), 250);
      return;
    }

    row.click();
    setTimeout(() => {
      const open = $("v16OpenOptionChart");
      if (open && !open.disabled && !open.hidden) open.click();
      lastFocusKey = key;
      const details = $("v17ChainEvidence");
      if (details) details.open = false;
      setAutopilotMessage(`Chart-first: ${decision.underlying} → ${decision.candidate_contract}. Exact engine-selected option chart is primary; chain remains evidence/debug.`, "ok");
    }, 25);
  }

  function setupVoice() {
    const button = $("v17VoiceAutopilot");
    if (!button) return;
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      button.disabled = true;
      button.title = "Speech recognition is not available in this browser.";
      return;
    }
    button.addEventListener("click", () => {
      const recognition = new Recognition();
      recognition.lang = "en-IN";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      setAutopilotMessage("Listening for a V17 PAPER trading command…", "warn");
      recognition.onresult = event => {
        const text = String(event.results?.[0]?.[0]?.transcript || "").trim();
        const percentMatch = text.match(/(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)/i);
        const percent = percentMatch ? Number(percentMatch[1]) : null;
        if (/\b(stop|pause)\b.*\b(trading|jarvis|entries)\b|\b(stop|pause)\s+trading\b/i.test(text)) return controlAutopilot("stop", percent);
        if (/\b(start|resume|run)\b.*\b(trading|jarvis|autopilot)\b|\bstart\s+trading\b/i.test(text)) return controlAutopilot("start", percent);
        if (percent !== null) {
          if ($("v17OptionsCapital")) $("v17OptionsCapital").value = String(percent);
          saveCapitalPreference();
          return;
        }
        setAutopilotMessage(`Voice heard: “${text}” · say “Jarvis, use 50 percent capital for options and start trading.”`, "warn");
      };
      recognition.onerror = event => setAutopilotMessage(`Voice command unavailable: ${event.error || "speech error"}.`, "error");
      try { recognition.start(); } catch (error) { setAutopilotMessage(`Voice command unavailable: ${error.message}`, "error"); }
    });
  }

  function bindControls() {
    $("v17StartAutopilot")?.addEventListener("click", () => controlAutopilot("start"));
    $("v17StopAutopilot")?.addEventListener("click", () => controlAutopilot("stop"));
    $("v17OptionsCapital")?.addEventListener("change", saveCapitalPreference);
    setupVoice();
  }

  async function readStatus() {
    const workspace = activeWorkspace();
    const response = await upstreamFetch(`/api/v17/trading/status?workspace=${encodeURIComponent(workspace)}`, {cache: "no-store"});
    let payload = {};
    try { payload = await response.json(); } catch {}
    if (!response.ok || payload.success !== true) throw new Error(payload.reason || `HTTP ${response.status}`);
    return payload;
  }

  function normalizeFeedState(status) {
    const stream = status?.market_data?.stream || {};
    if (stream.state) return String(stream.state).toUpperCase();
    if (stream.connected === true) return stream.fresh === false ? "STALE" : "CONNECTED";
    return stream.running ? "RECONNECTING" : "DISCONNECTED";
  }

  function ensurePerformanceDiagnostics() {
    let details = $("v17PerformanceDiagnostics");
    if (details) return details;
    const host = document.querySelector(".intel-panel");
    if (!host) return null;
    details = document.createElement("details");
    details.id = "v17PerformanceDiagnostics";
    details.style.cssText = "border:1px solid #174052;border-radius:6px;padding:7px;margin:8px 0;background:#06141b;color:#9cc6d4;font-size:8px;";
    details.innerHTML = '<summary style="cursor:pointer;color:#91dff1;letter-spacing:.08em">V17.4 PERFORMANCE · DATA PLANE</summary><pre id="v17PerformanceText" style="white-space:pre-wrap;margin:7px 0 0;color:#86aab8;font:8px/1.45 Consolas,monospace">Diagnostics waiting…</pre>';
    host.appendChild(details);
    return details;
  }

  async function refreshPerformanceDiagnostics() {
    const details = ensurePerformanceDiagnostics();
    if (!details) return;
    const text = $("v17PerformanceText");
    const browser = window.JARVIS_V17_DATA_PLANE?.snapshot?.() || {};
    let server = {};
    try {
      const response = await upstreamFetch("/api/v17/diagnostics/performance", {
        cache: "no-store",
        jarvisPriority: 4,
        jarvisScope: "diagnostics",
      });
      if (response.ok) server = await response.json();
    } catch {}
    if (!text) return;
    const marketCache = server?.server?.market_cache || {};
    const stream = server?.server?.fyers_stream || {};
    text.textContent = [
      `workspace       ${browser.workspace || "—"} · generation ${browser.generation ?? "—"}`,
      `active jobs     live ${browser.active?.live ?? 0} · history ${browser.active?.history ?? 0} · module ${browser.active?.module ?? 0}`,
      `queued jobs     live ${browser.queued?.live ?? 0} · history ${browser.queued?.history ?? 0} · module ${browser.queued?.module ?? 0}`,
      `browser cache   hits ${browser.metrics?.cacheHits ?? 0} · single-flight ${browser.metrics?.singleFlightHits ?? 0}`,
      `superseded      ${browser.metrics?.superseded ?? 0} · slow ${browser.metrics?.slowRequests ?? 0}`,
      `server history  entries ${marketCache.entries ?? "—"} · pending ${marketCache.pending ?? "—"} · provider loads ${marketCache.provider_loads ?? "—"}`,
      `FYERS stream    ${stream.connected ? "CONNECTED" : stream.running ? "RECONNECTING" : "OFFLINE"} · snapshots ${stream.snapshots ?? "—"}`,
      "Read-only diagnostics · PAPER safety and execution authority unchanged.",
    ].join("\n");
  }

  function renderStatus(status) {
    const pill = $("v17RuntimePill");
    if (pill) {
      pill.dataset.state = "ok";
      setText(pill, "V17 · ACTIVE");
      pill.title = `${status.service || "JARVIS V17"} · ${status.decision_source || "VERIFIED DATA"}`;
    }
    const route = status.route || {};
    const requested = String(route.requested_workspace || status.workspace || activeWorkspace()).toUpperCase();
    const execution = String(route.execution_workspace || status.execution_workspace || requested).toUpperCase();
    const feedState = normalizeFeedState(status);
    const feed = status?.market_data?.stream || {};
    setText($("v17RouteState"), requested);
    const feedNode = $("v17FeedState");
    if (feedNode) {
      feedNode.dataset.state = feedState.toLowerCase();
      setText(feedNode, `FYERS · ${feedState}`);
      const retry = Number(feed.retry_in_seconds);
      feedNode.title = Number.isFinite(retry) && retry > 0 ? `Read-only market data · reconnect in ~${retry.toFixed(1)}s` : "Read-only FYERS market-data WebSocket · broker orders disabled";
    }
    const summary = $("v17RuntimeSummary");
    if (summary) {
      const underlyings = Array.isArray(status.verified_auto_option_underlyings) ? status.verified_auto_option_underlyings.join(" / ") : "NIFTY / BANKNIFTY / SENSEX";
      const routeText = requested === execution ? requested : `${requested} → ${execution} execution`;
      const feedText = feedState === "CONNECTED" ? "FYERS stream fresh" : feedState === "STALE" ? "FYERS stream stale — new entries fail closed" : `FYERS stream ${feedState.toLowerCase()}`;
      const controlText = status?.control_plane?.armed
        ? `ARMED · ${String(status.control_plane.last_action || "IN SYNC").replaceAll("_"," ")}`
        : "DISARMED";
      setText(summary, `${routeText} · ${feedText} · ${controlText}. Verified PAPER options: ${underlyings}. Adaptive evidence decides; hard safety gates remain authoritative.`);
    }
    setText($("v17RuntimeMode"), status.live_execution ? "LIVE" : "PAPER ONLY");
    const armed = Boolean(status?.control_plane?.armed ?? status?.autopilot_preferences?.armed);
    const armedNode = $("v17ArmedState");
    if (armedNode) {
      armedNode.dataset.state = armed ? "connected" : "paused";
      setText(armedNode, armed ? "ARMED · AUTO-RESUME" : "DISARMED");
      armedNode.title = armed
        ? "Explicit PAPER intent is durable across terminal restarts. Session and safety gates still decide whether each lane can enter."
        : "New PAPER entries stay paused across restarts until START JARVIS is pressed.";
    }
    if (status.autopilot_preferences) {
      latestPreferences = status.autopilot_preferences;
      const input = $("v17OptionsCapital");
      if (input && document.activeElement !== input) input.value = String(Math.round(Number(latestPreferences.options_capital_fraction || 0.5) * 100));
      applyChartPreference();
    }
    window.JARVIS_V17_STATUS = status;
    window.dispatchEvent(new CustomEvent("jarvis:v17-status",{detail:status}));
    relabelInheritedLineage();
  }

  function renderFailure(error) {
    const pill = $("v17RuntimePill");
    if (pill) {
      pill.dataset.state = "error";
      setText(pill, "V17 · STATUS ERROR");
      pill.title = String(error?.message || error || "V17 status unavailable");
    }
    const feedNode = $("v17FeedState");
    if (feedNode) {
      feedNode.dataset.state = "unavailable";
      setText(feedNode, "FYERS · UNKNOWN");
    }
    setText($("v17RuntimeSummary"), "V17 shell loaded, but runtime status is unavailable. New trading remains fail-closed.");
  }

  async function refresh() {
    try { renderStatus(await readStatus()); }
    catch (error) { renderFailure(error); }
  }

  function boot() {
    ensureStyle();
    brandStaticSurface();
    relabelInheritedLineage();
    ensureChainEvidenceMode();
    bindControls();
    readPreferences().catch(error => setAutopilotMessage(`Preferences unavailable: ${error.message}`, "warn"));
    refresh();
    refreshPerformanceDiagnostics();
    setInterval(refresh, 15000);
    setInterval(refreshPerformanceDiagnostics, 30000);
    const observer = new MutationObserver(() => {
      relabelInheritedLineage();
      ensureChainEvidenceMode();
      applyChartPreference();
    });
    observer.observe(document.body, {subtree: true, childList: true, characterData: true});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, {once: true});
  else boot();
})();
