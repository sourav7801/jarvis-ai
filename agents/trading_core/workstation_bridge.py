
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path.home() / "Documents" / "JARVIS_Trading"
STATE_FILE = ROOT / "jarvis_workstation_state_v1.json"
EVENT_FILE = ROOT / "jarvis_event_bus_v8.jsonl"
NEWS_FILE = ROOT / "jarvis_news_latest_v1.json"


class WorkstationBridge:
    """File-based bridge: simple, robust, no dependency on the UI framework."""

    def write_state(self, trading_state: dict, paper_state: dict, news: list[dict]) -> dict:
        ROOT.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().astimezone().isoformat(),
            "trading": trading_state,
            "paper": paper_state,
            "news": news[:30],
        }
        STATE_FILE.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
        return payload

    def read_recent_events(self, limit: int = 50) -> list[dict]:
        if not EVENT_FILE.exists():
            return []
        rows = EVENT_FILE.read_text(encoding="utf-8").splitlines()
        out = []
        for line in rows[-limit:]:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
        return out

    def write_news(self, news: list[dict]) -> None:
        ROOT.mkdir(parents=True, exist_ok=True)
        NEWS_FILE.write_text(
            json.dumps(
                {
                    "updated_at": datetime.now().astimezone().isoformat(),
                    "items": news[:50],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
