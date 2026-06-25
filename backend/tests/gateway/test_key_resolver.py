"""
Unit tests for KeyResolver (app.gateway.key_resolver).

No network — Settings and KeyManager are stubbed. Covers platform-first
resolution, BYOK fallback, Ollama, and the no-key error path.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateway.exceptions import GatewayAuthError
from app.gateway.key_resolver import KeyResolver


def _settings(**kwargs):
    """Build a stand-in Settings object with only the attrs we care about."""
    defaults = {
        "anthropic_api_key": None,
        "openai_api_key": None,
        "gemini_api_key": None,
        "ollama_base_url": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _resolver(settings):
    return KeyResolver(supabase=MagicMock(), settings=settings)


@pytest.mark.asyncio
async def test_platform_key_returned_for_anthropic():
    resolver = _resolver(_settings(anthropic_api_key="sk-ant-platform"))
    res = await resolver.resolve("anthropic", "user-1")
    assert res.api_key == "sk-ant-platform"
    assert res.used_platform_key is True
    assert res.api_base is None


@pytest.mark.asyncio
async def test_openai_platform_key_from_settings():
    resolver = _resolver(_settings(openai_api_key="sk-openai"))
    res = await resolver.resolve("openai", "user-1")
    assert res.api_key == "sk-openai"
    assert res.used_platform_key is True


@pytest.mark.asyncio
async def test_gemini_platform_key_from_settings():
    resolver = _resolver(_settings(gemini_api_key="g-key"))
    res = await resolver.resolve("gemini", "user-1")
    assert res.api_key == "g-key"
    assert res.used_platform_key is True


@pytest.mark.asyncio
async def test_byok_fallback_when_no_platform_key():
    resolver = _resolver(_settings())  # no platform keys
    with patch(
        "app.providers.key_manager.KeyManager.get_key",
        new=AsyncMock(return_value="user-byok-key"),
    ):
        res = await resolver.resolve("anthropic", "user-1")
    assert res.api_key == "user-byok-key"
    assert res.used_platform_key is False


@pytest.mark.asyncio
async def test_auth_error_when_no_key_available():
    resolver = _resolver(_settings())
    with patch(
        "app.providers.key_manager.KeyManager.get_key",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(GatewayAuthError) as exc:
            await resolver.resolve("anthropic", "user-1")
    assert exc.value.code == "no_api_key"


@pytest.mark.asyncio
async def test_byok_failure_does_not_raise_then_falls_to_auth_error():
    resolver = _resolver(_settings())
    with patch(
        "app.providers.key_manager.KeyManager.get_key",
        new=AsyncMock(side_effect=RuntimeError("db down")),
    ):
        with pytest.raises(GatewayAuthError):
            await resolver.resolve("openai", "user-1")


@pytest.mark.asyncio
async def test_ollama_returns_no_key_resolution():
    resolver = _resolver(_settings(ollama_base_url="http://localhost:11434"))
    res = await resolver.resolve("ollama", "user-1")
    assert res.api_key is None
    assert res.api_base == "http://localhost:11434"
    assert res.used_platform_key is False


@pytest.mark.asyncio
async def test_platform_key_preferred_over_byok():
    """If a platform key exists, BYOK must NOT be consulted."""
    resolver = _resolver(_settings(anthropic_api_key="platform"))
    get_key = AsyncMock(return_value="byok")
    with patch("app.providers.key_manager.KeyManager.get_key", new=get_key):
        res = await resolver.resolve("anthropic", "user-1")
    assert res.api_key == "platform"
    assert res.used_platform_key is True
    get_key.assert_not_called()
