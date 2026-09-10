(() => {
  "use strict";

  const STORAGE_KEY = "jarvis.quant.layout.v16";
  const VALID_LAYOUTS = new Set([1, 2, 3, 4, 5, 6, 7, 8]);

  function parseLayout(value) {
    const number = Number(value);
    return Number.isInteger(number) && VALID_LAYOUTS.has(number) ? number : null;
  }

  function preferredColumns(count) {
    if (count <= 1) return 1;
    if (count === 2) return 2;
    if (count === 3) return 3;
    if (count === 4) return 2;
    if (count <= 6) return 3;
    return 4;
  }

  function applyGridGeometry() {
    const host = document.getElementById("chartGrid");
    if (!host || typeof layout === "undefined") return;

    const count = parseLayout(layout) || 1;
    let columns = preferredColumns(count);
    const width = host.getBoundingClientRect().width;

    if (width > 0 && width < 760) columns = Math.min(columns, 2);
    const rows = Math.ceil(count / columns);

    host.style.gridTemplateColumns = `repeat(${columns}, minmax(0, 1fr))`;
    host.style.gridTemplateRows = `repeat(${rows}, minmax(0, 1fr))`;
    host.dataset.expectedCharts = String(count);

    const cells = Array.from(host.querySelectorAll(":scope > .chart-cell"));
    if (cells.length > count) {
      cells.slice(count).forEach((cell) => cell.remove());
    }
    host.dataset.renderedCharts = String(
      host.querySelectorAll(":scope > .chart-cell").length
    );
  }

  function persistLayout(value) {
    const count = parseLayout(value);
    if (!count) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, String(count));
    } catch {
      // Local storage is optional; layout still works for this session.
    }
  }

  function savedLayout() {
    try {
      return parseLayout(window.localStorage.getItem(STORAGE_KEY));
    } catch {
      return null;
    }
  }

  function bindPersistence() {
    document.querySelectorAll("[data-layout]").forEach((button) => {
      if (button.dataset.v16LayoutBound === "1") return;
      button.dataset.v16LayoutBound = "1";
      button.addEventListener("click", () => {
        const count = parseLayout(button.dataset.layout);
        if (!count) return;
        persistLayout(count);
        window.requestAnimationFrame(applyGridGeometry);
      });
    });
  }

  function restoreSavedLayout() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("analyze") === "1") {
      applyGridGeometry();
      return;
    }
    const saved = savedLayout();
    if (!saved || typeof layout === "undefined" || saved === layout) {
      applyGridGeometry();
      return;
    }

    layout = saved;
    if (typeof selectedSlot !== "undefined" && selectedSlot >= layout) {
      selectedSlot = 0;
    }
    if (typeof syncControls === "function") syncControls();
    if (typeof mountCharts === "function") {
      Promise.resolve(mountCharts()).finally(applyGridGeometry);
    } else {
      applyGridGeometry();
    }
  }

  const grid = document.getElementById("chartGrid");
  if (grid) {
    const observer = new MutationObserver(applyGridGeometry);
    observer.observe(grid, {
      attributes: true,
      attributeFilter: ["class"],
      childList: true,
    });
    window.addEventListener("resize", applyGridGeometry);
  }

  bindPersistence();
  applyGridGeometry();

  if (document.readyState === "complete") {
    window.setTimeout(restoreSavedLayout, 250);
  } else {
    window.addEventListener(
      "load",
      () => window.setTimeout(restoreSavedLayout, 250),
      { once: true }
    );
  }
})();
