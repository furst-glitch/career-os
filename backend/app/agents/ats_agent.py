from app.agents.base import BaseAgent, AgentResult


class AtsAgent(BaseAgent):
    name = "ats_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("ats_agent er ikke implementeret endnu")
