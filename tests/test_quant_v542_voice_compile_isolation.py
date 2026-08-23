from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(r"C:\\Jarvis")
VOICE_TEST = ROOT / "tests" / "test_jarvis_v32_hybrid_voice.py"


class QuantV542VoiceCompileIsolationTests(unittest.TestCase):
    def test_voice_compile_output_is_process_unique(self):
        source = VOICE_TEST.read_text(encoding="utf-8")
        self.assertIn("os.getpid()", source)
        self.assertIn("JarvisVoiceService.test.", source)
        self.assertNotIn("'/out:C:\\\\Jarvis\\\\.jarvis-dev\\\\JarvisVoiceService.test.exe'", source)


if __name__ == "__main__":
    unittest.main()
