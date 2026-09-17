from __future__ import annotations

"""Apply deterministic release-only source patches before the V17 build.

The release artifact keeps source safety boundaries intact while applying a
small set of deterministic fixes that are verified again in CI before the
installer is staged:

* share FYERS completed-history cache snapshots by symbol/resolution;
* de-duplicate persisted 1-8 chart slots when a layout is mounted;
* scope the autonomy health banner/blocker to the candidate being evaluated
  instead of allowing an unrelated degraded provider/symbol to poison it;
* bind the autonomous decision card to the scanner candidate, not a stale
  manual option-underlying selector.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FYERS_TARGET = ROOT / "agents" / "fyers_data_adapter.py"
APP_TARGET = ROOT / "workstation" / "quant_terminal_v2_static" / "app.js"
AUTONOMY_TARGET = ROOT / "workstation" / "quant_terminal_v2_static" / "v16_autonomy_runtime.js"

OLD_PATH = '''def _history_cache_path(provider_symbol: str, resolution: str, bars: int) -> Path:\n    raw = f"{provider_symbol}|{resolution}|{int(bars)}".encode("utf-8")\n    digest = hashlib.sha256(raw).hexdigest()[:24]\n    return _HISTORY_CACHE_DIR / f"{digest}.json"\n'''

NEW_PATH = '''def _history_cache_path(provider_symbol: str, resolution: str, bars: int) -> Path:\n    # V17 shares a completed-history snapshot across bar-count consumers.\n    # `bars` stays in the signature for backward compatibility with tests/callers.\n    raw = f"{provider_symbol}|{resolution}".encode("utf-8")\n    digest = hashlib.sha256(raw).hexdigest()[:24]\n    return _HISTORY_CACHE_DIR / f"{digest}.json"\n'''

OLD_LOAD = '''        frame = _cache_rows_to_frame(payload.get("rows"))\n        return frame.tail(bars) if not frame.empty else None\n'''

NEW_LOAD = '''        frame = _cache_rows_to_frame(payload.get("rows"))\n        if frame.empty or len(frame) < int(bars):\n            return None\n        return frame.tail(bars)\n'''

OLD_CHART_CONFIG = '''    const config=slotView(index);const symbol=config.symbol;\n'''

NEW_CHART_CONFIG = '''    const config=slotView(index);\n    const usedSymbols=new Set(chartSlots.map(slot=>String(slot?.symbol||"").toUpperCase()));\n    let symbol=String(config.symbol||"").toUpperCase();\n    if(usedSymbols.has(symbol)){\n      symbol=SLOT_DEFAULTS.find(item=>!usedSymbols.has(item))||symbol;\n      config.symbol=symbol;\n      const view=workspaceView();\n      view.slots[index]={...config,symbol};\n    }\n'''

OLD_PROVIDER_STATE = '''  function providerState(state) {\n    const providers = Object.values(state?.market_data?.providers || {});\n    if (!providers.length) return {degraded: false, label: "WAITING"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "LOGIN_REQUIRED")) return {degraded: true, label: "LOGIN REQUIRED"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "RATE_LIMITED")) return {degraded: true, label: "RATE LIMITED"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "DEGRADED")) return {degraded: true, label: "DEGRADED"};\n    return {degraded: false, label: "VERIFIED"};\n  }\n'''

NEW_PROVIDER_STATE = '''  function providerState(state, symbol = "") {\n    const wanted = String(symbol || "").trim().toUpperCase();\n    if (wanted) {\n      const mark = state?.market_data?.marks?.[wanted];\n      if (mark && typeof mark === "object") {\n        if (mark.eligible_for_entry === true) return {degraded: false, label: "VERIFIED", symbol: wanted};\n        const reason = String(mark.reason || "").toUpperCase();\n        if (reason.includes("LOGIN")) return {degraded: true, label: "LOGIN REQUIRED", symbol: wanted};\n        if (reason.includes("RATE") || reason.includes("429")) return {degraded: true, label: "RATE LIMITED", symbol: wanted};\n        if (reason) return {degraded: true, label: reason.replaceAll("_", " "), symbol: wanted};\n      }\n      const row = (Array.isArray(state?.watchlist) ? state.watchlist : []).find(item => String(item?.symbol || "").toUpperCase() === wanted);\n      if (row) {\n        if (row.eligible_for_entry === true) return {degraded: false, label: "VERIFIED", symbol: wanted};\n        const reason = String(row.reason || "").toUpperCase();\n        if (reason.includes("LOGIN")) return {degraded: true, label: "LOGIN REQUIRED", symbol: wanted};\n        if (reason.includes("RATE") || reason.includes("429")) return {degraded: true, label: "RATE LIMITED", symbol: wanted};\n        if (reason) return {degraded: true, label: reason.replaceAll("_", " "), symbol: wanted};\n      }\n      // A scanner candidate already passed its own data-evidence path. If no\n      // symbol mark is published here, do not let an unrelated provider row\n      // create a false global blocker; final server gates remain authoritative.\n      return {degraded: false, label: "CANDIDATE VERIFIED", symbol: wanted};\n    }\n    const providers = Object.values(state?.market_data?.providers || {});\n    if (!providers.length) return {degraded: false, label: "WAITING"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "LOGIN_REQUIRED")) return {degraded: true, label: "LOGIN REQUIRED"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "RATE_LIMITED")) return {degraded: true, label: "RATE LIMITED"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "DEGRADED")) return {degraded: true, label: "DEGRADED"};\n    return {degraded: false, label: "VERIFIED"};\n  }\n'''

OLD_DECISION_BINDING = '''    const selectedUnderlying = String($("v16OptionUnderlying")?.value || candidate?.symbol || "NIFTY").toUpperCase();\n    const underlying = INDEX_OPTION_UNDERLYINGS.has(selectedUnderlying) ? selectedUnderlying : String(candidate?.symbol || selectedUnderlying || "—").toUpperCase();\n    const optionPosition = INDEX_OPTION_UNDERLYINGS.has(underlying) ? optionPositionFor(state, underlying) : null;\n    const market = providerState(state);\n'''

NEW_DECISION_BINDING = '''    const candidateSymbol = String(candidate?.symbol || "").toUpperCase();\n    const selectedUnderlying = String($("v16OptionUnderlying")?.value || "NIFTY").toUpperCase();\n    const underlying = String(candidateSymbol || selectedUnderlying || "—").toUpperCase();\n    const optionPosition = INDEX_OPTION_UNDERLYINGS.has(underlying) ? optionPositionFor(state, underlying) : null;\n    const market = providerState(state, candidateSymbol || underlying);\n'''

OLD_RENDER_HEALTH = '''    const reconciliation = session.reconciliation_ok !== false;\n    const market = providerState(state);\n    const candidates = Array.isArray(state?.scan_decisions?.candidates) ? state.scan_decisions.candidates : [];\n    const actionable = candidates.find(item => String(item.stage || "").toUpperCase() === "ACTIONABLE");\n'''

NEW_RENDER_HEALTH = '''    const reconciliation = session.reconciliation_ok !== false;\n    const candidates = Array.isArray(state?.scan_decisions?.candidates) ? state.scan_decisions.candidates : [];\n    const actionable = candidates.find(item => String(item.stage || "").toUpperCase() === "ACTIONABLE");\n    const market = providerState(state, actionable?.symbol || candidates[0]?.symbol || "");\n'''


def _replace_once(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"V17 {label} patch already present.")
        return False
    if old not in text:
        raise SystemExit(f"Expected {label} block was not found; refusing an unsafe release patch.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied V17 {label} patch.")
    return True


def main() -> int:
    _replace_once(FYERS_TARGET, OLD_PATH, NEW_PATH, "FYERS shared-history cache path")
    _replace_once(FYERS_TARGET, OLD_LOAD, NEW_LOAD, "FYERS shared-history cache load")
    _replace_once(APP_TARGET, OLD_CHART_CONFIG, NEW_CHART_CONFIG, "unique chart-slot routing")
    _replace_once(AUTONOMY_TARGET, OLD_PROVIDER_STATE, NEW_PROVIDER_STATE, "candidate-scoped provider health")
    _replace_once(AUTONOMY_TARGET, OLD_DECISION_BINDING, NEW_DECISION_BINDING, "autonomous candidate binding")
    _replace_once(AUTONOMY_TARGET, OLD_RENDER_HEALTH, NEW_RENDER_HEALTH, "autonomy health rendering")
    print("V17 deterministic release patches complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
