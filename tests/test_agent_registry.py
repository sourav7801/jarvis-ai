import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from omni.agent_registry import AgentIsolation, AgentRegistry, AgentRequest, AgentSpec, AgentStatus, default_agent_specs
from omni.contracts import Step
from omni.contracts import Plan, StepStatus
from omni.audit import AuditStore
from omni.dispatch import StepDispatcher
from omni.isolated_runner import IsolatedAgentRunner, WorkerLimits, sign_payload, verify_payload

def spec(**overrides):
    values = {'name': 'demo', 'module': 'agents.demo', 'entrypoint': 'run', 'label': 'DEMO', 'capabilities': frozenset({'demo.read'}), 'max_input_chars': 100, 'max_output_chars': 100}
    values.update(overrides)
    return AgentSpec(**values)

class AgentRegistryTests(unittest.TestCase):

    def test_default_agents_are_unique_and_capability_scoped(self):
        registry = AgentRegistry(default_agent_specs())
        self.assertEqual(registry.names(), ('chat', 'coding', 'critic', 'customer_success', 'data_ai', 'design', 'engineering', 'evaluator', 'experiment', 'finance', 'health', 'knowledge', 'learning', 'legal', 'marketing', 'meta_improvement', 'office', 'operations', 'operator', 'people', 'product', 'quality', 'research', 'sales', 'security', 'skill_builder', 'strategy', 'trading', 'web_intelligence'))
        self.assertTrue(all((registry.get(name).capabilities for name in registry.names())))

    def test_capability_mismatch_is_rejected_without_import(self):
        registry = AgentRegistry([spec()])
        with patch('omni.agent_registry.audit_event'), patch('omni.agent_registry.importlib.import_module') as importer:
            response = registry.execute(AgentRequest('demo', 'work', frozenset({'demo.write'})))
        self.assertEqual(response.status, AgentStatus.REJECTED)
        importer.assert_not_called()

    def test_result_is_normalized_and_bounded(self):
        module = Mock()
        module.run.return_value = {'message': 'x' * 20}
        registry = AgentRegistry([spec(max_output_chars=10)])
        with patch('omni.agent_registry.audit_event'), patch('omni.agent_registry.importlib.import_module', return_value=module):
            response = registry.execute(AgentRequest('demo', 'work'))
        self.assertTrue(response.success)
        self.assertEqual(response.message, 'x' * 10)

    def test_agent_exception_is_normalized(self):
        module = Mock()
        module.run.side_effect = RuntimeError('broken')
        registry = AgentRegistry([spec()])
        with patch('omni.agent_registry.audit_event'), patch('omni.agent_registry.importlib.import_module', return_value=module):
            response = registry.execute(AgentRequest('demo', 'work'))
        self.assertEqual(response.status, AgentStatus.FAILED)
        self.assertEqual(response.error_type, 'RuntimeError')

    def test_isolated_agent_never_falls_back_in_process(self):
        registry = AgentRegistry([spec(isolation=AgentIsolation.ISOLATED_PROCESS)])
        with patch('omni.agent_registry.audit_event'), patch('omni.agent_registry.importlib.import_module') as importer:
            response = registry.execute(AgentRequest('demo', 'work'))
        self.assertEqual(response.status, AgentStatus.UNAVAILABLE)
        importer.assert_not_called()

class StepDispatcherTests(unittest.TestCase):

    def test_dispatches_agent_step(self):
        module = Mock()
        module.run.return_value = 'done'
        registry = AgentRegistry([spec()])
        dispatcher = StepDispatcher(registry, lambda _decision: 'unused')
        with patch('omni.agent_registry.audit_event'), patch('omni.agent_registry.importlib.import_module', return_value=module):
            result = dispatcher(Step('agent:demo', {'text': 'work', 'capabilities': ['demo.read']}))
        self.assertTrue(result.success)
        self.assertEqual(result.output, 'done')

    def test_dispatches_namespaced_tool_step(self):
        executor = Mock(return_value='tool-result')
        dispatcher = StepDispatcher(AgentRegistry(), executor)
        result = dispatcher(Step('tool:current_time', {}))
        self.assertTrue(result.success)
        executor.assert_called_once_with({'action': 'tool', 'tool': 'current_time', 'arguments': {}})

    def test_main_executes_durable_namespaced_plan(self):
        import main
        with tempfile.TemporaryDirectory() as directory:
            store = AuditStore(Path(directory) / 'audit.sqlite3')
            plan = Plan('tool plan', [Step('tool:current_time')])
            with patch.object(main, 'get_audit_store', return_value=store), patch.object(main, 'execute_tool', return_value='time-ok'):
                completed = main.execute_plan(plan)
        self.assertEqual(completed.steps[0].status, StepStatus.SUCCEEDED)
        self.assertEqual(completed.steps[0].output, 'time-ok')

class IsolatedRunnerTests(unittest.TestCase):

    def test_signed_payload_detects_tampering(self):
        payload = {'request': 'safe'}
        signature = sign_payload(payload, 'secret')
        self.assertTrue(verify_payload(payload, signature, 'secret'))
        self.assertFalse(verify_payload({'request': 'changed'}, signature, 'secret'))

    def test_dependency_free_health_agent_runs_in_isolation(self):
        health_spec = next((item for item in default_agent_specs() if item.name == 'health'))
        runner = IsolatedAgentRunner(limits=WorkerLimits(timeout_seconds=10), signing_key='test-secret')
        with patch('omni.isolated_runner.audit_event'):
            result = runner(health_spec, 'health check')
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'HEALTHY')
if __name__ == '__main__':
    unittest.main()
