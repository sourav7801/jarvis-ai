from __future__ import annotations

"""Apply V17 closed-market market-data routing patches.

This patch is intentionally idempotent and direct-pull safe.  It changes only
read-side market-data behaviour:

* when an Indian/MCX session is CLOSED and the FYERS bridge already has a last
  verified stream snapshot, return that snapshot for display instead of making
  repeated REST quote fallbacks;
* keep the snapshot explicitly stale/market-closed so automatic entry freshness
  and session gates remain fail-closed;
* render CLOSED/STALE/REST accurately in the browser watchlist.

Trading writes, Paper Desk authority and the live-execution lock are untouched.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANT_TARGET = ROOT / "workstation" / "quant_terminal_v2.py"
APP_TARGET = ROOT / "workstation" / "quant_terminal_v2_static" / "app.js"

OLD_LIVE_FALLBACK_ANCHOR = '''    if bridge_healthy:\n        payload["symbol"] = canonical\n        payload["instrument"] = metadata\n        payload["snapshot_kind"] = "LIVE_STREAM"\n        payload["stream_degraded"] = False\n        payload["snapshot_age_seconds"] = round(bridge_age_seconds or 0.0, 3)\n        payload["live_orders"] = False\n        return payload\n\n    # The stream is an optimization, not the only read path. This fallback is\n'''

NEW_LIVE_FALLBACK_ANCHOR = '''    if bridge_healthy:\n        payload["symbol"] = canonical\n        payload["instrument"] = metadata\n        payload["snapshot_kind"] = "LIVE_STREAM"\n        payload["stream_degraded"] = False\n        payload["snapshot_age_seconds"] = round(bridge_age_seconds or 0.0, 3)\n        payload["live_orders"] = False\n        return payload\n\n    # A stale stream snapshot is expected after the instrument's trading\n    # session closes.  If FYERS already supplied a verified last price, do not\n    # spend REST quote quota trying to refresh a market that cannot produce a\n    # new tradable tick.  UNKNOWN calendar state intentionally falls through to\n    # the normal REST fallback; only an explicitly CLOSED session uses this\n    # branch.  The result remains stale and market_closed, so automatic entry\n    # freshness/session gates stay fail-closed.\n    session_closed = False\n    try:\n        from workstation.paper_market_data import PAPER_MARKET_DATA\n\n        session_closed = not bool(PAPER_MARKET_DATA.session_open(canonical))\n    except Exception:\n        session_closed = False\n    if (\n        session_closed\n        and payload\n        and payload.get("success")\n        and bridge_snapshot.get("ltp") is not None\n    ):\n        payload["symbol"] = canonical\n        payload["instrument"] = metadata\n        payload["snapshot_kind"] = "MARKET_CLOSED_STREAM_CACHE"\n        payload["stream_degraded"] = False\n        payload["stale"] = True\n        payload["market_closed"] = True\n        payload["snapshot_age_seconds"] = bridge_age_seconds\n        payload["message"] = (\n            "Market session is closed; serving the last verified FYERS stream "\n            "snapshot without REST quote retries."\n        )\n        payload["live_orders"] = False\n        return payload\n\n    # The stream is an optimization, not the only read path. This fallback is\n'''

OLD_WATCH_TEXT = '''  change.textContent=(Number.isFinite(diff)?`${sign}${diff.toFixed(2)}`:"")+(Number.isFinite(pct)?` (${pct>0?"+":""}${pct.toFixed(2)}%)`:"")+(meta.degraded?" · REST":"");\n'''
NEW_WATCH_TEXT = '''  const feedState=String(meta.statusLabel||(meta.degraded?"REST":"")).toUpperCase();\n  change.textContent=(Number.isFinite(diff)?`${sign}${diff.toFixed(2)}`:"")+(Number.isFinite(pct)?` (${pct>0?"+":""}${pct.toFixed(2)}%)`:"")+(feedState?` · ${feedState}`:"");\n'''

OLD_REFRESH_ONE = '''  try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},6000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale)});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message})}\n'''
NEW_REFRESH_ONE = '''  try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},6000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale),statusLabel:payload.market_closed?"CLOSED":payload.stale?"STALE":payload.stream_degraded?"REST":""});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message})}\n'''

OLD_REFRESH_BATCH = '''      try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},12000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale)});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message})}\n'''
NEW_REFRESH_BATCH = '''      try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},12000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale),statusLabel:payload.market_closed?"CLOSED":payload.stale?"STALE":payload.stream_degraded?"REST":""});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message})}\n'''


def _replace_once(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"V17 {label} patch already present.")
        return False
    if old not in text:
        raise SystemExit(f"Expected {label} block was not found; refusing a partial market-session patch.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied V17 {label} patch.")
    return True


def main() -> int:
    _replace_once(
        QUANT_TARGET,
        OLD_LIVE_FALLBACK_ANCHOR,
        NEW_LIVE_FALLBACK_ANCHOR,
        "closed-market FYERS snapshot short-circuit",
    )
    _replace_once(APP_TARGET, OLD_WATCH_TEXT, NEW_WATCH_TEXT, "watchlist feed-state label")
    _replace_once(APP_TARGET, OLD_REFRESH_ONE, NEW_REFRESH_ONE, "single watch refresh status")
    _replace_once(APP_TARGET, OLD_REFRESH_BATCH, NEW_REFRESH_BATCH, "batched watch refresh status")
    print("V17 closed-market market-data patches complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
