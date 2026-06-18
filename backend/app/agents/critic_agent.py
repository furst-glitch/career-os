from app.agents.base import BaseAgent, AgentResult


class CriticAgent(BaseAgent):
    name = "critic_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("critic_agent er ikke implementeret endnu")
