from __future__ import annotations

from typing import Any

from workstation.crypto_options_intelligence import option_command_payload
from workstation.india_options_intelligence import analyze_india_option_request


def options_command_payload(text: str) -> dict[str, Any] | None:
    command = str(text or "").strip()
    if not command:
        return None

    india = analyze_india_option_request(command)
    if india is not None:
        return india

    return option_command_payload(command)
