"""Beginner-friendly launcher for the canonical browser dashboard."""

from __future__ import annotations

import os
import secrets
import threading
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = PROJECT_ROOT / "data" / "state" / "workstation_api_token.txt"


def _valid_token(value: str) -> bool:
    return len(value) >= 32 and all(character.isalnum() or character in "-_" for character in value)


def local_api_token() -> str:
    """Return one stable, private token shared by canonical local launches."""

    configured = os.getenv("JARVIS_WORKSTATION_API_TOKEN", "").strip()
    if configured:
        return configured
    try:
        saved = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        saved = ""
    if _valid_token(saved):
        return saved
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return token


def existing_jarvis(host: str, port: int) -> bool:
    """Identify an already-running local JARVIS without needing its token."""

    try:
        with urllib.request.urlopen(
            f"http://{host}:{port}/api/health", timeout=0.75
        ) as response:
            if response.status != 200:
                return False
            import json

            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("service") == "OMNI-JARVIS"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def main() -> None:
    os.environ.setdefault("JARVIS_MARKET_DATA_PROVIDER", "AUTO")
    os.environ.setdefault("JARVIS_WORKSTATION_API_TOKEN", local_api_token())

    from config import WORKSTATION_HOST, WORKSTATION_PORT

    token = os.environ["JARVIS_WORKSTATION_API_TOKEN"]
    url = f"http://{WORKSTATION_HOST}:{WORKSTATION_PORT}/?token={token}"
    if existing_jarvis(WORKSTATION_HOST, WORKSTATION_PORT):
        print("JARVIS is already running. Opening the existing dashboard.")
        webbrowser.open(url)
        return
    opener = threading.Timer(1.25, webbrowser.open, args=(url,))
    opener.daemon = True
    opener.start()

    from workstation.app import main as run_workstation

    run_workstation()


if __name__ == "__main__":
    main()
