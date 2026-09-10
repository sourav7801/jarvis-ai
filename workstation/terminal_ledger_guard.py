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


def legacy_exposure(desk):
    if desk.db_path.resolve() != TERMINAL_DB.resolve():
        return []
    issues = []
    if LEGACY_ACCOUNT.exists():
        try:
            data = json.loads(LEGACY_ACCOUNT.read_text(encoding="utf-8"))
            count = len(data.get("positions") or [])
            if count:
                issues.append({"book": "Legacy paper account", "open_count": count, "path": str(LEGACY_ACCOUNT)})
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
