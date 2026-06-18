from app.agents.base import BaseAgent, AgentResult


class CvAgent(BaseAgent):
    name = "cv_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("cv_agent er ikke implementeret endnu")
