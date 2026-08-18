from __future__ import annotations

import asyncio
import inspect
import uuid
from dataclasses import MISSING, asdict, fields, is_dataclass
from typing import Any

from omni.agent_registry import (
    AgentRegistry,
    AgentRequest,
    default_agent_specs,
)
from omni.collaboration import CollaborationEngine


class RegistryAdapterError(RuntimeError):
    pass


class GovernedAgentRunner:
    """
    Adapter between CollaborationEngine and the existing AgentRegistry.

    It NEVER imports or executes specialist modules directly.
    All execution goes through AgentRegistry.
    """

    METHOD_NAMES = (
        "execute",
        "run",
        "dispatch",
        "invoke",
        "run_agent",
        "call_agent",
        "handle",
    )

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

        self.specs = {
            spec.name: spec
            for spec in default_agent_specs()
        }

        self.method_name, self.method = (
            self._resolve_method()
        )

    def _resolve_method(self):

        for name in self.METHOD_NAMES:

            method = getattr(
                self.registry,
                name,
                None,
            )

            if callable(method):
                return name, method

        public = [
            name
            for name in dir(self.registry)
            if not name.startswith("_")
            and callable(
                getattr(self.registry, name, None)
            )
        ]

        raise RegistryAdapterError(
            "Could not locate AgentRegistry execution "
            f"method. Public methods: {public}"
        )

    def _capability_for(self, agent: str) -> str:
        """
        Select a deterministic, low-risk capability for
        multi-agent collaboration.

        This must never depend on set/frozenset iteration order.
        """

        spec = self.specs.get(agent)

        if spec is None:
            raise RegistryAdapterError(
                f"Unknown operational agent: {agent}"
            )

        capabilities = frozenset(
            getattr(spec, "capabilities", ()) or ()
        )

        if not capabilities:
            raise RegistryAdapterError(
                f"Agent '{agent}' exposes no capability."
            )

        preferred = {
            "operator": "goal.plan",
            "health": "system.health",
            "research": "research.read",
            "web_intelligence": "web.search",
            "coding": "code.analyze",
            "office": "document.analyze",
            "chat": "conversation",

            # IMPORTANT:
            # collaboration performs research/analysis,
            # not synthetic execution.
            "trading": "trading.research",
            "learning": "learning.acquire",
            "knowledge": "knowledge.structure",
            "skill_builder": "skill.propose",
            "experiment": "experiment.design",
            "evaluator": "evaluation.score",
            "critic": "critique.review",
            "meta_improvement": "system.improvement.propose",

            "strategy": "strategy.analyze",
            "product": "product.plan",
            "engineering": "architecture.analyze",
            "data_ai": "ai.evaluate",
            "design": "experience.plan",
            "security": "security.analyze",
            "legal": "legal.research",
            "finance": "finance.model",
            "operations": "operations.plan",
            "marketing": "marketing.plan",
            "sales": "sales.plan",
            "customer_success": "customer_success.plan",
            "people": "people.plan",
            "quality": "quality.analyze",
        }.get(agent)

        if preferred in capabilities:
            return preferred

        # Deterministic fallback.
        return sorted(capabilities)[0]

    def _make_request(
        self,
        agent: str,
        prompt: str,
        context: dict[str, Any],
    ) -> AgentRequest:

        capability = self._capability_for(agent)

        payload = {
            "request": prompt,
            "context": context,
            "collaboration": True,
        }

        values = {
            "agent": agent,
            "agent_name": agent,
            "name": agent,
            "target": agent,
            "target_agent": agent,

            "capability": capability,
            "required_capability": capability,
            "required_capabilities": frozenset({capability}),

            "payload": payload,
            "data": payload,
            "arguments": payload,
            "params": payload,

            "prompt": prompt,
            "query": prompt,
            "message": prompt,
            "task": prompt,
            "instruction": prompt,

            "context": context,
            "metadata": context,

            "request_id": str(uuid.uuid4()),
            "trace_id": str(uuid.uuid4()),
            "correlation_id": str(uuid.uuid4()),
        }

        if is_dataclass(AgentRequest):

            kwargs = {}

            for field in fields(AgentRequest):

                name = field.name

                if name in values:
                    kwargs[name] = values[name]
                    continue

                required = (
                    field.default is MISSING
                    and field.default_factory is MISSING
                )

                if not required:
                    continue

                annotation = str(
                    field.type
                ).lower()

                if (
                    "dict" in annotation
                    or "mapping" in annotation
                    or "any" in annotation
                ):
                    kwargs[name] = payload

                elif "str" in annotation:
                    kwargs[name] = prompt

                else:
                    raise RegistryAdapterError(
                        "Unsupported required "
                        "AgentRequest field: "
                        f"{name} ({field.type})"
                    )

            return AgentRequest(**kwargs)

        signature = inspect.signature(
            AgentRequest
        )

        kwargs = {}

        for name, param in signature.parameters.items():

            if name in values:
                kwargs[name] = values[name]
                continue

            if param.default is not inspect._empty:
                continue

            annotation = str(
                param.annotation
            ).lower()

            if (
                "dict" in annotation
                or "mapping" in annotation
                or "any" in annotation
            ):
                kwargs[name] = payload

            elif "str" in annotation:
                kwargs[name] = prompt

            else:
                raise RegistryAdapterError(
                    f"Unsupported AgentRequest parameter: {name}"
                )

        return AgentRequest(**kwargs)

    def _invoke_registry(
        self,
        request: AgentRequest,
        agent: str,
        prompt: str,
        context: dict[str, Any],
    ):

        signature = inspect.signature(
            self.method
        )

        parameters = list(
            signature.parameters.values()
        )

        # Most registry implementations accept
        # exactly one AgentRequest.
        if len(parameters) == 1:
            result = self.method(request)

        else:

            kwargs = {}

            for param in parameters:

                name = param.name

                if name in {
                    "request",
                    "agent_request",
                    "req",
                }:
                    kwargs[name] = request

                elif name in {
                    "agent",
                    "agent_name",
                    "target_agent",
                }:
                    kwargs[name] = agent

                elif name in {
                    "prompt",
                    "message",
                    "query",
                    "task",
                }:
                    kwargs[name] = prompt

                elif name in {
                    "context",
                    "metadata",
                }:
                    kwargs[name] = context

                elif (
                    param.default
                    is inspect._empty
                ):
                    raise RegistryAdapterError(
                        "Unsupported required registry "
                        f"parameter: {name}"
                    )

            result = self.method(**kwargs)

        if inspect.isawaitable(result):

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                result = asyncio.run(result)
            else:
                raise RegistryAdapterError(
                    "Async AgentRegistry call encountered "
                    "inside an active event loop."
                )

        return result

    @staticmethod
    def _normalize_response(response):

        if is_dataclass(response):
            data = asdict(response)

        elif isinstance(response, dict):
            data = response

        else:
            data = None

        if data is not None:

            success = data.get(
                "success",
                data.get("ok", True),
            )

            if success is False:
                raise RegistryAdapterError(
                    str(
                        data.get("error")
                        or data.get("message")
                        or "Agent execution failed."
                    )
                )

            for key in (
                "result",
                "output",
                "response",
                "answer",
                "data",
                "message",
                "payload",
            ):
                if key in data:
                    return data[key]

            return data

        success = getattr(
            response,
            "success",
            getattr(response, "ok", True),
        )

        if success is False:

            raise RegistryAdapterError(
                str(
                    getattr(response, "error", None)
                    or getattr(response, "message", None)
                    or "Agent execution failed."
                )
            )

        for name in (
            "result",
            "output",
            "response",
            "answer",
            "data",
            "message",
            "payload",
        ):

            if hasattr(response, name):
                value = getattr(
                    response,
                    name
                )

                if value is not None:
                    return value

        return response

    def __call__(
        self,
        agent: str,
        prompt: str,
        context: dict[str, Any],
    ):

        request = self._make_request(
            agent,
            prompt,
            context,
        )

        response = self._invoke_registry(
            request,
            agent,
            prompt,
            context,
        )

        return self._normalize_response(
            response
        )


def resolve_main_registry() -> AgentRegistry:
    """
    Reuse the exact AgentRegistry already owned by main.py.
    """

    import main

    for value in vars(main).values():

        if isinstance(
            value,
            AgentRegistry,
        ):
            return value

    raise RegistryAdapterError(
        "main.py does not expose an AgentRegistry instance."
    )


class GovernedCollaborationRuntime:

    def __init__(
        self,
        registry: AgentRegistry,
    ):
        self.registry = registry

        self.runner = GovernedAgentRunner(
            registry
        )

        self.engine = CollaborationEngine()

    def collaborate(
        self,
        request: str,
    ):
        return self.engine.collaborate(
            request,
            self.runner,
        )


def build_runtime():
    return GovernedCollaborationRuntime(
        resolve_main_registry()
    )
