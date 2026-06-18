from app.agents.base import BaseAgent, AgentResult


class CareerCoachAgent(BaseAgent):
    name = "career_coach_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("career_coach_agent er ikke implementeret endnu")
