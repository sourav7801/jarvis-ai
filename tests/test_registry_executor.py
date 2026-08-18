import unittest

import tools.computer_phase1  # registers tools
from core.executor import ToolExecutor
from core.types import ToolCall
from tools.registry import list_tools


class RegistryExecutorTests(unittest.TestCase):
    def test_current_time_registered(self):
        self.assertIn("current_time", list_tools())

    def test_current_time_executes(self):
        result = ToolExecutor().execute(ToolCall("current_time", {}))
        self.assertTrue(result.success)
        self.assertEqual(result.tool, "current_time")
        self.assertIn("Current date and time:", result.message)

    def test_unknown_tool_fails_safely(self):
        result = ToolExecutor().execute(ToolCall("does_not_exist", {}))
        self.assertFalse(result.success)
        self.assertIn("Unknown tool", result.error)


if __name__ == "__main__":
    unittest.main()
