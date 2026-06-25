"""
AI Gateway interface contracts.
These Protocols define what each component must implement.
Concrete implementations live in their respective modules.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from app.gateway.schemas import (
    GatewayResponse,
    KeyResolution,
    ModelPricing,
    ModelSelection,
    PIIScanResult,
    PolicyDecision,
    ProviderResponse,
)


@runtime_checkable
class PolicyServiceProtocol(Protocol):
    """Fast, cached policy evaluation. No AI I/O."""

    async def evaluate(
        self,
        user_id: str,
        task_capability: str,
    ) -> PolicyDecision:
        """Evaluate all policy checks for a given user and capability."""
        ...


@runtime_checkable
class ModelRouterProtocol(Protocol):
    """Pure function: agent + plan -> model selection. No I/O."""

    def route(
        self,
        agent_name: str,
        task_capability: str,
        user_plan: str,
        user_override: dict[str, Any] | None = None,
    ) -> ModelSelection:
        """Select the optimal model for a given context."""
        ...


@runtime_checkable
class KeyResolverProtocol(Protocol):
    """Resolve API keys. Platform-first, BYOK opt-in."""

    async def resolve(
        self,
        provider: str,
        user_id: str,
    ) -> KeyResolution:
        """Resolve the API key for a provider and user."""
        ...


@runtime_checkable
class ProviderAdapterProtocol(Protocol):
    """Adapter interface for a single AI provider."""

    name: str
    supported_models: frozenset[str]

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool,
        temperature: float,
        max_tokens: int,
        timeout: int,
        api_key: str | None,
        api_base: str | None,
        **kwargs: Any,
    ) -> ProviderResponse | AsyncGenerator[str, None]:
        """Execute a completion request."""
        ...

    async def embed(
        self,
        text: str,
        model: str,
        api_key: str | None,
    ) -> list[float]:
        """Generate an embedding vector."""
        ...

    async def count_tokens(
        self,
        messages: list[dict[str, str]],
        model: str,
    ) -> int:
        """Count tokens for a message list (pre-call estimation)."""
        ...

    def normalize_error(self, raw_exception: Exception) -> Exception:
        """Normalize a provider-specific exception to a GatewayError."""
        ...


@runtime_checkable
class CostEngineProtocol(Protocol):
    """Calculate AI costs. DB-backed pricing, cached."""

    async def calculate(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
    ) -> Decimal:
        """Calculate exact cost for a completed call."""
        ...

    async def get_pricing(self, model: str) -> ModelPricing:
        """Get current pricing for a model."""
        ...


@runtime_checkable
class UsageTrackerProtocol(Protocol):
    """Record AI usage. Async, not on critical path."""

    async def record(
        self,
        request_id: str,
        response: GatewayResponse,
        agent_id: str | None,
    ) -> None:
        """Record usage to ai_usage table and update budget."""
        ...


@runtime_checkable
class AuditWriterProtocol(Protocol):
    """Write audit events. Async, not on critical path."""

    async def write(
        self,
        request_id: str,
        outcome: str,
        metadata: dict[str, Any],
    ) -> None:
        """Write an audit event."""
        ...


@runtime_checkable
class PIIScannerProtocol(Protocol):
    """Scan and redact PII from text. No I/O."""

    def scan(self, text: str, agent_name: str) -> PIIScanResult:
        """Scan text for PII and return sanitized version."""
        ...


@runtime_checkable
class PromptTemplateRegistryProtocol(Protocol):
    """Resolve system prompts from templates. DB-backed, cached."""

    async def get_system_prompt(
        self,
        agent_name: str,
        variables: dict[str, str] | None = None,
    ) -> str | None:
        """Get the active system prompt for an agent. Returns None if not found."""
        ...
