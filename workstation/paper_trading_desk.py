from __future__ import annotations

from contextlib import contextmanager
import json
import re
import sqlite3
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "trading" / "paper_desk.sqlite3"
DEFAULT_EQUITY = 100000.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if number == number else default
    except (TypeError, ValueError):
        return default


def _side(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"BUY", "LONG"}:
        return "LONG"
    if normalized in {"SELL", "SHORT"}:
        return "SHORT"
    raise ValueError(f"Unsupported paper side: {value}")


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
    mark: float | None
    unrealized_pnl: float
    risk_at_stop: float
    notional: float
    timeframe: str
    strategy: str
    score: float | None
    source: str
    opened_at: str

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
    ) -> None:
        self.db_path = Path(db_path)
        self.starting_equity = float(starting_equity)
        self.max_open_positions = int(max_open_positions)
        self.max_total_risk_fraction = float(max_total_risk_fraction)
        self.max_single_risk_fraction = float(max_single_risk_fraction)
        self.max_gross_exposure_multiple = float(max_gross_exposure_multiple)
        self._lock = threading.RLock()
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
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
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
                """
            )

    def _event(self, conn: sqlite3.Connection, position_id: int | None, event_type: str, payload: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO paper_events(position_id,event_type,created_at,payload_json) VALUES(?,?,?,?)",
            (position_id, event_type, _now(), json.dumps(payload, default=str, sort_keys=True)),
        )

    @staticmethod
    def _pnl(side: str, entry: float, mark: float, quantity: float) -> float:
        direction = 1.0 if side == "LONG" else -1.0
        return (mark - entry) * direction * quantity

    @staticmethod
    def _risk_at_stop(entry: float, stop: float | None, quantity: float) -> float:
        if stop is None:
            return 0.0
        return abs(entry - stop) * quantity

    def _realized_pnl(self, conn: sqlite3.Connection) -> float:
        row = conn.execute(
            "SELECT COALESCE(SUM(realized_pnl),0) AS pnl FROM paper_positions WHERE status='CLOSED'"
        ).fetchone()
        return _f(row["pnl"] if row else 0.0)

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

    def snapshot(self, mark_loader: Callable[[str], float | None] | None = None) -> dict[str, Any]:
        with self._lock, self._connection() as conn:
            rows = self._open_rows(conn)
            realized = self._realized_pnl(conn)
            positions: list[PaperPosition] = []
            unrealized = 0.0
            gross = 0.0
            net = 0.0
            risk = 0.0

            for row in rows:
                entry = _f(row["entry"])
                quantity = _f(row["quantity"])
                mark = self._mark_for_symbol(str(row["symbol"]), mark_loader)
                if mark is None:
                    mark = entry
                side = str(row["side"])
                pnl = self._pnl(side, entry, mark, quantity)
                notional = abs(mark * quantity)
                position_risk = self._risk_at_stop(
                    entry,
                    _f(row["stop"]) if row["stop"] is not None else None,
                    quantity,
                )
                unrealized += pnl
                gross += notional
                net += notional if side == "LONG" else -notional
                risk += position_risk
                positions.append(
                    PaperPosition(
                        id=int(row["id"]),
                        external_id=row["external_id"],
                        symbol=str(row["symbol"]),
                        asset_type=str(row["asset_type"]),
                        side=side,
                        quantity=quantity,
                        entry=entry,
                        stop=_f(row["stop"]) if row["stop"] is not None else None,
                        target=_f(row["target"]) if row["target"] is not None else None,
                        mark=mark,
                        unrealized_pnl=pnl,
                        risk_at_stop=position_risk,
                        notional=notional,
                        timeframe=str(row["timeframe"]),
                        strategy=str(row["strategy"]),
                        score=_f(row["score"]) if row["score"] is not None else None,
                        source=str(row["source"]),
                        opened_at=str(row["opened_at"]),
                    )
                )

            equity = self.starting_equity + realized + unrealized
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
                "open_count": len(positions),
                "max_open_positions": self.max_open_positions,
                "positions": [item.to_dict() for item in positions],
                "paper_only": True,
                "live_execution": False,
            }

    def open_position(
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
    ) -> dict[str, Any]:
        symbol = str(symbol or "").strip().upper()
        resolved_side = _side(side)
        entry_value = _f(entry)
        stop_value = _f(stop) if stop is not None else None
        target_value = _f(target) if target is not None else None
        if not symbol or entry_value <= 0:
            return {"success": False, "reason": "INVALID_ENTRY", "paper_only": True, "live_execution": False}

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
            if int(snapshot["open_count"]) >= self.max_open_positions:
                return {"success": False, "reason": "MAX_OPEN_POSITIONS", "paper_only": True, "live_execution": False}

            equity = max(_f(snapshot["equity"]), 0.0)
            risk_budget = equity * self.max_single_risk_fraction
            per_unit_risk = abs(entry_value - stop_value) if stop_value is not None else 0.0

            if quantity is None:
                if per_unit_risk <= 0:
                    return {"success": False, "reason": "STOP_REQUIRED_FOR_SIZING", "paper_only": True, "live_execution": False}
                quantity_value = max(0.0, float(int(risk_budget // per_unit_risk)))
            else:
                quantity_value = max(0.0, _f(quantity))

            if quantity_value <= 0:
                return {"success": False, "reason": "POSITION_SIZE_ZERO", "paper_only": True, "live_execution": False}

            trade_risk = per_unit_risk * quantity_value
            if trade_risk > risk_budget + 1e-9:
                return {"success": False, "reason": "SINGLE_TRADE_RISK_LIMIT", "paper_only": True, "live_execution": False}

            total_risk_after = _f(snapshot["risk_at_stops"]) + trade_risk
            if equity > 0 and total_risk_after > equity * self.max_total_risk_fraction:
                return {"success": False, "reason": "PORTFOLIO_RISK_LIMIT", "paper_only": True, "live_execution": False}

            notional_after = _f(snapshot["gross_exposure"]) + abs(entry_value * quantity_value)
            if equity > 0 and notional_after > equity * self.max_gross_exposure_multiple:
                return {"success": False, "reason": "GROSS_EXPOSURE_LIMIT", "paper_only": True, "live_execution": False}

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
                    str(asset_type or "SPOT").upper(),
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
                    json.dumps(metadata or {}, default=str, sort_keys=True),
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
                },
            )
            conn.commit()

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

            pnl = self._pnl(str(row["side"]), _f(row["entry"]), exit_value, _f(row["quantity"]))
            conn.execute(
                "UPDATE paper_positions SET status='CLOSED',closed_at=?,exit_price=?,realized_pnl=? WHERE id=?",
                (_now(), exit_value, pnl, int(row["id"])),
            )
            self._event(
                conn,
                int(row["id"]),
                "CLOSE",
                {"exit_price": exit_value, "realized_pnl": pnl, "reason": reason},
            )
            conn.commit()

        return {
            "success": True,
            "reason": reason,
            "position_id": int(row["id"]),
            "symbol": str(row["symbol"]),
            "exit_price": exit_value,
            "realized_pnl": pnl,
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
                closed.append(
                    self.close_position(
                        position_id=int(row["id"]),
                        exit_price=mark,
                        reason=reason,
                    )
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


def live_mark_loader(symbol: str) -> float | None:
    try:
        from workstation.quant_terminal_v2 import live_payload

        payload = live_payload(symbol)
        snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
        if isinstance(snapshot, dict) and snapshot.get("ltp") is not None:
            return float(snapshot["ltp"])
    except Exception:
        return None
    return None


def portfolio_payload() -> dict[str, Any]:
    return paper_desk.snapshot(mark_loader=live_mark_loader)


def format_portfolio(payload: dict[str, Any]) -> str:
    positions = list(payload.get("positions") or [])
    lines = [
        "JARVIS PAPER TRADING PORTFOLIO",
        "--------------------------------------------------",
        f"Paper Equity: {float(payload.get('equity') or 0):,.2f}",
        f"Total P&L: {float(payload.get('total_pnl') or 0):+,.2f}",
        f"Realized P&L: {float(payload.get('realized_pnl') or 0):+,.2f}",
        f"Unrealized P&L: {float(payload.get('unrealized_pnl') or 0):+,.2f}",
        f"Gross Exposure: {float(payload.get('gross_exposure') or 0):,.2f}",
        f"Risk at Stops: {float(payload.get('risk_at_stops') or 0):,.2f} ({float(payload.get('risk_percent_of_equity') or 0):.2f}%)",
        f"Open Positions: {int(payload.get('open_count') or 0)} / {int(payload.get('max_open_positions') or 0)}",
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
        from workstation.paper_autonomy_engine import paper_autonomy

        if kind == "AUTO_START":
            auto = paper_autonomy.start()
            speech = "Autonomous paper trading started across the governed multi-asset universe. Live broker execution remains locked."
        elif kind == "AUTO_STOP":
            auto = paper_autonomy.stop()
            speech = "Autonomous paper trading stopped. Existing paper positions remain in the portfolio and continue to be visible."
        else:
            auto = paper_autonomy.status()
            speech = (
                f"Autonomous paper trading is {'RUNNING' if auto.get('running') else 'STOPPED'}. "
                f"Scans={auto.get('scan_cycles', 0)}, opens={auto.get('positions_opened', 0)}, closes={auto.get('positions_closed', 0)}."
            )
        portfolio = portfolio_payload()
        return {
            "action": kind.lower(),
            "speech": speech,
            "autonomy": auto,
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
