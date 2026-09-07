from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omni.cognitive_event_bus import CognitiveEventBus, CognitiveEventType


class CognitiveEventRedactionTests(unittest.TestCase):
    def test_sensitive_payload_and_provenance_fields_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bus = CognitiveEventBus(Path(folder) / "events.json", persist=False)
            bus.publish(
                CognitiveEventType.MODEL_ROUTE_COMPLETED,
                source="router",
                subject="local-model",
                payload={
                    "provider": "test",
                    "api_key": "should-not-survive",
                    "nested": {"Authorization": "Bearer abc", "safe": "visible"},
                },
                provenance={"token": "secret-token", "safe": True},
            )
            event = bus.snapshot()["events"][0]
            self.assertEqual(event["payload"]["api_key"], "[REDACTED]")
            self.assertEqual(event["payload"]["nested"]["Authorization"], "[REDACTED]")
            self.assertEqual(event["provenance"]["token"], "[REDACTED]")
            self.assertEqual(event["payload"]["nested"]["safe"], "visible")
            self.assertTrue(bus.snapshot()["redacts_sensitive_fields"])


if __name__ == "__main__":
    unittest.main()
