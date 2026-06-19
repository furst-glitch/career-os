from app.agents.base import AgentResult, BaseAgent


class InterviewAgent(BaseAgent):
    name = "interview_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("interview_agent er ikke implementeret endnu")
