import tempfile
import unittest

from pathlib import (
    Path,
)

from unittest.mock import (
    patch,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.operator_v5_reliability import (
    EvidenceLedger,
    OperatorV5Reliability,
)

from omni.universal_command_bridge import (
    command_bridge,
)

from omni.voice_conversation_v2 import (
    voice_conversation_v2,
)


class MegaSprintATests(
    unittest.TestCase
):

    def test_protected_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_operator_v5_status(
        self,
    ):

        status = (
            main
            .jarvis_operator_v5_status()
        )


        self.assertTrue(
            status[
                "cursor_guard"
            ]
        )


        self.assertFalse(
            status[
                "automatic_destructive_escalation"
            ]
        )


    def test_evidence_ledger(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            ledger = EvidenceLedger(
                Path(
                    tmp
                )
                / "evidence.jsonl"
            )


            ledger.record(
                "test",
                value=1,
            )


            rows = ledger.recent()


            self.assertEqual(
                rows[
                    -1
                ][
                    "event"
                ],
                "test",
            )


    def test_file_verification(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(
                    tmp
                )
                / "file.txt"
            )


            path.write_text(
                "hello",
                encoding="utf-8",
            )


            operator = (
                OperatorV5Reliability(
                    ledger=
                        EvidenceLedger(
                            Path(
                                tmp
                            )
                            / "ledger.jsonl"
                        )
                )
            )


            result = operator.verify_file(
                path
            )


            self.assertTrue(
                result[
                    "verified"
                ]
            )


    def test_command_bridge_discovery(
        self,
    ):

        self.assertIsInstance(
            command_bridge.discover(),
            tuple,
        )


    def test_command_bridge_native(
        self,
    ):

        with patch.object(
            command_bridge,
            "_native",
            return_value="hello",
        ):

            result = (
                command_bridge
                .execute(
                    "hello"
                )
            )


            self.assertTrue(
                result[
                    "success"
                ]
            )


            self.assertEqual(
                result[
                    "response"
                ],
                "hello",
            )


    def test_voice_v2_status(
        self,
    ):

        status = (
            voice_conversation_v2
            .status()
        )


        self.assertIn(
            "continuous_existing_voice_mode",
            status,
        )


    def test_system_status(
        self,
    ):

        status = (
            main.jarvis_system_status()
        )


        self.assertTrue(
            status[
                "protected_core"
            ]
        )


    def test_trading_remains_blocked(
        self,
    ):

        status = (
            main.jarvis_trading_v8_status()
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "automatic_broker_order"
            ]
        )


    def test_public_apis(
        self,
    ):

        names = (
            "jarvis_operator_v5_status",
            "jarvis_operator_v5_snapshot",
            "jarvis_operator_v5_resume",
            "jarvis_operator_v5_apply_replan",
            "jarvis_operator_v5_evidence",
            "jarvis_command",
            "jarvis_voice_v2_status",
            "jarvis_system_status",
        )


        for name in names:

            self.assertTrue(
                callable(
                    getattr(
                        main,
                        name,
                    )
                )
            )


if __name__ == "__main__":

    unittest.main()
