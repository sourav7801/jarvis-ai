from pathlib import Path
import unittest


class QuantV32ManifestTests(unittest.TestCase):
    def test_manifest_keeps_live_execution_locked(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "workstation"
            / "options_intelligence_manifest.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Live broker execution remains locked", text)
        self.assertIn("NIFTY and BANKNIFTY", text)


if __name__ == "__main__":
    unittest.main()
