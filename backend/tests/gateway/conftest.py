"""
Pre-stubs that prevent import-chain failures in gateway unit tests.

Gateway unit tests run without environment variables. Any module that imports
app.core.config at module level (or transitively via key_manager → deps → config)
would raise a Settings ValidationError. We register lightweight stubs in
sys.modules at conftest load time — before any test module is imported.

The check `if mod not in sys.modules` ensures real modules (already loaded in a
full-env CI run) are never overwritten.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def _make_key_manager_stub() -> MagicMock:
    """Stub for app.providers.key_manager — avoids deps → config import chain."""
    stub = MagicMock()
    stub.KeyManager = MagicMock()
    stub.KeyManager.get_key = AsyncMock(return_value=None)
    return stub


def _make_config_stub() -> MagicMock:
    """Stub for app.core.config — returns safe test defaults for all key attrs."""
    stub = MagicMock()
    stub.settings = SimpleNamespace(
        anthropic_api_key="sk-ant-test",
        openai_api_key=None,
        gemini_api_key=None,
        ollama_base_url=None,
    )
    return stub


# Only stub key_manager to break the key_manager → deps → config → Settings()
# import chain. We do NOT stub app.core.config here — that would pollute the
# test session and break smoke tests that verify real settings attributes.
if "app.providers.key_manager" not in sys.modules:
    sys.modules["app.providers.key_manager"] = _make_key_manager_stub()  # type: ignore[assignment]
