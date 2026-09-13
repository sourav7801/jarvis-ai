"""Keep earlier default paper books from minting a second terminal balance.

Existing records, research and exits are retained. Explicit isolated test or
research books at other paths are independent of the default terminal account.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3

from config import STATE_DIR

ROOT = Path(__file__).resolve().parents[1]
TERMINAL_DB = Path(os.getenv("JARVIS_PAPER_DB", str(ROOT / "data/trading/paper_desk.sqlite3"))).expanduser()
LEGACY_ACCOUNT = STATE_DIR / "paper_portfolio.json"
LEGACY_SPREADS = ROOT / "data/trading/paper_option_spreads.sqlite3"


def terminal_controls(path):
    if Path(path).resolve() not in {LEGACY_ACCOUNT.resolve(), LEGACY_SPREADS.resolve()} or not TERMINAL_DB.exists():
        return False
    try:
        with closing(sqlite3.connect(TERMINAL_DB.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
            return conn.execute("SELECT 1 FROM sqlite_master WHERE name='terminal_workspaces'").fetchone() is not None
    except sqlite3.Error:
        # An unreadable authority cannot authorize new exposure elsewhere.
        return True


def _first_scalar(record, *keys):
    if not isinstance(record, dict):
        return None
    for key in keys:
        value = record.get(key)
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
            return value[:96]
        if isinstance(value, (int, float, bool)):
            return value
    return None


def _legacy_position_summary(record, index):
    """Return only execution-safe fields needed to identify old exposure.

    Free-form notes, prompts and arbitrary metadata are deliberately excluded so
    diagnostics can identify the blocking paper position without copying the
    legacy payload into the canonical ledger or browser.
    """
    return {
        "record": index,
        "symbol": _first_scalar(record, "symbol", "instrument", "ticker") or "UNKNOWN",
        "side": _first_scalar(record, "side", "direction", "action"),
        "quantity": _first_scalar(record, "quantity", "qty", "lots"),
        "entry_price": _first_scalar(record, "entry_price", "entry", "avg_price", "average_price", "price"),
        "stop": _first_scalar(record, "stop_loss", "stop", "sl"),
        "target": _first_scalar(record, "target", "target_price", "tp"),
        "opened_at": _first_scalar(record, "opened_at", "entry_time", "timestamp", "created_at"),
        "status": _first_scalar(record, "status", "state"),
        "option_type": _first_scalar(record, "option_type", "type"),
        "strike": _first_scalar(record, "strike", "strike_price"),
        "expiry": _first_scalar(record, "expiry", "expiry_date"),
        "workspace": _first_scalar(record, "portfolio_bucket", "workspace", "bucket", "profile"),
    }


def legacy_exposure(desk):
    if desk.db_path.resolve() != TERMINAL_DB.resolve():
        return []
    issues = []
    if LEGACY_ACCOUNT.exists():
        try:
            data = json.loads(LEGACY_ACCOUNT.read_text(encoding="utf-8"))
            positions = data.get("positions") or []
            count = len(positions)
            if count:
                issues.append(
                    {
                        "book": "Legacy paper account",
                        "open_count": count,
                        "path": str(LEGACY_ACCOUNT),
                        "position_summaries": [
                            _legacy_position_summary(record, index)
                            for index, record in enumerate(positions[:10], start=1)
                        ],
                    }
                )
        except (OSError, ValueError, TypeError):
            issues.append({"book": "Legacy paper account", "error": "UNREADABLE_RECORDS", "path": str(LEGACY_ACCOUNT)})
    if LEGACY_SPREADS.exists():
        try:
            with closing(sqlite3.connect(LEGACY_SPREADS.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
                count = conn.execute("SELECT COUNT(*) FROM option_spreads WHERE status='OPEN'").fetchone()[0]
            if count:
                issues.append({"book": "Legacy defined-risk spreads", "open_count": count, "path": str(LEGACY_SPREADS)})
        except sqlite3.Error:
            issues.append({"book": "Legacy defined-risk spreads", "error": "UNREADABLE_RECORDS", "path": str(LEGACY_SPREADS)})
    return issues
