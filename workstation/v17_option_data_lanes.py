"""V17 isolated option-data lanes.

Option-chain research and option-premium chart loading are deliberately
separated from the shared Quant research pool. A slow/rate-limited provider
must degrade only the option surface, never stall workspace-state, charts,
position monitoring, or unrelated research.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import threading
import time
from typing import Any, Callable

from workstation.quant_intelligence_modules import intelligence_module_payload


class _SingleLane:
    def __init__(self, name: str, workers: int = 1, cache_ttl: float = 15.0) -> None:
        self.name = name
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=name)
        self.cache_ttl = float(cache_ttl)
        self.lock = threading.RLock()
        self.futures: dict[tuple[Any, ...], Future] = {}
        self.cache: dict[tuple[Any, ...], tuple[float, Any]] = {}

    def _purge(self) -> None:
        now = time.monotonic()
        for key, (at, _payload) in list(self.cache.items()):
            if now - at > self.cache_ttl:
                self.cache.pop(key, None)

    def request(self, key: tuple[Any, ...], loader: Callable[[], Any], *, wait: float = 0.0) -> dict[str, Any]:
        with self.lock:
            self._purge()
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] <= self.cache_ttl:
                return {"success": True, "pending": False, "result": cached[1], "cache_hit": True}

            future = self.futures.get(key)
            if future is not None and future.done():
                try:
                    payload = future.result()
                except Exception as exc:
                    self.futures.pop(key, None)
                    return {
                        "success": False,
                        "pending": False,
                        "reason": "OPTIONS_DATA_ERROR",
                        "message": f"{type(exc).__name__}: {exc}"[:700],
                    }
                self.futures.pop(key, None)
                self.cache[key] = (time.monotonic(), payload)
                return {"success": True, "pending": False, "result": payload, "cache_hit": False}

            if future is None:
                # Hard back-pressure: one active task per lane and no unbounded
                # queue of different option requests.
                active = [item for item in self.futures.values() if not item.done()]
                if active:
                    return {
                        "success": False,
                        "pending": False,
                        "reason": "OPTIONS_DATA_LANE_BUSY",
                        "message": "Option data lane is serving another request. The terminal remains responsive; retry shortly.",
                        "busy": True,
                    }
                future = self.pool.submit(loader)
                self.futures[key] = future

        if wait <= 0:
            return {
                "success": True,
                "pending": True,
                "reason": "OPTIONS_DATA_LOADING",
                "message": "Option data is loading in the isolated V17 lane.",
            }

        try:
            payload = future.result(timeout=wait)
        except TimeoutError:
            return {
                "success": False,
                "pending": False,
                "reason": "OPTIONS_DATA_TIMEOUT",
                "message": f"{self.name} exceeded the {wait:.1f}s UI deadline; the request was isolated from the main terminal.",
            }
        except Exception as exc:
            with self.lock:
                self.futures.pop(key, None)
            return {
                "success": False,
                "pending": False,
                "reason": "OPTIONS_DATA_ERROR",
                "message": f"{type(exc).__name__}: {exc}"[:700],
            }

        with self.lock:
            self.futures.pop(key, None)
            self.cache[key] = (time.monotonic(), payload)
        return {"success": True, "pending": False, "result": payload, "cache_hit": False}


class V17OptionDataLanes:
    def __init__(self) -> None:
        self.chain = _SingleLane("JarvisV17OptionChain", cache_ttl=15.0)
        self.chart = _SingleLane("JarvisV17OptionChart", cache_ttl=8.0)

    @staticmethod
    def chain_result(symbol: str, expiry: str | None) -> dict[str, Any]:
        payload = intelligence_module_payload(
            "option-chain",
            symbol,
            profile="intraday",
            expiry=expiry,
        )
        return dict(payload or {})

    @staticmethod
    def chart_result(provider: str, instrument: str, timeframe: str, bars: int) -> dict[str, Any]:
        from workstation.option_chart_data import option_candles

        return dict(option_candles(provider, instrument, timeframe, bars) or {})

    def chain_request(self, workspace: str, symbol: str, expiry: str | None) -> dict[str, Any]:
        key = (str(symbol).upper(), str(expiry or "NEAREST"))
        return self.chain.request(
            key,
            lambda: self.chain_result(symbol, expiry),
            wait=0.0,
        )

    def chart_request(self, provider: str, instrument: str, timeframe: str, bars: int) -> dict[str, Any]:
        key = (str(provider).upper(), str(instrument), str(timeframe), int(bars))
        return self.chart.request(
            key,
            lambda: self.chart_result(provider, instrument, timeframe, bars),
            wait=8.5,
        )


OPTION_DATA_LANES = V17OptionDataLanes()


__all__ = ["V17OptionDataLanes", "OPTION_DATA_LANES"]
