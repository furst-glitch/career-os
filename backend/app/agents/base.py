from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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
            .single()
            .execute()
        )
        return result.data or {}

    async def get_memory_context(self) -> str:
        result = self.supabase.rpc(
            "get_memory_snapshot",
            {"p_user_id": self.user_id},
        ).execute()
        return result.data or ""

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

    @abstractmethod
    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError
