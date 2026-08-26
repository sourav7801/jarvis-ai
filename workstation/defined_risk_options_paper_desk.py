"""Persistent paper-only desk for verified defined-risk debit verticals."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from workstation.options_chain_analytics import NormalizedOptionContract


REQUIRED_GREEKS = ("iv", "delta", "gamma", "theta", "vega")


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


@dataclass(frozen=True)
class DebitVerticalCandidate:
    candidate_id: str
    underlying: str
    direction: str
    strategy: str
    expiry: str
    provider: str
    long_symbol: str
    short_symbol: str
    option_type: str
    long_strike: float
    short_strike: float
    long_fill: float
    short_fill: float
    net_debit: float
    width: float
    contract_multiplier: float
    max_loss_per_lot: float
    max_profit_per_lot: float
    currency: str
    evidence_timestamp: str
    payload_hash: str
    verified: bool = True
    stale: bool = False
    defined_risk: bool = True
    naked_short: bool = False
    paper_only: bool = True
    live_execution: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _eligible(contract: NormalizedOptionContract, option_type: str, expiry: str) -> bool:
    if contract.option_type != option_type or contract.expiry != expiry or not contract.symbol:
        return False
    numbers = [contract.bid, contract.ask, contract.open_interest, contract.volume]
    numbers.extend(getattr(contract, key) for key in REQUIRED_GREEKS)
    if not all(_finite(value) for value in numbers):
        return False
    if float(contract.ask) <= 0 or float(contract.bid) < 0 or float(contract.ask) < float(contract.bid):
        return False
    mid = contract.mid
    return bool(mid and mid > 0 and float(contract.spread or 0) / mid <= 0.15 and float(contract.open_interest) > 0 and float(contract.volume) > 0)


def select_debit_vertical(
    contracts: Iterable[NormalizedOptionContract],
    *,
    direction: str,
    expiry: str,
    contract_multiplier: float,
    currency: str,
    evidence_timestamp: str,
    verified: bool,
    stale: bool,
) -> DebitVerticalCandidate:
    normalized_direction = str(direction).upper()
    if normalized_direction not in {"LONG", "SHORT"}:
        raise ValueError("Options direction must be LONG or SHORT.")
    if not verified or stale:
        raise ValueError("Options candidates require verified, fresh chain evidence.")
    if not _finite(contract_multiplier) or float(contract_multiplier) <= 0 or not str(currency).strip():
        raise ValueError("Verified contract multiplier and currency are required.")
    try:
        expiry_date = datetime.fromisoformat(str(expiry).replace("Z", "+00:00")).date()
    except ValueError as error:
        raise ValueError("Exact ISO option expiry is required.") from error
    if expiry_date < datetime.now(timezone.utc).date():
        raise ValueError("Expired option contracts cannot be opened.")
    option_type = "CE" if normalized_direction == "LONG" else "PE"
    rows = [item for item in contracts if _eligible(item, option_type, expiry)]
    if len(rows) < 2:
        raise ValueError("At least two liquid contracts with complete Greeks/OI are required.")
    providers = {item.provider for item in rows}
    underlyings = {item.underlying for item in rows}
    if len(providers) != 1 or len(underlyings) != 1:
        raise ValueError("Spread legs must share one provider and underlying.")
    if normalized_direction == "LONG":
        long_leg = min(rows, key=lambda item: abs(float(item.delta) - 0.50))
        shorts = [item for item in rows if item.strike > long_leg.strike]
        short_leg = min(shorts, key=lambda item: abs(float(item.delta) - 0.25), default=None)
        strategy = "BULL_CALL_DEBIT"
    else:
        long_leg = min(rows, key=lambda item: abs(float(item.delta) + 0.50))
        shorts = [item for item in rows if item.strike < long_leg.strike]
        short_leg = min(shorts, key=lambda item: abs(float(item.delta) + 0.25), default=None)
        strategy = "BEAR_PUT_DEBIT"
    if short_leg is None:
        raise ValueError("No farther out-of-the-money hedge leg satisfied the policy.")
    long_fill = float(long_leg.ask)
    short_fill = float(short_leg.bid)
    debit = long_fill - short_fill
    width = abs(short_leg.strike - long_leg.strike)
    if debit <= 0 or debit >= width:
        raise ValueError("Conservative spread debit must be positive and below strike width.")
    identity = {
        "provider": long_leg.provider, "underlying": long_leg.underlying,
        "expiry": expiry, "strategy": strategy, "long": long_leg.symbol,
        "short": short_leg.symbol, "evidence_timestamp": evidence_timestamp,
        "long_fill": long_fill, "short_fill": short_fill,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    multiplier = float(contract_multiplier)
    return DebitVerticalCandidate(
        candidate_id=digest[:32], underlying=long_leg.underlying,
        direction=normalized_direction, strategy=strategy, expiry=expiry,
        provider=long_leg.provider, long_symbol=str(long_leg.symbol), short_symbol=str(short_leg.symbol),
        option_type=option_type, long_strike=long_leg.strike, short_strike=short_leg.strike,
        long_fill=long_fill, short_fill=short_fill, net_debit=debit, width=width,
        contract_multiplier=multiplier, max_loss_per_lot=debit * multiplier,
        max_profit_per_lot=(width - debit) * multiplier, currency=str(currency).upper(),
        evidence_timestamp=str(evidence_timestamp), payload_hash=digest,
    )


class DefinedRiskOptionsPaperDesk:
    def __init__(
        self,
        path: Path | None = None,
        *,
        max_risk_percent: float = 0.75,
        max_open_spreads: int = 4,
        loss_exit_fraction: float = 0.50,
        profit_exit_fraction: float = 0.75,
    ):
        self.path = path or Path(__file__).resolve().parents[1] / "data" / "trading" / "paper_option_spreads.sqlite3"
        self.max_risk_percent = max(0.05, min(float(max_risk_percent), 2.0))
        self.max_open_spreads = max(1, min(int(max_open_spreads), 20))
        self.loss_exit_fraction = max(0.10, min(float(loss_exit_fraction), 1.0))
        self.profit_exit_fraction = max(0.10, min(float(profit_exit_fraction), 1.0))
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """CREATE TABLE IF NOT EXISTS option_spreads (
                candidate_id TEXT PRIMARY KEY, opened_at TEXT NOT NULL, status TEXT NOT NULL,
                strategy TEXT NOT NULL, underlying TEXT NOT NULL, expiry TEXT NOT NULL,
                provider TEXT NOT NULL, currency TEXT NOT NULL, quantity INTEGER NOT NULL,
                max_loss REAL NOT NULL, max_profit REAL NOT NULL, payload_json TEXT NOT NULL,
                paper_only INTEGER NOT NULL DEFAULT 1, live_execution INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS idx_option_spread_status ON option_spreads(status, opened_at);
                CREATE TABLE IF NOT EXISTS option_spread_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_option_event_candidate ON option_spread_events(candidate_id, id);"""
            )
            existing = {row[1] for row in connection.execute("PRAGMA table_info(option_spreads)")}
            migrations = {
                "last_mark": "REAL", "unrealized_pnl": "REAL NOT NULL DEFAULT 0",
                "realized_pnl": "REAL", "last_mark_at": "TEXT", "closed_at": "TEXT",
                "exit_reason": "TEXT",
            }
            for column, definition in migrations.items():
                if column not in existing:
                    connection.execute(f"ALTER TABLE option_spreads ADD COLUMN {column} {definition}")
            connection.commit()

    @staticmethod
    def _certificate_time(certificate: dict[str, Any], *, maximum_age_seconds: float = 120.0) -> datetime:
        if certificate.get("verified") is not True or certificate.get("stale") is True:
            raise ValueError("A verified fresh options mark certificate is required.")
        raw = certificate.get("received_at")
        if not raw:
            raise ValueError("Options mark received timestamp is required.")
        try:
            received = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Options mark timestamp is invalid.") from error
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - received.astimezone(timezone.utc)).total_seconds() > maximum_age_seconds:
            raise ValueError("Options mark is too old.")
        return received.astimezone(timezone.utc)

    @staticmethod
    def _event(connection: sqlite3.Connection, candidate_id: str, event_type: str, payload: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO option_spread_events(candidate_id,created_at,event_type,payload_json) VALUES(?,?,?,?)",
            (candidate_id, datetime.now(timezone.utc).isoformat(), event_type, json.dumps(payload, sort_keys=True)),
        )

    def open_spread(self, candidate: DebitVerticalCandidate, *, equity: float) -> dict[str, Any]:
        if not isinstance(candidate, DebitVerticalCandidate) or not candidate.defined_risk or candidate.naked_short:
            raise ValueError("Only validated defined-risk debit verticals are accepted.")
        if not candidate.verified or candidate.stale or candidate.live_execution:
            raise ValueError("Candidate violates the paper-only evidence boundary.")
        if not _finite(equity) or float(equity) <= 0:
            raise ValueError("Positive paper equity is required.")
        risk_budget = float(equity) * self.max_risk_percent / 100.0
        lots = math.floor(risk_budget / candidate.max_loss_per_lot)
        if lots < 1:
            return {"success": False, "status": "RISK_BUDGET_TOO_SMALL", "paper_only": True, "live_execution": False}
        with self._lock, closing(self._connect()) as connection:
            open_count = connection.execute("SELECT COUNT(*) FROM option_spreads WHERE status='OPEN'").fetchone()[0]
            if open_count >= self.max_open_spreads:
                return {"success": False, "status": "MAX_OPEN_SPREADS", "paper_only": True, "live_execution": False}
            existing = connection.execute("SELECT status FROM option_spreads WHERE candidate_id=?", (candidate.candidate_id,)).fetchone()
            if existing:
                return {"success": False, "status": "ALREADY_RECORDED", "paper_only": True, "live_execution": False}
            payload = candidate.to_dict()
            connection.execute(
                """INSERT INTO option_spreads
                (candidate_id,opened_at,status,strategy,underlying,expiry,provider,currency,
                quantity,max_loss,max_profit,payload_json,paper_only,live_execution)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    candidate.candidate_id, datetime.now(timezone.utc).isoformat(), "OPEN",
                    candidate.strategy, candidate.underlying, candidate.expiry, candidate.provider,
                    candidate.currency, lots, candidate.max_loss_per_lot * lots,
                    candidate.max_profit_per_lot * lots, json.dumps(payload, sort_keys=True), 1, 0,
                ),
            )
            self._event(connection, candidate.candidate_id, "OPENED", {"quantity": lots, "max_loss": candidate.max_loss_per_lot * lots, "max_profit": candidate.max_profit_per_lot * lots})
            connection.commit()
        return {
            "success": True, "status": "OPEN", "candidate_id": candidate.candidate_id,
            "quantity": lots, "max_loss": candidate.max_loss_per_lot * lots,
            "max_profit": candidate.max_profit_per_lot * lots,
            "legs": [
                {"symbol": candidate.long_symbol, "side": "BUY", "fill": candidate.long_fill},
                {"symbol": candidate.short_symbol, "side": "SELL_TO_HEDGE", "fill": candidate.short_fill},
            ],
            "atomic_synthetic_fill": True, "paper_only": True, "live_execution": False,
        }

    def mark_spread(
        self,
        candidate_id: str,
        *,
        long_bid: float,
        short_ask: float,
        certificate: dict[str, Any],
    ) -> dict[str, Any]:
        received = self._certificate_time(certificate)
        if not _finite(long_bid) or not _finite(short_ask) or float(long_bid) < 0 or float(short_ask) < 0:
            raise ValueError("Finite non-negative close-side leg quotes are required.")
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM option_spreads WHERE candidate_id=?", (candidate_id,)).fetchone()
            if not row:
                raise KeyError(f"Unknown option spread: {candidate_id}")
            if row["status"] != "OPEN":
                return {"success": False, "status": str(row["status"]), "paper_only": True, "live_execution": False}
            payload = json.loads(row["payload_json"])
            close_value = max(0.0, float(long_bid) - float(short_ask))
            quantity = int(row["quantity"])
            pnl = (close_value - float(payload["net_debit"])) * float(payload["contract_multiplier"]) * quantity
            reason = None
            if pnl <= -float(row["max_loss"]) * self.loss_exit_fraction:
                reason = "LOSS_LIMIT"
            elif pnl >= float(row["max_profit"]) * self.profit_exit_fraction:
                reason = "PROFIT_TARGET"
            status = "CLOSED" if reason else "OPEN"
            connection.execute(
                """UPDATE option_spreads SET last_mark=?,unrealized_pnl=?,last_mark_at=?,
                status=?,realized_pnl=?,closed_at=?,exit_reason=? WHERE candidate_id=?""",
                (
                    close_value, 0.0 if reason else pnl, received.isoformat(), status,
                    pnl if reason else None, received.isoformat() if reason else None, reason, candidate_id,
                ),
            )
            self._event(connection, candidate_id, reason or "MARKED", {"long_bid": float(long_bid), "short_ask": float(short_ask), "close_value": close_value, "pnl": pnl})
            connection.commit()
        return {"success": True, "status": status, "exit_reason": reason, "close_value": close_value, "pnl": pnl, "paper_only": True, "live_execution": False}

    def settle_expired(
        self,
        candidate_id: str,
        *,
        settlement_price: float,
        certificate: dict[str, Any],
    ) -> dict[str, Any]:
        received = self._certificate_time(certificate, maximum_age_seconds=600.0)
        if certificate.get("official_settlement") is not True or not _finite(settlement_price) or float(settlement_price) <= 0:
            raise ValueError("Verified official settlement price is required.")
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM option_spreads WHERE candidate_id=?", (candidate_id,)).fetchone()
            if not row:
                raise KeyError(f"Unknown option spread: {candidate_id}")
            if row["status"] != "OPEN":
                return {"success": False, "status": str(row["status"]), "paper_only": True, "live_execution": False}
            payload = json.loads(row["payload_json"])
            expiry = datetime.fromisoformat(str(row["expiry"]).replace("Z", "+00:00")).date()
            if received.date() < expiry:
                raise ValueError("Spread cannot settle before its exact expiry date.")
            settlement = float(settlement_price)
            if payload["option_type"] == "CE":
                long_intrinsic = max(0.0, settlement - float(payload["long_strike"]))
                short_intrinsic = max(0.0, settlement - float(payload["short_strike"]))
            else:
                long_intrinsic = max(0.0, float(payload["long_strike"]) - settlement)
                short_intrinsic = max(0.0, float(payload["short_strike"]) - settlement)
            close_value = max(0.0, long_intrinsic - short_intrinsic)
            pnl = (close_value - float(payload["net_debit"])) * float(payload["contract_multiplier"]) * int(row["quantity"])
            connection.execute(
                """UPDATE option_spreads SET status='CLOSED',last_mark=?,unrealized_pnl=0,
                realized_pnl=?,last_mark_at=?,closed_at=?,exit_reason='EXPIRY_SETTLEMENT'
                WHERE candidate_id=?""",
                (close_value, pnl, received.isoformat(), received.isoformat(), candidate_id),
            )
            self._event(connection, candidate_id, "EXPIRY_SETTLEMENT", {"settlement_price": settlement, "close_value": close_value, "pnl": pnl})
            connection.commit()
        return {"success": True, "status": "CLOSED", "exit_reason": "EXPIRY_SETTLEMENT", "close_value": close_value, "pnl": pnl, "paper_only": True, "live_execution": False}

    def snapshot(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = [dict(row) for row in connection.execute("SELECT * FROM option_spreads ORDER BY opened_at DESC")]
            events = [dict(row) for row in connection.execute("SELECT * FROM option_spread_events ORDER BY id DESC LIMIT 100")]
        for row in rows:
            row["payload"] = json.loads(row.pop("payload_json"))
            row["paper_only"] = bool(row["paper_only"])
            row["live_execution"] = bool(row["live_execution"])
        for event in events:
            event["payload"] = json.loads(event.pop("payload_json"))
        return {
            "positions": rows, "events": events,
            "open_count": sum(row["status"] == "OPEN" for row in rows),
            "unrealized_pnl": sum(float(row.get("unrealized_pnl") or 0.0) for row in rows if row["status"] == "OPEN"),
            "realized_pnl": sum(float(row.get("realized_pnl") or 0.0) for row in rows if row["status"] == "CLOSED"),
            "paper_only": True, "live_execution": False,
        }


DEFINED_RISK_OPTIONS_DESK = DefinedRiskOptionsPaperDesk()
