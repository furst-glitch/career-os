"""
LiteLLM provider med BYOK-first key resolution, budget-check og usage-logging.
Alle AI-kald i CareerOS skal gå igennem denne klasse.

Key resolution order:
  1. Brugerens egen nøgle (BYOK) — bruges hvis tilgængelig
  2. System-nøgle fra .env — fallback til SaaS-mode
  3. Ingen nøgle → NoProviderKeyError
"""
import time
from typing import Any

from app.core.config import settings
from app.core.deps import get_supabase_admin
from app.providers.key_manager import KeyManager


class BudgetExceededError(Exception):
    pass


class NoProviderKeyError(Exception):
    pass


class LiteLLMProvider:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self._used_user_key = False
        self.supabase = get_supabase_admin()

    async def _get_agent_config(self, agent_name: str) -> dict:
        result = (
            self.supabase.table("agent_registry")
            .select("*")
            .eq("name", agent_name)
            .limit(1)
            .execute()
        )
        config = (result.data[0] if result and result.data else None) or {}
        if config:
            override_result = (
                self.supabase.table("agent_configurations")
                .select("model_override, provider_override, temperature_override")
                .eq("agent_id", config["id"])
                .eq("user_id", self.user_id)
                .limit(1)
                .execute()
            )
            config["agent_configurations"] = (override_result.data if override_result else None) or []
        return config

    def _check_budget(self) -> None:
        if self._used_user_key:
            return

        result = (
            self.supabase.table("ai_budgets")
            .select("monthly_limit_usd, warning_threshold, hard_limit, current_spend_usd")
            .eq("user_id", self.user_id)
            .limit(1)
            .execute()
        )

        budget_data = (result.data[0] if result and result.data else None)
        if not budget_data:
            return

        budget = budget_data
        limit = budget.get("monthly_limit_usd", 0)
        spend = budget.get("current_spend_usd", 0)

        if limit > 0 and spend >= limit and budget.get("hard_limit"):
            raise BudgetExceededError(
                f"Månedligt AI-budget overskredet ({spend:.2f} / {limit:.2f} USD)"
            )

    async def _get_user_default_provider(self) -> str | None:
        result = (
            self.supabase.table("user_profiles")
            .select("default_ai_provider")
            .eq("user_id", self.user_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("default_ai_provider")
        return None

    def _default_model_for_provider(self, provider: str) -> str:
        """Returnerer standardmodel for en given provider fra settings (ingen hardcodes)."""
        if provider == "anthropic":
            return settings.anthropic_default_model
        return settings.openai_default_model

    def _system_key_for(self, provider: str) -> str | None:
        return {"openai": settings.openai_api_key, "anthropic": settings.anthropic_api_key}.get(provider)

    async def _has_key(self, provider: str) -> bool:
        """Returnerer True hvis der er en brugernøgle ELLER systemets nøgle til denne provider."""
        if provider == "ollama":
            return bool(await KeyManager.get_key(self.user_id, "ollama") or settings.ollama_base_url)
        return bool(await KeyManager.get_key(self.user_id, provider) or self._system_key_for(provider))

    async def _find_available_provider(self, preferred: str) -> str:
        """
        Returnerer preferred hvis den har en nøgle.
        Ellers prøves openai → anthropic i den rækkefølge.
        Sikrer at systemet altid bruger den udbyder brugeren faktisk har en nøgle til.
        """
        if await self._has_key(preferred):
            return preferred
        for fallback in ["openai", "anthropic"]:
            if fallback != preferred and await self._has_key(fallback):
                import logging
                logging.getLogger("app.providers").info(
                    "Ingen nøgle for '%s', falder tilbage til '%s'.", preferred, fallback
                )
                return fallback
        return preferred  # ingen nøgler — _resolve_api_key vil give NoProviderKeyError

    async def _resolve_model(self, agent_name: str, provider: str | None = None) -> tuple[str, str]:
        config = await self._get_agent_config(agent_name)
        overrides = config.get("agent_configurations") or [{}]
        override = overrides[0] if overrides else {}

        preferred_provider = (
            provider
            or override.get("provider_override")
            or await self._get_user_default_provider()
            or config.get("default_provider", "openai")
        )

        # Brug den foretrukne udbyder KUN hvis der er en nøgle til den.
        # Ellers skift automatisk til en udbyder brugeren faktisk har konfigureret.
        resolved_provider = await self._find_available_provider(preferred_provider)

        # Model: bruger-override → agent_registry (kun hvis vi blev ved den foretrukne provider) → settings-default
        resolved_model = (
            override.get("model_override")
            or (config.get("default_model") if resolved_provider == preferred_provider else None)
            or self._default_model_for_provider(resolved_provider)
        )

        return resolved_provider, resolved_model

    async def _resolve_api_key(self, provider: str) -> tuple[str | None, str | None]:
        """
        Returnerer (api_key, api_base).
        BYOK-first: brugerens nøgle har altid forrang over system-nøgler.
        Ollama bruger api_base i stedet for api_key.
        """
        if provider == "ollama":
            user_url = await KeyManager.get_key(self.user_id, "ollama")
            base_url = user_url or settings.ollama_base_url
            if not base_url:
                raise NoProviderKeyError(
                    "Ingen Ollama endpoint konfigureret. Tilføj din Ollama URL under AI-udbydere."
                )
            self._used_user_key = bool(user_url)
            return None, base_url

        user_key = await KeyManager.get_key(self.user_id, provider)
        if user_key:
            self._used_user_key = True
            return user_key, None

        system_key = self._system_key_for(provider)
        if system_key:
            self._used_user_key = False
            return system_key, None

        raise NoProviderKeyError(
            f"Ingen API-nøgle fundet for '{provider}'. "
            "Tilføj din nøgle under Indstillinger → AI-udbydere."
        )

    async def complete(
        self,
        agent_name: str,
        messages: list[dict],
        stream: bool = False,
        provider: str | None = None,
        **kwargs: Any,
    ) -> Any:
        import litellm

        resolved_provider, model = await self._resolve_model(agent_name, provider)
        api_key, api_base = await self._resolve_api_key(resolved_provider)

        self._check_budget()

        if resolved_provider == "ollama":
            litellm_model = f"ollama/{model}"
        elif resolved_provider == "openai":
            litellm_model = model
        else:
            litellm_model = f"{resolved_provider}/{model}"

        call_kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }
        if api_key:
            call_kwargs["api_key"] = api_key
        if api_base:
            call_kwargs["api_base"] = api_base

        # Use agent's configured timeout_seconds from agent_registry.
        # Caller can override by passing timeout= in kwargs (already in call_kwargs via **kwargs).
        if "timeout" not in call_kwargs:
            agent_cfg = await self._get_agent_config(agent_name)
            call_kwargs["timeout"] = agent_cfg.get("timeout_seconds", 60)

        start = time.time()
        try:
            response = await litellm.acompletion(**call_kwargs)
        except Exception as exc:
            exc_name = type(exc).__name__
            exc_str = str(exc)

            # AuthenticationError → bad/missing key
            if "AuthenticationError" in exc_name or "401" in exc_str:
                raise NoProviderKeyError(
                    f"API-nøglen for '{resolved_provider}' er ugyldig eller udløbet."
                )
            # Timeout / ReadTimeout
            if "Timeout" in exc_name or "timeout" in exc_str.lower():
                raise TimeoutError(
                    "AI-svaret tog for lang tid (>30 sek). Prøv igen — udbyderen er langsom lige nu."
                )
            # NotFoundError / model not found → try settings default model as fallback
            if "NotFoundError" in exc_name or "not_found" in exc_str.lower() or "model_not_found" in exc_str.lower():
                fallback_model = self._default_model_for_provider(resolved_provider)
                if fallback_model != model:
                    import logging
                    logging.getLogger("app.providers").warning(
                        "Model '%s' ikke fundet for provider '%s'. Prøver fallback '%s'.",
                        model, resolved_provider, fallback_model,
                    )
                    if resolved_provider == "openai":
                        fallback_litellm = fallback_model
                    else:
                        fallback_litellm = f"{resolved_provider}/{fallback_model}"
                    fallback_kwargs = {**call_kwargs, "model": fallback_litellm}
                    try:
                        response = await litellm.acompletion(**fallback_kwargs)
                    except Exception as fallback_exc:
                        raise NoProviderKeyError(
                            f"Model '{model}' og fallback '{fallback_model}' fejlede for '{resolved_provider}'. "
                            f"Tjek din API-nøgle og prøv igen."
                        ) from fallback_exc
                    self._latency_ms = int((time.time() - start) * 1000)
                    return response
            # Re-raise everything else (NoProviderKeyError, BudgetExceeded, etc.)
            raise
        self._latency_ms = int((time.time() - start) * 1000)

        return response

    async def embed(self, text: str) -> list[float]:
        import litellm

        # Embeddings kræver OpenAI — brug brugerens nøgle eller systemnøgle
        provider = await self._find_available_provider("openai")
        if provider != "openai":
            raise NoProviderKeyError(
                "Embeddings kræver en OpenAI API-nøgle. "
                "Tilføj din nøgle under Indstillinger → AI-udbydere."
            )
        api_key, _ = await self._resolve_api_key("openai")

        response = await litellm.aembedding(
            model="text-embedding-3-small",
            input=text,
            api_key=api_key,
        )
        return response.data[0]["embedding"]

    @property
    def used_user_key(self) -> bool:
        return self._used_user_key
