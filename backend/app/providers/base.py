from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    @abstractmethod
    async def complete(self, agent_name: str, messages: list[dict], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError
