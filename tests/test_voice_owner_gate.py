from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.voice_owner_gate import VoiceOwnerGate


class VoiceOwnerGateTests(unittest.TestCase):
    def _gate(self, root: Path, *, required: bool) -> VoiceOwnerGate:
        return VoiceOwnerGate(
            state_path=root / "owner_gate.json",
            require_owner=required,
            provider_probe=lambda: False,
        )

    def test_default_dictation_mode_does_not_claim_speaker_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            gate = self._gate(Path(temp), required=False)

            status = gate.status()
            decision = gate.authorize_voice_command()

            self.assertEqual(status["mode"], "DICTATION_ONLY")
            self.assertFalse(status["owner_verified"])
            self.assertFalse(status["owner_lock_enforced"])
            self.assertTrue(decision["allowed"])
            self.assertEqual(decision["reason"], "OWNER_LOCK_NOT_REQUIRED")

    def test_required_owner_lock_fails_closed_without_provider_or_enrollment(self):
        with tempfile.TemporaryDirectory() as temp:
            gate = self._gate(Path(temp), required=True)

            status = gate.status()
            decision = gate.authorize_voice_command()

            self.assertEqual(status["mode"], "ENROLLMENT_REQUIRED")
            self.assertTrue(status["owner_lock_required"])
            self.assertFalse(status["owner_lock_enforced"])
            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["reason"], "OWNER_VERIFICATION_UNAVAILABLE")

    def test_client_claim_cannot_bypass_missing_trusted_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            gate = self._gate(Path(temp), required=True)

            decision = gate.authorize_voice_command(
                {"owner_verified": True, "score": 1.0, "provider": "browser"}
            )

            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["reason"], "OWNER_VERIFICATION_UNAVAILABLE")

    def test_environment_constructor_is_bounded_and_truthful(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ,
            {
                "JARVIS_REQUIRE_OWNER_VOICE": "1",
                "JARVIS_VOICE_OWNER_STATE": str(Path(temp) / "gate.json"),
            },
            clear=False,
        ):
            gate = VoiceOwnerGate.from_environment(provider_probe=lambda: False)

            self.assertTrue(gate.status()["owner_lock_required"])
            self.assertFalse(gate.authorize_voice_command()["allowed"])


if __name__ == "__main__":
    unittest.main()
