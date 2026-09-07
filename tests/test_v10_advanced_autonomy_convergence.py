from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.agent_registry import default_agent_specs
from omni.critic_verifier import CriticVerifier
from omni.evidence_ledger import EvidenceLedger
from omni.engineering_governance import GovernedEngineeringWorkflow
from omni.system_diagnostics import SystemDiagnostics
from workstation import completion_console_v10


ROOT = Path(__file__).resolve().parents[1]


class EvidenceLedgerV10Tests(unittest.TestCase):
    def test_evidence_is_bounded_persistent_and_redacts_nested_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.json"
            ledger = EvidenceLedger(path)
            row = ledger.record(
                kind="TEST",
                subject="nested-redaction",
                claim="verify nested secrets are never persisted",
                source="unit-test",
                freshness="FRESH",
                evidence={
                    "outer": {
                        "level2": {
                            "level3": {
                                "authorization": "Bearer should-not-persist",
                                "safe": "visible",
                            }
                        }
                    }
                },
                provenance={"api_key": "also-secret", "safe": "ok"},
            )
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("should-not-persist", raw)
            self.assertNotIn("also-secret", raw)
            self.assertEqual(row["freshness"], "FRESH")
            reloaded = EvidenceLedger(path).snapshot()
            self.assertEqual(reloaded["count"], 1)
            self.assertTrue(reloaded["redacts_sensitive_fields"])
            self.assertFalse(reloaded["live_execution"])


class CriticVerifierV10Tests(unittest.TestCase):
    def make_verifier(self):
        return CriticVerifier()

    def test_verified_when_fresh_provenanced_evidence_passes(self):
        verifier = self.make_verifier()
        with patch("omni.evidence_ledger.EVIDENCE_LEDGER.record", return_value={}), \
             patch("omni.cognitive_event_bus.COGNITIVE_EVENT_BUS.publish", return_value={}):
            result = verifier.verify(
                subject="engineering:test",
                domain="ENGINEERING",
                evidence=[{
                    "source": "unit-test",
                    "freshness": "FRESH",
                    "provenance": {"sha": "abc"},
                    "claim": "test passed",
                }],
                required_evidence=1,
                require_fresh=True,
                require_provenance=True,
                policy={"live_execution": False, "automatic_broker_order": False, "external_actions": "APPROVAL_GATED"},
            )
        self.assertEqual(result["verdict"], "VERIFIED")
        self.assertTrue(result["progression_allowed"])
        self.assertFalse(result["safety"]["live_execution"])

    def test_contradiction_blocks_progression(self):
        verifier = self.make_verifier()
        with patch("omni.evidence_ledger.EVIDENCE_LEDGER.record", return_value={}), \
             patch("omni.cognitive_event_bus.COGNITIVE_EVENT_BUS.publish", return_value={}):
            result = verifier.verify(
                subject="market:test",
                domain="MARKETS",
                evidence=[{"source": "verified", "freshness": "FRESH", "provenance": {"provider": "TEST"}}],
                contradictions=["higher timeframe structure conflicts"],
                required_evidence=1,
                require_fresh=True,
                require_provenance=True,
            )
        self.assertEqual(result["verdict"], "CONTRADICTED")
        self.assertFalse(result["progression_allowed"])

    def test_unsafe_policy_fails_closed(self):
        verifier = self.make_verifier()
        with patch("omni.evidence_ledger.EVIDENCE_LEDGER.record", return_value={}), \
             patch("omni.cognitive_event_bus.COGNITIVE_EVENT_BUS.publish", return_value={}):
            result = verifier.verify(
                subject="unsafe",
                evidence=[{"source": "test", "freshness": "FRESH", "provenance": {"x": 1}}],
                policy={"live_execution": True},
            )
        self.assertEqual(result["verdict"], "FAILED")
        self.assertIn("LIVE_EXECUTION_REQUESTED", result["checks"]["policy_violations"])


class EngineeringGovernanceV10Tests(unittest.TestCase):
    def test_inspection_and_plan_are_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            workflow = GovernedEngineeringWorkflow(Path(folder) / "state.json")
            inspection = workflow.inspect()
            self.assertTrue(inspection["success"])
            self.assertFalse(inspection["automatic_editing"])
            with patch("omni.code_intelligence.CODE_INTELLIGENCE.search", return_value=[]):
                plan = workflow.plan("Add a bounded diagnostic endpoint without changing live execution.")
            self.assertEqual(plan["current_stage"], "PLAN")
            self.assertFalse(plan["safety"]["automatic_editing"])
            self.assertFalse(plan["safety"]["automatic_merge"])
            self.assertFalse(plan["safety"]["live_execution"])

    def test_branch_creation_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            workflow = GovernedEngineeringWorkflow(Path(folder) / "state.json")
            with self.assertRaises(PermissionError):
                workflow.create_child_branch("jarvis-dev/test-v10", operator_confirmed=False)


class SystemDiagnosticsV10Tests(unittest.TestCase):
    def test_unknown_or_destructive_recovery_is_rejected(self):
        diagnostics = SystemDiagnostics()
        with self.assertRaises(PermissionError):
            diagnostics.apply_safe_recovery("DELETE_FILES")

    def test_status_never_claims_unknown_process_termination(self):
        diagnostics = SystemDiagnostics()
        fake = {
            "overall": "READY",
            "incidents": [],
            "recovery_proposals": [],
            "automatic_repair_scope": ["RECOVER_EXPIRED_MISSION_LEASES", "REFRESH_WORLD_MODEL"],
        }
        with patch.object(diagnostics, "inspect", return_value=fake):
            status = diagnostics.status()
        self.assertFalse(status["unknown_process_termination"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["automatic_broker_order"])


class CompletionV10Tests(unittest.TestCase):
    def test_overview_adds_advanced_surfaces_without_weakening_safety(self):
        base = {
            "success": True,
            "version": "9.3",
            "overall": "READY",
            "subsystems": {},
            "safety": {
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            },
        }
        advanced = {
            name: {"healthy": True, "state": "READY", "data": {"success": True}, "error": None}
            for name in (
                "critic_verifier", "evidence_ledger", "engineering_governance",
                "system_diagnostics", "trading_governance",
            )
        }
        with patch.object(completion_console_v10.v93, "overview_payload", return_value=base), \
             patch.object(completion_console_v10.ADVANCED, "collect", return_value=advanced):
            payload = completion_console_v10.overview_payload()
        self.assertEqual(payload["version"], "10.0")
        self.assertTrue(payload["advanced"]["system_critic"])
        self.assertTrue(payload["advanced"]["governed_engineering"])
        self.assertTrue(payload["safety"]["paper_only"])
        self.assertFalse(payload["safety"]["live_execution"])
        self.assertFalse(payload["safety"]["automatic_broker_order"])
        self.assertFalse(payload["safety"]["automatic_production_strategy_rewrite"])

    def test_ui_contains_advanced_navigation_and_no_broker_order_surface(self):
        html = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "workstation" / "completion_console_static" / "v10_advanced.js").read_text(encoding="utf-8")
        self.assertIn('id="criticNav"', html)
        self.assertIn('id="engineeringGovNav"', html)
        self.assertIn('id="systemDiagNav"', html)
        self.assertIn('id="tradingGovNav"', html)
        self.assertIn("/api/critic", script)
        self.assertIn("/api/engineering", script)
        self.assertIn("/api/system-diagnostics", script)
        self.assertIn("/api/trading-governance", script)
        forbidden = ("place_order(", "modify_order(", "cancel_order(", "submit_order(")
        for token in forbidden:
            self.assertNotIn(token, script)


class V10PermanentAgentContractTests(unittest.TestCase):
    def test_system_planes_do_not_become_agent_30(self):
        specs = {spec.name: spec for spec in default_agent_specs()}
        self.assertEqual(len(specs), 29)

        # Protected legacy Critic specialist remains part of the 29-agent contract.
        self.assertIn("critic", specs)
        self.assertEqual(specs["critic"].module, "agents.meta_critic")

        # V10 orchestration/governance planes are system services, not agent #30+.
        for name in (
            "executive",
            "autonomy_orchestrator",
            "critic_verifier",
            "engineering_governance",
            "system_diagnostics",
            "trading_governance",
            "evidence_ledger",
            "world_model",
            "cognitive_event_bus",
        ):
            self.assertNotIn(name, specs)


if __name__ == "__main__":
    unittest.main()
