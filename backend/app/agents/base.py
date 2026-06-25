import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.gateway.gateway import AIGateway
    from app.gateway.schemas import GatewayResponse

logger = logging.getLogger("app.agents")


@dataclass
class AgentUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    model: str = ""
    provider: str = ""


@dataclass
class AgentResult:
    content: str
    usage: AgentUsage = field(default_factory=AgentUsage)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    name: str = ""

    # ── Gateway capability declaration (Sprint 5) ──────────────────────────
    # Each agent declares which plan_capability it uses. Agents with multiple
    # LLM-calling methods and different capabilities override `capabilities`
    # to provide a per-method mapping (method_name → capability string).
    #
    # Valid strings must exist in the plan_capabilities table. AIPolicyService
    # enforces this at request time (fail-closed since Sprint 5).
    capability: str = "chat"
    capabilities: dict[str, str] = {}  # method_name → capability override

    def __init__(self, user_id: str, supabase: Any) -> None:
        self.user_id = user_id
        self.supabase = supabase
        self._config: dict | None = None

    @property
    def config(self) -> dict:
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> dict:
        result = (
            self.supabase.table("agent_registry")
            .select("*, agent_configurations(*)")
            .eq("name", self.name)
            .limit(1)
            .execute()
        )
        rows = result.data if result and result.data else []
        return rows[0] if rows else {}

    async def get_memory_context(self) -> str:
        result = self.supabase.rpc(
            "get_memory_snapshot",
            {"p_user_id": self.user_id},
        ).execute()
        return (result.data if result else None) or ""

    async def log_usage(self, usage: AgentUsage, operation: str = "", used_user_key: bool = False) -> None:
        agent_id = self.config.get("id")
        self.supabase.table("ai_usage").insert({
            "user_id": self.user_id,
            "agent_id": agent_id,
            "provider": usage.provider,
            "model": usage.model,
            "operation": operation or self.name,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": usage.cost_usd,
            "latency_ms": usage.latency_ms,
            "used_user_key": used_user_key,
        }).execute()

    # ── AI Gateway integration (Sprint 5) ─────────────────────────────────

    def _get_gateway(self) -> "AIGateway":
        """Lazily build and cache the AIGateway for this agent instance."""
        if not hasattr(self, "_gateway_instance"):
            from app.gateway.factory import build_gateway
            from app.services.cache_service import get_cache

            self._gateway_instance = build_gateway(self.supabase, get_cache())
        return self._gateway_instance

    @staticmethod
    def _usage_from_response(response: "GatewayResponse") -> AgentUsage:
        """Convert a GatewayResponse's usage into the AgentUsage shape."""
        return AgentUsage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            cost_usd=float(response.usage.cost_usd),
            latency_ms=response.latency_ms,
            model=response.model_used,
            provider=response.provider_used,
        )

    async def _call_gateway(
        self,
        task_capability: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.5,
        max_tokens: int = 2048,
        response_format: dict | None = None,
        stream: bool = False,
    ) -> "GatewayResponse":
        """
        One-liner entry point for Gateway-based agents.

        Builds a GatewayRequest from the provided arguments and dispatches it
        through the full Gateway pipeline (policy → key → PII → route →
        provider → usage → audit → response).

        Callers receive a GatewayResponse; convert to AgentUsage via
        _usage_from_response() and to AgentResult manually.
        """
        from app.gateway.schemas import GatewayRequest

        return await self._get_gateway().complete(
            GatewayRequest(
                user_id=self.user_id,
                agent_name=self.name,
                task_capability=task_capability,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                stream=stream,
            )
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def run_tracked(self, input_data: dict) -> AgentResult:
        """Wraps run() with timing + Sentry error tracking."""
        start = time.monotonic()
        try:
            result = await self.run(input_data)
            ms = round((time.monotonic() - start) * 1000)
            logger.info(
                "Agent %s completed in %dms (tokens=%d)",
                self.name, ms, result.usage.total_tokens,
            )
            return result
        except Exception as exc:
            ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "Agent %s FAILED after %dms: %s",
                self.name, ms, exc,
            )
            try:
                import sentry_sdk
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("agent", self.name)
                    scope.set_user({"id": self.user_id})
                    sentry_sdk.capture_exception(exc)
            except ImportError:
                pass
            raise

    @abstractmethod
    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError
