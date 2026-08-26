from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import re
import threading
import time
from typing import Any, Iterable
import urllib.request

from workstation.advanced_pattern_engine import analyze_chart_patterns
from workstation.scanner_universe_registry import (
    DEFAULT_SCANNER_UNIVERSE_REGISTRY,
    ScannerInstrument,
    UniverseSnapshot,
)


DEFAULT_MORNING_UNIVERSES = (
    "NIFTY50",
    "BANKNIFTY",
    "SENSEX30",
    "INDIA_INDICES",
    "MCX_MAJOR",
    "CRYPTO_MAJOR",
)
ALL_RESEARCH_UNIVERSES = DEFAULT_MORNING_UNIVERSES + ("GLOBAL_MAJOR",)

_UNIVERSE_ALIASES = {
    "NIFTY": "NIFTY50",
    "NIFTY50": "NIFTY50",
    "BANKNIFTY": "BANKNIFTY",
    "BANK": "BANKNIFTY",
    "SENSEX": "SENSEX30",
    "SENSEX30": "SENSEX30",
    "INDICES": "INDIA_INDICES",
    "INDEX": "INDIA_INDICES",
    "CRYPTO": "CRYPTO_MAJOR",
    "COMMODITIES": "MCX_MAJOR",
    "COMMODITY": "MCX_MAJOR",
    "MCX": "MCX_MAJOR",
    "GLOBAL": "GLOBAL_MAJOR",
    "US": "GLOBAL_MAJOR",
}


def _download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Quant-Research/5.5"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return response.read(2_000_000).decode("utf-8-sig", errors="replace")


def _requested_universes(text: str) -> tuple[str, ...]:
    value = " ".join(str(text or "").upper().split())
    if re.search(r"\b(?:ALL|EVERY)\s+(?:MARKETS?|UNIVERSES?|ASSETS?)\b", value):
        return ALL_RESEARCH_UNIVERSES
    selected: list[str] = []
    patterns = (
        (r"\bNIFTY\s*50\b", "NIFTY50"),
        (r"\bBANK\s*NIFTY\b|\bBANKNIFTY\b", "BANKNIFTY"),
        (r"\bSENSEX(?:\s*30)?\b", "SENSEX30"),
        (r"\b(?:CRYPTO|BITCOIN|BTC|ETHEREUM|ETH|SOLANA|SOL)\b", "CRYPTO_MAJOR"),
        (r"\b(?:COMMODIT(?:Y|IES)|MCX|CRUDE\s*OIL|GOLD|SILVER|NATURAL\s*GAS)\b", "MCX_MAJOR"),
        (r"\b(?:GLOBAL|US|NASDAQ|NYSE)\b", "GLOBAL_MAJOR"),
        (r"\b(?:INDICES|INDEXES|INDIA\s+INDEX)\b", "INDIA_INDICES"),
    )
    for pattern, universe in patterns:
        if re.search(pattern, value) and universe not in selected:
            selected.append(universe)
    return tuple(selected or ("NIFTY50",))


def is_multi_market_scan_request(text: str) -> bool:
    value = str(text or "")
    return bool(
        re.search(r"\b(?:scan|find|rank|check|analy[sz]e)\b", value, re.I)
        and re.search(
            r"\b(?:nifty\s*50|bank\s*nifty|sensex|stocks?|companies|indices|markets?|"
            r"crypto|bitcoin|commodit(?:y|ies)|mcx|global|nasdaq|nyse)\b",
            value,
            re.I,
        )
    )


class MultiMarketScanner:
    """Bounded discovery scanner; automatic paper authority stays downstream."""

    def __init__(self, *, max_workers: int = 3, cache_seconds: float = 300.0) -> None:
        self.max_workers = max(1, min(int(max_workers), 4))
        self.cache_seconds = max(30.0, float(cache_seconds))
        self._lock = threading.RLock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._selected = DEFAULT_MORNING_UNIVERSES
        self._started_at: str | None = None
        self._completed_at: str | None = None
        self._last_completed_mono = 0.0
        self._scanned = 0
        self._total = 0
        self._auto_enroll = False
        self._profile = "intraday"
        self._results: list[dict[str, Any]] = []
        self._errors: list[dict[str, Any]] = []
        self._sources: dict[str, dict[str, Any]] = {}

    def status(self) -> dict[str, Any]:
        with self._lock:
            candidates = [row for row in self._results if row.get("candidate")]
            by_universe: dict[str, dict[str, int]] = {}
            for universe in self._selected:
                rows = [row for row in self._results if universe in row.get("universes", [])]
                by_universe[universe] = {
                    "scanned": len(rows),
                    "data_ok": sum(1 for row in rows if row.get("success")),
                    "candidates": sum(1 for row in rows if row.get("candidate")),
                    "auto_paper_eligible": sum(
                        1 for row in rows if row.get("candidate") and row.get("auto_paper_eligible")
                    ),
                }
            return {
                "success": True,
                "running": self._running,
                "selected_universes": list(self._selected),
                "profile": self._profile,
                "started_at": self._started_at,
                "completed_at": self._completed_at,
                "scanned": self._scanned,
                "total": self._total,
                "candidate_count": len(candidates),
                "executable_watch_count": sum(
                    1 for row in candidates if row.get("auto_paper_eligible")
                ),
                "by_universe": by_universe,
                "sources": dict(self._sources),
                "candidates": candidates[:40],
                "results": list(self._results[:160]),
                "errors": list(self._errors[:30]),
                "auto_enroll": self._auto_enroll,
                "paper_only": True,
                "live_execution": False,
            }

    @staticmethod
    def _snapshots(selected: Iterable[str]) -> list[UniverseSnapshot]:
        registry = DEFAULT_SCANNER_UNIVERSE_REGISTRY
        makers = {
            "NIFTY50": lambda: registry.nifty50(_download_text),
            "BANKNIFTY": lambda: registry.banknifty(_download_text),
            "SENSEX30": lambda: registry.sensex30(_download_text),
            "INDIA_INDICES": registry.indices,
            "CRYPTO_MAJOR": registry.crypto,
            "MCX_MAJOR": registry.commodities,
            "GLOBAL_MAJOR": registry.global_equities,
            "INDIA_CONFIGURED": registry.configured_india,
        }
        snapshots = []
        for name in selected:
            maker = makers.get(name)
            if maker:
                snapshots.append(maker())
        return snapshots

    def start(
        self,
        *,
        universes: Iterable[str] = DEFAULT_MORNING_UNIVERSES,
        force: bool = False,
        auto_enroll: bool = False,
        profile: str = "intraday",
    ) -> dict[str, Any]:
        normalized = tuple(
            dict.fromkeys(
                _UNIVERSE_ALIASES.get(str(item).strip().upper(), str(item).strip().upper())
                for item in universes
                if str(item).strip()
            )
        ) or DEFAULT_MORNING_UNIVERSES
        with self._lock:
            if self._running:
                self._auto_enroll = self._auto_enroll or bool(auto_enroll)
                return self.status()
            if (
                not force
                and normalized == self._selected
                and self._last_completed_mono
                and time.monotonic() - self._last_completed_mono < self.cache_seconds
            ):
                if auto_enroll:
                    self._enroll_candidates_locked()
                return self.status()
            self._running = True
            self._selected = normalized
            self._profile = str(profile or "intraday")
            self._auto_enroll = bool(auto_enroll)
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._completed_at = None
            self._scanned = 0
            self._total = 0
            self._results = []
            self._errors = []
            self._sources = {}
            self._thread = threading.Thread(
                target=self._run,
                name="JarvisMultiMarketScanner",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    @staticmethod
    def _scan_one(instrument: ScannerInstrument) -> dict[str, Any]:
        from omni.trading_intelligence.quant_firm_engine import decide
        from workstation.quant_terminal_v2 import candles_payload, completed_candles

        # Runtime exchange constituent lists can contain valid symbols that are
        # not part of the static NIFTY50/SENSEX convenience aliases. Preserve
        # the registry's explicit broker symbol so the equity resolver does not
        # have to guess what exchange a bare ticker belongs to.
        data_symbol = (
            instrument.provider_symbol
            if instrument.asset_class == "EQUITY" and instrument.market == "INDIA"
            else instrument.symbol
        )
        payload = candles_payload(data_symbol, "1d", 180)
        raw = list(payload.get("candles") or [])
        candles = completed_candles(raw, "1d")
        base = {
            "symbol": instrument.symbol,
            "label": instrument.label,
            "asset_class": instrument.asset_class,
            "market": instrument.market,
            "exchange": instrument.exchange,
            "provider": instrument.provider,
            "provider_symbol": instrument.provider_symbol,
            "universes": list(instrument.universe),
            "auto_paper_eligible": instrument.auto_paper_eligible,
            "eligibility_gate": instrument.eligibility_gate,
            "data_quality": instrument.data_quality,
        }
        if not payload.get("success") or len(candles) < 60:
            return {
                **base,
                "success": False,
                "candidate": False,
                "message": payload.get("message") or "Daily candles unavailable.",
                "paper_only": True,
                "live_execution": False,
            }
        pattern = analyze_chart_patterns(candles)
        decision = decide(instrument.symbol, "1d", candles).to_dict()
        pattern_direction = str(pattern.get("direction") or "NEUTRAL")
        decision_side = str(decision.get("side") or "WAIT")
        decision_direction = (
            "BULLISH" if decision_side == "LONG" else "BEARISH" if decision_side == "SHORT" else "NEUTRAL"
        )
        score = 0.65 * float(pattern.get("score") or 0.0) + 0.35 * float(decision.get("score") or 0.0)
        if decision_direction not in {"NEUTRAL", pattern_direction}:
            score -= 18.0
        state = str(pattern.get("state") or "NO_EDGE")
        candidate = state in {
            "CONFIRMED_BREAKOUT", "UNCONFIRMED_BREAKOUT", "BREAKOUT_WATCH",
            "CONFIRMED_BREAKDOWN", "UNCONFIRMED_BREAKDOWN", "BREAKDOWN_WATCH",
        } and score >= 55.0
        return {
            **base,
            "success": True,
            "candidate": candidate,
            "state": state,
            "direction": pattern_direction,
            "signal": "BUY" if pattern_direction == "BULLISH" else "SELL" if pattern_direction == "BEARISH" else "WAIT",
            "score": round(max(0.0, min(score, 100.0)), 2),
            "close": float(candles[-1]["close"]),
            "breakout_level": pattern.get("breakout_level"),
            "breakdown_level": pattern.get("breakdown_level"),
            "volume_ratio": pattern.get("volume_ratio"),
            "structure": pattern.get("structure"),
            "patterns": pattern.get("patterns") or [],
            "quant_side": decision_side,
            "quant_score": decision.get("score"),
            "forming_bar_excluded": len(candles) < len(raw),
            "message": pattern.get("message"),
            "paper_only": True,
            "live_execution": False,
        }

    def _enroll_candidates_locked(self) -> None:
        symbols = [
            row["symbol"]
            for row in self._results
            if row.get("candidate") and row.get("auto_paper_eligible")
        ][:14]
        if not symbols:
            return
        from workstation.paper_autonomy_engine import paper_autonomy

        paper_autonomy.add_symbols(symbols, cap=24)
        paper_autonomy.trigger_scan()

    def _run(self) -> None:
        try:
            snapshots = self._snapshots(self._selected)
            instruments_by_symbol: dict[str, ScannerInstrument] = {}
            sources: dict[str, dict[str, Any]] = {}
            for snapshot in snapshots:
                sources[snapshot.name] = {
                    "authority": snapshot.authority,
                    "source_url": snapshot.source_url,
                    "source_mode": snapshot.source_mode,
                    "count": len(snapshot.instruments),
                }
                for item in snapshot.instruments:
                    existing = instruments_by_symbol.get(item.symbol)
                    if existing is None:
                        instruments_by_symbol[item.symbol] = item
                    else:
                        instruments_by_symbol[item.symbol] = ScannerInstrument(
                            **{
                                **existing.__dict__,
                                "universe": tuple(dict.fromkeys(existing.universe + item.universe)),
                                "auto_paper_eligible": existing.auto_paper_eligible and item.auto_paper_eligible,
                            }
                        )
            instruments = list(instruments_by_symbol.values())
            with self._lock:
                self._total = len(instruments)
                self._sources = sources
            rows: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {pool.submit(self._scan_one, item): item for item in instruments}
                for future in as_completed(futures):
                    item = futures[future]
                    try:
                        row = future.result()
                    except Exception as exc:
                        row = {
                            "success": False,
                            "symbol": item.symbol,
                            "label": item.label,
                            "universes": list(item.universe),
                            "candidate": False,
                            "message": f"{type(exc).__name__}: {exc}"[:300],
                        }
                    rows.append(row)
                    with self._lock:
                        self._scanned += 1
                        if not row.get("success"):
                            self._errors.append(
                                {"symbol": item.symbol, "message": str(row.get("message") or "")[:240]}
                            )
            rows.sort(
                key=lambda row: (bool(row.get("candidate")), float(row.get("score") or 0.0)),
                reverse=True,
            )
            with self._lock:
                self._results = rows
                self._last_completed_mono = time.monotonic()
                self._completed_at = datetime.now(timezone.utc).isoformat()
                if self._auto_enroll:
                    self._enroll_candidates_locked()
        finally:
            with self._lock:
                self._running = False


multi_market_scanner = MultiMarketScanner()


def multi_market_scan_command_payload(text: str) -> dict[str, Any] | None:
    if not is_multi_market_scan_request(text):
        return None
    universes = _requested_universes(text)
    status = multi_market_scanner.start(universes=universes, force=True, auto_enroll=False)
    return {
        **status,
        "action": "multi_market_discovery_scan",
        "speech": (
            "The governed multi-market discovery scan has started for "
            + ", ".join(universes)
            + ". It ranks completed-bar structure and patterns. Candidates remain research-only "
            "until fresh data, session, strategy, risk and paper-execution gates pass."
        ),
    }
