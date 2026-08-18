
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from .models import PaperPosition, Setup


class PaperEngine:
    def __init__(self) -> None:
        self.positions: list[PaperPosition] = []

    def open(self, setup: Setup, qty: int) -> PaperPosition | None:
        if setup.status != "PAPER_CANDIDATE" or qty <= 0:
            return None

        pos = PaperPosition(
            id=str(uuid4()),
            symbol=setup.symbol,
            direction=setup.direction,
            entry=float(setup.entry),
            stop=float(setup.stop),
            target=float(setup.target),
            qty=int(qty),
            opened_at=datetime.now(),
        )
        self.positions.append(pos)
        return pos

    def snapshot(self) -> list[dict]:
        return [
            {
                "id": p.id,
                "symbol": p.symbol,
                "direction": p.direction,
                "entry": p.entry,
                "stop": p.stop,
                "target": p.target,
                "qty": p.qty,
                "status": p.status,
                "pnl": p.pnl,
            }
            for p in self.positions
        ]
