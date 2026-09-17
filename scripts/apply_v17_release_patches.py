from __future__ import annotations

"""Apply deterministic V17 runtime patches for both direct pulls and releases.

This patcher is intentionally idempotent.  A normal GitHub pull followed by the
V17 launcher applies the same guarded source state that CI/release builds use.
It never enables live broker execution or alters the PAPER safety boundary.

Patches:
* share FYERS history snapshots by symbol/resolution, not requested bar count;
* prefetch one bounded canonical history snapshot for competing consumers;
* slow the shared REST governor and use escalating cooldown after provider 429s;
* add a cross-process FYERS quote cache so separate JARVIS services reuse quotes;
* de-duplicate persisted 1-8 chart slots;
* scope UI provider health to the candidate being evaluated;
* bind the decision card to the scanner candidate.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FYERS_TARGET = ROOT / "agents" / "fyers_data_adapter.py"
APP_TARGET = ROOT / "workstation" / "quant_terminal_v2_static" / "app.js"
AUTONOMY_TARGET = ROOT / "workstation" / "quant_terminal_v2_static" / "v16_autonomy_runtime.js"

OLD_GOVERNOR_CONSTANTS = '''_HISTORY_CACHE_DIR = _GOVERNOR_DIR / "history_cache"\n_MIN_REQUEST_INTERVAL_SECONDS = 1.05\n_RATE_LIMIT_COOLDOWN_SECONDS = 65.0\n_LOCK_STALE_SECONDS = 30.0\n'''

NEW_GOVERNOR_CONSTANTS = '''_HISTORY_CACHE_DIR = _GOVERNOR_DIR / "history_cache"\n_QUOTE_CACHE_DIR = _GOVERNOR_DIR / "quote_cache"\n_MIN_REQUEST_INTERVAL_SECONDS = 1.50\n_RATE_LIMIT_COOLDOWN_SECONDS = 180.0\n_LOCK_STALE_SECONDS = 30.0\n_CANONICAL_HISTORY_BARS = 800\n_QUOTE_CACHE_TTL_SECONDS = 8.0\n'''

OLD_ENSURE_DIRS = '''def _ensure_governor_dirs() -> None:\n    _HISTORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)\n'''

NEW_ENSURE_DIRS = '''def _ensure_governor_dirs() -> None:\n    _HISTORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)\n    _QUOTE_CACHE_DIR.mkdir(parents=True, exist_ok=True)\n'''

OLD_COOLDOWN = '''        if details.get("provider_code") == 429:\n            state["cooldown_until_epoch"] = finished + _RATE_LIMIT_COOLDOWN_SECONDS\n        elif float(state.get("cooldown_until_epoch") or 0.0) <= finished:\n            state["cooldown_until_epoch"] = 0.0\n'''

NEW_COOLDOWN = '''        if details.get("provider_code") == 429:\n            strikes = min(int(state.get("rate_limit_strikes") or 0) + 1, 4)\n            state["rate_limit_strikes"] = strikes\n            cooldown = min(900.0, _RATE_LIMIT_COOLDOWN_SECONDS * (2 ** (strikes - 1)))\n            state["cooldown_until_epoch"] = finished + cooldown\n        elif float(state.get("cooldown_until_epoch") or 0.0) <= finished:\n            state["cooldown_until_epoch"] = 0.0\n            state["rate_limit_strikes"] = 0\n'''

OLD_PATH = '''def _history_cache_path(provider_symbol: str, resolution: str, bars: int) -> Path:\n    raw = f"{provider_symbol}|{resolution}|{int(bars)}".encode("utf-8")\n    digest = hashlib.sha256(raw).hexdigest()[:24]\n    return _HISTORY_CACHE_DIR / f"{digest}.json"\n'''

NEW_PATH = '''def _history_cache_path(provider_symbol: str, resolution: str, bars: int) -> Path:\n    # Share one completed-history snapshot across all bar-count consumers.\n    # `bars` stays in the signature for backward compatibility.\n    raw = f"{provider_symbol}|{resolution}".encode("utf-8")\n    digest = hashlib.sha256(raw).hexdigest()[:24]\n    return _HISTORY_CACHE_DIR / f"{digest}.json"\n'''

OLD_LOAD = '''        frame = _cache_rows_to_frame(payload.get("rows"))\n        return frame.tail(bars) if not frame.empty else None\n'''

NEW_LOAD = '''        frame = _cache_rows_to_frame(payload.get("rows"))\n        if frame.empty or len(frame) < int(bars):\n            return None\n        return frame.tail(bars)\n'''

OLD_HISTORY_WINDOW = '''        fyers = client or create_client()\n        end = datetime.now(INDIA_TZ).date()\n        start = end - timedelta(days=_calendar_days_for_bars(bars, resolution))\n'''

NEW_HISTORY_WINDOW = '''        fyers = client or create_client()\n        snapshot_bars = max(int(bars), _CANONICAL_HISTORY_BARS)\n        end = datetime.now(INDIA_TZ).date()\n        start = end - timedelta(days=_calendar_days_for_bars(snapshot_bars, resolution))\n'''

OLD_HISTORY_FRAME = '''        frame = candles_to_frame(rows).tail(bars)\n        if frame.empty:\n'''

NEW_HISTORY_FRAME = '''        snapshot = candles_to_frame(rows).tail(snapshot_bars)\n        if snapshot.empty:\n'''

OLD_HISTORY_SAVE = '''        _save_history_cache(provider_symbol, resolution, bars, frame)\n        return {\n'''

NEW_HISTORY_SAVE = '''        _save_history_cache(provider_symbol, resolution, snapshot_bars, snapshot)\n        frame = snapshot.tail(int(bars))\n        return {\n'''

V1706_HISTORY_MARKERS = (
    "def _history_snapshot_bars(requested_bars: int) -> int:",
    "def _history_request_lock(provider_symbol: str, resolution: str, timeout_seconds: float = 45.0):",
    '"cache_identity": "provider_symbol+resolution"',
)

QUOTE_HELPERS = '''\n\ndef _quote_cache_path(provider_symbol: str) -> Path:\n    raw = str(provider_symbol or "").strip().upper().encode("utf-8")\n    digest = hashlib.sha256(raw).hexdigest()[:24]\n    return _QUOTE_CACHE_DIR / f"{digest}.json"\n\n\ndef _load_quote_cache(provider_symbol: str) -> dict[str, Any] | None:\n    try:\n        payload = json.loads(_quote_cache_path(provider_symbol).read_text(encoding="utf-8"))\n        age = time.time() - float(payload.get("saved_at_epoch") or 0.0)\n        quote = payload.get("quote")\n        if age < 0 or age > _QUOTE_CACHE_TTL_SECONDS or not isinstance(quote, dict):\n            return None\n        if not quote.get("success"):\n            return None\n        try:\n            if float(quote.get("ltp") or 0.0) <= 0:\n                return None\n        except (TypeError, ValueError):\n            return None\n        result = dict(quote)\n        result["provider_cache_hit"] = True\n        result["provider_cache_age_seconds"] = round(age, 3)\n        return result\n    except (OSError, TypeError, ValueError, json.JSONDecodeError):\n        return None\n\n\ndef _save_quote_cache(provider_symbol: str, quote: dict[str, Any]) -> None:\n    if not isinstance(quote, dict) or not quote.get("success"):\n        return\n    _write_json_atomic(\n        _quote_cache_path(provider_symbol),\n        {\n            "saved_at_epoch": time.time(),\n            "provider_symbol": provider_symbol,\n            "quote": quote,\n        },\n    )\n'''

QUOTE_HELPER_ANCHOR = '''\n\ndef get_quote(symbol: str, *, client: Any = None) -> dict[str, Any]:\n'''

OLD_QUOTE_START = '''        provider_symbol = normalize_symbol(symbol)\n        fyers = client or create_client()\n        response = _governed_provider_call(lambda: fyers.quotes(data={"symbols": provider_symbol}))\n'''

NEW_QUOTE_START = '''        provider_symbol = normalize_symbol(symbol)\n        cached = _load_quote_cache(provider_symbol)\n        if cached is not None:\n            cached["symbol"] = str(symbol or "").strip().upper()\n            cached["provider_symbol"] = provider_symbol\n            return cached\n        fyers = client or create_client()\n        response = _governed_provider_call(lambda: fyers.quotes(data={"symbols": provider_symbol}))\n'''

OLD_QUOTE_SUCCESS = '''        return {\n            "success": True,\n            "source": "FYERS",\n            "symbol": str(symbol).strip().upper(),\n            "provider_symbol": provider_symbol,\n            "provider_state": "READY",\n            "provider_code": 200,\n            "ltp": values.get("lp"),\n            "change": values.get("ch"),\n            "change_percent": values.get("chp"),\n            "open": values.get("open_price"),\n            "high": values.get("high_price"),\n            "low": values.get("low_price"),\n            "previous_close": values.get("prev_close_price"),\n            "volume": values.get("volume"),\n            "bid": values.get("bid"),\n            "ask": values.get("ask"),\n            "exchange_timestamp": values.get("tt"),\n        }\n'''

NEW_QUOTE_SUCCESS = '''        result = {\n            "success": True,\n            "source": "FYERS",\n            "symbol": str(symbol).strip().upper(),\n            "provider_symbol": provider_symbol,\n            "provider_state": "READY",\n            "provider_code": 200,\n            "provider_cache_hit": False,\n            "ltp": values.get("lp"),\n            "change": values.get("ch"),\n            "change_percent": values.get("chp"),\n            "open": values.get("open_price"),\n            "high": values.get("high_price"),\n            "low": values.get("low_price"),\n            "previous_close": values.get("prev_close_price"),\n            "volume": values.get("volume"),\n            "bid": values.get("bid"),\n            "ask": values.get("ask"),\n            "exchange_timestamp": values.get("tt"),\n        }\n        _save_quote_cache(provider_symbol, result)\n        return result\n'''

OLD_GOVERNOR_STATUS = '''        "last_provider_state": state.get("last_provider_state"),\n        "history_cache": True,\n'''

NEW_GOVERNOR_STATUS = '''        "last_provider_state": state.get("last_provider_state"),\n        "rate_limit_strikes": int(state.get("rate_limit_strikes") or 0),\n        "history_cache": True,\n        "quote_cache": True,\n        "canonical_history_bars": _CANONICAL_HISTORY_BARS,\n'''

OLD_CHART_CONFIG = '''    const config=slotView(index);const symbol=config.symbol;\n'''

NEW_CHART_CONFIG = '''    const config=slotView(index);\n    const usedSymbols=new Set(chartSlots.map(slot=>String(slot?.symbol||"").toUpperCase()));\n    let symbol=String(config.symbol||"").toUpperCase();\n    if(usedSymbols.has(symbol)){\n      symbol=SLOT_DEFAULTS.find(item=>!usedSymbols.has(item))||symbol;\n      config.symbol=symbol;\n      const view=workspaceView();\n      view.slots[index]={...config,symbol};\n    }\n'''

OLD_PROVIDER_STATE = '''  function providerState(state) {\n    const providers = Object.values(state?.market_data?.providers || {});\n    if (!providers.length) return {degraded: false, label: "WAITING"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "LOGIN_REQUIRED")) return {degraded: true, label: "LOGIN REQUIRED"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "RATE_LIMITED")) return {degraded: true, label: "RATE LIMITED"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "DEGRADED")) return {degraded: true, label: "DEGRADED"};\n    return {degraded: false, label: "VERIFIED"};\n  }\n'''

NEW_PROVIDER_STATE = '''  function providerState(state, symbol = "") {\n    const wanted = String(symbol || "").trim().toUpperCase();\n    if (wanted) {\n      const mark = state?.market_data?.marks?.[wanted];\n      if (mark && typeof mark === "object") {\n        if (mark.eligible_for_entry === true) return {degraded: false, label: "VERIFIED", symbol: wanted};\n        const reason = String(mark.reason || "").toUpperCase();\n        if (reason.includes("LOGIN")) return {degraded: true, label: "LOGIN REQUIRED", symbol: wanted};\n        if (reason.includes("RATE") || reason.includes("429")) return {degraded: true, label: "RATE LIMITED", symbol: wanted};\n        if (reason) return {degraded: true, label: reason.replaceAll("_", " "), symbol: wanted};\n      }\n      const row = (Array.isArray(state?.watchlist) ? state.watchlist : []).find(item => String(item?.symbol || "").toUpperCase() === wanted);\n      if (row) {\n        if (row.eligible_for_entry === true) return {degraded: false, label: "VERIFIED", symbol: wanted};\n        const reason = String(row.reason || "").toUpperCase();\n        if (reason.includes("LOGIN")) return {degraded: true, label: "LOGIN REQUIRED", symbol: wanted};\n        if (reason.includes("RATE") || reason.includes("429")) return {degraded: true, label: "RATE LIMITED", symbol: wanted};\n        if (reason) return {degraded: true, label: reason.replaceAll("_", " "), symbol: wanted};\n      }\n      return {degraded: false, label: "CANDIDATE VERIFIED", symbol: wanted};\n    }\n    const providers = Object.values(state?.market_data?.providers || {});\n    if (!providers.length) return {degraded: false, label: "WAITING"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "LOGIN_REQUIRED")) return {degraded: true, label: "LOGIN REQUIRED"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "RATE_LIMITED")) return {degraded: true, label: "RATE LIMITED"};\n    if (providers.some(item => String(item.state || "").toUpperCase() === "DEGRADED")) return {degraded: true, label: "DEGRADED"};\n    return {degraded: false, label: "VERIFIED"};\n  }\n'''

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
        raise SystemExit(f"Expected {label} block was not found; refusing an unsafe V17 patch.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied V17 {label} patch.")
    return True


def _insert_before_once(path: Path, anchor: str, block: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if block.strip() in text:
        print(f"V17 {label} patch already present.")
        return False
    if anchor not in text:
        raise SystemExit(f"Expected {label} anchor was not found; refusing an unsafe V17 patch.")
    path.write_text(text.replace(anchor, block + anchor, 1), encoding="utf-8")
    print(f"Applied V17 {label} patch.")
    return True


def _has_v1706_history_snapshot(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return all(marker in text for marker in V1706_HISTORY_MARKERS)


def _apply_legacy_history_patches(path: Path) -> bool:
    """Apply the pre-V17.0.6 history upgrade only when it is still needed.

    V17.0.6 replaces these intermediate blocks with a canonical
    symbol/timeframe cache plus single-flight lock.  Re-running this older
    patcher after that upgrade must recognize the newer implementation instead
    of treating its intentionally changed anchors as corruption.
    """
    if _has_v1706_history_snapshot(path):
        print(
            "V17 canonical FYERS history snapshot already present; "
            "legacy shared-history patches are superseded."
        )
        return False
    _replace_once(path, OLD_PATH, NEW_PATH, "FYERS shared-history cache path")
    _replace_once(path, OLD_LOAD, NEW_LOAD, "FYERS shared-history cache load")
    _replace_once(path, OLD_HISTORY_WINDOW, NEW_HISTORY_WINDOW, "FYERS canonical history window")
    _replace_once(path, OLD_HISTORY_FRAME, NEW_HISTORY_FRAME, "FYERS canonical history snapshot")
    _replace_once(path, OLD_HISTORY_SAVE, NEW_HISTORY_SAVE, "FYERS canonical history save")
    return True


def main() -> int:
    _replace_once(FYERS_TARGET, OLD_GOVERNOR_CONSTANTS, NEW_GOVERNOR_CONSTANTS, "FYERS governor constants")
    _replace_once(FYERS_TARGET, OLD_ENSURE_DIRS, NEW_ENSURE_DIRS, "FYERS cache directories")
    _replace_once(FYERS_TARGET, OLD_COOLDOWN, NEW_COOLDOWN, "FYERS escalating 429 cooldown")
    _apply_legacy_history_patches(FYERS_TARGET)
    _insert_before_once(FYERS_TARGET, QUOTE_HELPER_ANCHOR, QUOTE_HELPERS, "FYERS cross-process quote cache helpers")
    _replace_once(FYERS_TARGET, OLD_QUOTE_START, NEW_QUOTE_START, "FYERS quote cache read")
    _replace_once(FYERS_TARGET, OLD_QUOTE_SUCCESS, NEW_QUOTE_SUCCESS, "FYERS quote cache write")
    _replace_once(FYERS_TARGET, OLD_GOVERNOR_STATUS, NEW_GOVERNOR_STATUS, "FYERS governor diagnostics")
    _replace_once(APP_TARGET, OLD_CHART_CONFIG, NEW_CHART_CONFIG, "unique chart-slot routing")
    _replace_once(AUTONOMY_TARGET, OLD_PROVIDER_STATE, NEW_PROVIDER_STATE, "candidate-scoped provider health")
    _replace_once(AUTONOMY_TARGET, OLD_DECISION_BINDING, NEW_DECISION_BINDING, "autonomous candidate binding")
    _replace_once(AUTONOMY_TARGET, OLD_RENDER_HEALTH, NEW_RENDER_HEALTH, "autonomy health rendering")
    print("V17 direct-pull/runtime patches complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
