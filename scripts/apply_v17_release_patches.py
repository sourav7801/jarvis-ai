from __future__ import annotations

"""Apply deterministic release-only source patches before the V17 build.

The current FYERS governor historically keyed its completed-history cache by
(symbol, resolution, bars). That made semantically identical requests with
multiple bar counts hit FYERS independently and contributed to provider 429s.
The V17 release artifact uses one cache file per symbol/resolution and only
serves it when the cached snapshot is large enough for the requested history.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "agents" / "fyers_data_adapter.py"

OLD_PATH = '''def _history_cache_path(provider_symbol: str, resolution: str, bars: int) -> Path:\n    raw = f"{provider_symbol}|{resolution}|{int(bars)}".encode("utf-8")\n    digest = hashlib.sha256(raw).hexdigest()[:24]\n    return _HISTORY_CACHE_DIR / f"{digest}.json"\n'''

NEW_PATH = '''def _history_cache_path(provider_symbol: str, resolution: str, bars: int) -> Path:\n    # V17 shares a completed-history snapshot across bar-count consumers.\n    # `bars` stays in the signature for backward compatibility with tests/callers.\n    raw = f"{provider_symbol}|{resolution}".encode("utf-8")\n    digest = hashlib.sha256(raw).hexdigest()[:24]\n    return _HISTORY_CACHE_DIR / f"{digest}.json"\n'''

OLD_LOAD = '''        frame = _cache_rows_to_frame(payload.get("rows"))\n        return frame.tail(bars) if not frame.empty else None\n'''

NEW_LOAD = '''        frame = _cache_rows_to_frame(payload.get("rows"))\n        if frame.empty or len(frame) < int(bars):\n            return None\n        return frame.tail(bars)\n'''


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW_PATH in text and NEW_LOAD in text:
        print("V17 FYERS shared-history cache patch already present.")
        return 0
    if OLD_PATH not in text:
        raise SystemExit("Expected FYERS history-cache path block was not found; refusing an unsafe release patch.")
    if OLD_LOAD not in text:
        raise SystemExit("Expected FYERS history-cache load block was not found; refusing an unsafe release patch.")
    text = text.replace(OLD_PATH, NEW_PATH, 1).replace(OLD_LOAD, NEW_LOAD, 1)
    TARGET.write_text(text, encoding="utf-8")
    print("Applied V17 FYERS shared-history cache patch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
