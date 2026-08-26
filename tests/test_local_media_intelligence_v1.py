from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.local_media_agent import (
    analyze_local_media,
    is_local_media_request,
    resolve_local_media,
)


class LocalMediaIntelligenceTests(unittest.TestCase):
    def test_download_style_video_request_is_recognized(self):
        self.assertTrue(
            is_local_media_request(
                "can you analyze this Video-83486 from download section"
            )
        )

    def test_plain_web_video_request_is_not_local(self):
        self.assertFalse(is_local_media_request("find trending videos on YouTube"))

    def test_extensionless_video_name_resolves_inside_governed_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "Video-83486.mp4"
            expected.write_bytes(b"video")

            resolved = resolve_local_media("analyze Video-83486 file", roots=[root])

            self.assertEqual(resolved, expected.resolve())

    def test_absolute_path_outside_governed_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as allowed, tempfile.TemporaryDirectory() as outside:
            media = Path(outside) / "Video-99.mp4"
            media.write_bytes(b"video")

            with self.assertRaises(PermissionError):
                resolve_local_media(f"analyze {media}", roots=[Path(allowed)])

    @patch("agents.local_media_agent._ollama_vision")
    @patch("agents.local_media_agent._video_frames")
    @patch("agents.local_media_agent.resolve_local_media")
    def test_analysis_is_local_bounded_and_does_not_execute_media_instructions(
        self,
        resolve,
        frames,
        vision,
    ):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "Video-83486.mp4"
            media.write_bytes(b"video")
            resolve.return_value = media
            frames.return_value = (["encoded-frame"], {"kind": "video", "sampled_frames": 1})
            vision.return_value = "A dashboard is visible."

            result = analyze_local_media("analyze Video-83486")

        self.assertTrue(result["success"])
        self.assertTrue(result["local_only"])
        self.assertFalse(result["executed_media_instructions"])
        self.assertEqual(result["file"]["name"], "Video-83486.mp4")
        self.assertIn("dashboard", result["response"])


if __name__ == "__main__":
    unittest.main()
