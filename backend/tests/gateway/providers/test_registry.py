"""Tests for ProviderRegistry."""

from __future__ import annotations

import pytest

from app.gateway.exceptions import GatewayConfigError
from app.gateway.providers.anthropic import AnthropicAdapter
from app.gateway.providers.factory import build_default_provider_registry
from app.gateway.providers.openai import OpenAIAdapter
from app.gateway.providers.registry import ProviderRegistry


def test_register_and_get_returns_correct_adapter() -> None:
    adapter = AnthropicAdapter()
    registry = ProviderRegistry().register(adapter)
    assert registry.get("anthropic") is adapter


def test_get_unknown_provider_raises() -> None:
    registry = ProviderRegistry().register(AnthropicAdapter())
    with pytest.raises(GatewayConfigError) as exc_info:
        registry.get("does_not_exist")
    assert exc_info.value.code == "provider_not_registered"


def test_error_message_lists_available_providers() -> None:
    registry = ProviderRegistry().register(AnthropicAdapter()).register(OpenAIAdapter())
    with pytest.raises(GatewayConfigError) as exc_info:
        registry.get("missing")
    assert "anthropic" in str(exc_info.value)
    assert "openai" in str(exc_info.value)


def test_list_providers_sorted() -> None:
    registry = (
        ProviderRegistry()
        .register(OpenAIAdapter())
        .register(AnthropicAdapter())
    )
    assert registry.list_providers() == ["anthropic", "openai"]


def test_is_registered() -> None:
    registry = ProviderRegistry().register(AnthropicAdapter())
    assert registry.is_registered("anthropic") is True
    assert registry.is_registered("openai") is False


def test_register_returns_self_for_chaining() -> None:
    registry = ProviderRegistry()
    result = registry.register(AnthropicAdapter())
    assert result is registry


def test_register_overwrites_previous() -> None:
    first = AnthropicAdapter()
    second = AnthropicAdapter()
    registry = ProviderRegistry().register(first).register(second)
    assert registry.get("anthropic") is second
    assert len(registry) == 1


def test_len_returns_count() -> None:
    registry = ProviderRegistry()
    assert len(registry) == 0
    registry.register(AnthropicAdapter())
    assert len(registry) == 1
    registry.register(OpenAIAdapter())
    assert len(registry) == 2


def test_empty_registry_raises_on_get() -> None:
    registry = ProviderRegistry()
    with pytest.raises(GatewayConfigError):
        registry.get("anthropic")


def test_factory_registers_all_four_providers() -> None:
    registry = build_default_provider_registry()
    assert registry.list_providers() == ["anthropic", "gemini", "ollama", "openai"]
    assert len(registry) == 4
