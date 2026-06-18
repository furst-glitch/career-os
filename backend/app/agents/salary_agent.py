from app.agents.base import BaseAgent, AgentResult


class SalaryAgent(BaseAgent):
    name = "salary_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("salary_agent er ikke implementeret endnu")
