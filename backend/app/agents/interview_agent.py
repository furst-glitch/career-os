from app.agents.base import AgentResult, AgentUsage, BaseAgent


class InterviewAgent(BaseAgent):
    name = "interview_agent"

    async def run(self, input_data: dict) -> AgentResult:
        # This agent is registered but not yet implemented.
        # Returns a structured error so callers can handle it gracefully.
        return AgentResult(
            content="",
            usage=AgentUsage(),
            metadata={"error": "agent_not_implemented", "agent": self.name},
        )
