from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import jarvis_dev_agent


class DevAgentUntrackedGuardTests(unittest.TestCase):
    def test_changed_files_includes_new_untracked_paths(self):
        with (
            patch.object(
                jarvis_dev_agent,
                "git_text",
                return_value="agents/chat_agent.py\n",
            ),
            patch.object(
                jarvis_dev_agent,
                "untracked_files",
                return_value={"omni/new_runtime.py"},
            ),
        ):
            self.assertEqual(
                jarvis_dev_agent.changed_files("HEAD"),
                [
                    "agents/chat_agent.py",
                    "omni/new_runtime.py",
                ],
            )

    def test_untracked_protected_core_path_is_blocked(self):
        protected = next(
            iter(
                jarvis_dev_agent.PROTECTED_CORE
            )
        )

        with (
            patch.object(
                jarvis_dev_agent,
                "git_text",
                return_value="",
            ),
            patch.object(
                jarvis_dev_agent,
                "untracked_files",
                return_value={protected},
            ),
        ):
            files = jarvis_dev_agent.changed_files("HEAD")

        self.assertIn(
            protected,
            jarvis_dev_agent.protected_changes(files),
        )


if __name__ == "__main__":
    unittest.main()
