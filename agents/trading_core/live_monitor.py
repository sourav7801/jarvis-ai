
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .analysis_engine import analyze
from .edge_gate import load_edge_database, find_edge
from .market_structure import detect_structure
from .pattern_engine import detect_fvg, detect_liquidity, detect_orb, volume_anomaly
from .policy import market_policy
from .strategy_engine import build_setups


EVENT_DIR = Path.home() / "Documents" / "JARVIS_Trading"
EVENT_FILE = EVENT_DIR / "live_trading_events_v7.jsonl"
STATE_FILE = EVENT_DIR / "live_trading_state_v7.json"
IST = "Asia/Kolkata"


def ensure_dir() -> None:
    EVENT_DIR.mkdir(parents=True, exist_ok=True)


def as_ist_index(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return frame

    df = frame.copy()

    try:
        idx = pd.DatetimeIndex(df.index)

        if idx.tz is None:
            idx = idx.tz_localize(IST)
        else:
            idx = idx.tz_convert(IST)

        df.index = idx
    except Exception:
        # Keep the original index rather than failing the monitor.
        pass

    return df.sort_index()


def floor_bar(ts: pd.Timestamp, minutes: int) -> pd.Timestamp:
    if ts.tzinfo is None:
        ts = ts.tz_localize(IST)
    else:
        ts = ts.tz_convert(IST)

    naive = ts.tz_localize(None)
    minute = naive.minute - (naive.minute % minutes)

    return naive.replace(
        minute=minute,
        second=0,
        microsecond=0,
    ).tz_localize(IST)


def wall_clock_last_closed_bar(now: pd.Timestamp, minutes: int) -> pd.Timestamp:
    return floor_bar(now, minutes) - pd.Timedelta(minutes=minutes)


def latest_completed_data_bar(frame: pd.DataFrame, minutes: int) -> pd.Timestamp | None:
    """
    Returns the latest bar in the store that is definitely completed.

    During an active market session, the current bucket is considered open,
    so the previous bucket is used.

    When the market is closed, the latest stored candle is already historical
    and can be analyzed even if its timestamp is days earlier than the wall clock.
    """
    df = as_ist_index(frame)

    if df is None or df.empty:
        return None

    latest = pd.Timestamp(df.index[-1])

    # Use market session status from timestamps rather than assuming the
    # current wall-clock date must be represented in the store.
    now = pd.Timestamp.now(tz=IST)

    # If the latest bar's trading date is before today, it is unquestionably closed.
    if latest.date() < now.date():
        return latest

    # Same day: treat the current bucket as forming; use prior one.
    current_bucket = floor_bar(now, minutes)

    if latest >= current_bucket:
        prior = df.index[df.index < current_bucket]
        if len(prior):
            return pd.Timestamp(prior[-1])

    return latest


def closed_frame(frame: pd.DataFrame, minutes: int) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    df = as_ist_index(frame)

    if df is None or df.empty:
        return pd.DataFrame(), None

    closed_ts = latest_completed_data_bar(df, minutes)

    if closed_ts is None:
        return pd.DataFrame(), None

    filtered = df[df.index <= closed_ts].copy()

    return filtered, closed_ts


class LiveMonitorV7:
    """
    JARVIS Trading Core V7.

    Fix:
      - closed-market analysis uses the latest completed candle actually
        present in the data store, rather than the current wall-clock date.
      - active-session monitoring still excludes the current unfinished bucket.
      - live stream starts automatically.
      - no orders are placed.
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        poll_seconds: int = 3,
        auto_start_stream: bool = True,
    ) -> None:
        self.symbols = symbols or ["NIFTY", "BANKNIFTY", "SENSEX"]
        self.poll_seconds = max(2, int(poll_seconds))
        self.auto_start_stream = bool(auto_start_stream)

        self.stream = None
        self.running = False

        self.last_5m_processed: dict[str, str] = {}
        self.last_15m_processed: dict[str, str] = {}
        self.last_analysis: dict[str, dict[str, Any]] = {}

        ensure_dir()
        self._load_stream()

    def _load_stream(self) -> None:
        try:
            from agents.upstox_live_stream import upstox_live_stream
            self.stream = upstox_live_stream
        except Exception as exc:
            self.stream = None
            self._event(
                "STREAM_IMPORT_ERROR",
                {"message": str(exc)},
            )

    def _event(self, event: str, payload: dict[str, Any]) -> None:
        ensure_dir()

        row = {
            "timestamp": datetime.now().astimezone().isoformat(),
            "event": event,
            "payload": payload,
        }

        with EVENT_FILE.open(
            "a",
            encoding="utf-8",
        ) as f:
            f.write(
                json.dumps(
                    row,
                    default=str,
                )
                + "\n"
            )

    def _save_state(self, state: dict[str, Any]) -> None:
        ensure_dir()

        STATE_FILE.write_text(
            json.dumps(
                state,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    def start_stream(self) -> dict[str, Any]:
        if self.stream is None:
            self._load_stream()

        if self.stream is None:
            return {
                "success": False,
                "status": "STREAM_UNAVAILABLE",
            }

        try:
            if self.stream.store.is_running():
                return {
                    "success": True,
                    "status": "ALREADY_RUNNING",
                }

            return self.stream.start()

        except Exception as exc:
            return {
                "success": False,
                "status": "STREAM_START_ERROR",
                "message": str(exc),
            }

    def _ltp(self, symbol: str) -> dict[str, Any]:
        if self.stream is None:
            return {}

        try:
            return (
                self.stream
                .snapshot(symbol)
                .get("ltp", {})
                or {}
            )
        except Exception:
            return {}

    def _market_status(self) -> dict[str, Any]:
        if self.stream is None:
            return {}

        try:
            return (
                self.stream
                .store
                .diagnostics()
                .get(
                    "market_info",
                    {},
                )
            )
        except Exception:
            return {}

    def _analyze(
        self,
        symbol: str,
        df15: pd.DataFrame,
        df5: pd.DataFrame,
        closed15: pd.Timestamp | None,
        closed5: pd.Timestamp | None,
    ) -> dict[str, Any]:

        if df15.empty or df5.empty:
            return {
                "symbol": symbol,
                "status": "WAITING_FOR_DATA",
                "reason": (
                    "15m or 5m candle store has no usable data."
                ),
                "15m_bars": len(df15),
                "5m_bars": len(df5),
            }

        r15 = analyze(
            symbol,
            df15,
        )

        r5 = analyze(
            symbol,
            df5,
        )

        structure_15 = detect_structure(
            df15
        )

        structure_5 = detect_structure(
            df5
        )

        orb = detect_orb(
            df5
        )

        fvg = detect_fvg(
            df5
        )

        liquidity = detect_liquidity(
            df5
        )

        volume = volume_anomaly(
            df5
        )

        aligned = (
            r15.direction
            ==
            r5.direction
            and
            r15.direction
            in {
                "BULLISH",
                "BEARISH",
            }
        )

        score = 0.0
        reasons: list[str] = []

        if aligned:
            score += 30
            reasons.append(
                "15m and 5m direction agree."
            )
        else:
            reasons.append(
                "15m and 5m direction are not aligned."
            )

        if (
            r5.momentum_score >= 65
            or
            r5.momentum_score <= 35
        ):

            score += 20

            reasons.append(
                "5m momentum is decisive."
            )

        elif (
            r5.momentum_score >= 55
            or
            r5.momentum_score <= 45
        ):

            score += 8

            reasons.append(
                "5m momentum is moderate."
            )

        if structure_5.get(
            "bos"
        ):

            score += 15

            reasons.append(
                "5m BOS detected."
            )

        elif structure_5.get(
            "choch"
        ):

            score += 10

            reasons.append(
                "5m CHOCH detected."
            )

        if (
            orb.get(
                "status"
            )
            ==
            "CONFIRMED"
        ):

            score += 10

            reasons.append(
                "ORB confirmed: "
                f"{orb.get('breakout')}."
            )

        if fvg.get(
            "found"
        ):

            score += 8

            reasons.append(
                f"{fvg.get('type')} "
                "FVG/imbalance detected."
            )

        if liquidity.get(
            "sweep"
        ):

            score += 10

            reasons.append(
                "Liquidity sweep: "
                f"{liquidity.get('type')}."
            )

        if (
            volume.get(
                "status"
            )
            ==
            "HIGH"
        ):

            score += 7

            reasons.append(
                "High volume expansion."
            )

        elif (
            volume.get(
                "status"
            )
            ==
            "ELEVATED"
        ):

            score += 4

            reasons.append(
                "Elevated volume."
            )

        score = round(
            min(
                score,
                100,
            ),
            2,
        )

        setup = None

        edge = {
            "found": False,
            "eligible": False,
            "reason": "No setup.",
        }

        if (
            aligned
            and
            score >= 55
        ):

            setups = build_setups(
                symbol,
                df5,
                r5,
            )

            if setups:

                setup = setups[0]

                db = load_edge_database()

                edge = find_edge(
                    symbol,
                    setup.strategy,
                    db,
                )

        if setup is None:

            status = "WAIT"

            reason = (
                "No deterministic setup "
                "passed the signal filters."
            )

        elif not edge.get(
            "eligible"
        ):

            status = (
                "WAIT_RESEARCH_EDGE"
            )

            reason = (
                edge.get(
                    "reason",
                    "Research edge not validated.",
                )
            )

        else:

            status = "WATCH_PAPER"

            reason = (
                "Setup passed signal and research gates. "
                "Option and risk gates remain."
            )

        return {
            "symbol": symbol,

            "status": status,

            "reason": reason,

            "score": score,

            "closed_15m": closed15,

            "closed_5m": closed5,

            "15m": {
                "direction":
                    r15.direction,
                "regime":
                    r15.regime,
                "momentum":
                    r15.momentum_score,
                "vwap":
                    r15.vwap_state,
                "ema":
                    r15.ema_state,
                "structure":
                    structure_15.get(
                        "state"
                    ),
            },

            "5m": {
                "direction":
                    r5.direction,
                "regime":
                    r5.regime,
                "momentum":
                    r5.momentum_score,
                "vwap":
                    r5.vwap_state,
                "ema":
                    r5.ema_state,
                "structure":
                    structure_5.get(
                        "state"
                    ),
            },

            "features": {
                "orb": orb,
                "fvg": fvg,
                "liquidity": liquidity,
                "volume": volume,
            },

            "setup": (
                {
                    "symbol":
                        setup.symbol,
                    "strategy":
                        setup.strategy,
                    "direction":
                        setup.direction,
                    "entry":
                        setup.entry,
                    "stop":
                        setup.stop,
                    "target":
                        setup.target,
                    "rr":
                        setup.rr,
                    "score":
                        setup.score,
                    "status":
                        setup.status,
                    "reasons":
                        setup.reasons,
                }
                if setup
                else None
            ),

            "edge":
                edge,

            "live": {
                "ltp":
                    self._ltp(
                        symbol
                    ),
            },

            "bars": {
                "15m":
                    len(df15),
                "5m":
                    len(df5),
            },
        }

    def scan_symbol(
        self,
        symbol: str,
    ) -> dict[str, Any]:

        if self.stream is None:

            return {
                "symbol":
                    symbol,
                "status":
                    "STREAM_UNAVAILABLE",
            }

        store = (
            self.stream.store
        )

        raw15 = store.get_dataframe(
            symbol,
            "15m",
        )

        raw5 = store.get_dataframe(
            symbol,
            "5m",
        )

        df15, closed15 = (
            closed_frame(
                raw15,
                15,
            )
        )

        df5, closed5 = (
            closed_frame(
                raw5,
                5,
            )
        )

        result = self._analyze(
            symbol,
            df15,
            df5,
            closed15,
            closed5,
        )

        self.last_analysis[
            symbol
        ] = result

        return result

    def _closure_keys(
        self,
        symbol: str,
    ) -> tuple[str | None, str | None]:

        if self.stream is None:
            return None, None

        store = (
            self.stream.store
        )

        raw15 = store.get_dataframe(
            symbol,
            "15m",
        )

        raw5 = store.get_dataframe(
            symbol,
            "5m",
        )

        _, closed15 = (
            closed_frame(
                raw15,
                15,
            )
        )

        _, closed5 = (
            closed_frame(
                raw5,
                5,
            )
        )

        return (
            str(closed5)
            if closed5 is not None
            else None,

            str(closed15)
            if closed15 is not None
            else None,
        )

    def _process_events(
        self,
        symbol: str,
    ) -> list[dict[str, Any]]:

        key5, key15 = (
            self._closure_keys(
                symbol
            )
        )

        events = []

        if (
            key5 is not None
            and
            key5
            !=
            self.last_5m_processed.get(
                symbol
            )
        ):

            self.last_5m_processed[
                symbol
            ] = key5

            result = self.scan_symbol(
                symbol
            )

            result = dict(result)

            result[
                "event_type"
            ] = "5M_CLOSED"

            self._event(
                "5M_CLOSED",
                result,
            )

            events.append(
                result
            )

        if (
            key15 is not None
            and
            key15
            !=
            self.last_15m_processed.get(
                symbol
            )
        ):

            self.last_15m_processed[
                symbol
            ] = key15

            result = (
                self.last_analysis.get(
                    symbol
                )
                or
                self.scan_symbol(
                    symbol
                )
            )

            result = dict(
                result
            )

            result[
                "event_type"
            ] = "15M_CLOSED"

            self._event(
                "15M_CLOSED",
                result,
            )

            events.append(
                result
            )

        return events

    def snapshot(self) -> dict[str, Any]:

        return {
            "as_of":
                datetime.now()
                .astimezone()
                .isoformat(),

            "provider":
                "UPSTOX",

            "stream":
                (
                    self.stream.store.diagnostics()
                    if self.stream is not None
                    else {}
                ),

            "market_status":
                self._market_status(),

            "results":
                self.last_analysis,

            "execution": {
                "paper":
                    False,
                "live":
                    False,
            },
        }

    def run_forever(
        self,
    ) -> None:

        if self.auto_start_stream:

            startup = (
                self.start_stream()
            )

            print(
                "JARVIS LIVE MONITOR V7 > "
                f"Stream startup: {startup}"
            )

        self.running = True

        print("=" * 68)

        print(
            "JARVIS TRADING CORE V7 LIVE MONITOR"
        )

        print("=" * 68)

        print(
            "Candle-close aware: ENABLED"
        )

        print(
            "Closed-market historical fallback: ENABLED"
        )

        print(
            "15m = CONTEXT"
        )

        print(
            "5m = TRIGGER"
        )

        print(
            "Auto-start Upstox: ENABLED"
        )

        print(
            "Live orders: DISABLED"
        )

        print(
            "Paper orders: DISABLED"
        )

        print()

        # Prime immediately from the latest completed candles.
        # This means the monitor can show a useful state even while the
        # market is closed.
        for symbol in self.symbols:

            result = self.scan_symbol(
                symbol
            )

            key5, key15 = (
                self._closure_keys(
                    symbol
                )
            )

            self.last_5m_processed[
                symbol
            ] = key5 or ""

            self.last_15m_processed[
                symbol
            ] = key15 or ""

            print(
                f"{symbol} | "
                f"Status={result.get('status')} | "
                f"Score={result.get('score')} | "
                f"LTP={self._ltp(symbol).get('price')} | "
                f"15m={result.get('15m', {}).get('direction')} | "
                f"5m={result.get('5m', {}).get('direction')} | "
                f"Closed5m={result.get('closed_5m')} | "
                f"Closed15m={result.get('closed_15m')}"
            )

        self._save_state(
            self.snapshot()
        )

        while self.running:

            try:

                if self.stream is None:
                    self._load_stream()

                if (
                    self.auto_start_stream
                    and
                    self.stream is not None
                    and
                    not self.stream.store.is_running()
                ):

                    retry = (
                        self.start_stream()
                    )

                    print(
                        "JARVIS LIVE MONITOR V7 > "
                        f"Stream retry: {retry}"
                    )

                for symbol in self.symbols:

                    events = (
                        self._process_events(
                            symbol
                        )
                    )

                    state = (
                        self.last_analysis.get(
                            symbol,
                            {},
                        )
                    )

                    ltp = (
                        self._ltp(
                            symbol
                        )
                    )

                    print(
                        f"{symbol} | "
                        f"Status={state.get('status')} | "
                        f"Score={state.get('score')} | "
                        f"LTP={ltp.get('price')} | "
                        f"15m={state.get('15m', {}).get('direction')} | "
                        f"5m={state.get('5m', {}).get('direction')} | "
                        f"Events={len(events)}"
                    )

                    for event in events:

                        print(
                            "JARVIS EVENT > "
                            f"{symbol} "
                            f"{event.get('event_type')} "
                            f"{event.get('status')} "
                            f"score={event.get('score')}"
                        )

                self._save_state(
                    self.snapshot()
                )

                time.sleep(
                    self.poll_seconds
                )

            except KeyboardInterrupt:

                self.running = False
                break

            except Exception as exc:

                self._event(
                    "MONITOR_ERROR",
                    {
                        "message":
                            str(exc)
                    },
                )

                print(
                    "JARVIS LIVE MONITOR V7 > "
                    f"ERROR: {exc}"
                )

                time.sleep(
                    self.poll_seconds
                )

        self.stop()

    def stop(
        self,
    ) -> None:

        self.running = False

        try:

            if self.stream is not None:
                self.stream.stop()

        except Exception:
            pass


def main() -> None:

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "JARVIS Trading Core V7 "
            "Live Monitor"
        )
    )

    parser.add_argument(
        "--poll",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--no-auto-stream",
        action="store_true",
    )

    args = parser.parse_args()

    monitor = (
        LiveMonitorV7(
            poll_seconds=args.poll,
            auto_start_stream=(
                not args.no_auto_stream
            ),
        )
    )

    monitor.run_forever()


if __name__ == "__main__":
    main()
