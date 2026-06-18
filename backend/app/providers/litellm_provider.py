"""
LiteLLM provider med budget-check og automatisk usage-logging.
Alle AI-kald i CareerOS skal gå igennem denne klasse.
"""
import time
from typing import Any, AsyncIterator

from app.core.config import settings
from app.core.deps import get_supabase_admin
from app.providers.key_manager import KeyManager


class BudgetExceededError(Exception):
    pass


class LiteLLMProvider:
    def __init__(self, user_id: str, used_user_key: bool = False) -> None:
        self.user_id = user_id
        self.used_user_key = used_user_key
        self.supabase = get_supabase_admin()

    async def _get_agent_config(self, agent_name: str) -> dict:
        result = (
            self.supabase.table("agent_registry")
            .select("*, agent_configurations(model_override, provider_override, temperature_override)")
            .eq("name", agent_name)
            .single()
            .execute()
        )
        return result.data or {}

    def _check_budget(self) -> None:
        if self.used_user_key:
            return

        result = (
            self.supabase.table("ai_budgets")
            .select("monthly_limit_usd, warning_threshold, hard_limit, current_spend_usd")
            .eq("user_id", self.user_id)
            .single()
            .execute()
        )

        if not result.data:
            return

        budget = result.data
        limit = budget.get("monthly_limit_usd", 0)
        spend = budget.get("current_spend_usd", 0)

        if limit > 0 and spend >= limit and budget.get("hard_limit"):
            raise BudgetExceededError(
                f"Månedligt AI-budget overskredet ({spend:.2f} / {limit:.2f} USD)"
            )

    async def _resolve_model(self, agent_name: str, provider: str | None = None) -> tuple[str, str]:
        config = await self._get_agent_config(agent_name)
        overrides = config.get("agent_configurations") or [{}]
        override = overrides[0] if overrides else {}

        resolved_provider = override.get("provider_override") or config.get("default_provider", "openai")
        resolved_model = override.get("model_override") or config.get("default_model", "gpt-4o")

        if provider:
            resolved_provider = provider

        return resolved_provider, resolved_model

    async def _get_api_key(self, provider: str) -> str | None:
        if self.used_user_key:
            return await KeyManager.get_key(self.user_id, provider)

        key_map = {
            "openai": settings.openai_api_key,
            "anthropic": settings.anthropic_api_key,
        }
        return key_map.get(provider)

    async def complete(
        self,
        agent_name: str,
        messages: list[dict],
        stream: bool = False,
        provider: str | None = None,
        **kwargs: Any,
    ) -> Any:
        import litellm

        self._check_budget()

        resolved_provider, model = await self._resolve_model(agent_name, provider)
        api_key = await self._get_api_key(resolved_provider)

        litellm_model = f"{resolved_provider}/{model}" if resolved_provider != "openai" else model

        start = time.time()
        response = await litellm.acompletion(
            model=litellm_model,
            messages=messages,
            api_key=api_key,
            stream=stream,
            **kwargs,
        )
        latency_ms = int((time.time() - start) * 1000)

        return response

    async def embed(self, text: str) -> list[float]:
        import litellm

        api_key = await self._get_api_key("openai")
        response = await litellm.aembedding(
            model="text-embedding-3-small",
            input=text,
            api_key=api_key,
        )
        return response.data[0]["embedding"]
