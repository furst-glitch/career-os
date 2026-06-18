"""
Multi-agent review pipeline.

Kørsel:
  1. Review Board definerer hvilke agenter der aktiveres
  2. ATS + HR + Hiring Manager kører parallelt
  3. Critic syntetiserer og angriber svagheder
  4. Career Coach kontekstualiserer ift. Career Memory + mål
  5. Review Board producerer endelig rapport med handlingsplan
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.agents.base import AgentResult


@dataclass
class PipelineReport:
    document_id: str
    agent_outputs: dict[str, AgentResult] = field(default_factory=dict)
    final_summary: str = ""
    critical_issues: list[str] = field(default_factory=list)
    quick_wins: list[str] = field(default_factory=list)
    action_plan: list[str] = field(default_factory=list)
    overall_score: float = 0.0


class ReviewPipeline:
    DEFAULT_AGENTS = [
        "ats_agent",
        "hr_agent",
        "hiring_manager_agent",
        "critic_agent",
        "career_coach_agent",
        "review_board_agent",
    ]

    def __init__(self, user_id: str, supabase: Any) -> None:
        self.user_id = user_id
        self.supabase = supabase

    async def run(
        self,
        document_id: str,
        job_id: str | None = None,
        agents: list[str] | None = None,
    ) -> PipelineReport:
        active_agents = agents or self.DEFAULT_AGENTS
        report = PipelineReport(document_id=document_id)

        # Fase 1: Parallelt (ATS + HR + Hiring Manager)
        parallel_agents = [a for a in active_agents if a in ("ats_agent", "hr_agent", "hiring_manager_agent")]
        parallel_results = await self._run_parallel(parallel_agents, document_id, job_id)
        report.agent_outputs.update(parallel_results)

        # Fase 2: Sequentielt (Critic → Coach → Review Board)
        for agent_name in ("critic_agent", "career_coach_agent", "review_board_agent"):
            if agent_name in active_agents:
                result = await self._run_agent(agent_name, document_id, job_id, report.agent_outputs)
                report.agent_outputs[agent_name] = result

        # Hent Review Board output som endelig rapport
        if "review_board_agent" in report.agent_outputs:
            self._parse_final_report(report)

        return report

    async def _run_parallel(
        self, agent_names: list[str], document_id: str, job_id: str | None
    ) -> dict[str, AgentResult]:
        tasks = {
            name: self._run_agent(name, document_id, job_id, {})
            for name in agent_names
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {
            name: result
            for name, result in zip(tasks.keys(), results)
            if isinstance(result, AgentResult)
        }

    async def _run_agent(
        self,
        agent_name: str,
        document_id: str,
        job_id: str | None,
        prior_outputs: dict,
    ) -> AgentResult:
        # Dynamisk import for at undgå cirkulære imports
        agent_map = {
            "ats_agent": "app.agents.ats_agent.ATSAgent",
            "hr_agent": "app.agents.hr_agent.HRAgent",
            "hiring_manager_agent": "app.agents.hiring_manager_agent.HiringManagerAgent",
            "critic_agent": "app.agents.critic_agent.CriticAgent",
            "career_coach_agent": "app.agents.career_coach_agent.CareerCoachAgent",
            "review_board_agent": "app.agents.review_board_agent.ReviewBoardAgent",
        }

        if agent_name not in agent_map:
            raise ValueError(f"Ukendt agent: {agent_name}")

        module_path, class_name = agent_map[agent_name].rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        agent_class = getattr(module, class_name)

        agent = agent_class(user_id=self.user_id, supabase=self.supabase)
        return await agent.run({
            "document_id": document_id,
            "job_id": job_id,
            "prior_outputs": prior_outputs,
        })

    def _parse_final_report(self, report: PipelineReport) -> None:
        # Review Board Agent udfylder dette via structured output
        board_output = report.agent_outputs.get("review_board_agent")
        if board_output and board_output.metadata:
            report.final_summary = board_output.content
            report.critical_issues = board_output.metadata.get("critical_issues", [])
            report.quick_wins = board_output.metadata.get("quick_wins", [])
            report.action_plan = board_output.metadata.get("action_plan", [])
            report.overall_score = board_output.metadata.get("overall_score", 0.0)
