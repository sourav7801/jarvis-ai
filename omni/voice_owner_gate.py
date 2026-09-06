from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "data" / "voice" / "owner_gate.json"


def _enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _speaker_provider_available() -> bool:
    """Return true only when the supported local speaker stack is installed."""

    return bool(
        importlib.util.find_spec("speechbrain")
        and importlib.util.find_spec("torch")
        and importlib.util.find_spec("torchaudio")
    )


@dataclass(frozen=True)
class VoiceAuthorization:
    allowed: bool
    reason: str
    owner_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "owner_verified": self.owner_verified,
        }


class VoiceOwnerGate:
    """Fail-closed boundary between dictation and speaker identity.

    Browser speech recognition provides text and confidence, not a trustworthy
    speaker identity. This gate never accepts a browser-provided
    ``owner_verified`` claim. When owner lock is required, voice commands stay
    blocked until a supported local verifier and an owner enrollment exist.
    """

    def __init__(
        self,
        *,
        state_path: Path = DEFAULT_STATE_PATH,
        require_owner: bool = False,
        provider_probe: Callable[[], bool] = _speaker_provider_available,
    ) -> None:
        self.state_path = Path(state_path)
        self.require_owner = bool(require_owner)
        self._provider_probe = provider_probe

    @classmethod
    def from_environment(
        cls,
        *,
        provider_probe: Callable[[], bool] = _speaker_provider_available,
    ) -> "VoiceOwnerGate":
        return cls(
            state_path=Path(
                os.getenv("JARVIS_VOICE_OWNER_STATE", str(DEFAULT_STATE_PATH))
            ),
            require_owner=_enabled(os.getenv("JARVIS_REQUIRE_OWNER_VOICE")),
            provider_probe=provider_probe,
        )

    def _enrollment(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return {}
        if not isinstance(value, dict):
            return {}
        if not value.get("enrollment_id") or not value.get("provider"):
            return {}
        return value

    def status(self) -> dict[str, Any]:
        provider_available = bool(self._provider_probe())
        enrollment = self._enrollment()
        enrolled = bool(enrollment)
        # Enrollment metadata and installed libraries are prerequisites, not a
        # proof that the current utterance has passed speaker verification.
        # The real-time trusted verifier/grant bridge is intentionally not
        # claimed until it exists.
        enforced = False

        if self.require_owner and provider_available and enrolled:
            mode = "VERIFIER_RUNTIME_REQUIRED"
            detail = (
                "Owner enrollment metadata and the model stack are present, but "
                "the trusted real-time verification grant bridge is not active. "
                "Voice commands remain blocked."
            )
        elif self.require_owner:
            mode = "ENROLLMENT_REQUIRED"
            detail = (
                "Owner lock is required, so voice commands fail closed until a "
                "supported local speaker verifier is installed and enrolled."
            )
        else:
            mode = "DICTATION_ONLY"
            detail = (
                "Speech-to-text is available, but speaker identity is not verified. "
                "Wake words and transcript confidence are not owner authentication."
            )

        return {
            "mode": mode,
            "owner_lock_required": self.require_owner,
            "owner_lock_enforced": enforced,
            "owner_verified": False,
            "provider": str(enrollment.get("provider") or "SPEECHBRAIN_ECAPA"),
            "provider_available": provider_available,
            "enrolled": enrolled,
            "raw_audio_stored": False,
            "detail": detail,
        }

    def authorize_voice_command(
        self,
        _untrusted_client_claim: Any = None,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["owner_lock_required"]:
            return VoiceAuthorization(True, "OWNER_LOCK_NOT_REQUIRED").to_dict()

        # Client claims are ignored. A supported local verifier must eventually
        # issue a server-side grant; until then, required mode remains closed.
        return VoiceAuthorization(
            False,
            "OWNER_VERIFICATION_UNAVAILABLE",
        ).to_dict()


VOICE_OWNER_GATE = VoiceOwnerGate.from_environment()
