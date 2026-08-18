
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path.home() / "Documents" / "JARVIS_Trading"
ALERT_FILE = ROOT / "jarvis_alerts_v8.jsonl"


def speak(text: str) -> bool:
    """
    Windows-native TTS fallback.

    Uses PowerShell System.Speech when available. This is event-to-voice,
    not microphone speech recognition.
    """
    try:
        escaped = text.replace("'", "''")
        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{escaped}')"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return True
    except Exception:
        return False


def run_forever(poll_seconds: int = 2):
    pos = 0
    seen = set()

    print("JARVIS VOICE EVENT BRIDGE")
    print("Source:", ALERT_FILE)
    print("Press Ctrl+C to stop.")

    while True:
        if ALERT_FILE.exists():
            lines = ALERT_FILE.read_text(encoding="utf-8").splitlines()
            for line in lines[pos:]:
                pos += 1
                try:
                    x = json.loads(line)
                except Exception:
                    continue

                event_id = x.get("event_id")
                if not event_id or event_id in seen:
                    continue
                seen.add(event_id)

                message = (
                    f"{x.get('symbol', '')}. "
                    f"{x.get('title', '')}. "
                    f"{x.get('message', '')}"
                )

                print("JARVIS VOICE >", message)
                speak(message)

        time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
