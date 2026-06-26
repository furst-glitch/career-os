from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider


class EmploymentChatAgent(BaseAgent):
    name = "employment_chat_agent"

    async def run(self, input_data: dict) -> AgentResult:
        system = input_data.get("system_prompt", "")
        messages = input_data.get("messages", [])

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": system}] + [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m.get("role") in ("user", "assistant") and m.get("content")
            ],
            stream=True,
            temperature=0.4,
            max_tokens=1500,
        )
        # TODO: log_usage — streaming response; token counts unavailable until stream is consumed.
        return AgentResult(content="", usage=AgentUsage(), metadata={"stream": resp})
