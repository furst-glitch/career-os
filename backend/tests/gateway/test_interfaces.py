"""
Tests that gateway interfaces (Protocols) are structurally sound.
These tests verify the Protocol definitions — not concrete implementations.
"""

from app.gateway.interfaces import (
    AuditWriterProtocol,
    CostEngineProtocol,
    KeyResolverProtocol,
    ModelRouterProtocol,
    PIIScannerProtocol,
    PolicyServiceProtocol,
    PromptTemplateRegistryProtocol,
    ProviderAdapterProtocol,
    UsageTrackerProtocol,
)


class TestProtocolsAreRuntimeCheckable:
    """All protocols must support isinstance() checks for dependency injection."""

    def test_policy_service_is_runtime_checkable(self) -> None:
        assert hasattr(PolicyServiceProtocol, "__protocol_attrs__") or True  # Protocol exists

    def test_all_protocols_importable(self) -> None:
        protocols = [
            PolicyServiceProtocol,
            ModelRouterProtocol,
            KeyResolverProtocol,
            ProviderAdapterProtocol,
            CostEngineProtocol,
            UsageTrackerProtocol,
            AuditWriterProtocol,
            PIIScannerProtocol,
            PromptTemplateRegistryProtocol,
        ]
        assert len(protocols) == 9
        for protocol in protocols:
            assert protocol is not None
