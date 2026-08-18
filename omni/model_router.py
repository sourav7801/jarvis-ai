"""Provider-neutral model profiles and deterministic routing policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .runtime import audit_event


class PrivacyLevel(str, Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    CLOUD_ALLOWED = "CLOUD_ALLOWED"


class ModelTier(int, Enum):
    REFLEX = 1
    REASONING = 2
    FRONTIER = 3


@dataclass(frozen=True)
class ModelProfile:
    id: str
    provider: str
    model: str
    tier: ModelTier
    context_tokens: int
    expected_latency_ms: int
    local: bool
    capabilities: frozenset[str] = field(default_factory=frozenset)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.provider.strip() or not self.model.strip():
            raise ValueError("Model identity fields cannot be empty.")
        if self.context_tokens < 1 or self.expected_latency_ms < 0:
            raise ValueError("Model capacity and latency must be non-negative.")


@dataclass(frozen=True)
class ModelRequest:
    task_type: str
    minimum_tier: ModelTier = ModelTier.REFLEX
    required_context_tokens: int = 1
    maximum_latency_ms: int | None = None
    privacy: PrivacyLevel = PrivacyLevel.LOCAL_ONLY
    required_capabilities: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.task_type.strip():
            raise ValueError("task_type cannot be empty.")
        if self.required_context_tokens < 1:
            raise ValueError("required_context_tokens must be positive.")
        if self.maximum_latency_ms is not None and self.maximum_latency_ms < 0:
            raise ValueError("maximum_latency_ms cannot be negative.")


@dataclass(frozen=True)
class RoutingDecision:
    profile: ModelProfile | None
    reason: str
    considered: int


class ModelRouter:
    def __init__(self, profiles: Iterable[ModelProfile]):
        self.profiles = tuple(profiles)
        if len({profile.id for profile in self.profiles}) != len(self.profiles):
            raise ValueError("Model profile IDs must be unique.")

    def route(self, request: ModelRequest) -> RoutingDecision:
        eligible = []
        for profile in self.profiles:
            if not profile.enabled:
                continue
            if request.privacy == PrivacyLevel.LOCAL_ONLY and not profile.local:
                continue
            if profile.tier < request.minimum_tier:
                continue
            if profile.context_tokens < request.required_context_tokens:
                continue
            if request.maximum_latency_ms is not None and (
                profile.expected_latency_ms > request.maximum_latency_ms
            ):
                continue
            if not request.required_capabilities.issubset(profile.capabilities):
                continue
            eligible.append(profile)

        if not eligible:
            decision = RoutingDecision(None, "NO_ELIGIBLE_MODEL", len(self.profiles))
        else:
            selected = min(
                eligible,
                key=lambda profile: (
                    int(profile.tier),
                    profile.expected_latency_ms,
                    profile.context_tokens,
                    profile.id,
                ),
            )
            decision = RoutingDecision(
                selected,
                "LOWEST_CAPABLE_TIER_AND_LATENCY",
                len(self.profiles),
            )

        audit_event(
            "model_router",
            request.task_type,
            "SELECTED" if decision.profile else "UNAVAILABLE",
            {
                "profile_id": decision.profile.id if decision.profile else None,
                "minimum_tier": int(request.minimum_tier),
                "required_context_tokens": request.required_context_tokens,
                "privacy": request.privacy.value,
                "required_capabilities": sorted(request.required_capabilities),
            },
        )
        return decision


def default_profiles(local_model: str) -> tuple[ModelProfile, ...]:
    return (
        ModelProfile(
            id="local-reflex",
            provider="ollama",
            model=local_model,
            tier=ModelTier.REFLEX,
            context_tokens=8_192,
            expected_latency_ms=1_500,
            local=True,
            capabilities=frozenset({"tool_routing", "chat"}),
        ),
        ModelProfile(
            id="local-reasoning",
            provider="ollama",
            model=local_model,
            tier=ModelTier.REASONING,
            context_tokens=32_768,
            expected_latency_ms=8_000,
            local=True,
            capabilities=frozenset({"tool_routing", "chat", "reasoning", "coding"}),
        ),
    )

