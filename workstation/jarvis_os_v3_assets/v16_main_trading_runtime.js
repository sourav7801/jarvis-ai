/* JARVIS V16 main-workstation trading enhancement.
 *
 * This file is appended to the protected Master app.js response by the V16
 * bridge. Because it executes in the same classic-script lexical scope, it
 * upgrades the existing chartSlots/setChartCount/renderChartSlots bindings
 * without forking the JARVIS desktop or creating a second UI architecture.
 *
 * Port 8787 remains internal. Browser traffic uses same-origin V16 Master
 * proxy endpoints only. Live broker execution is never exposed here.
 */

const V16_CHART_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "GOLD",
    "SILVER",
    "BTC",
    "ETH",
    "SOL",
    "NATURALGAS"
];

const V16_CHART_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];
const V16_LAYOUT_STORAGE = "jarvis.v16.main.chart.count";
const V16_CHART_CACHE = new Map();
let v16SelectedChartSlot = 0;
let v16ProviderLabel = "WAITING";
let v16TradingHealthBusy = false;

function v16LayoutColumns(count) {
    if (count <= 1) return 1;
    if (count === 2) return 2;
    if (count === 3) return 3;
    if (count === 4) return 2;
    if (count <= 6) return 3;
    return 4;
}

function v16NormalizeChartCount(value) {
    const count = Number(value);
    return Number.isInteger(count) && count >= 1 && count <= 8 ? count : 1;
}

function v16DefaultSlot(index) {
    const symbol = V16_CHART_SYMBOLS[index % V16_CHART_SYMBOLS.length];
    return {symbol, timeframe: selectedTimeframe || "15m"};
}

function v16SetGridGeometry() {
    const grid = document.getElementById("chartGrid");
    if (!grid) return;
    const count = Math.max(1, chartSlots.length);
    let columns = v16LayoutColumns(count);
    if (grid.clientWidth > 0 && grid.clientWidth < 760) {
        columns = Math.min(columns, 2);
    }
    const rows = Math.ceil(count / columns);
    grid.className = "v16ChartGrid";
    grid.style.gridTemplateColumns = `repeat(${columns}, minmax(0, 1fr))`;
    grid.style.gridTemplateRows = `repeat(${rows}, minmax(0, 1fr))`;
    grid.dataset.chartCount = String(count);
}

function v16FetchJson(path) {
    return fetch(path, {cache: "no-store"}).then(async response => {
        const payload = await response.json();
        if (!response.ok || payload.success === false) {
            throw new Error(payload.message || payload.reason || `HTTP ${response.status}`);
        }
        return payload;
    });
}

async function v16FetchChart(symbol, timeframe) {
    const key = `${symbol}|${timeframe}`;
    const cached = V16_CHART_CACHE.get(key);
    const now = Date.now();
    if (cached && now - cached.at < 9000) return cached.payload;

    const endpoint = "/api/v16/trading/chart?symbol="
        + encodeURIComponent(symbol)
        + "&timeframe="
        + encodeURIComponent(timeframe);

    // The professional runtime intentionally returns PENDING while its bounded
    // analysis worker owns the first provider request. Poll the same job rather
    // than issuing parallel provider reads.
    for (let attempt = 0; attempt < 24; attempt++) {
        const envelope = await v16FetchJson(endpoint);
        if (!envelope.pending) {
            const payload = envelope.result || envelope;
            if (!payload || payload.success === false || !((payload.candles || payload.bars || []).length)) {
                throw new Error(payload?.message || payload?.reason || "Verified candles unavailable");
            }
            V16_CHART_CACHE.set(key, {at: Date.now(), payload});
            return payload;
        }
        await new Promise(resolve => setTimeout(resolve, 180 + Math.min(attempt * 20, 220)));
    }
    throw new Error("Chart worker is still busy; retrying on the next refresh cycle");
}

function v16SyncPrimaryControls(slot, index) {
    if (index !== v16SelectedChartSlot) return;
    const selector = document.getElementById("chartSymbol");
    if (selector && [...selector.options].some(option => option.value === slot.symbol || option.textContent.trim() === slot.symbol)) {
        selector.value = slot.symbol;
    }
    selectedTimeframe = slot.timeframe;
    document.querySelectorAll("[data-timeframe]").forEach(button => {
        button.classList.toggle("selected", button.dataset.timeframe === selectedTimeframe);
    });
}

function v16ChartPane(slot, index) {
    const pane = document.createElement("div");
    pane.className = "chartPane v16ChartPane" + (index === v16SelectedChartSlot ? " selected" : "");
    pane.dataset.slot = String(index);

    const head = document.createElement("div");
    head.className = "v16ChartPaneHead";

    const symbol = document.createElement("select");
    symbol.className = "v16ChartSymbol";
    const symbols = V16_CHART_SYMBOLS.includes(slot.symbol) ? V16_CHART_SYMBOLS : [slot.symbol, ...V16_CHART_SYMBOLS];
    symbols.forEach(name => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        if (name === slot.symbol) option.selected = true;
        symbol.appendChild(option);
    });

    const timeframe = document.createElement("select");
    timeframe.className = "v16ChartTimeframe";
    V16_CHART_TIMEFRAMES.forEach(name => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        if (name === slot.timeframe) option.selected = true;
        timeframe.appendChild(option);
    });

    const provider = document.createElement("span");
    provider.className = "v16ChartProvider";
    provider.textContent = "VERIFIED DATA";
    head.append(symbol, timeframe, provider);

    const canvas = document.createElement("canvas");
    canvas.className = "chartCanvas";
    canvas.id = "chartCanvas" + index;

    const status = document.createElement("div");
    status.className = "chartStatus";
    status.id = "chartStatus" + index;
    status.textContent = `${slot.symbol} · ${slot.timeframe} · QUEUED`;

    pane.append(head, canvas, status);

    pane.addEventListener("mousedown", () => {
        v16SelectedChartSlot = index;
        document.querySelectorAll(".v16ChartPane").forEach(node => node.classList.toggle("selected", Number(node.dataset.slot) === index));
        v16SyncPrimaryControls(chartSlots[index], index);
    });

    symbol.addEventListener("change", event => {
        event.stopPropagation();
        const oldKey = `${chartSlots[index].symbol}|${chartSlots[index].timeframe}`;
        chartSlots[index] = {...chartSlots[index], symbol: symbol.value};
        V16_CHART_CACHE.delete(oldKey);
        v16SyncPrimaryControls(chartSlots[index], index);
        persistWorkspace();
        v16LoadChart(index, true);
    });

    timeframe.addEventListener("change", event => {
        event.stopPropagation();
        const oldKey = `${chartSlots[index].symbol}|${chartSlots[index].timeframe}`;
        chartSlots[index] = {...chartSlots[index], timeframe: timeframe.value};
        V16_CHART_CACHE.delete(oldKey);
        v16SyncPrimaryControls(chartSlots[index], index);
        persistWorkspace();
        v16LoadChart(index, true);
    });

    return pane;
}

async function v16LoadChart(index, force = false) {
    const slot = chartSlots[index];
    if (!slot) return;
    const status = document.getElementById("chartStatus" + index);
    const pane = status?.closest(".v16ChartPane");
    const provider = pane?.querySelector(".v16ChartProvider");
    if (status) status.textContent = `${slot.symbol} · ${slot.timeframe} · LOADING`;

    try {
        if (force) V16_CHART_CACHE.delete(`${slot.symbol}|${slot.timeframe}`);
        const payload = await v16FetchChart(slot.symbol, slot.timeframe);
        const bars = payload.candles || payload.bars || [];
        const canvas = document.getElementById("chartCanvas" + index);
        if (!canvas || chartSlots[index] !== slot) return;
        drawCandles(canvas, bars);

        const quote = payload.quote || {};
        const verified = quote.verified === true || quote.eligible_for_exit === true || payload.verified === true;
        const source = quote.provider || quote.source || payload.provider || "VERIFIED";
        v16ProviderLabel = verified ? source : (quote.reason || payload.message || "DEGRADED");
        if (provider) {
            provider.textContent = verified ? `${source} · LIVE` : "DATA CHECK";
            provider.classList.toggle("degraded", !verified);
        }
        if (status) {
            const suffix = verified ? "LIVE" : (quote.reason || "HISTORY VERIFIED");
            status.textContent = `${slot.symbol} · ${slot.timeframe} · ${suffix}`;
        }

        if (index === v16SelectedChartSlot) {
            const title = document.getElementById("chartTitle");
            const providerLabel = document.getElementById("chartProvider");
            const price = document.getElementById("chartPrice");
            if (title) title.textContent = `${slot.symbol} · ${slot.timeframe}`;
            if (providerLabel) providerLabel.textContent = verified ? `VERIFIED · ${source}` : "VERIFIED HISTORY · LIVE MARK BLOCKED";
            if (price) {
                const last = bars.at(-1);
                price.textContent = last ? Number(last.close).toLocaleString("en-IN", {maximumFractionDigits: 2}) : "—";
            }
        }
        v16RenderHealthStrip();
    } catch (error) {
        if (status) status.textContent = `${slot.symbol} · ${slot.timeframe} · ${error.message}`;
        if (provider) {
            provider.textContent = "UNAVAILABLE";
            provider.classList.add("degraded");
        }
    }
}

// Replace the V15 1/2/4 clamp with exact persistent 1..8 layouts.
setChartCount = function(count) {
    count = v16NormalizeChartCount(count);
    while (chartSlots.length < count) chartSlots.push(v16DefaultSlot(chartSlots.length));
    chartSlots = chartSlots.slice(0, count);
    if (v16SelectedChartSlot >= count) v16SelectedChartSlot = count - 1;
    try { localStorage.setItem(V16_LAYOUT_STORAGE, String(count)); } catch (_) {}
    renderChartSlots();
};

renderChartSlots = function() {
    const grid = document.getElementById("chartGrid");
    if (!grid) return;
    grid.replaceChildren();
    v16SetGridGeometry();
    chartSlots.forEach((slot, index) => {
        grid.appendChild(v16ChartPane(slot, index));
        // Stagger initial reads. Eight panes never hit the provider at once.
        window.setTimeout(() => v16LoadChart(index), index * 140);
    });
    persistWorkspace();
    v16UpdateLayoutButtons();
};

loadChart = function(index) {
    return v16LoadChart(index, true);
};

function v16UpdateLayoutButtons() {
    document.querySelectorAll("[data-v16-chart-count]").forEach(button => {
        button.classList.toggle("selected", Number(button.dataset.v16ChartCount) === chartSlots.length);
    });
    const count = document.getElementById("v16ChartCount");
    if (count) count.textContent = `${chartSlots.length} CHART${chartSlots.length === 1 ? "" : "S"}`;
}

function v16InstallLayoutControls() {
    const toolbar = document.querySelector("#win-chart .chartToolbar");
    if (!toolbar || document.getElementById("v16LayoutControls")) return;
    const group = document.createElement("div");
    group.id = "v16LayoutControls";
    group.className = "v16LayoutControls";
    const label = document.createElement("span");
    label.id = "v16ChartCount";
    label.textContent = "1 CHART";
    group.appendChild(label);
    for (let count = 1; count <= 8; count++) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.v16ChartCount = String(count);
        button.textContent = String(count);
        button.title = `Show exactly ${count} chart${count === 1 ? "" : "s"}`;
        button.addEventListener("click", event => {
            event.preventDefault();
            setChartCount(count);
        });
        group.appendChild(button);
    }
    toolbar.appendChild(group);
}

function v16RewireMainNavigation() {
    const buttons = [...document.querySelectorAll("#topbar nav button")];
    const find = label => buttons.find(button => button.textContent.trim().toUpperCase() === label);
    const bind = (label, action) => {
        const button = find(label);
        if (!button) return;
        button.removeAttribute("onclick");
        button.onclick = null;
        button.addEventListener("click", event => {
            event.preventDefault();
            action();
        });
    };

    bind("TRADING INTELLIGENCE", () => applyLayout("trading"));
    bind("CHART TERMINAL", () => {
        maximizeWindow("chart");
        window.setTimeout(() => {
            v16SetGridGeometry();
            chartSlots.forEach((_, index) => v16LoadChart(index));
        }, 80);
    });
    bind("QUANT", () => {
        openWindow("quant");
        focusWindow(document.getElementById("win-quant"));
    });
}

function v16RenderHealthStrip(extra = {}) {
    let strip = document.getElementById("v16TradingHealth");
    const top = document.querySelector("#topbar .topStatus");
    if (!top) return;
    if (!strip) {
        strip = document.createElement("div");
        strip.id = "v16TradingHealth";
        strip.className = "v16TradingHealth";
        top.prepend(strip);
    }
    const service = extra.service || strip.dataset.service || "CHECKING";
    const paper = extra.paper_only !== false;
    const liveLocked = extra.live_execution !== true;
    strip.dataset.service = service;
    strip.innerHTML = [
        `<span class="${service === "READY" ? "ok" : service === "CHECKING" ? "wait" : "bad"}">TRADING ${service}</span>`,
        `<span class="ok">PAPER ${paper ? "ONLY" : "CHECK"}</span>`,
        `<span class="${liveLocked ? "ok" : "bad"}">LIVE ${liveLocked ? "LOCKED" : "UNSAFE"}</span>`,
        `<span class="wait">${chartSlots.length}/8 CHARTS</span>`,
        `<span class="wait" title="Latest visible chart provider">${String(v16ProviderLabel).slice(0, 24)}</span>`
    ].join("");
}

async function v16RefreshTradingHealth() {
    if (v16TradingHealthBusy) return;
    v16TradingHealthBusy = true;
    try {
        const health = await v16FetchJson("/api/v16/trading/health");
        v16RenderHealthStrip({
            service: health.service === "JARVIS_PROFESSIONAL_PAPER_TERMINAL" ? "READY" : "DEGRADED",
            paper_only: health.paper_only,
            live_execution: health.live_execution
        });
    } catch (_) {
        v16RenderHealthStrip({service: "OFFLINE", paper_only: true, live_execution: false});
    } finally {
        v16TradingHealthBusy = false;
    }
}

function v16RefreshVisibleCharts() {
    if (document.hidden) return;
    const chartWindow = document.getElementById("win-chart");
    if (!chartWindow || chartWindow.style.display === "none") return;
    chartSlots.forEach((_, index) => {
        window.setTimeout(() => v16LoadChart(index), index * 100);
    });
}

function v16InstallMainTradingRuntime() {
    v16RewireMainNavigation();
    v16InstallLayoutControls();
    let preferred = chartSlots.length;
    try {
        const saved = Number(localStorage.getItem(V16_LAYOUT_STORAGE));
        if (Number.isInteger(saved) && saved >= 1 && saved <= 8) preferred = saved;
    } catch (_) {}
    setChartCount(preferred);
    v16RenderHealthStrip({service: "CHECKING", paper_only: true, live_execution: false});
    v16RefreshTradingHealth();
    window.setInterval(v16RefreshTradingHealth, 5000);
    window.setInterval(v16RefreshVisibleCharts, 15000);
    window.addEventListener("resize", () => {
        v16SetGridGeometry();
        chartSlots.forEach((_, index) => {
            const cached = V16_CHART_CACHE.get(`${chartSlots[index].symbol}|${chartSlots[index].timeframe}`);
            if (cached) {
                const canvas = document.getElementById("chartCanvas" + index);
                if (canvas) drawCandles(canvas, cached.payload.candles || cached.payload.bars || []);
            }
        });
    });
}

v16InstallMainTradingRuntime();
