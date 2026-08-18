
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4


BOOK = Path.home() / "Documents" / "JARVIS_Trading" / "paper_book_v1.json"


@dataclass
class PaperTrade:
    trade_id: str
    symbol: str
    direction: str
    entry: float
    stop: float
    target: float
    qty: int
    status: str
    opened_at: str
    closed_at: str | None = None
    exit: float | None = None
    pnl: float = 0.0
    r_multiple: float = 0.0


class PaperBroker:
    """
    Simulation only. This class never calls a broker order endpoint.
    """

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.trades: list[PaperTrade] = []
        self._load()

    def _load(self):
        if not BOOK.exists():
            return
        try:
            payload = json.loads(BOOK.read_text(encoding="utf-8"))
            self.trades = [
                PaperTrade(**x)
                for x in payload.get("trades", [])
            ]
        except Exception:
            self.trades = []

    def _save(self):
        BOOK.parent.mkdir(parents=True, exist_ok=True)
        BOOK.write_text(
            json.dumps(
                {
                    "initial_capital": self.initial_capital,
                    "trades": [asdict(x) for x in self.trades],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def open(self, symbol, direction, entry, stop, target, qty):
        if qty <= 0 or entry <= 0 or stop <= 0 or target <= 0:
            return {
                "success": False,
                "reason": "Invalid paper trade parameters.",
            }

        t = PaperTrade(
            trade_id=str(uuid4()),
            symbol=symbol,
            direction=direction,
            entry=float(entry),
            stop=float(stop),
            target=float(target),
            qty=int(qty),
            status="OPEN",
            opened_at=datetime.now().astimezone().isoformat(),
        )
        self.trades.append(t)
        self._save()
        return {
            "success": True,
            "status": "PAPER_OPEN",
            "trade": asdict(t),
        }

    def update(self, symbol: str, price: float):
        changed = []
        for t in self.trades:
            if t.status != "OPEN" or t.symbol != symbol:
                continue

            hit_target = (
                price >= t.target if t.direction == "LONG"
                else price <= t.target
            )
            hit_stop = (
                price <= t.stop if t.direction == "LONG"
                else price >= t.stop
            )

            if hit_target or hit_stop:
                t.exit = float(t.target if hit_target else t.stop)
                t.closed_at = datetime.now().astimezone().isoformat()
                t.status = "CLOSED"

                if t.direction == "LONG":
                    t.pnl = (t.exit - t.entry) * t.qty
                else:
                    t.pnl = (t.entry - t.exit) * t.qty

                risk = abs(t.entry - t.stop) * t.qty
                t.r_multiple = (
                    t.pnl / risk if risk > 0 else 0.0
                )
                changed.append(asdict(t))

        if changed:
            self._save()

        return changed

    def snapshot(self):
        open_trades = [asdict(t) for t in self.trades if t.status == "OPEN"]
        closed = [asdict(t) for t in self.trades if t.status == "CLOSED"]
        pnl = sum(float(t.get("pnl", 0)) for t in closed)
        return {
            "initial_capital": self.initial_capital,
            "realized_pnl": pnl,
            "open": open_trades,
            "closed_count": len(closed),
        }
