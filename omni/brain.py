from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from omni.agent_registry import AgentSpec, default_agent_specs


@dataclass(frozen=True)
class BrainDecision:
    intent: str
    primary_agent: str
    supporting_agents: tuple[str, ...] = ()
    confidence: float = 1.0
    reason: str = ""
    requires_approval: bool = False
    capabilities: tuple[str, ...] = ()




@dataclass(frozen=True)
class DelegationStep:
    order: int
    agent: str
    role: str
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class DelegationPlan:
    request: str
    intent: str
    lead_agent: str
    steps: tuple[DelegationStep, ...]
    confidence: float
    requires_approval: bool = False

    @property
    def agent_count(self) -> int:
        return len(self.steps)

    @property
    def agents(self) -> tuple[str, ...]:
        return tuple(step.agent for step in self.steps)


class JarvisBrain:

    def __init__(self, specs: Iterable[AgentSpec] | None = None):
        self.specs = tuple(specs or default_agent_specs())
        self._agents = {spec.name: spec for spec in self.specs}

    @property
    def agent_count(self):
        return len(self._agents)

    def agent_names(self):
        return tuple(self._agents)

    def has_agent(self, name):
        return name in self._agents

    def capabilities_for(self, name):
        spec = self._agents.get(name)
        return tuple(spec.capabilities) if spec else ()

    def _decision(
        self,
        intent,
        agent,
        confidence,
        reason,
        supporting=(),
    ):
        if agent not in self._agents:
            agent = "chat"
            confidence = min(confidence, 0.40)
            reason += " Specialist unavailable."

        supporting = tuple(
            x for x in supporting
            if x in self._agents and x != agent
        )

        return BrainDecision(
            intent=intent,
            primary_agent=agent,
            supporting_agents=supporting,
            confidence=confidence,
            reason=reason,
            capabilities=self.capabilities_for(agent),
        )


    def plan(self, request: str) -> DelegationPlan:
        """
        Convert one user request into a bounded multi-agent plan.

        This plans delegation only. Execution remains governed by
        the existing orchestrator, capability checks and approvals.
        """
        decision = self.decide(request)

        ordered = []

        def add(agent: str, role: str):
            if not agent:
                return

            if agent not in self._agents:
                return

            if any(step.agent == agent for step in ordered):
                return

            ordered.append(
                DelegationStep(
                    order=len(ordered) + 1,
                    agent=agent,
                    role=role,
                    capabilities=self.capabilities_for(agent),
                )
            )

        add(
            decision.primary_agent,
            "lead",
        )

        for agent in decision.supporting_agents:
            add(
                agent,
                "support",
            )

        return DelegationPlan(
            request=str(request or ""),
            intent=decision.intent,
            lead_agent=decision.primary_agent,
            steps=tuple(ordered),
            confidence=decision.confidence,
            requires_approval=decision.requires_approval,
        )


    def decide(self, request: str):
        text = (request or "").strip().lower()

        if not text:
            return self._decision(
                "conversation", "chat", .5,
                "Empty/conversational request."
            )

        # WEB first when explicit web/search/news language exists.
        if any(x in text for x in (
            "search the web",
            "search web",
            "search the internet",
            "search internet",
            "google",
            "look up",
            "lookup",
            "find online",
            "research online",
            "latest news",
            "latest ai news",
            "current news",
            "news about",
            "website",
        )):
            return self._decision(
                "web_research",
                "web_intelligence",
                .98,
                "Explicit web intelligence request.",
                ("research",),
            )

        if any(x in text for x in (
            "trade", "trading", "nifty", "banknifty",
            "sensex", "fyers", "market", "stock",
            "option", "portfolio", "crude", "gold",
        )):
            return self._decision(
                "trading",
                "trading",
                .98,
                "Trading/market request.",
                ("research", "web_intelligence"),
            )

        if any(x in text for x in (
            "code", "python", "debug", "bug",
            "program", "script", "repository",
            "github", "software",
        )):
            return self._decision(
                "coding",
                "coding",
                .96,
                "Coding request.",
                ("engineering", "security"),
            )

        if any(x in text for x in (
            "document", "report", "presentation",
            "spreadsheet", "excel", "word",
            "powerpoint", "pdf",
        )):
            return self._decision(
                "office", "office", .95,
                "Office/document request."
            )

        if any(x in text for x in (
            "business", "company", "startup",
            "venture", "business plan",
        )):
            return self._decision(
                "company_strategy",
                "strategy",
                .94,
                "Company strategy request.",
                ("product", "finance", "marketing", "operations"),
            )

        if any(x in text for x in (
            "security", "threat", "vulnerability",
            "cyber", "attack surface",
        )):
            return self._decision(
                "security", "security", .97,
                "Security request."
            )

        if any(x in text for x in (
            "finance", "budget", "cash flow",
            "valuation", "financial model",
        )):
            return self._decision(
                "finance", "finance", .96,
                "Finance request."
            )

        if any(x in text for x in (
            "legal", "compliance", "contract",
            "regulation",
        )):
            return self._decision(
                "legal", "legal", .96,
                "Legal/compliance request."
            )

        if any(x in text for x in (
            "health check", "system health",
            "jarvis status", "diagnostic",
        )):
            return self._decision(
                "health", "health", .99,
                "System health request."
            )

        if any(x in text for x in (
            "do this for me",
            "handle this",
            "complete this task",
            "execute this task",
            "take care of this",
        )):
            return self._decision(
                "operator", "operator", .85,
                "General delegated task."
            )

        return self._decision(
            "conversation",
            "chat",
            .70,
            "No specialist domain detected."
        )


brain = JarvisBrain()
