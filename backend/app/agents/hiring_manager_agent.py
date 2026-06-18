from app.agents.base import BaseAgent, AgentResult


class HiringManagerAgent(BaseAgent):
    name = "hiring_manager_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("hiring_manager_agent er ikke implementeret endnu")
