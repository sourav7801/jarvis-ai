"""FYERS API v3 authentication for JARVIS market-data access.

This module deliberately exposes no order-placement helpers.  It creates the
official SDK client used by the historical, quote, and data-WebSocket adapters.
Tokens are stored outside the repository by default.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from typing import Any, Callable, Optional


DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSTATION_TOKEN_FILE = PROJECT_ROOT / "data" / "state" / "workstation_api_token.txt"


def _default_token_file() -> Path:
    return (
        Path.home()
        / "Documents"
        / "JARVIS_Trading"
        / "fyers_token.json"
    )


@dataclass(frozen=True)
class FyersSettings:
    app_id: str
    secret_id: str
    redirect_uri: str
    token_file: Path

    @classmethod
    def from_env(cls) -> "FyersSettings":
        token_file = Path(
            os.getenv(
                "JARVIS_FYERS_TOKEN_FILE",
                str(_default_token_file()),
            )
        ).expanduser()
        app_id = os.getenv("FYERS_APP_ID", "").strip()
        # Once login has succeeded, the non-secret App ID stored alongside the
        # token is enough for data clients.  This lets the workstation restart
        # without asking users to re-enter credentials in every terminal.
        if not app_id and token_file.exists():
            try:
                stored = json.loads(token_file.read_text(encoding="utf-8"))
                app_id = str(stored.get("app_id", "")).strip()
            except (OSError, json.JSONDecodeError, AttributeError):
                pass
        return cls(
            app_id=app_id,
            secret_id=os.getenv("FYERS_SECRET_ID", "").strip(),
            redirect_uri=os.getenv(
                "FYERS_REDIRECT_URI", DEFAULT_REDIRECT_URI
            ).strip(),
            token_file=token_file,
        )

    def validate(self, require_secret: bool = True) -> None:
        missing = []
        if not self.app_id:
            missing.append("FYERS_APP_ID")
        if require_secret and not self.secret_id:
            missing.append("FYERS_SECRET_ID")
        if not self.redirect_uri:
            missing.append("FYERS_REDIRECT_URI")
        if missing:
            raise RuntimeError(
                "Missing FYERS environment variables: " + ", ".join(missing)
            )


def _sdk_model() -> Any:
    try:
        from fyers_apiv3 import fyersModel
    except ImportError as exc:
        raise RuntimeError(
            "FYERS SDK is not installed. Run: python -m pip install fyers-apiv3"
        ) from exc
    return fyersModel


def save_token(
    token_response: dict[str, Any],
    settings: Optional[FyersSettings] = None,
) -> Path:
    settings = settings or FyersSettings.from_env()
    access_token = str(token_response.get("access_token", "")).strip()
    if not access_token:
        raise RuntimeError(
            str(token_response.get("message") or "FYERS returned no access token.")
        )

    # Store only authentication material needed by the official SDK.  The app
    # secret is never written to disk by JARVIS.
    safe_payload: dict[str, Any] = {
        "access_token": access_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "app_id": settings.app_id,
    }
    for key in ("refresh_token", "expires_at", "token_type"):
        if token_response.get(key):
            safe_payload[key] = token_response[key]

    settings.token_file.parent.mkdir(parents=True, exist_ok=True)
    settings.token_file.write_text(
        json.dumps(safe_payload, indent=2), encoding="utf-8"
    )
    try:
        settings.token_file.chmod(0o600)
    except OSError:
        # Windows ACLs remain the authority when POSIX permission bits are not
        # available.  The file is still outside the project and never logged.
        pass
    return settings.token_file


def load_token(
    settings: Optional[FyersSettings] = None,
) -> Optional[dict[str, Any]]:
    settings = settings or FyersSettings.from_env()
    if not settings.token_file.exists():
        return None
    try:
        payload = json.loads(settings.token_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not read FYERS token file: {settings.token_file}"
        ) from exc
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise RuntimeError("FYERS token file does not contain an access token.")
    return payload


def _session(settings: FyersSettings) -> Any:
    settings.validate(require_secret=True)
    return _sdk_model().SessionModel(
        client_id=settings.app_id,
        secret_key=settings.secret_id,
        redirect_uri=settings.redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )


def generate_login_url(
    settings: Optional[FyersSettings] = None,
) -> str:
    settings = settings or FyersSettings.from_env()
    return str(_session(settings).generate_authcode())


def extract_auth_code(value: str) -> str:
    """Accept either FYERS' auth_code or the complete redirected URL."""

    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme and parsed.query:
        params = urllib.parse.parse_qs(parsed.query)
        return str(
            (params.get("auth_code") or params.get("code") or [""])[0]
        ).strip()
    return value


def exchange_auth_code(
    auth_code: str,
    settings: Optional[FyersSettings] = None,
) -> dict[str, Any]:
    settings = settings or FyersSettings.from_env()
    code = extract_auth_code(auth_code)
    if not code:
        raise RuntimeError("No FYERS authorization code was provided.")
    session = _session(settings)
    session.set_token(code)
    response = session.generate_token()
    if not isinstance(response, dict):
        raise RuntimeError("FYERS returned an invalid token response.")
    save_token(response, settings)
    return response


def create_client(
    settings: Optional[FyersSettings] = None,
    *,
    validate_profile: bool = False,
) -> Any:
    settings = settings or FyersSettings.from_env()
    settings.validate(require_secret=False)
    payload = load_token(settings)
    if payload is None:
        raise RuntimeError(
            "No FYERS token is saved. Run: python -m agents.fyers_auth_manager login"
        )
    client = _sdk_model().FyersModel(
        client_id=settings.app_id,
        token=str(payload["access_token"]),
        is_async=False,
        log_path="",
    )
    if validate_profile:
        response = client.get_profile()
        if not isinstance(response, dict) or response.get("s") not in {
            "ok",
            "success",
        }:
            message = response.get("message") if isinstance(response, dict) else response
            raise RuntimeError(f"FYERS token validation failed: {message}")
    return client


def websocket_access_token(
    settings: Optional[FyersSettings] = None,
) -> str:
    settings = settings or FyersSettings.from_env()
    settings.validate(require_secret=False)
    payload = load_token(settings)
    if payload is None:
        raise RuntimeError(
            "No FYERS token is saved. Run: python -m agents.fyers_auth_manager login"
        )
    token = str(payload["access_token"]).strip()
    prefix = f"{settings.app_id}:"
    return token if token.startswith(prefix) else prefix + token


def is_configured() -> bool:
    settings = FyersSettings.from_env()
    return bool(settings.app_id and settings.token_file.exists())


def interactive_login_settings(
    settings: Optional[FyersSettings] = None,
    *,
    input_fn: Callable[[str], str] = input,
    secret_fn: Callable[[str], str] = getpass.getpass,
) -> FyersSettings:
    """Complete missing login-only settings without exposing the secret.

    The App ID is normally recovered from the existing token file.  The App
    Secret is deliberately requested through a no-echo terminal prompt and is
    kept only in this process for the authorization-code exchange.
    """

    current = settings or FyersSettings.from_env()
    app_id = current.app_id or input_fn("FYERS App ID: ").strip()
    secret_id = current.secret_id
    if not secret_id:
        print(
            "Your FYERS App Secret is required for today's login. "
            "Input is hidden and JARVIS will not save it."
        )
        secret_id = secret_fn("FYERS App Secret (hidden): ").strip()
    completed = FyersSettings(
        app_id=app_id,
        secret_id=secret_id,
        redirect_uri=current.redirect_uri or DEFAULT_REDIRECT_URI,
        token_file=current.token_file,
    )
    completed.validate(require_secret=True)
    return completed


def notify_running_workstation() -> bool:
    """Ask the authenticated local dashboard to reload broker data."""

    try:
        api_token = WORKSTATION_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not api_token:
        return False
    host = os.getenv("JARVIS_WORKSTATION_HOST", "127.0.0.1").strip()
    port = int(os.getenv("JARVIS_WORKSTATION_PORT", "8787"))
    body = b"{}"
    request = urllib.request.Request(
        f"http://{host}:{port}/api/market/restart",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "X-Jarvis-Token": api_token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and bool(payload.get("configured"))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def login(*, open_browser: bool = True) -> Path:
    settings = interactive_login_settings()
    url = generate_login_url(settings)
    print("\nFYERS login URL:\n")
    print(url)
    if open_browser:
        webbrowser.open(url)
    print(
        "\nAfter login, copy the auth_code or the entire redirected URL.\n"
        "Do not paste your App Secret or access token here."
    )
    auth_value = input("\nFYERS auth_code / redirected URL: ").strip()
    exchange_auth_code(auth_value, settings)
    if notify_running_workstation():
        print("\nThe running JARVIS dashboard reloaded FYERS market data.")
    else:
        print("\nFYERS token saved. Relaunch JARVIS if the dashboard was already open.")
    return settings.token_file


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="JARVIS FYERS data-only authentication helper"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    login_parser = subparsers.add_parser("login", help="Create today's FYERS token")
    login_parser.add_argument(
        "--no-browser", action="store_true", help="Print the URL without opening it"
    )
    subparsers.add_parser("check", help="Validate the saved token with get_profile")
    subparsers.add_parser("path", help="Show where the token is stored")
    args = parser.parse_args(argv)

    try:
        if args.command == "login":
            token_path = login(open_browser=not args.no_browser)
            print(f"\nFYERS login succeeded. Token saved to:\n{token_path}")
        elif args.command == "check":
            create_client(validate_profile=True)
            print("FYERS connection is valid. Data APIs are ready.")
        else:
            print(FyersSettings.from_env().token_file)
    except (KeyboardInterrupt, EOFError):
        print("\nFYERS setup cancelled.")
        return 130
    except (RuntimeError, OSError) as exc:
        print(f"FYERS setup error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
