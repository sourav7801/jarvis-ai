import unittest

from tools.jarvis_dev_agent import (
    PROTECTED_CORE,
    protected_changes,
)


class JarvisDevAgentTests(unittest.TestCase):

    def test_protected_core_detection(self):

        result = protected_changes(
            [
                "workstation/app.py",
                "omni/runtime.py",
            ]
        )

        self.assertEqual(
            result,
            ["omni/runtime.py"],
        )


    def test_normal_file_is_allowed(self):

        result = protected_changes(
            [
                "workstation/app.py",
                "agents/trading_agent.py",
            ]
        )

        self.assertEqual(
            result,
            [],
        )


    def test_core_manifest_contains_runtime(self):

        self.assertIn(
            "omni/runtime.py",
            PROTECTED_CORE,
        )


if __name__ == "__main__":
    unittest.main()
