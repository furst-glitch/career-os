from app.agents.base import BaseAgent, AgentResult


class ApplicationAgent(BaseAgent):
    name = "application_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("application_agent er ikke implementeret endnu")
