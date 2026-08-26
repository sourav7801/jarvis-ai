from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import start_jarvis_v3


class IdempotentMasterLauncherTests(unittest.TestCase):
    @patch("start_jarvis_v3.urllib.request.urlopen")
    def test_existing_master_requires_expected_dashboard_markers(self, urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = (
            b"<title>JARVIS</title> OMNI OPERATING COMMAND CENTER "
            b"window.JARVIS_TOKEN = 'private'"
        )
        urlopen.return_value.__enter__.return_value = response

        self.assertTrue(start_jarvis_v3.existing_jarvis_master())

    @patch("start_jarvis_v3.urllib.request.urlopen")
    def test_unknown_local_service_is_not_reused(self, urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b"<title>Another application</title>"
        urlopen.return_value.__enter__.return_value = response

        self.assertFalse(start_jarvis_v3.existing_jarvis_master())

    @patch("start_jarvis_v3.webbrowser.open")
    @patch("start_jarvis_v3.existing_jarvis_master", return_value=True)
    @patch("start_jarvis_v3.port_open", return_value=True)
    def test_main_reuses_healthy_master_and_exits_successfully(
        self,
        _port_open,
        _existing,
        browser_open,
    ):
        start_jarvis_v3.main()

        browser_open.assert_called_once_with("http://127.0.0.1:8797")


if __name__ == "__main__":
    unittest.main()
