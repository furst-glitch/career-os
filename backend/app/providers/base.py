"""
Provider base class.
Will be extended/replaced by AbstractProviderAdapter in backend/app/gateway/providers/base.py
during AI Gateway implementation (Sprint 2-3).
See: docs/ai-gateway-spec-v1.md, Section 7.
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    @abstractmethod
    async def complete(self, agent_name: str, messages: list[dict], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError
