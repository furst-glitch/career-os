from app.agents.base import AgentResult, BaseAgent


class JobAgent(BaseAgent):
    name = "job_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("job_agent er ikke implementeret endnu")
