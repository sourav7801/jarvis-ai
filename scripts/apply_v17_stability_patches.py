from __future__ import annotations

"""Apply V17 browser/runtime load-stability patches.

This patcher is intentionally idempotent and is run by ``JARVIS_V17.bat``
after the canonical V17 release/data patches.  It changes only read-side UI
scheduling.  Trading writes, Paper Desk gates, and the live-execution lock are
untouched.

Goals:
* prevent the startup watchlist from bursting ten simultaneous localhost reads;
* limit chart/history reads so canonical workspace-state keeps a free lane;
* rotate live chart polling instead of polling every visible chart each tick;
* prevent overlapping live polling cycles;
* hydrate charts first, then the watchlist, then start periodic polling.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_TARGET = ROOT / "workstation" / "quant_terminal_v2_static" / "app.js"

OLD_RUNTIME_COUNTERS = '''let signalTimer=null;\nlet watchCursor=0;\nconst indicatorState={ema:true,vwap:true,bb:true,rsi:true};\n'''
NEW_RUNTIME_COUNTERS = '''let signalTimer=null;\nlet watchCursor=0;\nlet chartLiveCursor=0;\nlet liveTickBusy=false;\nconst indicatorState={ema:true,vwap:true,bb:true,rsi:true};\n'''

OLD_CANDLE_GATE = '''    if(candleActive>=4)await new Promise(resolve=>candleQueue.push(resolve));else candleActive++;\n'''
NEW_CANDLE_GATE = '''    if(candleActive>=2)await new Promise(resolve=>candleQueue.push(resolve));else candleActive++;\n'''

OLD_REFRESH_ALL = '''async function refreshAllWatch(){\n  await Promise.allSettled(MARKETS.map(async item=>{\n    try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},10000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale)});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message})}\n  }));\n}\n'''
NEW_REFRESH_ALL = '''async function refreshAllWatch(){\n  // Hydrate in tiny batches so watchlist reads never consume the browser's\n  // entire localhost connection pool and starve canonical trading state.\n  for(let offset=0;offset<MARKETS.length;offset+=2){\n    const batch=MARKETS.slice(offset,offset+2);\n    await Promise.allSettled(batch.map(async item=>{\n      try{const payload=await fetchJson(`/api/live?${new URLSearchParams({symbol:item.symbol})}`,{},12000);if(payload.success&&payload.snapshot)updateWatchTile(item.symbol,payload.snapshot,{degraded:Boolean(payload.stream_degraded||payload.stale)});else updateWatchTile(item.symbol,null,{message:payload.message||"data unavailable"})}catch(error){updateWatchTile(item.symbol,null,{message:error.message})}\n    }));\n  }\n}\n'''

OLD_START_TIMERS = '''function startTimers(){\n  if(liveTimer)clearInterval(liveTimer);liveTimer=setInterval(()=>{chartSlots.forEach(slot=>{if(String(marketMeta(slot.symbol).kind).startsWith("INDIA"))pollSlotLive(slot)});refreshOneWatch()},1200);\n  if(providerTimer)clearInterval(providerTimer);providerTimer=setInterval(refreshProvider,5000);\n  if(signalTimer)clearInterval(signalTimer);signalTimer=setInterval(()=>loadDecision(selectedSymbol),30000);\n}\n'''
NEW_START_TIMERS = '''function startTimers(){\n  if(liveTimer)clearInterval(liveTimer);\n  liveTimer=setInterval(async()=>{\n    if(liveTickBusy)return;\n    liveTickBusy=true;\n    try{\n      const india=chartSlots.filter(slot=>String(marketMeta(slot.symbol).kind).startsWith("INDIA"));\n      const tasks=[];\n      if(india.length){const slot=india[chartLiveCursor%india.length];chartLiveCursor++;tasks.push(pollSlotLive(slot))}\n      tasks.push(refreshOneWatch());\n      await Promise.allSettled(tasks);\n    }finally{liveTickBusy=false}\n  },2500);\n  if(providerTimer)clearInterval(providerTimer);providerTimer=setInterval(refreshProvider,7000);\n  if(signalTimer)clearInterval(signalTimer);signalTimer=setInterval(()=>loadDecision(selectedSymbol),30000);\n}\n'''

OLD_BOOTSTRAP_TAIL = '''  buildWatch();bindControls();syncControls();const watchHydration=refreshAllWatch();await mountCharts();refreshProvider();startTimers();await watchHydration;if(params.get("analyze")==="1")await scanSelected();\n}\n'''
NEW_BOOTSTRAP_TAIL = '''  // Do not burst watchlist + charts + canonical observers at boot.  Charts get\n  // first use of the bounded history lanes, then watch tiles hydrate in pairs.\n  buildWatch();bindControls();syncControls();await mountCharts();refreshProvider();await refreshAllWatch();startTimers();if(params.get("analyze")==="1")await scanSelected();\n}\n'''


def _replace_once(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"V17 {label} patch already present.")
        return False
    if old not in text:
        raise SystemExit(f"Expected {label} block was not found; refusing a partial stability patch.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied V17 {label} patch.")
    return True


def main() -> int:
    _replace_once(APP_TARGET, OLD_RUNTIME_COUNTERS, NEW_RUNTIME_COUNTERS, "browser polling counters")
    _replace_once(APP_TARGET, OLD_CANDLE_GATE, NEW_CANDLE_GATE, "bounded chart-history concurrency")
    _replace_once(APP_TARGET, OLD_REFRESH_ALL, NEW_REFRESH_ALL, "staged watchlist hydration")
    _replace_once(APP_TARGET, OLD_START_TIMERS, NEW_START_TIMERS, "rotating non-overlapping live polling")
    _replace_once(APP_TARGET, OLD_BOOTSTRAP_TAIL, NEW_BOOTSTRAP_TAIL, "staged terminal bootstrap")
    print("V17 browser/runtime stability patches complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
