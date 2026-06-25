"""
KeyResolver — resolves AI provider API keys.

Purpose: Provide the correct API key for each provider call.
Strategy: Platform-key-first. Use platform's own key by default.
          Fall back to BYOK (user's key) only when platform key is unavailable.
          Raise GatewayAuthError if neither is available.

Responsibility: Key lookup only. No caching (keys change infrequently but must be fresh).
Dependencies: Supabase (for user BYOK keys), Settings (for platform keys).
Limitations:
  - Key validity is not verified here — provider call will fail if key is invalid.
  - BYOK keys are AES-256 encrypted at rest; this class handles decryption via KeyManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.gateway.exceptions import GatewayAuthError
from app.gateway.schemas import KeyResolution

if TYPE_CHECKING:
    from supabase import Client

    from app.core.config import Settings


class KeyResolver:
    """
    Resolves API keys for provider calls. Platform-key-first, BYOK fallback.

    Stateless apart from injected dependencies — safe to share across requests.
    """

    def __init__(self, supabase: "Client", settings: "Settings") -> None:
        self._supabase = supabase
        self._settings = settings

    async def resolve(self, provider: str, user_id: str) -> KeyResolution:
        """
        Resolve the API key for a provider.

        Priority order:
        1. Platform key (from settings) — used for all users by default.
        2. BYOK key (from user_api_keys table) — only if platform key is missing.
        3. GatewayAuthError — if neither is available.

        Ollama uses no key (api_base instead).
        """
        # Ollama: no API key needed, just api_base
        if provider == "ollama":
            return KeyResolution(
                api_key=None,
                api_base=getattr(self._settings, "ollama_base_url", None),
                used_platform_key=False,
            )

        # Step 1: Platform key
        platform_key = self._get_platform_key(provider)
        if platform_key:
            return KeyResolution(api_key=platform_key, api_base=None, used_platform_key=True)

        # Step 2: BYOK fallback
        byok_key = await self._get_byok_key(provider, user_id)
        if byok_key:
            return KeyResolution(api_key=byok_key, api_base=None, used_platform_key=False)

        raise GatewayAuthError(
            f"No API key available for provider {provider!r}. "
            "Configure a platform key or enable BYOK.",
            code="no_api_key",
        )

    def _get_platform_key(self, provider: str) -> str | None:
        """Get the platform's API key for a provider from settings."""
        key_map = {
            "anthropic": getattr(self._settings, "anthropic_api_key", None),
            "openai": getattr(self._settings, "openai_api_key", None),
            "gemini": getattr(self._settings, "gemini_api_key", None),
        }
        return key_map.get(provider)

    async def _get_byok_key(self, provider: str, user_id: str) -> str | None:
        """Retrieve and decrypt the user's BYOK key from user_api_keys table."""
        try:
            from app.providers.key_manager import KeyManager

            return await KeyManager.get_key(user_id, provider=provider)
        except Exception:
            return None
