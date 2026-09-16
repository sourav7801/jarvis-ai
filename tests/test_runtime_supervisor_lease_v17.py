import tempfile
import unittest
from pathlib import Path

from scripts.runtime_supervisor_safety_v15 import SupervisorLeaseV15


class SupervisorLeaseV17RegressionTests(unittest.TestCase):
    def test_second_supervisor_fails_cleanly_and_can_acquire_after_release(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = SupervisorLeaseV15(root)
            second = SupervisorLeaseV15(root)

            self.assertTrue(first.acquire())
            try:
                # Contention must be a normal False result. In the previous
                # Windows implementation read(1) on the locked byte could raise
                # PermissionError before the lock attempt was reached.
                self.assertFalse(second.acquire())
            finally:
                first.release()

            self.assertTrue(second.acquire())
            second.release()


if __name__ == "__main__":
    unittest.main()
