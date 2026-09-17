from __future__ import annotations

"""Apply V17 canonical FYERS history-snapshot patches.

The live quote path is intentionally untouched. This patch changes only the
read-only historical/chart boundary so multiple chart/scanner consumers asking
for the same symbol and timeframe do not create separate FYERS REST calls just
because they requested different bar counts.

Safety contract:
* cache identity is provider-symbol + resolution (not requested bar count);
* one cross-process single-flight lock protects each history identity;
* a bounded canonical snapshot is fetched once and sliced locally;
* provider 429 cooldown may serve the last verified history snapshot only as
  explicitly stale/degraded display data;
* stale/rate-limited history is propagated to Quant Terminal evidence and is
  rejected before strategy/automatic-entry evidence is built;
* no trading write path or live-execution setting is changed.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_TARGET = ROOT / "agents" / "fyers_data_adapter.py"
QUANT_TARGET = ROOT / "workstation" / "quant_terminal_v2.py"


NEW_CACHE_BLOCK = r'''def _history_snapshot_bars(requested_bars: int) -> int:
    """Return the canonical per-symbol/timeframe snapshot size.

    A larger common snapshot lets 220/300/500-bar consumers reuse one provider
    response. Very large explicit requests are still honored rather than
    silently truncated.
    """
    try:
        configured = int(float(os.getenv("JARVIS_FYERS_HISTORY_SNAPSHOT_BARS", "1000")))
    except (TypeError, ValueError):
        configured = 1000
    return max(int(requested_bars), max(220, min(configured, 5000)))


def _history_stale_ttl_seconds() -> float:
    try:
        configured = float(os.getenv("JARVIS_FYERS_HISTORY_STALE_TTL_SECONDS", "900"))
    except (TypeError, ValueError):
        configured = 900.0
    return max(_cache_ttl_seconds("1"), min(configured, 3600.0))


def _history_cache_path(provider_symbol: str, resolution: str, bars: int | None = None) -> Path:
    # ``bars`` is accepted for backwards compatibility but deliberately does
    # not participate in identity. All consumers of a provider symbol and
    # resolution share one canonical snapshot and slice it locally.
    raw = f"{provider_symbol}|{resolution}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:24]
    return _HISTORY_CACHE_DIR / f"{digest}.json"


def _history_request_lock_path(provider_symbol: str, resolution: str) -> Path:
    raw = f"{provider_symbol}|{resolution}|singleflight".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:24]
    return _HISTORY_CACHE_DIR / f"{digest}.request.lock"


@contextmanager
def _history_request_lock(provider_symbol: str, resolution: str, timeout_seconds: float = 45.0):
    """Cross-process single-flight lock for one canonical history snapshot."""
    _ensure_governor_dirs()
    path = _history_request_lock_path(provider_symbol, resolution)
    deadline = time.monotonic() + max(float(timeout_seconds), 1.0)
    fd: int | None = None
    while time.monotonic() < deadline:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n{time.time()}".encode("ascii", errors="ignore"))
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > 120.0:
                    path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            time.sleep(0.05)
    if fd is None:
        raise RuntimeError(
            f"FYERS history single-flight lock timed out for {provider_symbol} {resolution}."
        )
    try:
        yield
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _frame_to_cache_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    table = frame.reset_index()
    rows: list[dict[str, Any]] = []
    for record in table.to_dict(orient="records"):
        clean: dict[str, Any] = {}
        for key, value in record.items():
            if hasattr(value, "isoformat"):
                clean[str(key)] = value.isoformat()
            elif hasattr(value, "item"):
                try:
                    clean[str(key)] = value.item()
                except Exception:
                    clean[str(key)] = str(value)
            else:
                clean[str(key)] = value
        rows.append(clean)
    return rows


def _cache_rows_to_frame(rows: Any) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    frame = pd.DataFrame(rows)
    if "Timestamp" not in frame.columns:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"], errors="coerce")
    for column in ("Open", "High", "Low", "Close", "Volume"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame.dropna(subset=["Timestamp", "Open", "High", "Low", "Close"])
        .sort_values("Timestamp")
        .set_index("Timestamp")
    )


def _read_history_cache(provider_symbol: str, resolution: str) -> tuple[pd.DataFrame | None, float | None]:
    path = _history_cache_path(provider_symbol, resolution)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - float(payload.get("saved_at_epoch") or 0.0)
        frame = _cache_rows_to_frame(payload.get("rows"))
        if age < 0 or frame.empty:
            return None, None
        return frame, age
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None, None


def _load_history_cache(
    provider_symbol: str,
    resolution: str,
    bars: int,
    *,
    max_age_seconds: float | None = None,
    require_full: bool = True,
) -> pd.DataFrame | None:
    frame, age = _read_history_cache(provider_symbol, resolution)
    if frame is None or age is None:
        return None
    ttl = _cache_ttl_seconds(resolution) if max_age_seconds is None else max(float(max_age_seconds), 0.0)
    if age > ttl:
        return None
    requested = max(1, int(bars))
    if require_full and len(frame) < requested:
        return None
    return frame.tail(requested)


def _save_history_cache(provider_symbol: str, resolution: str, bars: int, frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    canonical = frame.sort_index().tail(max(1, int(bars)))
    _write_json_atomic(
        _history_cache_path(provider_symbol, resolution),
        {
            "saved_at_epoch": time.time(),
            "provider_symbol": provider_symbol,
            "resolution": resolution,
            "bars": len(canonical),
            "cache_identity": "provider_symbol+resolution",
            "rows": _frame_to_cache_rows(canonical),
        },
    )


'''


NEW_GET_INTRADAY = r'''def get_intraday_data(
    symbol: str,
    market: str = "india",
    timeframe: str = "5m",
    bars: int = 500,
    *,
    client: Any = None,
) -> dict[str, Any]:
    requested_symbol = str(symbol or "").strip().upper()
    if str(market or "").strip().lower() not in {"india", "indian", "nse", "bse"}:
        return {"success": False, "source": "FYERS", "message": "The FYERS adapter currently supports Indian markets only."}
    if bars <= 0:
        return {"success": False, "source": "FYERS", "message": "bars must be greater than zero."}
    try:
        provider_symbol = normalize_symbol(symbol)
        resolution = resolution_for(timeframe)
    except ValueError as exc:
        return {"success": False, "source": "FYERS", "message": str(exc), "bars": 0, "data": None}
    if client is None and not is_configured():
        return {
            "success": False,
            "source": "FYERS",
            "provider_state": "LOGIN_REQUIRED",
            "message": "FYERS is not configured. Set FYERS_APP_ID and run python -m agents.fyers_auth_manager login.",
            "bars": 0,
            "data": None,
        }

    requested_bars = max(1, int(bars))
    snapshot_bars = _history_snapshot_bars(requested_bars)

    def ready_cache_payload(frame: pd.DataFrame, *, after_singleflight: bool = False) -> dict[str, Any]:
        return {
            "success": True,
            "source": "FYERS",
            "data_quality": "BROKER_HISTORICAL",
            "symbol": requested_symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": len(frame),
            "data": frame,
            "message": (
                "Historical candles loaded from the canonical FYERS symbol/timeframe cache"
                + (" after single-flight coalescing." if after_singleflight else ".")
            ),
            "provider_state": "READY",
            "provider_code": 200,
            "provider_cache_hit": True,
            "provider_cache_stale": False,
            "provider_rate_limited": False,
            "stale": False,
            "stream_degraded": False,
            "cache_identity": "provider_symbol+resolution",
            "market_data_fabricated": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def stale_cache_payload(exc: FyersRateLimited | None, details: dict[str, Any] | None = None) -> dict[str, Any] | None:
        stale = _load_history_cache(
            provider_symbol,
            resolution,
            requested_bars,
            max_age_seconds=_history_stale_ttl_seconds(),
            require_full=False,
        )
        if stale is None or stale.empty:
            return None
        retry_after = int(round(exc.retry_after_seconds)) if exc is not None else int(
            (details or {}).get("retry_after_seconds") or _RATE_LIMIT_COOLDOWN_SECONDS
        )
        return {
            "success": True,
            "source": "FYERS",
            "data_quality": "BROKER_HISTORICAL_STALE",
            "symbol": requested_symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": len(stale),
            "data": stale,
            "message": (
                "FYERS history is rate limited; serving the last verified canonical "
                "history snapshot for display only. Automatic evidence remains blocked."
            ),
            "provider_state": "RATE_LIMITED",
            "provider_code": 429,
            "retry_after_seconds": retry_after,
            "provider_cache_hit": True,
            "provider_cache_stale": True,
            "provider_rate_limited": True,
            "stale": True,
            "stream_degraded": True,
            "cache_identity": "provider_symbol+resolution",
            "market_data_fabricated": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    cached = _load_history_cache(provider_symbol, resolution, requested_bars)
    if cached is not None:
        return ready_cache_payload(cached)

    try:
        # Different workers requesting 220/300/500 bars for the same market
        # identity now collapse into one provider call. The follower rechecks
        # the canonical snapshot after the leader releases this lock.
        with _history_request_lock(provider_symbol, resolution):
            cached = _load_history_cache(provider_symbol, resolution, requested_bars)
            if cached is not None:
                return ready_cache_payload(cached, after_singleflight=True)

            fyers = client or create_client()
            end = datetime.now(INDIA_TZ).date()
            start = end - timedelta(days=_calendar_days_for_bars(snapshot_bars, resolution))
            max_days = 100 if resolution.isdigit() else 366
            rows: list[list[Any]] = []
            errors: list[dict[str, Any]] = []
            rate_limit_details: dict[str, Any] | None = None
            for range_from, range_to in _windows(start, end, max_days):
                try:
                    response = _governed_provider_call(
                        lambda rf=range_from, rt=range_to: fyers.history(
                            data={
                                "symbol": provider_symbol,
                                "resolution": resolution,
                                "date_format": "1",
                                "range_from": rf.isoformat(),
                                "range_to": rt.isoformat(),
                                "cont_flag": "1",
                            }
                        )
                    )
                except FyersRateLimited as exc:
                    stale_payload = stale_cache_payload(exc)
                    if stale_payload is not None:
                        return stale_payload
                    raise
                if isinstance(response, dict) and response.get("s") == "ok":
                    rows.extend(response.get("candles") or [])
                elif isinstance(response, dict) and response.get("s") == "no_data":
                    continue
                else:
                    details = _response_details(response)
                    errors.append(details)
                    if details.get("provider_state") == "RATE_LIMITED":
                        rate_limit_details = details
                        break

            if rate_limit_details is not None:
                stale_payload = stale_cache_payload(None, rate_limit_details)
                if stale_payload is not None:
                    return stale_payload
                return {
                    "success": False,
                    "source": "FYERS",
                    "data_quality": "UNAVAILABLE",
                    "symbol": requested_symbol,
                    "provider_symbol": provider_symbol,
                    "timeframe": timeframe,
                    "bars": 0,
                    "data": None,
                    **rate_limit_details,
                    "provider_cache_hit": False,
                    "provider_cache_stale": False,
                    "provider_rate_limited": True,
                    "stale": True,
                    "stream_degraded": True,
                    "market_data_fabricated": False,
                }

            frame = candles_to_frame(rows).tail(snapshot_bars)
            if frame.empty:
                details = errors[-1] if errors else {
                    "provider_state": "NO_DATA",
                    "provider_code": None,
                    "message": "FYERS returned no candles.",
                    "retry_after_seconds": None,
                }
                return {
                    "success": False,
                    "source": "FYERS",
                    "data_quality": "UNAVAILABLE",
                    "symbol": requested_symbol,
                    "provider_symbol": provider_symbol,
                    "timeframe": timeframe,
                    "bars": 0,
                    "data": None,
                    **details,
                    "provider_cache_hit": False,
                    "provider_cache_stale": False,
                    "provider_rate_limited": False,
                    "market_data_fabricated": False,
                }

            _save_history_cache(provider_symbol, resolution, snapshot_bars, frame)
            sliced = frame.tail(requested_bars)
            return {
                "success": True,
                "source": "FYERS",
                "data_quality": "BROKER_HISTORICAL",
                "symbol": requested_symbol,
                "provider_symbol": provider_symbol,
                "timeframe": timeframe,
                "bars": len(sliced),
                "data": sliced,
                "message": "Historical candles loaded from FYERS API v3 into the canonical symbol/timeframe snapshot.",
                "provider_state": "READY",
                "provider_code": 200,
                "provider_cache_hit": False,
                "provider_cache_stale": False,
                "provider_rate_limited": False,
                "provider_snapshot_bars": len(frame),
                "stale": False,
                "stream_degraded": False,
                "cache_identity": "provider_symbol+resolution",
                "provider_warnings": errors,
                "market_data_fabricated": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    except FyersRateLimited as exc:
        stale_payload = stale_cache_payload(exc)
        if stale_payload is not None:
            return stale_payload
        return {
            "success": False,
            "source": "FYERS",
            "data_quality": "UNAVAILABLE",
            "symbol": requested_symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": 0,
            "data": None,
            "provider_state": "RATE_LIMITED",
            "provider_code": 429,
            "retry_after_seconds": int(round(exc.retry_after_seconds)),
            "provider_cache_hit": False,
            "provider_cache_stale": False,
            "provider_rate_limited": True,
            "stale": True,
            "stream_degraded": True,
            "message": str(exc),
            "market_data_fabricated": False,
        }
    except Exception as exc:
        return {
            "success": False,
            "source": "FYERS",
            "data_quality": "UNAVAILABLE",
            "symbol": requested_symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": 0,
            "data": None,
            "provider_state": "PROVIDER_ERROR",
            "provider_code": None,
            "message": str(exc),
            "market_data_fabricated": False,
        }


'''


OLD_FYERS_RETURN = r'''    return {
        "success": bool(payload.get("success") and candles),
        "source": payload.get("source") or "FYERS",
        "data_quality": payload.get("data_quality") or (
            "BROKER_HISTORICAL" if candles else "UNAVAILABLE"
        ),
        "symbol": symbol,
        "provider_symbol": payload.get("provider_symbol") or provider_symbol or symbol,
        "timeframe": timeframe,
        "bars": len(candles),
        "candles": candles,
        "message": payload.get("message") or (
            "Historical candles loaded from FYERS." if candles else "FYERS candles unavailable."
        ),
        "paper_only": True,
        "live_execution": False,
    }
'''

NEW_FYERS_RETURN = r'''    return {
        "success": bool(payload.get("success") and candles),
        "source": payload.get("source") or "FYERS",
        "data_quality": payload.get("data_quality") or (
            "BROKER_HISTORICAL" if candles else "UNAVAILABLE"
        ),
        "symbol": symbol,
        "provider_symbol": payload.get("provider_symbol") or provider_symbol or symbol,
        "timeframe": timeframe,
        "bars": len(candles),
        "candles": candles,
        "message": payload.get("message") or (
            "Historical candles loaded from FYERS." if candles else "FYERS candles unavailable."
        ),
        # Preserve provider degradation all the way to evidence. A stale cache
        # may remain useful for chart display but must never become verified
        # autonomous evidence merely because its last candle is recent.
        "provider_cache_hit": bool(payload.get("provider_cache_hit")),
        "provider_cache_stale": bool(payload.get("provider_cache_stale")),
        "provider_rate_limited": bool(payload.get("provider_rate_limited")),
        "stale": bool(payload.get("stale") or payload.get("provider_cache_stale")),
        "stream_degraded": bool(
            payload.get("stream_degraded")
            or payload.get("provider_cache_stale")
            or payload.get("provider_rate_limited")
        ),
        "retry_after_seconds": payload.get("retry_after_seconds"),
        "paper_only": True,
        "live_execution": False,
    }
'''

OLD_EVIDENCE_START = r'''    payload = candles_payload(symbol, timeframe, 220)
    raw_candles = list(payload.get("candles") or [])
    from workstation.terminal_data import validate_candles
'''

NEW_EVIDENCE_START = r'''    payload = candles_payload(symbol, timeframe, 220)
    raw_candles = list(payload.get("candles") or [])
    provider_stale = bool(
        payload.get("stale")
        or payload.get("provider_cache_stale")
        or payload.get("provider_rate_limited")
    )
    if provider_stale:
        return {
            "timeframe": timeframe,
            "available": False,
            "message": payload.get("message") or "Provider history is stale/degraded.",
            "source": payload.get("source"),
            "data_quality": payload.get("data_quality") or "BROKER_HISTORICAL_STALE",
            "raw_bars": len(raw_candles),
            "complete_bars": 0,
            "stale": True,
            "provider_cache_stale": bool(payload.get("provider_cache_stale")),
            "provider_rate_limited": bool(payload.get("provider_rate_limited")),
        }
    from workstation.terminal_data import validate_candles
'''


def _replace_between(path: Path, start: str, end: str, replacement: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if replacement.strip() in text:
        print(f"V17 {label} patch already present.")
        return False
    start_index = text.find(start)
    end_index = text.find(end, start_index + len(start)) if start_index >= 0 else -1
    if start_index < 0 or end_index < 0:
        raise SystemExit(f"Expected {label} anchors were not found; refusing a partial history patch.")
    path.write_text(text[:start_index] + replacement + text[end_index:], encoding="utf-8")
    print(f"Applied V17 {label} patch.")
    return True


def _replace_once(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"V17 {label} patch already present.")
        return False
    if old not in text:
        raise SystemExit(f"Expected {label} block was not found; refusing a partial history patch.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied V17 {label} patch.")
    return True


def main() -> int:
    _replace_between(
        ADAPTER_TARGET,
        "def _history_cache_path(provider_symbol: str, resolution: str, bars: int) -> Path:\n",
        "def candles_to_frame(rows: list[list[Any]]) -> pd.DataFrame:\n",
        NEW_CACHE_BLOCK,
        "canonical FYERS history cache",
    )
    _replace_between(
        ADAPTER_TARGET,
        "def get_intraday_data(\n",
        "def get_quote(symbol: str, *, client: Any = None) -> dict[str, Any]:\n",
        NEW_GET_INTRADAY,
        "FYERS history single-flight and stale fallback",
    )
    _replace_once(QUANT_TARGET, OLD_FYERS_RETURN, NEW_FYERS_RETURN, "history degradation propagation")
    _replace_once(QUANT_TARGET, OLD_EVIDENCE_START, NEW_EVIDENCE_START, "stale history evidence hard block")
    print("V17 canonical FYERS history snapshot patches complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
