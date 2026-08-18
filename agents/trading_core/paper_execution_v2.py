
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from typing import Any


BOOK = Path.home() / "Documents" / "JARVIS_Trading" / "paper_book_v2.json"


@dataclass
class PaperPosition:
    id: str
    symbol: str
    strategy: str
    direction: str
    entry: float
    stop: float
    target: float
    rr: float
    qty: int
    status: str
    opened_at: str
    close_price: float | None = None
    closed_at: str | None = None
    pnl: float = 0.0
    r_multiple: float = 0.0
    close_reason: str | None = None


class PaperExecutionV2:
    """
    Simulation only.

    This layer accepts a candidate only after the caller explicitly marks it
    PAPER_CANDIDATE. It never contacts a broker.
    """

    def __init__(self, capital: float = 100000.0):
        self.capital = float(capital)
        self.positions: list[PaperPosition] = []
        self._load()

    def _load(self):
        if not BOOK.exists():
            return
        try:
            payload = json.loads(BOOK.read_text(encoding="utf-8"))
            self.capital = float(payload.get("capital", self.capital))
            self.positions = [
                PaperPosition(**x)
                for x in payload.get("positions", [])
            ]
        except Exception:
            self.positions = []

    def _save(self):
        BOOK.parent.mkdir(parents=True, exist_ok=True)
        BOOK.write_text(
            json.dumps(
                {
                    "capital": self.capital,
                    "positions": [asdict(x) for x in self.positions],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def open_candidate(self, candidate: dict[str, Any], qty: int = 1):
        required = [
            "symbol",
            "strategy",
            "direction",
            "entry",
            "stop",
            "target",
            "rr",
        ]
        if any(k not in candidate for k in required):
            return {
                "success": False,
                "reason": "Candidate missing required fields.",
            }

        if float(candidate["rr"]) < 1.20:
            return {
                "success": False,
                "reason": "Candidate R/R below minimum.",
            }

        p = PaperPosition(
            id=str(uuid4()),
            symbol=str(candidate["symbol"]),
            strategy=str(candidate["strategy"]),
            direction=str(candidate["direction"]),
            entry=float(candidate["entry"]),
            stop=float(candidate["stop"]),
            target=float(candidate["target"]),
            rr=float(candidate["rr"]),
            qty=int(qty),
            status="OPEN",
            opened_at=datetime.now().astimezone().isoformat(),
        )

        self.positions.append(p)
        self._save()

        return {
            "success": True,
            "status": "PAPER_OPEN",
            "position": asdict(p),
        }

    def update_price(self, symbol: str, price: float):
        events = []

        for p in self.positions:
            if p.status != "OPEN" or p.symbol != symbol:
                continue

            hit_target = (
                price >= p.target
                if p.direction == "BULLISH"
                else price <= p.target
            )

            hit_stop = (
                price <= p.stop
                if p.direction == "BULLISH"
                else price >= p.stop
            )

            if not hit_target and not hit_stop:
                continue

            p.close_price = p.target if hit_target else p.stop
            p.closed_at = datetime.now().astimezone().isoformat()
            p.status = "CLOSED"
            p.close_reason = "TARGET" if hit_target else "STOP"

            if p.direction == "BULLISH":
                p.pnl = (p.close_price - p.entry) * p.qty
            else:
                p.pnl = (p.entry - p.close_price) * p.qty

            risk = abs(p.entry - p.stop) * p.qty
            p.r_multiple = p.pnl / risk if risk > 0 else 0.0
            self.capital += p.pnl

            events.append(asdict(p))

        if events:
            self._save()

        return events

    def snapshot(self):
        open_positions = [
            asdict(x)
            for x in self.positions
            if x.status == "OPEN"
        ]
        closed = [
            asdict(x)
            for x in self.positions
            if x.status == "CLOSED"
        ]
        return {
            "capital": self.capital,
            "open_positions": open_positions,
            "closed_count": len(closed),
            "realized_pnl": sum(
                float(x["pnl"])
                for x in closed
            ),
        }
