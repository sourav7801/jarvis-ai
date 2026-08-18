"""Central configuration for the canonical OMNI-JARVIS runtime."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

OLLAMA_URL = os.getenv(
    "JARVIS_OLLAMA_URL", "http://127.0.0.1:11434/api/generate"
).strip()
OLLAMA_MODEL = os.getenv("JARVIS_OLLAMA_MODEL", "llama3.2:3b").strip()
OLLAMA_TIMEOUT_SECONDS = float(
    os.getenv("JARVIS_OLLAMA_TIMEOUT_SECONDS", "60")
)
MAX_PARALLEL_TASKS = max(
    1, int(os.getenv("JARVIS_MAX_PARALLEL_TASKS", "4"))
)

DATA_DIR = Path(
    os.getenv("JARVIS_DATA_DIR", str(PROJECT_ROOT / "data"))
).expanduser()
STATE_DIR = Path(
    os.getenv("JARVIS_STATE_DIR", str(DATA_DIR / "state"))
).expanduser()
MISSION_STATE_FILE = Path(
    os.getenv(
        "JARVIS_MISSION_STATE_FILE",
        str(STATE_DIR / "mission_control.json"),
    )
).expanduser()
MISSION_WORKSPACES_DIR = Path(
    os.getenv(
        "JARVIS_MISSION_WORKSPACES_DIR",
        str(STATE_DIR / "missions"),
    )
).expanduser()
WEB_RESEARCH_STATE_FILE = Path(
    os.getenv(
        "JARVIS_WEB_RESEARCH_STATE_FILE",
        str(STATE_DIR / "web_intelligence.json"),
    )
).expanduser()
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
AUDIT_DB = Path(
    os.getenv("JARVIS_AUDIT_DB", str(STATE_DIR / "omni_jarvis.sqlite3"))
).expanduser()
HYBRID_MEMORY_DB = Path(
    os.getenv("JARVIS_HYBRID_MEMORY_DB", str(STATE_DIR / "memory.sqlite3"))
).expanduser()
MEMORY_FILE = Path(
    os.getenv("JARVIS_MEMORY_FILE", str(PROJECT_ROOT / "memory.json"))
).expanduser()

# Safety invariant: live order execution is off unless a future, separately
# audited execution service implements broker and human approval controls.
LIVE_TRADING_ENABLED = False

# AUTO prefers authenticated FYERS data when configured and preserves the
# existing providers as fallbacks.  This setting never enables broker orders.
MARKET_DATA_PROVIDER = os.getenv(
    "JARVIS_MARKET_DATA_PROVIDER", "AUTO"
).strip().upper()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


FYERS_LIVE_DATA_ENABLED = _env_bool("JARVIS_FYERS_LIVE_ENABLED", True)
FYERS_LIVE_LITE_MODE = _env_bool("JARVIS_FYERS_LITE_MODE", False)
FYERS_LIVE_SYMBOLS = tuple(
    item.strip().upper()
    for item in os.getenv(
        "JARVIS_FYERS_LIVE_SYMBOLS", "NIFTY,BANKNIFTY,SENSEX"
    ).split(",")
    if item.strip()
)

WORKSTATION_HOST = os.getenv("JARVIS_WORKSTATION_HOST", "127.0.0.1").strip()
WORKSTATION_PORT = int(os.getenv("JARVIS_WORKSTATION_PORT", "8787"))
WORKSTATION_API_TOKEN = os.getenv("JARVIS_WORKSTATION_API_TOKEN", "").strip()
ISOLATED_AGENT_NAMES = frozenset(
    name.strip().lower()
    for name in os.getenv("JARVIS_ISOLATED_AGENTS", "").split(",")
    if name.strip()
)
WORKER_TIMEOUT_SECONDS = min(
    max(int(os.getenv("JARVIS_WORKER_TIMEOUT_SECONDS", "60")), 1), 300
)
