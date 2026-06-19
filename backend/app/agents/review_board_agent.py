from app.agents.base import AgentResult, BaseAgent


class ReviewBoardAgent(BaseAgent):
    name = "review_board_agent"

    async def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError("review_board_agent er ikke implementeret endnu")
