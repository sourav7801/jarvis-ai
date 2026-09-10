from __future__ import annotations

from contextlib import contextmanager
import json
import math
import os
import re
import sqlite3
import threading
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from omni.trading_intelligence.backtest_schema import ExecutionCostConfig
from omni.trading_intelligence.cost_model import ExecutionCostModel
from workstation.paper_instrument_accounting import (
    normalized_price_grid,
    quantize_quantity,
    validate_instrument_spec,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("JARVIS_PAPER_DB", str(PROJECT_ROOT / "data/trading/paper_desk.sqlite3"))).expanduser()
DEFAULT_EQUITY = 100000.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _side(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"BUY", "LONG"}:
        return "LONG"
    if normalized in {"SELL", "SHORT"}:
        return "SHORT"
    raise ValueError(f"Unsupported paper side: {value}")


def is_performance_review_request(command: str) -> bool:
    """Return true for natural-language questions about trading outcomes."""

    value = re.sub(r"\s+", " ", str(command or "")).strip().lower()
    review = re.search(
        r"\b(?:analy[sz]e|review|explain|diagnose|check|why|mistakes?|improv(?:e|ing))\b",
        value,
    )
    performance = re.search(
        r"\b(?:loss(?:es|ing)?|losing|profit(?:s|able)?|p\s*&\s*l|pnl|"
        r"win(?:s|ning)?|performance|booked|closed)\b",
        value,
    )
    trading = re.search(
        r"\b(?:trade|trades|trading|position|positions|paper|strategy|strategies)\b",
        value,
    )
    temporal_trade_result = performance and re.search(
        r"\b(?:today|yesterday|daily|session|recent|last)\b", value
    )
    return bool(review and performance and (trading or temporal_trade_result))


@dataclass(frozen=True)
class PaperPosition:
    id: int
    external_id: str | None
    symbol: str
    asset_type: str
    side: str
    quantity: float
    entry: float
    stop: float | None
    target: float | None
    initial_stop: float | None
    exit_policy: dict[str, Any] | None
    mark: float | None
    unrealized_pnl: float
    risk_at_stop: float
    notional: float
    timeframe: str
    strategy: str
    score: float | None
    source: str
    opened_at: str
    native_currency: str
    valuation_currency: str
    contract_multiplier: float
    quantity_step: float
    tick_size: float | None
    cost_model_status: str
    portfolio_bucket: str
    bucket_allocation_fraction: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PaperTradingDesk:
    """Persistent synthetic paper broker for JARVIS.

    This is a research ledger only.  It records simulated positions, marks them
    from read-only market data, computes P&L/risk, and never imports a broker
    order surface.
    """

    def __init__(
        self,
        db_path: Path | str = DB_PATH,
        *,
        starting_equity: float = DEFAULT_EQUITY,
        max_open_positions: int = 8,
        max_total_risk_fraction: float = 0.04,
        max_single_risk_fraction: float = 0.01,
        max_gross_exposure_multiple: float = 2.0,
        max_daily_loss_fraction: float = 0.02,
        max_drawdown_fraction: float = 0.10,
        max_symbol_exposure_fraction: float = 1.00,
        max_asset_class_exposure_fraction: float = 1.50,
        max_strategy_exposure_fraction: float = 1.50,
        max_direction_exposure_fraction: float = 2.00,
        max_correlated_exposure_fraction: float = 1.00,
        correlation_clusters: dict[str, str] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.starting_equity = float(starting_equity)
        self.max_open_positions = int(max_open_positions)
        self.max_total_risk_fraction = float(max_total_risk_fraction)
        self.max_single_risk_fraction = float(max_single_risk_fraction)
        self.max_gross_exposure_multiple = float(max_gross_exposure_multiple)
        self.max_daily_loss_fraction = max(0.0, float(max_daily_loss_fraction))
        self.max_drawdown_fraction = max(0.0, float(max_drawdown_fraction))
        self.max_symbol_exposure_fraction = max(0.0, float(max_symbol_exposure_fraction))
        self.max_asset_class_exposure_fraction = max(0.0, float(max_asset_class_exposure_fraction))
        self.max_strategy_exposure_fraction = max(0.0, float(max_strategy_exposure_fraction))
        self.max_direction_exposure_fraction = max(0.0, float(max_direction_exposure_fraction))
        self.max_correlated_exposure_fraction = max(0.0, float(max_correlated_exposure_fraction))
        self.correlation_clusters = {
            str(symbol).strip().upper(): str(cluster).strip().upper()
            for symbol, cluster in (correlation_clusters or {}).items()
            if str(symbol).strip() and str(cluster).strip()
        }
        self._lock = threading.RLock()
        self._transaction = threading.local()
        self._ensure_schema()

    @property
    def live_execution(self) -> bool:
        return False

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @contextmanager
    def _connection(self):
        # Re-entrant operations (risk snapshot, partials and exits) must share
        # the admission transaction. SQLite, not a process-local RLock, owns
        # cross-process serialization.
        active = getattr(self._transaction, "connection", None)
        if active is not None:
            yield active
            return
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._transaction.connection = connection
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self._transaction.connection = None
            connection.close()

    def _ensure_schema(self) -> None:
        with self._lock, self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    symbol TEXT NOT NULL,
                    asset_type TEXT NOT NULL DEFAULT 'SPOT',
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry REAL NOT NULL,
                    stop REAL,
                    target REAL,
                    timeframe TEXT NOT NULL DEFAULT '',
                    strategy TEXT NOT NULL DEFAULT '',
                    score REAL,
                    source TEXT NOT NULL DEFAULT 'JARVIS',
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    exit_price REAL,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_paper_positions_status
                    ON paper_positions(status);
                CREATE INDEX IF NOT EXISTS idx_paper_positions_symbol
                    ON paper_positions(symbol);
                CREATE TABLE IF NOT EXISTS paper_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_id INTEGER,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS paper_risk_state (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def _event(self, conn: sqlite3.Connection, position_id: int | None, event_type: str, payload: dict[str, Any]) -> None:
        cursor = conn.execute(
            "INSERT INTO paper_events(position_id,event_type,created_at,payload_json) VALUES(?,?,?,?)",
            (position_id, event_type, _now(), json.dumps(payload, default=str, sort_keys=True)),
        )
        if event_type in {"CLOSE", "SCALE_OUT"}:
            from workstation import workspace_accounts as accounts
            if accounts.enabled(conn):
                position = conn.execute("SELECT * FROM paper_positions WHERE id=?", (position_id,)).fetchone()
                meta = self._metadata(position)
                conn.execute("INSERT INTO terminal_orders(workspace,external_id,position_id,status,reason,created_at,payload_json,kind) VALUES(?,?,?,?,?,?,?,?)",
                             (accounts.workspace(meta.get("portfolio_bucket")), f"exit:{position_id}:{cursor.lastrowid}", position_id, "FILLED", payload.get("reason") or meta.get("exit_reason") or event_type, _now(),
                              json.dumps({**payload, "symbol": position["symbol"], "side": "SELL" if position["side"] == "LONG" else "BUY"}, default=str), event_type))

    @staticmethod
    def _pnl(side: str, entry: float, mark: float, quantity: float) -> float:
        direction = 1.0 if side == "LONG" else -1.0
        return (mark - entry) * direction * quantity

    @staticmethod
    def _risk_at_stop(entry: float, stop: float | None, quantity: float, side: str | None = None) -> float:
        if stop is None:
            return 0.0
        distance = (entry - stop) * (1 if side == "LONG" else -1) if side else abs(entry - stop)
        return max(0., distance) * quantity

    def _realized_pnl(self, conn: sqlite3.Connection) -> float:
        """Total booked P&L: closed trades plus partials banked on open ones.

        A scale-out banks cash before the position is flat, so the amount is
        parked in the open row's ``realized_pnl`` column and folded into the
        final figure when the remainder closes.  Summing every row therefore
        counts each leg exactly once.
        """

        row = conn.execute(
            "SELECT COALESCE(SUM(realized_pnl),0) AS pnl FROM paper_positions"
        ).fetchone()
        return _f(row["pnl"] if row else 0.0)

    def _daily_realized_pnl(
        self,
        conn: sqlite3.Connection,
        now: datetime | None = None,
    ) -> float:
        """Booked P&L attributed to the current UTC day.

        This feeds the daily-loss lock, so each leg has to land on the day it
        was actually booked.  Positions carrying a scale-out ledger are
        attributed leg by leg; everything else keeps the original rule of
        attributing the whole trade to its close timestamp, which preserves
        the behaviour for every position opened before partial exits existed.
        """

        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        day_start = current.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        total = 0.0
        for row in conn.execute("SELECT * FROM paper_positions").fetchall():
            metadata = self._metadata(row)
            legs = metadata.get("scale_outs")
            if not isinstance(legs, list) or not legs:
                if str(row["status"]) == "CLOSED" and str(row["closed_at"] or "") >= day_start:
                    total += _f(row["realized_pnl"])
                continue
            for leg in legs:
                if isinstance(leg, dict) and str(leg.get("at") or "") >= day_start:
                    total += _f(leg.get("pnl"))
            if str(row["status"]) == "CLOSED" and str(row["closed_at"] or "") >= day_start:
                total += _f(metadata.get("final_leg_pnl"))
        return total

    @staticmethod
    def _risk_state_value(conn: sqlite3.Connection, key: str, default: float) -> float:
        row = conn.execute(
            "SELECT value_json FROM paper_risk_state WHERE key=?",
            (key,),
        ).fetchone()
        if row is None:
            return float(default)
        try:
            return _f(json.loads(row["value_json"]), default)
        except (TypeError, ValueError, json.JSONDecodeError):
            return float(default)

    @staticmethod
    def _set_risk_state(conn: sqlite3.Connection, key: str, value: float) -> None:
        conn.execute(
            "INSERT INTO paper_risk_state(key,value_json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (key, json.dumps(float(value)), _now()),
        )

    @staticmethod
    def _add_exposure(target: dict[str, float], key: str, value: float) -> None:
        normalized = str(key or "UNSPECIFIED").strip().upper() or "UNSPECIFIED"
        target[normalized] = target.get(normalized, 0.0) + float(value)

    def _open_rows(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return list(
            conn.execute(
                "SELECT * FROM paper_positions WHERE status='OPEN' ORDER BY opened_at ASC"
            ).fetchall()
        )

    def _mark_for_symbol(self, symbol: str, mark_loader: Callable[[str], float | None] | None) -> float | None:
        if mark_loader is None:
            return None
        try:
            value = mark_loader(symbol)
            return float(value) if value is not None else None
        except Exception:
            return None

    @staticmethod
    def _metadata(row: sqlite3.Row) -> dict[str, Any]:
        try:
            value = json.loads(row["metadata_json"] or "{}")
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _accounting(metadata: dict[str, Any]) -> dict[str, Any]:
        spec = metadata.get("instrument_spec") if isinstance(metadata.get("instrument_spec"), dict) else {}
        valuation_multiplier = max(_f(metadata.get("valuation_multiplier"), 1.0), 0.000001)
        contract_multiplier = max(_f(spec.get("contract_multiplier"), 1.0), 0.000001)
        return {
            "valuation_multiplier": valuation_multiplier,
            "contract_multiplier": contract_multiplier,
            "position_multiplier": valuation_multiplier * contract_multiplier,
            "native_currency": str(spec.get("native_currency") or "INR"),
            "valuation_currency": str(spec.get("valuation_currency") or "INR"),
            "quantity_step": max(_f(spec.get("quantity_step"), 1.0), 0.00000001),
            "tick_size": _f(spec.get("tick_size")) or None,
            "cost_model_status": str(metadata.get("cost_model_status") or spec.get("cost_model_status") or "UNCONFIGURED"),
            "entry_fees": max(_f(metadata.get("entry_fees")), 0.0),
            "entry_friction_cost": max(_f(metadata.get("entry_friction_cost")), 0.0),
        }

    def _excursion_metadata(
        self,
        row: sqlite3.Row,
        mark: float,
        *,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Return metadata updated with adverse/favorable synthetic excursions."""

        metadata = self._metadata(row)
        accounting = self._accounting(metadata)
        current_pnl = (
            self._pnl(
                str(row["side"]),
                _f(row["entry"]),
                float(mark),
                _f(row["quantity"]),
            )
            * accounting["position_multiplier"]
            - accounting["entry_fees"]
        )
        initial_trade_risk = max(
            _f(metadata.get("initial_trade_risk")),
            self._risk_at_stop(
                _f(row["entry"]),
                _f(row["stop"]) if row["stop"] is not None else None,
                _f(row["quantity"]),
            )
            * accounting["position_multiplier"],
        )
        metadata["mae_pnl"] = min(_f(metadata.get("mae_pnl")), current_pnl, 0.0)
        metadata["mfe_pnl"] = max(_f(metadata.get("mfe_pnl")), current_pnl, 0.0)
        if initial_trade_risk > 0:
            metadata["mae_r"] = min(_f(metadata.get("mae_r")), current_pnl / initial_trade_risk, 0.0)
            metadata["mfe_r"] = max(_f(metadata.get("mfe_r")), current_pnl / initial_trade_risk, 0.0)
        metadata["initial_trade_risk"] = initial_trade_risk
        metadata["last_mark"] = float(mark)
        metadata["last_mark_at"] = observed_at or _now()
        return metadata

    def snapshot(self, mark_loader: Callable[[str], float | None] | None = None) -> dict[str, Any]:
        # Never perform provider I/O while holding the ledger transaction.
        fetched_marks = {}
        if mark_loader is not None:
            with self._lock, self._connection() as conn:
                symbols = {str(row["symbol"]) for row in self._open_rows(conn)}
            fetched_marks = {symbol: self._mark_for_symbol(symbol, mark_loader) for symbol in symbols}
        with self._lock, self._connection() as conn:
            rows = self._open_rows(conn)
            realized = self._realized_pnl(conn)
            positions: list[PaperPosition] = []
            unrealized = 0.0
            gross = 0.0
            net = 0.0
            risk = 0.0
            symbol_exposure: dict[str, float] = {}
            asset_class_exposure: dict[str, float] = {}
            strategy_exposure: dict[str, float] = {}
            direction_exposure: dict[str, float] = {}
            correlation_cluster_exposure: dict[str, float] = {}
            bucket_exposure: dict[str, float] = {}
            bucket_risk_at_stops: dict[str, float] = {}

            for row in rows:
                row_metadata = self._metadata(row)
                accounting = self._accounting(row_metadata)
                position_multiplier = accounting["position_multiplier"]
                entry = _f(row["entry"])
                quantity = _f(row["quantity"])
                mark = fetched_marks.get(str(row["symbol"]))
                if mark is None:
                    mark = _f(row_metadata.get("last_mark"), entry)
                side = str(row["side"])
                pnl = (
                    self._pnl(side, entry, mark, quantity) * position_multiplier
                    - accounting["entry_fees"]
                )
                notional = abs(mark * quantity) * position_multiplier
                position_risk = self._risk_at_stop(
                    entry,
                    _f(row["stop"]) if row["stop"] is not None else None,
                    quantity,
                    side,
                ) * position_multiplier
                unrealized += pnl
                gross += notional
                net += notional if side == "LONG" else -notional
                risk += position_risk
                symbol = str(row["symbol"])
                asset_type = str(row["asset_type"])
                strategy = str(row["strategy"])
                self._add_exposure(symbol_exposure, symbol, notional)
                self._add_exposure(asset_class_exposure, asset_type, notional)
                self._add_exposure(strategy_exposure, strategy, notional)
                self._add_exposure(direction_exposure, side, notional)
                cluster = self.correlation_clusters.get(symbol.strip().upper())
                if cluster:
                    self._add_exposure(correlation_cluster_exposure, cluster, notional)
                portfolio_bucket = str(
                    row_metadata.get("portfolio_bucket") or "GENERAL"
                ).strip().upper() or "GENERAL"
                bucket_allocation_fraction = max(
                    0.0,
                    min(_f(row_metadata.get("bucket_allocation_fraction"), 1.0), 1.0),
                )
                self._add_exposure(bucket_exposure, portfolio_bucket, notional)
                self._add_exposure(
                    bucket_risk_at_stops, portfolio_bucket, position_risk
                )
                positions.append(
                    PaperPosition(
                        id=int(row["id"]),
                        external_id=row["external_id"],
                        symbol=symbol,
                        asset_type=asset_type,
                        side=side,
                        quantity=quantity,
                        entry=entry,
                        stop=_f(row["stop"]) if row["stop"] is not None else None,
                        target=_f(row["target"]) if row["target"] is not None else None,
                        initial_stop=(
                            entry - _f(row_metadata.get("initial_risk"))
                            if side == "LONG" and _f(row_metadata.get("initial_risk")) > 0
                            else entry + _f(row_metadata.get("initial_risk"))
                            if side == "SHORT" and _f(row_metadata.get("initial_risk")) > 0
                            else _f(row["stop"]) if row["stop"] is not None else None
                        ),
                        exit_policy=(
                            row_metadata.get("exit_policy")
                            if isinstance(row_metadata.get("exit_policy"), dict)
                            else None
                        ),
                        mark=mark,
                        unrealized_pnl=pnl,
                        risk_at_stop=position_risk,
                        notional=notional,
                        timeframe=str(row["timeframe"]),
                        strategy=strategy,
                        score=_f(row["score"]) if row["score"] is not None else None,
                        source=str(row["source"]),
                        opened_at=str(row["opened_at"]),
                        native_currency=accounting["native_currency"],
                        valuation_currency=accounting["valuation_currency"],
                        contract_multiplier=accounting["contract_multiplier"],
                        quantity_step=accounting["quantity_step"],
                        tick_size=accounting["tick_size"],
                        cost_model_status=accounting["cost_model_status"],
                        portfolio_bucket=portfolio_bucket,
                        bucket_allocation_fraction=bucket_allocation_fraction,
                    )
                )

            equity = self.starting_equity + realized + unrealized
            daily_realized = self._daily_realized_pnl(conn)
            daily_total = daily_realized + unrealized
            stored_peak = self._risk_state_value(conn, "peak_equity", self.starting_equity)
            peak_equity = max(stored_peak, equity, self.starting_equity)
            if peak_equity != stored_peak:
                self._set_risk_state(conn, "peak_equity", peak_equity)
            drawdown = max(0.0, peak_equity - equity)
            drawdown_fraction = drawdown / peak_equity if peak_equity > 0 else 0.0
            daily_loss_limit = self.starting_equity * self.max_daily_loss_fraction
            daily_loss_locked = daily_loss_limit > 0 and daily_total <= -daily_loss_limit
            drawdown_locked = self.max_drawdown_fraction > 0 and drawdown_fraction >= self.max_drawdown_fraction
            risk_locks = []
            if daily_loss_locked:
                risk_locks.append("DAILY_LOSS_LOCK")
            if drawdown_locked:
                risk_locks.append("MAX_DRAWDOWN_LOCK")
            if equity <= 0:
                risk_locks.append("EQUITY_DEPLETED_LOCK")
            return {
                "success": True,
                "mode": "PAPER",
                "starting_equity": self.starting_equity,
                "equity": equity,
                "realized_pnl": realized,
                "unrealized_pnl": unrealized,
                "total_pnl": realized + unrealized,
                "gross_exposure": gross,
                "net_exposure": net,
                "risk_at_stops": risk,
                "risk_percent_of_equity": (risk / equity * 100.0) if equity > 0 else 0.0,
                "daily_realized_pnl": daily_realized,
                "daily_total_pnl": daily_total,
                "daily_loss_limit": daily_loss_limit,
                "peak_equity": peak_equity,
                "drawdown": drawdown,
                "drawdown_percent": drawdown_fraction * 100.0,
                "entry_locked": bool(risk_locks),
                "risk_locks": risk_locks,
                "symbol_exposure": symbol_exposure,
                "asset_class_exposure": asset_class_exposure,
                "strategy_exposure": strategy_exposure,
                "direction_exposure": direction_exposure,
                "correlation_cluster_exposure": correlation_cluster_exposure,
                "bucket_exposure": bucket_exposure,
                "bucket_risk_at_stops": bucket_risk_at_stops,
                "correlation_clusters_status": "CONFIGURED" if self.correlation_clusters else "UNCONFIGURED",
                "risk_limits": {
                    "max_single_risk_fraction": self.max_single_risk_fraction,
                    "max_total_risk_fraction": self.max_total_risk_fraction,
                    "max_gross_exposure_multiple": self.max_gross_exposure_multiple,
                    "max_daily_loss_fraction": self.max_daily_loss_fraction,
                    "max_drawdown_fraction": self.max_drawdown_fraction,
                    "max_symbol_exposure_fraction": self.max_symbol_exposure_fraction,
                    "max_asset_class_exposure_fraction": self.max_asset_class_exposure_fraction,
                    "max_strategy_exposure_fraction": self.max_strategy_exposure_fraction,
                    "max_direction_exposure_fraction": self.max_direction_exposure_fraction,
                    "max_correlated_exposure_fraction": self.max_correlated_exposure_fraction,
                },
                "open_count": len(positions),
                "max_open_positions": self.max_open_positions,
                "positions": [item.to_dict() for item in positions],
                "paper_only": True,
                "live_execution": False,
            }

    def open_position(self, **request) -> dict[str, Any]:
        from workstation import workspace_accounts as accounts

        with self._lock, self._connection() as conn:
            controlled = accounts.enabled(conn)
            if not controlled:
                return self._open_position(**request)
            key = request.get("external_id")
            if key:
                existing = conn.execute("SELECT id FROM paper_positions WHERE external_id=?", (key,)).fetchone()
                if existing:
                    return {"success": True, "reason": "ALREADY_RECORDED", "position_id": existing["id"], "paper_only": True, "live_execution": False}
            call, admission = accounts.plan_admission(self, conn, request)
            result = self._open_position(**call) if admission.get("success") else admission
            if admission.get("sizing"):
                result["sizing"] = admission["sizing"]
            conn.execute("INSERT INTO terminal_orders(workspace,external_id,position_id,status,reason,created_at,payload_json) VALUES(?,?,?,?,?,?,?)",
                         (accounts.workspace(request.get("portfolio_bucket")), key, result.get("position_id"),
                          "FILLED" if result.get("success") else "REJECTED", result.get("reason", "UNKNOWN"), _now(),
                          json.dumps({"symbol": request.get("symbol"), "side": request.get("side"), **result}, default=str)))
            return result

    def _open_position(
        self,
        *,
        symbol: str,
        side: str,
        entry: float,
        stop: float | None,
        target: float | None,
        quantity: float | None = None,
        timeframe: str = "5m",
        strategy: str = "QUANT_ENSEMBLE",
        score: float | None = None,
        source: str = "JARVIS_AUTO_PAPER",
        asset_type: str = "SPOT",
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        risk_multiplier: float = 1.0,
        valuation_multiplier: float = 1.0,
        instrument_spec: dict[str, Any] | None = None,
        execution_cost_config: dict[str, Any] | None = None,
        portfolio_bucket: str = "GENERAL",
        bucket_allocation_fraction: float = 1.0,
    ) -> dict[str, Any]:
        symbol = str(symbol or "").strip().upper()
        resolved_side = _side(side)
        entry_value = _f(entry)
        stop_value = _f(stop) if stop is not None else None
        target_value = _f(target) if target is not None else None
        normalized_bucket = str(portfolio_bucket or "GENERAL").strip().upper() or "GENERAL"
        bounded_bucket_fraction = max(
            0.01,
            min(_f(bucket_allocation_fraction, 1.0), 1.0),
        )
        if not symbol or entry_value <= 0:
            return {"success": False, "reason": "INVALID_ENTRY", "paper_only": True, "live_execution": False}

        spec, spec_error = validate_instrument_spec(instrument_spec, asset_type=asset_type)
        if spec_error:
            return {
                "success": False,
                "reason": spec_error,
                "paper_only": True,
                "live_execution": False,
            }
        if spec is not None:
            entry_value, stop_value, target_value = normalized_price_grid(
                side=resolved_side,
                entry=entry_value,
                stop=stop_value,
                target=target_value,
                tick_size=spec.tick_size,
            )

        cost_model = None
        cost_status = spec.cost_model_status if spec is not None else "UNCONFIGURED"
        if execution_cost_config is not None:
            allowed_cost_fields = {
                "brokerage_bps", "exchange_bps", "other_bps", "tax_bps_buy",
                "tax_bps_sell", "fixed_per_order", "per_contract", "slippage_bps", "spread_bps",
            }
            try:
                config = ExecutionCostConfig(
                    **{key: value for key, value in execution_cost_config.items() if key in allowed_cost_fields}
                )
                cost_model = ExecutionCostModel(config)
                cost_status = "CONFIGURED"
            except (TypeError, ValueError):
                return {"success": False, "reason": "INVALID_COST_CONFIG", "paper_only": True, "live_execution": False}

        with self._lock, self._connection() as conn:
            if external_id:
                existing = conn.execute(
                    "SELECT id,status FROM paper_positions WHERE external_id=?",
                    (external_id,),
                ).fetchone()
                if existing:
                    return {
                        "success": True,
                        "reason": "ALREADY_RECORDED",
                        "position_id": int(existing["id"]),
                        "paper_only": True,
                        "live_execution": False,
                    }

            snapshot = self.snapshot()
            if "DAILY_LOSS_LOCK" in snapshot.get("risk_locks", []):
                return {"success": False, "reason": "DAILY_LOSS_LOCK", "paper_only": True, "live_execution": False}
            if "MAX_DRAWDOWN_LOCK" in snapshot.get("risk_locks", []):
                return {"success": False, "reason": "MAX_DRAWDOWN_LOCK", "paper_only": True, "live_execution": False}
            if bool(snapshot.get("entry_locked")):
                return {"success": False, "reason": "PORTFOLIO_ENTRY_LOCKED", "paper_only": True, "live_execution": False}
            if int(snapshot["open_count"]) >= self.max_open_positions:
                return {"success": False, "reason": "MAX_OPEN_POSITIONS", "paper_only": True, "live_execution": False}

            equity = max(_f(snapshot["equity"]), 0.0)
            bounded_risk_multiplier = max(0.1, min(_f(risk_multiplier, 1.0), 1.0))
            risk_budget = equity * self.max_single_risk_fraction * bounded_risk_multiplier
            bounded_valuation_multiplier = max(_f(valuation_multiplier, 1.0), 0.000001)
            contract_multiplier = spec.contract_multiplier if spec is not None else 1.0
            position_multiplier = bounded_valuation_multiplier * contract_multiplier
            per_unit_risk = (
                abs(entry_value - stop_value) * position_multiplier
                if stop_value is not None
                else 0.0
            )

            if quantity is None:
                if per_unit_risk <= 0:
                    return {"success": False, "reason": "STOP_REQUIRED_FOR_SIZING", "paper_only": True, "live_execution": False}
                raw_quantity = max(0.0, risk_budget // per_unit_risk)
                quantity_value = quantize_quantity(raw_quantity, spec.quantity_step if spec is not None else 1.0)
            else:
                quantity_value = quantize_quantity(
                    max(0.0, _f(quantity)), spec.quantity_step if spec is not None else 0.00000001
                )

            if quantity_value <= 0:
                return {"success": False, "reason": "POSITION_SIZE_ZERO", "paper_only": True, "live_execution": False}

            entry_reference = entry_value
            entry_fees = 0.0
            entry_friction_cost = 0.0
            if cost_model is not None:
                entry_execution = cost_model.execution(
                    entry_reference,
                    "buy" if resolved_side == "LONG" else "sell",
                    quantity_value,
                    position_multiplier,
                )
                entry_value = float(entry_execution["fill_price"])
                entry_fees = float(entry_execution["fees"])
                entry_friction_cost = float(entry_execution["friction_cost"])
                per_unit_risk = (
                    abs(entry_value - stop_value) * position_multiplier
                    if stop_value is not None
                    else 0.0
                )

            trade_risk = per_unit_risk * quantity_value + entry_fees
            if trade_risk > risk_budget + 1e-9:
                return {"success": False, "reason": "SINGLE_TRADE_RISK_LIMIT", "paper_only": True, "live_execution": False}

            total_risk_after = _f(snapshot["risk_at_stops"]) + trade_risk
            if equity > 0 and total_risk_after > equity * self.max_total_risk_fraction:
                return {"success": False, "reason": "PORTFOLIO_RISK_LIMIT", "paper_only": True, "live_execution": False}
            bucket_risk = snapshot.get("bucket_risk_at_stops")
            bucket_risk = bucket_risk if isinstance(bucket_risk, dict) else {}
            bucket_risk_after = _f(bucket_risk.get(normalized_bucket)) + trade_risk
            bucket_risk_limit = (
                equity * self.max_total_risk_fraction * bounded_bucket_fraction
            )
            if equity > 0 and bucket_risk_after > bucket_risk_limit + 1e-9:
                return {
                    "success": False,
                    "reason": "BUCKET_RISK_LIMIT",
                    "portfolio_bucket": normalized_bucket,
                    "bucket_risk_limit": bucket_risk_limit,
                    "paper_only": True,
                    "live_execution": False,
                }

            new_notional = abs(entry_value * quantity_value) * position_multiplier
            notional_after = _f(snapshot["gross_exposure"]) + new_notional
            if equity > 0 and notional_after > equity * self.max_gross_exposure_multiple:
                return {"success": False, "reason": "GROSS_EXPOSURE_LIMIT", "paper_only": True, "live_execution": False}
            bucket_exposures = snapshot.get("bucket_exposure")
            bucket_exposures = bucket_exposures if isinstance(bucket_exposures, dict) else {}
            bucket_notional_after = _f(bucket_exposures.get(normalized_bucket)) + new_notional
            bucket_notional_limit = (
                equity * self.max_gross_exposure_multiple * bounded_bucket_fraction
            )
            if equity > 0 and bucket_notional_after > bucket_notional_limit + 1e-9:
                return {
                    "success": False,
                    "reason": "BUCKET_EXPOSURE_LIMIT",
                    "portfolio_bucket": normalized_bucket,
                    "bucket_exposure_limit": bucket_notional_limit,
                    "paper_only": True,
                    "live_execution": False,
                }

            def exposure_after(group: str, key: str) -> float:
                exposures = snapshot.get(group) if isinstance(snapshot.get(group), dict) else {}
                normalized = str(key or "UNSPECIFIED").strip().upper() or "UNSPECIFIED"
                return _f(exposures.get(normalized)) + new_notional

            if (
                equity > 0
                and self.max_symbol_exposure_fraction > 0
                and exposure_after("symbol_exposure", symbol) > equity * self.max_symbol_exposure_fraction
            ):
                return {"success": False, "reason": "MAX_SYMBOL_EXPOSURE", "paper_only": True, "live_execution": False}
            normalized_asset_type = str(asset_type or "SPOT").strip().upper() or "SPOT"
            if (
                equity > 0
                and self.max_asset_class_exposure_fraction > 0
                and exposure_after("asset_class_exposure", normalized_asset_type)
                > equity * self.max_asset_class_exposure_fraction
            ):
                return {"success": False, "reason": "MAX_ASSET_CLASS_EXPOSURE", "paper_only": True, "live_execution": False}
            if (
                equity > 0
                and self.max_strategy_exposure_fraction > 0
                and exposure_after("strategy_exposure", strategy) > equity * self.max_strategy_exposure_fraction
            ):
                return {"success": False, "reason": "MAX_STRATEGY_EXPOSURE", "paper_only": True, "live_execution": False}
            if (
                equity > 0
                and self.max_direction_exposure_fraction > 0
                and exposure_after("direction_exposure", resolved_side) > equity * self.max_direction_exposure_fraction
            ):
                return {"success": False, "reason": "MAX_DIRECTION_EXPOSURE", "paper_only": True, "live_execution": False}
            correlation_cluster = self.correlation_clusters.get(symbol)
            if (
                correlation_cluster
                and equity > 0
                and self.max_correlated_exposure_fraction > 0
                and exposure_after("correlation_cluster_exposure", correlation_cluster)
                > equity * self.max_correlated_exposure_fraction
            ):
                return {"success": False, "reason": "MAX_CORRELATED_EXPOSURE", "paper_only": True, "live_execution": False}

            cursor = conn.execute(
                """
                INSERT INTO paper_positions(
                    external_id,symbol,asset_type,side,quantity,entry,stop,target,
                    timeframe,strategy,score,source,status,opened_at,metadata_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    external_id,
                    symbol,
                    normalized_asset_type,
                    resolved_side,
                    quantity_value,
                    entry_value,
                    stop_value,
                    target_value,
                    str(timeframe or ""),
                    str(strategy or ""),
                    _f(score) if score is not None else None,
                    str(source or "JARVIS"),
                    "OPEN",
                    _now(),
                    json.dumps(
                        {
                            **(metadata or {}),
                            "portfolio_bucket": normalized_bucket,
                            "bucket_allocation_fraction": bounded_bucket_fraction,
                            "valuation_multiplier": bounded_valuation_multiplier,
                            "instrument_spec": spec.to_dict() if spec is not None else None,
                            "position_multiplier": position_multiplier,
                            "entry_reference": entry_reference,
                            "entry_fees": entry_fees,
                            "entry_friction_cost": entry_friction_cost,
                            "initial_risk": abs(entry_value - stop_value) if stop_value is not None else 0.0,
                            "initial_trade_risk": trade_risk,
                            "mae_pnl": 0.0,
                            "mfe_pnl": 0.0,
                            "mae_r": 0.0,
                            "mfe_r": 0.0,
                            "last_mark": entry_value,
                            "last_mark_at": _now(),
                            "execution_cost_config": execution_cost_config,
                            "cost_model_status": cost_status,
                        },
                        default=str,
                        sort_keys=True,
                    ),
                ),
            )
            position_id = int(cursor.lastrowid)
            self._event(
                conn,
                position_id,
                "OPEN",
                {
                    "symbol": symbol,
                    "side": resolved_side,
                    "quantity": quantity_value,
                    "entry": entry_value,
                    "stop": stop_value,
                    "target": target_value,
                    "strategy": strategy,
                    "source": source,
                    "risk_multiplier": bounded_risk_multiplier,
                    "valuation_multiplier": bounded_valuation_multiplier,
                    "contract_multiplier": contract_multiplier,
                    "position_multiplier": position_multiplier,
                    "instrument_spec": spec.to_dict() if spec is not None else None,
                    "entry_reference": entry_reference,
                    "entry_fees": entry_fees,
                    "entry_friction_cost": entry_friction_cost,
                    "cost_model_status": cost_status,
                },
            )

        return {
            "success": True,
            "reason": "PAPER_POSITION_OPENED",
            "position_id": position_id,
            "symbol": symbol,
            "side": resolved_side,
            "quantity": quantity_value,
            "entry": entry_value,
            "stop": stop_value,
            "target": target_value,
            "risk_multiplier": bounded_risk_multiplier,
            "valuation_multiplier": bounded_valuation_multiplier,
            "contract_multiplier": contract_multiplier,
            "position_multiplier": position_multiplier,
            "instrument_spec": spec.to_dict() if spec is not None else None,
            "entry_reference": entry_reference,
            "entry_fees": entry_fees,
            "entry_friction_cost": entry_friction_cost,
            "cost_model_status": cost_status,
            "paper_only": True,
            "live_execution": False,
        }

    def reduce_position(
        self,
        *,
        position_id: int,
        exit_price: float,
        fraction: float,
        reason: str = "PAPER_SCALE_OUT",
    ) -> dict[str, Any]:
        """Bank part of an open position without flattening it.

        This is the partial-exit primitive behind the scale-out ladder.  It
        only ever reduces exposure, it has no live-order surface, and the
        banked cash is parked in the open row's ``realized_pnl`` column so the
        portfolio total and the daily-loss lock both see it immediately.
        Rounding the remainder to the instrument quantity step can leave
        nothing behind, in which case the trade is closed outright rather than
        left as an untradeable dust position.
        """

        exit_value = _f(exit_price)
        if exit_value <= 0:
            return {"success": False, "reason": "INVALID_EXIT", "paper_only": True, "live_execution": False}

        share = _f(fraction)
        if not 0.0 < share < 1.0:
            return {"success": False, "reason": "INVALID_FRACTION", "paper_only": True, "live_execution": False}

        with self._lock, self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM paper_positions WHERE status='OPEN' AND id=?",
                (int(position_id),),
            ).fetchone()
            if row is None:
                return {"success": False, "reason": "NO_OPEN_POSITION", "paper_only": True, "live_execution": False}

            metadata = self._metadata(row)
            accounting = self._accounting(metadata)
            multiplier = accounting["position_multiplier"]
            step = accounting["quantity_step"]
            quantity = _f(row["quantity"])
            if quantity <= 0:
                return {"success": False, "reason": "NO_QUANTITY", "paper_only": True, "live_execution": False}

            # Quantize the requested exit leg, not the remainder. Flooring the
            # remainder implicitly rounded the exit *up* (30 x 34% became 11),
            # over-banking profit and allowing a 0.1-unit request on a 1-unit
            # grid to reduce a full unit. Exposure may only fall by an exact,
            # explicitly requested tradable quantity.
            reduced = quantize_quantity(quantity * share, step)
            if reduced < step:
                return {
                    "success": False,
                    "reason": "SCALE_OUT_BELOW_QUANTITY_STEP",
                    "paper_only": True,
                    "live_execution": False,
                }
            remaining = quantize_quantity(quantity - reduced, step)
            if remaining <= 0:
                return self.close_position(
                    position_id=int(row["id"]),
                    exit_price=exit_value,
                    reason=reason,
                )

            exit_reference = exit_value
            exit_fees = 0.0
            exit_friction_cost = 0.0
            cost_config = metadata.get("execution_cost_config")
            if isinstance(cost_config, dict) and accounting["cost_model_status"] == "CONFIGURED":
                try:
                    model = ExecutionCostModel(ExecutionCostConfig(**cost_config))
                    execution = model.execution(
                        exit_reference,
                        "sell" if str(row["side"]) == "LONG" else "buy",
                        reduced,
                        multiplier,
                    )
                    exit_value = float(execution["fill_price"])
                    exit_fees = float(execution["fees"])
                    exit_friction_cost = float(execution["friction_cost"])
                except (TypeError, ValueError):
                    return {
                        "success": False,
                        "reason": "INVALID_STORED_COST_CONFIG",
                        "paper_only": True,
                        "live_execution": False,
                    }

            # Entry costs follow the quantity out of the door so the remainder
            # is not charged twice for the same fill.
            entry_share = accounting["entry_fees"] * (reduced / quantity)
            friction_share = accounting["entry_friction_cost"] * (reduced / quantity)
            gross_pnl = self._pnl(str(row["side"]), _f(row["entry"]), exit_value, reduced) * multiplier
            leg_pnl = gross_pnl - entry_share - exit_fees
            booked_at = _now()

            initial_trade_risk = _f(metadata.get("initial_trade_risk"))
            metadata["entry_fees"] = max(accounting["entry_fees"] - entry_share, 0.0)
            metadata["entry_friction_cost"] = max(accounting["entry_friction_cost"] - friction_share, 0.0)
            ledger = metadata.get("scale_outs")
            ledger = list(ledger) if isinstance(ledger, list) else []
            ledger.append(
                {
                    "at": booked_at,
                    "reason": str(reason),
                    "fraction": share,
                    "quantity": reduced,
                    "remaining_quantity": remaining,
                    "exit_reference": exit_reference,
                    "exit_price": exit_value,
                    "gross_pnl": gross_pnl,
                    "pnl": leg_pnl,
                    "entry_fees": entry_share,
                    "exit_fees": exit_fees,
                    "exit_friction_cost": exit_friction_cost,
                    "r_multiple": (leg_pnl / initial_trade_risk) if initial_trade_risk > 0 else None,
                }
            )
            metadata["scale_outs"] = ledger
            metadata["scale_out_count"] = len(ledger)
            banked = _f(row["realized_pnl"]) + leg_pnl
            position_symbol = str(row["symbol"])
            position_side = str(row["side"])

            conn.execute(
                "UPDATE paper_positions SET quantity=?,realized_pnl=?,metadata_json=? WHERE id=?",
                (
                    remaining,
                    banked,
                    json.dumps(metadata, default=str, sort_keys=True),
                    int(row["id"]),
                ),
            )
            self._event(
                conn,
                int(row["id"]),
                "SCALE_OUT",
                {
                    "reason": str(reason),
                    "fraction": share,
                    "quantity": reduced,
                    "remaining_quantity": remaining,
                    "exit_price": exit_value,
                    "pnl": leg_pnl,
                    "banked_pnl": banked,
                },
            )

        return {
            "success": True,
            "reason": "PAPER_POSITION_REDUCED",
            "position_id": int(position_id),
            "symbol": position_symbol,
            "side": position_side,
            "quantity": reduced,
            "remaining_quantity": remaining,
            "exit_price": exit_value,
            "pnl": leg_pnl,
            "banked_pnl": banked,
            "paper_only": True,
            "live_execution": False,
        }

    def close_position(
        self,
        *,
        position_id: int | None = None,
        symbol: str | None = None,
        external_id: str | None = None,
        exit_price: float,
        reason: str = "PAPER_EXIT",
    ) -> dict[str, Any]:
        exit_value = _f(exit_price)
        if exit_value <= 0:
            return {"success": False, "reason": "INVALID_EXIT", "paper_only": True, "live_execution": False}

        clauses = ["status='OPEN'"]
        params: list[Any] = []
        if position_id is not None:
            clauses.append("id=?")
            params.append(int(position_id))
        elif external_id:
            clauses.append("external_id=?")
            params.append(str(external_id))
        elif symbol:
            clauses.append("symbol=?")
            params.append(str(symbol).strip().upper())
        else:
            return {"success": False, "reason": "POSITION_SELECTOR_REQUIRED", "paper_only": True, "live_execution": False}

        with self._lock, self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM paper_positions WHERE " + " AND ".join(clauses) + " ORDER BY id LIMIT 1",
                tuple(params),
            ).fetchone()
            if row is None:
                return {"success": False, "reason": "NO_OPEN_POSITION", "paper_only": True, "live_execution": False}

            row_metadata = self._metadata(row)
            accounting = self._accounting(row_metadata)
            position_multiplier = accounting["position_multiplier"]
            exit_reference = exit_value
            exit_fees = 0.0
            exit_friction_cost = 0.0
            cost_config = row_metadata.get("execution_cost_config")
            if isinstance(cost_config, dict) and accounting["cost_model_status"] == "CONFIGURED":
                try:
                    model = ExecutionCostModel(ExecutionCostConfig(**cost_config))
                    execution = model.execution(
                        exit_reference,
                        "sell" if str(row["side"]) == "LONG" else "buy",
                        _f(row["quantity"]),
                        position_multiplier,
                    )
                    exit_value = float(execution["fill_price"])
                    exit_fees = float(execution["fees"])
                    exit_friction_cost = float(execution["friction_cost"])
                except (TypeError, ValueError):
                    return {"success": False, "reason": "INVALID_STORED_COST_CONFIG", "paper_only": True, "live_execution": False}
            gross_pnl = (
                self._pnl(str(row["side"]), _f(row["entry"]), exit_value, _f(row["quantity"]))
                * position_multiplier
            )
            final_leg_pnl = gross_pnl - accounting["entry_fees"] - exit_fees
            # Partial exits already banked cash into this row.  The closed row
            # carries the whole trade so the portfolio total stays a single sum.
            banked_pnl = _f(row["realized_pnl"])
            pnl = final_leg_pnl + banked_pnl
            closed_at = _now()
            final_metadata = self._excursion_metadata(row, exit_value, observed_at=closed_at)
            final_metadata.update(
                {
                    "exit_reference": exit_reference,
                    "exit_price": exit_value,
                    "exit_reason": str(reason),
                    "exit_fees": exit_fees,
                    "exit_friction_cost": exit_friction_cost,
                    "final_leg_pnl": final_leg_pnl,
                    "banked_scale_out_pnl": banked_pnl,
                }
            )
            conn.execute(
                "UPDATE paper_positions SET status='CLOSED',closed_at=?,exit_price=?,realized_pnl=?,metadata_json=? WHERE id=?",
                (
                    closed_at,
                    exit_value,
                    pnl,
                    json.dumps(final_metadata, default=str, sort_keys=True),
                    int(row["id"]),
                ),
            )
            self._event(
                conn,
                int(row["id"]),
                "CLOSE",
                {
                    "exit_reference": exit_reference,
                    "exit_price": exit_value,
                    "gross_pnl": gross_pnl,
                    "entry_fees": accounting["entry_fees"],
                    "exit_fees": exit_fees,
                    "exit_friction_cost": exit_friction_cost,
                    "realized_pnl": pnl,
                    "reason": reason,
                },
            )

        try:
            from omni.trading_intelligence.trade_learning_engine import learning_engine

            learning_engine.record_closed_row(
                row,
                exit_price=exit_value,
                pnl=pnl,
                reason=reason,
            )
        except Exception:
            # Learning telemetry must never block a synthetic paper exit.
            pass

        return {
            "success": True,
            "reason": reason,
            "position_id": int(row["id"]),
            "symbol": str(row["symbol"]),
            "asset_type": str(row["asset_type"]),
            "side": str(row["side"]),
            "quantity": _f(row["quantity"]),
            "entry": _f(row["entry"]),
            "stop": _f(row["stop"]) if row["stop"] is not None else None,
            "target": _f(row["target"]) if row["target"] is not None else None,
            "timeframe": str(row["timeframe"]),
            "strategy": str(row["strategy"]),
            "score": _f(row["score"]) if row["score"] is not None else None,
            "opened_at": str(row["opened_at"]),
            "closed_at": closed_at,
            "metadata": final_metadata,
            "exit_price": exit_value,
            "exit_reference": exit_reference,
            "gross_pnl": gross_pnl,
            "entry_fees": accounting["entry_fees"],
            "exit_fees": exit_fees,
            "exit_friction_cost": exit_friction_cost,
            "realized_pnl": pnl,
            "mae_pnl": _f(final_metadata.get("mae_pnl")),
            "mfe_pnl": _f(final_metadata.get("mfe_pnl")),
            "mae_r": _f(final_metadata.get("mae_r")),
            "mfe_r": _f(final_metadata.get("mfe_r")),
            "paper_only": True,
            "live_execution": False,
        }

    def evaluate_stops_targets(self, marks: dict[str, float]) -> list[dict[str, Any]]:
        closed: list[dict[str, Any]] = []
        with self._lock, self._connection() as conn:
            rows = self._open_rows(conn)
        for row in rows:
            symbol = str(row["symbol"])
            mark = marks.get(symbol)
            if mark is None:
                continue
            side = str(row["side"])
            stop = _f(row["stop"]) if row["stop"] is not None else None
            target = _f(row["target"]) if row["target"] is not None else None
            reason = None
            if side == "LONG":
                if stop is not None and mark <= stop:
                    reason = "STOP_HIT"
                elif target is not None and mark >= target:
                    reason = "TARGET_HIT"
            else:
                if stop is not None and mark >= stop:
                    reason = "STOP_HIT"
                elif target is not None and mark <= target:
                    reason = "TARGET_HIT"
            if reason:
                # Stops use the observed mark so a gap through the level is
                # never given an unrealistically better fill.  Targets fill at
                # the resting target reference so a polling gap cannot invent
                # favorable price improvement.
                exit_price = mark if reason == "STOP_HIT" else float(target)
                closed.append(
                    self.close_position(
                        position_id=int(row["id"]),
                        exit_price=exit_price,
                        reason=reason,
                    )
                )
        return closed

    def manage_positions(
        self,
        marks: dict[str, float],
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        # Keep rung bookkeeping, partial reductions and full exits in one
        # transaction so a crash cannot acknowledge an unexecuted scale-out.
        with self._lock, self._connection():
            return self._manage_positions(marks, now=now)

    def _manage_positions(
        self, marks: dict[str, float], *, now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Apply bounded synthetic exit policy, then fixed stop/target checks.

        Exit policy is opt-in through position metadata.  It may only reduce
        risk: move a stop to breakeven, trail it in the favorable direction,
        or close after an explicit maximum hold.  It cannot widen a stop and
        has no live-order surface.
        """

        current_time = now or datetime.now(timezone.utc)
        timed_out: list[tuple[int, float]] = []
        scale_outs: list[tuple[int, float, float, str]] = []
        with self._lock, self._connection() as conn:
            rows = self._open_rows(conn)
            for row in rows:
                metadata = self._metadata(row)
                symbol = str(row["symbol"])
                mark = _f(marks.get(symbol))
                if mark <= 0:
                    continue
                metadata = self._excursion_metadata(
                    row,
                    mark,
                    observed_at=current_time.astimezone(timezone.utc).isoformat(),
                )
                conn.execute(
                    "UPDATE paper_positions SET metadata_json=? WHERE id=?",
                    (json.dumps(metadata, default=str, sort_keys=True), int(row["id"])),
                )
                policy = metadata.get("exit_policy") if isinstance(metadata.get("exit_policy"), dict) else None
                if not policy:
                    continue
                entry = _f(row["entry"])
                stop = _f(row["stop"]) if row["stop"] is not None else None
                if stop is None or entry <= 0:
                    continue
                original_risk = _f(metadata.get("initial_risk"), abs(entry - stop))
                if original_risk <= 0:
                    continue
                side = str(row["side"])
                favorable_r = ((mark - entry) if side == "LONG" else (entry - mark)) / original_risk
                candidate_stop = stop
                breakeven_at = max(_f(policy.get("breakeven_at_r"), 1.0), 0.0)
                trailing_at = max(_f(policy.get("trailing_at_r"), 1.5), breakeven_at)
                trail_distance = max(_f(policy.get("trailing_distance_r"), 0.75), 0.1)
                if favorable_r >= breakeven_at:
                    candidate_stop = max(candidate_stop, entry) if side == "LONG" else min(candidate_stop, entry)
                if favorable_r >= trailing_at:
                    trail = mark - original_risk * trail_distance if side == "LONG" else mark + original_risk * trail_distance
                    candidate_stop = max(candidate_stop, trail) if side == "LONG" else min(candidate_stop, trail)
                risk_reduced = candidate_stop > stop if side == "LONG" else candidate_stop < stop
                if risk_reduced:
                    conn.execute("UPDATE paper_positions SET stop=? WHERE id=?", (candidate_stop, int(row["id"])))
                    self._event(
                        conn,
                        int(row["id"]),
                        "STOP_ADJUSTED",
                        {"old_stop": stop, "new_stop": candidate_stop, "mark": mark, "favorable_r": favorable_r},
                    )

                # Trailing target.  A fixed target caps a runner at its planned
                # R multiple, so once price trades through it the objective is
                # pushed further out instead of harvesting the move.  This is
                # only allowed while the stop already sits at or beyond
                # breakeven, which keeps the worst case bounded and monotonically
                # improving even though the position is held longer.
                trailing_target_r = max(_f(policy.get("trailing_target_r")), 0.0)
                target = _f(row["target"]) if row["target"] is not None else None
                if trailing_target_r > 0 and target is not None and target > 0:
                    protected = (
                        candidate_stop >= entry if side == "LONG" else candidate_stop <= entry
                    )
                    reached = mark >= target if side == "LONG" else mark <= target
                    if protected and reached:
                        extended = (
                            mark + original_risk * trailing_target_r
                            if side == "LONG"
                            else mark - original_risk * trailing_target_r
                        )
                        widened = extended > target if side == "LONG" else extended < target
                        if widened:
                            conn.execute(
                                "UPDATE paper_positions SET target=? WHERE id=?",
                                (extended, int(row["id"])),
                            )
                            self._event(
                                conn,
                                int(row["id"]),
                                "TARGET_EXTENDED",
                                {
                                    "old_target": target,
                                    "new_target": extended,
                                    "mark": mark,
                                    "favorable_r": favorable_r,
                                },
                            )

                # Scale-out ladder.  Each rung fires at most once, tracked by
                # rung index in metadata so a restart cannot double-book it.
                ladder = policy.get("scale_out")
                if isinstance(ladder, list) and ladder:
                    fired = metadata.get("scale_out_fired")
                    fired = {int(item) for item in fired if isinstance(item, (int, float))} if isinstance(fired, list) else set()
                    fired_now = False
                    for index, rung in enumerate(ladder):
                        if index in fired or not isinstance(rung, dict):
                            continue
                        at_r = _f(rung.get("at_r"))
                        fraction = _f(rung.get("fraction"))
                        if at_r <= 0 or not 0.0 < fraction < 1.0:
                            continue
                        if favorable_r >= at_r:
                            fired.add(index)
                            fired_now = True
                            scale_outs.append(
                                (
                                    int(row["id"]),
                                    mark,
                                    fraction,
                                    f"PAPER_SCALE_OUT_{at_r:g}R",
                                )
                            )
                    if fired:
                        metadata["scale_out_fired"] = sorted(fired)
                        conn.execute(
                            "UPDATE paper_positions SET metadata_json=? WHERE id=?",
                            (
                                json.dumps(metadata, default=str, sort_keys=True),
                                int(row["id"]),
                            ),
                        )
                    # If a scale-out deliberately banks profit at the original
                    # target, retain the remaining runner behind the already
                    # protected stop. Otherwise the subsequent fixed-target
                    # sweep would flatten it on the same mark and defeat the
                    # ladder. The extension is one original R by default and
                    # can be configured through runner_target_r.
                    target = _f(row["target"]) if row["target"] is not None else None
                    protected = (
                        candidate_stop >= entry if side == "LONG" else candidate_stop <= entry
                    )
                    target_reached = bool(
                        target is not None
                        and target > 0
                        and (mark >= target if side == "LONG" else mark <= target)
                    )
                    if fired_now and protected and target_reached and trailing_target_r <= 0:
                        runner_target_r = max(_f(policy.get("runner_target_r"), 1.0), 0.25)
                        extended = (
                            mark + original_risk * runner_target_r
                            if side == "LONG"
                            else mark - original_risk * runner_target_r
                        )
                        conn.execute(
                            "UPDATE paper_positions SET target=? WHERE id=?",
                            (extended, int(row["id"])),
                        )
                        self._event(
                            conn,
                            int(row["id"]),
                            "RUNNER_TARGET_EXTENDED",
                            {
                                "old_target": target,
                                "new_target": extended,
                                "mark": mark,
                                "favorable_r": favorable_r,
                            },
                        )

                max_hold_minutes = _f(policy.get("max_hold_minutes"), 0.0)
                if max_hold_minutes > 0:
                    try:
                        opened_at = datetime.fromisoformat(str(row["opened_at"]))
                        if opened_at.tzinfo is None:
                            opened_at = opened_at.replace(tzinfo=timezone.utc)
                    except ValueError:
                        opened_at = current_time
                    if current_time >= opened_at + timedelta(minutes=max_hold_minutes):
                        timed_out.append((int(row["id"]), mark))

        # Bank partials before any full exit so a rung that triggered on this
        # same tick is not swallowed by the stop/target sweep below.
        reduced = [
            self.reduce_position(
                position_id=position_id,
                exit_price=mark,
                fraction=fraction,
                reason=reason,
            )
            for position_id, mark, fraction, reason in scale_outs
        ]

        closed = [
            self.close_position(position_id=position_id, exit_price=mark, reason="TIME_STOP")
            for position_id, mark in timed_out
        ]
        closed.extend(self.evaluate_stops_targets(marks))
        closed.extend(
            item
            for item in reduced
            if item.get("success") and item.get("reason") != "PAPER_POSITION_REDUCED"
        )
        return closed

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 200))
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_events ORDER BY id DESC LIMIT ?",
                (bounded,),
            ).fetchall()
        result = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except Exception:
                payload = {}
            result.append(
                {
                    "id": int(row["id"]),
                    "position_id": row["position_id"],
                    "event_type": str(row["event_type"]),
                    "created_at": str(row["created_at"]),
                    "payload": payload,
                }
            )
        return result

    def closed_positions(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 200))
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_positions WHERE status='CLOSED' ORDER BY id DESC LIMIT ?",
                (bounded,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            metadata = self._metadata(row)
            accounting = self._accounting(metadata)
            result.append(
                {
                    "id": int(row["id"]),
                    "external_id": row["external_id"],
                    "symbol": str(row["symbol"]),
                    "asset_type": str(row["asset_type"]),
                    "side": str(row["side"]),
                    "quantity": _f(row["quantity"]),
                    "entry": _f(row["entry"]),
                    "stop": _f(row["stop"]) if row["stop"] is not None else None,
                    "target": _f(row["target"]) if row["target"] is not None else None,
                    "exit_price": _f(row["exit_price"]) if row["exit_price"] is not None else None,
                    "realized_pnl": _f(row["realized_pnl"]),
                    "timeframe": str(row["timeframe"]),
                    "strategy": str(row["strategy"]),
                    "score": _f(row["score"]) if row["score"] is not None else None,
                    "source": str(row["source"]),
                    "opened_at": str(row["opened_at"]),
                    "closed_at": str(row["closed_at"] or ""),
                    "native_currency": accounting["native_currency"],
                    "valuation_currency": accounting["valuation_currency"],
                    "contract_multiplier": accounting["contract_multiplier"],
                    "cost_model_status": accounting["cost_model_status"],
                    "mae_pnl": _f(metadata.get("mae_pnl")),
                    "mfe_pnl": _f(metadata.get("mfe_pnl")),
                    "mae_r": _f(metadata.get("mae_r")),
                    "mfe_r": _f(metadata.get("mfe_r")),
                    "exit_reason": str(metadata.get("exit_reason") or ""),
                    "metadata": metadata,
                }
            )
        return result

    def performance_review(
        self,
        *,
        days: int = 2,
        timezone_name: str = "Asia/Kolkata",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Explain recent outcomes from this desk's durable trade ledger.

        This is deliberately descriptive, not a self-authorized strategy
        mutation.  It exposes the evidence needed by bounded learning and by
        the user: stops, excursions, contradictions, regime compatibility and
        whether the risk-reducing trailing policy actually activated.
        """

        bounded_days = max(1, min(int(days), 31))
        zone = ZoneInfo(timezone_name)
        current = (now or datetime.now(timezone.utc)).astimezone(zone)
        requested_dates = {
            (current - timedelta(days=offset)).date().isoformat()
            for offset in range(bounded_days)
        }
        rows = []
        for trade in self.closed_positions(200):
            try:
                closed = datetime.fromisoformat(str(trade.get("closed_at") or "").replace("Z", "+00:00"))
                if closed.tzinfo is None:
                    closed = closed.replace(tzinfo=timezone.utc)
                local_date = closed.astimezone(zone).date().isoformat()
            except ValueError:
                continue
            if local_date not in requested_dates:
                continue
            metadata = trade.get("metadata") if isinstance(trade.get("metadata"), dict) else {}
            contradictions = metadata.get("contradictions") if isinstance(metadata.get("contradictions"), list) else []
            evidence = metadata.get("evidence_graph") if isinstance(metadata.get("evidence_graph"), list) else []
            incompatible = sum(1 for item in evidence if isinstance(item, dict) and item.get("regime_compatible") is False)
            initial_risk = max(_f(metadata.get("initial_trade_risk")), 0.0)
            realized = _f(trade.get("realized_pnl"))
            mfe_r = _f(trade.get("mfe_r"))
            exit_policy = metadata.get("exit_policy") if isinstance(metadata.get("exit_policy"), dict) else {}
            trailing_at = _f(exit_policy.get("trailing_at_r"), 0.0)
            rows.append(
                {
                    "date": local_date,
                    "id": trade.get("id"),
                    "symbol": trade.get("symbol"),
                    "side": trade.get("side"),
                    "timeframe": trade.get("timeframe"),
                    "strategy": trade.get("strategy"),
                    "score": trade.get("score"),
                    "realized_pnl": realized,
                    "outcome": "WIN" if realized > 0 else "LOSS" if realized < 0 else "FLAT",
                    "r_multiple": realized / initial_risk if initial_risk > 0 else None,
                    "mae_r": _f(trade.get("mae_r")),
                    "mfe_r": mfe_r,
                    "exit_reason": trade.get("exit_reason"),
                    "regime": metadata.get("regime"),
                    "contradiction_count": len(contradictions),
                    "regime_incompatible_evidence": incompatible,
                    "trailing_policy": exit_policy or None,
                    "trailing_activated": bool(trailing_at > 0 and mfe_r >= trailing_at),
                    "patterns": metadata.get("chart_patterns") or [],
                }
            )

        daily = []
        for day in sorted(requested_dates, reverse=True):
            trades = [item for item in rows if item["date"] == day]
            daily.append(
                {
                    "date": day,
                    "trades": len(trades),
                    "wins": sum(item["outcome"] == "WIN" for item in trades),
                    "losses": sum(item["outcome"] == "LOSS" for item in trades),
                    "net_pnl": sum(_f(item["realized_pnl"]) for item in trades),
                }
            )
        losses = [item for item in rows if item["outcome"] == "LOSS"]
        findings: list[str] = []
        if losses:
            range_losses = sum("RANGE" in str(item.get("regime") or "").upper() for item in losses)
            conflict_losses = sum(int(item.get("contradiction_count") or 0) > 0 for item in losses)
            incompatible_losses = sum(int(item.get("regime_incompatible_evidence") or 0) > 0 for item in losses)
            low_score_losses = sum(_f(item.get("score")) < 68.0 for item in losses)
            missed_trailing = sum(
                _f(item.get("mfe_r")) > 0
                and not bool(item.get("trailing_activated"))
                for item in losses
            )
            if range_losses:
                findings.append(f"{range_losses}/{len(losses)} losses were opened while the recorded regime was range/mixed")
            if incompatible_losses:
                findings.append(f"{incompatible_losses}/{len(losses)} losses included regime-incompatible strategy evidence")
            if conflict_losses:
                findings.append(f"{conflict_losses}/{len(losses)} losses contained opposing strategy votes")
            if low_score_losses:
                findings.append(f"{low_score_losses}/{len(losses)} losses entered below a 68 score")
            if missed_trailing:
                findings.append(f"{missed_trailing}/{len(losses)} losses had favorable excursion but never reached the trailing trigger")
        return {
            "success": True,
            "timezone": timezone_name,
            "days": daily,
            "trades": rows,
            "findings": findings,
            "paper_only": True,
            "live_execution": False,
            "generated_at": _now(),
        }


def live_mark_loader(symbol: str) -> float | None:
    certificate = live_mark_snapshot(symbol)
    return float(certificate["mark"]) if certificate.get("eligible_for_entry") else None


def live_mark_snapshot(symbol: str, *, stale_after_seconds: float = 30.0) -> dict[str, Any]:
    """Exchange and receive timestamps both qualify read-only marks."""
    from workstation.terminal_data import quote_certificate
    from workstation.quant_terminal_v2 import live_payload
    try:
        if re.fullmatch(r"(?:NSE|BSE|MCX):[A-Z0-9._-]+(?:CE|PE)", symbol):
            from workstation.option_chart_data import option_live
            payload = option_live("FYERS", symbol)
        else:
            payload = live_payload(symbol)
        return quote_certificate(symbol, payload, max_age=stale_after_seconds)
    except Exception as exc:
        return {"success": False, "symbol": symbol, "mark": None,
                "verified": False, "stale": True, "eligible_for_exit": False,
                "eligible_for_entry": False, "reason": "MARK_UNAVAILABLE:" + type(exc).__name__,
                "paper_only": True, "live_execution": False}


def portfolio_payload() -> dict[str, Any]:
    return paper_desk.snapshot(mark_loader=live_mark_loader)


def paper_dashboard_payload() -> dict[str, Any]:
    autonomy: dict[str, Any]
    try:
        request = urllib.request.Request(
            "http://127.0.0.1:8787/api/paper/autonomy",
            headers={"User-Agent": "JARVIS-Master-Paper-Telemetry/1.0"},
        )
        with urllib.request.urlopen(request, timeout=1.5) as response:
            autonomy = json.loads(response.read(500_000).decode("utf-8"))
        if autonomy.get("paper_only") is not True or autonomy.get("live_execution") is not False:
            raise RuntimeError("Quant autonomy safety contract was invalid")
        autonomy = {**autonomy, "telemetry_source": "QUANT_SERVICE_8787"}
    except Exception as exc:
        from workstation.paper_autonomy_engine import paper_autonomy

        autonomy = {
            **paper_autonomy.status(),
            "telemetry_source": "MASTER_LOCAL_FALLBACK",
            "telemetry_warning": f"QUANT_TELEMETRY_UNAVAILABLE:{type(exc).__name__}",
        }

    try:
        from workstation.defined_risk_options_paper_desk import DEFINED_RISK_OPTIONS_DESK
        from workstation.options_paper_autonomy import OPTIONS_PAPER_AUTONOMY

        option_spreads = DEFINED_RISK_OPTIONS_DESK.snapshot()
        option_autonomy = OPTIONS_PAPER_AUTONOMY.status()
    except Exception as exc:
        option_spreads = {
            "positions": [], "open_count": 0, "paper_only": True,
            "live_execution": False, "status": f"UNAVAILABLE:{type(exc).__name__}",
        }
        option_autonomy = {
            "processed": 0, "opened": 0, "rejections": {}, "paper_only": True,
            "live_execution": False, "status": f"UNAVAILABLE:{type(exc).__name__}",
        }

    return {
        "success": True,
        "portfolio": portfolio_payload(),
        "closed_positions": paper_desk.closed_positions(50),
        "events": paper_desk.recent_events(80),
        "autonomy": autonomy,
        "defined_risk_option_spreads": option_spreads,
        "options_paper_autonomy": option_autonomy,
        "paper_only": True,
        "live_execution": False,
        "generated_at": _now(),
    }


def format_portfolio(payload: dict[str, Any]) -> str:
    positions = list(payload.get("positions") or [])
    lines = [
        "JARVIS PAPER TRADING PORTFOLIO",
        "--------------------------------------------------",
        f"Paper Equity: {float(payload.get('equity') or 0):,.2f}",
        f"Total P&L: {float(payload.get('total_pnl') or 0):+,.2f}",
        f"Realized P&L: {float(payload.get('realized_pnl') or 0):+,.2f}",
        f"Unrealized P&L: {float(payload.get('unrealized_pnl') or 0):+,.2f}",
        f"Daily P&L: {float(payload.get('daily_total_pnl') or 0):+,.2f}",
        f"Drawdown: {float(payload.get('drawdown') or 0):,.2f} ({float(payload.get('drawdown_percent') or 0):.2f}%)",
        f"Gross Exposure: {float(payload.get('gross_exposure') or 0):,.2f}",
        f"Risk at Stops: {float(payload.get('risk_at_stops') or 0):,.2f} ({float(payload.get('risk_percent_of_equity') or 0):.2f}%)",
        f"Open Positions: {int(payload.get('open_count') or 0)} / {int(payload.get('max_open_positions') or 0)}",
        f"Entry Risk Locks: {', '.join(payload.get('risk_locks') or []) or 'NONE'}",
        "",
    ]
    if not positions:
        lines.append("No open paper positions.")
    else:
        lines.append("OPEN POSITIONS")
        for item in positions:
            lines.append(
                f"- {item.get('symbol')} {item.get('side')} qty={float(item.get('quantity') or 0):g} "
                f"entry={float(item.get('entry') or 0):,.2f} mark={float(item.get('mark') or 0):,.2f} "
                f"P&L={float(item.get('unrealized_pnl') or 0):+,.2f} risk={float(item.get('risk_at_stop') or 0):,.2f}"
            )
    lines.extend(["", "Synthetic paper account only. Live broker execution remains locked."])
    return "\n".join(lines)


_PAPER_PORTFOLIO_RE = re.compile(
    r"\b(?:paper\s+(?:trading\s+)?(?:portfolio|positions?|p\s*(?:&|and)?\s*l|pnl|risk|exposure)|"
    r"my\s+paper\s+(?:trading\s+)?positions?|current\s+paper\s+(?:trading\s+)?portfolio)\b",
    flags=re.IGNORECASE,
)
_PAPER_OPEN_RE = re.compile(
    r"\b(?:open|show|launch|start)\s+(?:the\s+)?(?:paper\s+trading|paper\s+desk|paper\s+trading\s+terminal)\b",
    flags=re.IGNORECASE,
)
_AUTO_START_RE = re.compile(
    r"\b(?:start|enable|run|turn\s+on)\s+(?:autonomous|automatic|auto)\s+paper\s+trading\b|\bauto\s+paper\s+trading\s+on\b",
    flags=re.IGNORECASE,
)
_AUTO_STOP_RE = re.compile(
    r"\b(?:stop|disable|turn\s+off)\s+(?:autonomous|automatic|auto)\s+paper\s+trading\b|\bauto\s+paper\s+trading\s+off\b",
    flags=re.IGNORECASE,
)
_AUTO_STATUS_RE = re.compile(
    r"\b(?:autonomous|automatic|auto)\s+paper\s+trading\s+(?:status|state)\b",
    flags=re.IGNORECASE,
)


def paper_command_kind(text: str) -> str | None:
    value = str(text or "").strip()
    if _AUTO_STOP_RE.search(value):
        return "AUTO_STOP"
    if _AUTO_START_RE.search(value):
        return "AUTO_START"
    if _AUTO_STATUS_RE.search(value):
        return "AUTO_STATUS"
    if _PAPER_PORTFOLIO_RE.search(value):
        return "PORTFOLIO"
    if _PAPER_OPEN_RE.search(value):
        return "OPEN_DESK"
    return None


def paper_command_payload(text: str) -> dict[str, Any] | None:
    kind = paper_command_kind(text)
    if kind is None:
        return None

    if kind in {"AUTO_START", "AUTO_STOP", "AUTO_STATUS"}:
        if kind == "AUTO_START":
            from workstation.morning_trading_coordinator import start_morning_paper_workflow

            workflow = start_morning_paper_workflow()
            auto = dict(workflow.get("autonomy") or {})
            controller = dict(workflow.get("paper_portfolio_controller") or {})
            speech = str(
                workflow.get("speech")
                or "All-day paper trading started across the governed multi-asset universe."
            )
        elif kind == "AUTO_STOP":
            from workstation.paper_portfolio_controller import paper_portfolio_controller

            controller = paper_portfolio_controller.stop()
            auto = dict(controller.get("mandates", {}).get("INTRADAY") or {})
            speech = (
                "All-day paper trading stopped across intraday, swing and investment mandates. "
                "Existing paper positions remain visible."
            )
        else:
            from workstation.paper_portfolio_controller import paper_portfolio_controller

            controller = paper_portfolio_controller.status()
            auto = dict(controller.get("mandates", {}).get("INTRADAY") or {})
            speech = (
                f"All-day paper trading is {'RUNNING' if controller.get('running') else 'STOPPED'}. "
                f"Scans={auto.get('scan_cycles', 0)}, opens={auto.get('positions_opened', 0)}, closes={auto.get('positions_closed', 0)}."
            )
        portfolio = portfolio_payload()
        return {
            "action": kind.lower(),
            "speech": speech,
            "autonomy": auto,
            "paper_portfolio_controller": controller,
            "portfolio": portfolio,
            "paper_only": True,
            "live_execution": False,
        }

    portfolio = portfolio_payload()
    if kind == "OPEN_DESK":
        speech = "Paper Trading Desk opened. " + format_portfolio(portfolio)
        action = "open_paper_desk"
    else:
        speech = format_portfolio(portfolio)
        action = "paper_portfolio"

    return {
        "action": action,
        "speech": speech,
        "portfolio": portfolio,
        "paper_only": True,
        "live_execution": False,
    }


paper_desk = PaperTradingDesk()
