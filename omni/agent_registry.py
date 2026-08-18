"""Typed capability registry and execution boundary for specialized agents."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from .runtime import audit_event


class AgentStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    REJECTED = "REJECTED"


class AgentIsolation(str, Enum):
    IN_PROCESS = "IN_PROCESS"
    ISOLATED_PROCESS = "ISOLATED_PROCESS"


@dataclass(frozen=True)
class AgentSpec:
    name: str
    module: str
    entrypoint: str
    label: str
    capabilities: frozenset[str]
    enabled: bool = True
    max_input_chars: int = 20_000
    max_output_chars: int = 100_000
    isolation: AgentIsolation = AgentIsolation.IN_PROCESS

    def __post_init__(self) -> None:
        if not all(
            value.strip() for value in (self.name, self.module, self.entrypoint, self.label)
        ):
            raise ValueError("Agent identity fields cannot be empty.")
        if not self.capabilities:
            raise ValueError("Every agent requires at least one capability.")
        if self.max_input_chars < 1 or self.max_output_chars < 1:
            raise ValueError("Agent input and output bounds must be positive.")


@dataclass(frozen=True)
class AgentRequest:
    agent: str
    text: str
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    correlation_id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True)
class AgentResponse:
    status: AgentStatus
    agent: str
    message: str
    correlation_id: str
    data: Any = None
    error_type: str | None = None

    @property
    def success(self) -> bool:
        return self.status == AgentStatus.SUCCEEDED


class AgentRegistry:
    def __init__(self, specs=(), isolated_runner=None):
        self._specs: dict[str, AgentSpec] = {}
        self._isolated_runner = isolated_runner
        for spec in specs:
            self.register(spec)

    def register(self, spec: AgentSpec) -> None:
        name = spec.name.strip().lower()
        if name in self._specs:
            raise ValueError(f"Agent '{name}' is already registered.")
        self._specs[name] = spec

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def get(self, name: str) -> AgentSpec | None:
        return self._specs.get(str(name).strip().lower())

    def execute(self, request: AgentRequest) -> AgentResponse:
        name = request.agent.strip().lower()
        spec = self.get(name)
        if spec is None or not spec.enabled:
            return self._response(
                AgentStatus.UNAVAILABLE,
                name,
                "The requested agent is unavailable.",
                request,
            )
        text = str(request.text or "").strip()
        if not text or len(text) > spec.max_input_chars:
            return self._response(
                AgentStatus.REJECTED,
                name,
                "Agent input is empty or exceeds its configured bound.",
                request,
            )
        if not request.required_capabilities.issubset(spec.capabilities):
            return self._response(
                AgentStatus.REJECTED,
                name,
                "Agent does not provide all required capabilities.",
                request,
            )
        if (
            spec.isolation == AgentIsolation.ISOLATED_PROCESS
            and self._isolated_runner is None
        ):
            return self._response(
                AgentStatus.UNAVAILABLE,
                name,
                "Agent requires an isolated runner that is not configured.",
                request,
            )

        audit_event(
            "agent",
            name,
            "STARTED",
            {
                "input_characters": len(text),
                "capabilities": sorted(request.required_capabilities),
            },
            request.correlation_id,
        )
        try:
            if spec.isolation == AgentIsolation.ISOLATED_PROCESS:
                result = self._isolated_runner(spec, text)
            else:
                module = importlib.import_module(spec.module)
                function = getattr(module, spec.entrypoint)
                result = function(text)
            if isinstance(result, dict):
                message = str(
                    result.get("message") or result.get("response") or result
                )
            else:
                message = str(result)
            if len(message) > spec.max_output_chars:
                message = message[: spec.max_output_chars]
            response = AgentResponse(
                AgentStatus.SUCCEEDED,
                name,
                message,
                request.correlation_id,
                data=result,
            )
            audit_event(
                "agent",
                name,
                "SUCCEEDED",
                {"output_characters": len(message)},
                request.correlation_id,
            )
            return response
        except Exception as error:
            audit_event(
                "agent",
                name,
                "FAILED",
                {"error_type": type(error).__name__},
                request.correlation_id,
            )
            return AgentResponse(
                AgentStatus.FAILED,
                name,
                f"The {name} agent failed safely. Check diagnostics for details.",
                request.correlation_id,
                error_type=type(error).__name__,
            )

    @staticmethod
    def _response(
        status: AgentStatus,
        name: str,
        message: str,
        request: AgentRequest,
    ) -> AgentResponse:
        audit_event(
            "agent", name or "unknown", status.value, {}, request.correlation_id
        )
        return AgentResponse(status, name, message, request.correlation_id)


def default_agent_specs() -> tuple[AgentSpec, ...]:
    return (
        AgentSpec(
            "operator",
            "agents.universal_operator_agent",
            "operator",
            "JARVIS UNIVERSAL OPERATOR",
            frozenset({"goal.plan", "agent.coordinate", "tool.delegate"}),
        ),
        AgentSpec(
            "health",
            "agents.health_agent",
            "health",
            "JARVIS HEALTH AGENT",
            frozenset({"system.health"}),
        ),
        AgentSpec(
            "research",
            "agents.research_agent",
            "research",
            "JARVIS RESEARCH AGENT",
            frozenset({"research.read", "network.read"}),
        ),
        AgentSpec(
            "web_intelligence",
            "agents.web_intelligence_agent",
            "web_intelligence",
            "JARVIS WEB INTELLIGENCE AGENT",
            frozenset({"web.search", "web.read", "research.cite", "network.read"}),
        ),
        AgentSpec(
            "coding",
            "agents.coding_agent",
            "coding",
            "JARVIS CODING AGENT",
            frozenset({"code.analyze", "code.generate"}),
        ),
        AgentSpec(
            "office",
            "agents.office_agent",
            "office",
            "JARVIS OFFICE AGENT",
            frozenset({"document.analyze", "document.generate"}),
        ),
        AgentSpec(
            "chat",
            "agents.chat_agent",
            "chat",
            "JARVIS CHAT AGENT",
            frozenset({"conversation"}),
        ),
        AgentSpec(
            "trading",
            "agents.trading_agent",
            "trading",
            "JARVIS TRADING AGENT",
            frozenset({"trading.research", "market.read", "paper.simulate"}),
        ),
        AgentSpec(
            "strategy", "agents.company_department_agent", "strategy",
            "JARVIS EXECUTIVE STRATEGY AGENT",
            frozenset({"company.plan", "strategy.analyze"}),
        ),
        AgentSpec(
            "product", "agents.company_department_agent", "product",
            "JARVIS PRODUCT AGENT",
            frozenset({"product.plan", "requirements.generate"}),
        ),
        AgentSpec(
            "engineering", "agents.company_department_agent", "engineering",
            "JARVIS ENGINEERING AGENT",
            frozenset({"architecture.analyze", "delivery.plan"}),
        ),
        AgentSpec(
            "data_ai", "agents.company_department_agent", "data_ai",
            "JARVIS DATA AND AI AGENT",
            frozenset({"data.plan", "ai.evaluate"}),
        ),
        AgentSpec(
            "design", "agents.company_department_agent", "design",
            "JARVIS EXPERIENCE DESIGN AGENT",
            frozenset({"experience.plan", "accessibility.analyze"}),
        ),
        AgentSpec(
            "security", "agents.company_department_agent", "security",
            "JARVIS SECURITY AGENT",
            frozenset({"security.analyze", "threat_model.generate"}),
        ),
        AgentSpec(
            "legal", "agents.company_department_agent", "legal",
            "JARVIS LEGAL AND COMPLIANCE RESEARCH AGENT",
            frozenset({"legal.research", "compliance.plan"}),
        ),
        AgentSpec(
            "finance", "agents.company_department_agent", "finance",
            "JARVIS FINANCE AGENT",
            frozenset({"finance.model", "budget.plan"}),
        ),
        AgentSpec(
            "operations", "agents.company_department_agent", "operations",
            "JARVIS OPERATIONS AGENT",
            frozenset({"operations.plan", "process.generate"}),
        ),
        AgentSpec(
            "marketing", "agents.company_department_agent", "marketing",
            "JARVIS MARKETING AGENT",
            frozenset({"marketing.plan", "content.draft"}),
        ),
        AgentSpec(
            "sales", "agents.company_department_agent", "sales",
            "JARVIS SALES AGENT",
            frozenset({"sales.plan", "proposal.draft"}),
        ),
        AgentSpec(
            "customer_success", "agents.company_department_agent", "customer_success",
            "JARVIS CUSTOMER SUCCESS AGENT",
            frozenset({"customer_success.plan", "support.plan"}),
        ),
        AgentSpec(
            "people", "agents.company_department_agent", "people",
            "JARVIS PEOPLE OPERATIONS AGENT",
            frozenset({"people.plan", "role.design"}),
        ),
        AgentSpec(
            "quality", "agents.company_department_agent", "quality",
            "JARVIS QUALITY AND RISK AGENT",
            frozenset({"quality.analyze", "risk.plan"}),
        ),
    )



# JARVIS META AGENT REGISTRY EXTENSION V3

_JARVIS_ORIGINAL_DEFAULT_AGENT_SPECS = default_agent_specs


def default_agent_specs():

    original = tuple(
        _JARVIS_ORIGINAL_DEFAULT_AGENT_SPECS()
    )

    from omni.meta_agent_specs import (
        meta_agent_specs,
    )

    existing = {
        spec.name
        for spec in original
    }

    extras = tuple(
        spec
        for spec in meta_agent_specs()
        if spec.name not in existing
    )

    return (
        *original,
        *extras,
    )
