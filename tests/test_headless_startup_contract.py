from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import start_jarvis_v3


class HeadlessStartupContractTests(unittest.TestCase):
    def test_browser_is_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_NO_BROWSER", None)
            self.assertTrue(start_jarvis_v3.browser_enabled())

    def test_browser_can_be_suppressed_for_owned_background_health_checks(self):
        with patch.dict(os.environ, {"JARVIS_NO_BROWSER": "1"}):
            self.assertFalse(start_jarvis_v3.browser_enabled())


if __name__ == "__main__":
    unittest.main()
