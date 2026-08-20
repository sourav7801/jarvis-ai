from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(r"C:\\Jarvis")
VOICE_TEST = ROOT / "tests" / "test_jarvis_v32_hybrid_voice.py"


class QuantV542VoiceCompileIsolationTests(unittest.TestCase):
    def test_native_voice_compile_uses_unique_output(self):
        source = VOICE_TEST.read_text(encoding="utf-8")
        self.assertIn("JarvisVoiceService.test.", source)
        self.assertIn("uuid.uuid4().hex", source)
        self.assertNotIn("'/out:C:\\\\Jarvis\\\\.jarvis-dev\\\\JarvisVoiceService.test.exe'", source)

    def test_compile_artifact_cleanup_is_best_effort(self):
        source = VOICE_TEST.read_text(encoding="utf-8")
        self.assertIn("output.unlink(missing_ok=True)", source)
        self.assertIn("except OSError", source)


if __name__ == "__main__":
    unittest.main()
