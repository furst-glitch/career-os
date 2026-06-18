from app.agents.base import BaseAgent, AgentResult


class HrAgent(BaseAgent):
    name = "hr_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("hr_agent er ikke implementeret endnu")
