"""
Critic Agent — syntetiserer feedback fra ATS, HR og Hiring Manager
til en prioriteret liste af de vigtigste forbedringer.
"""
from app.agents.base import BaseAgent, AgentResult, AgentUsage
from app.providers.litellm_provider import LiteLLMProvider


class CriticAgent(BaseAgent):
    name = "critic_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          ats_review: str   (feedback fra ATSAgent)
          hr_review: str    (feedback fra HRAgent)
          hm_review: str    (feedback fra HiringManagerAgent)
          language: 'da' | 'en'
          doc_type: 'cover_letter' | 'cv'
        """
        ats_review = input_data.get("ats_review", "")
        hr_review = input_data.get("hr_review", "")
        hm_review = input_data.get("hm_review", "")
        language = input_data.get("language", "da")

        if language == "da":
            system = (
                "Du er en skarp redaktør. Du modtager feedback fra tre eksperter (ATS, HR, Hiring Manager) "
                "om et dokument. Din opgave: syntetiser feedbacken til de 5 VIGTIGSTE forbedringer, "
                "sorteret efter impact. Eliminer overlap. Vær specifik og handlingsorienteret. "
                "Format: '1. [forbedring]' til '5. [forbedring]'. Kun listen, ingen indledning."
            )
            user_msg = (
                f"ATS-feedback:\n{ats_review}\n\n"
                f"HR-feedback:\n{hr_review}\n\n"
                f"Hiring Manager-feedback:\n{hm_review}"
            )
        else:
            system = (
                "You are a sharp editor. You receive feedback from three experts (ATS, HR, Hiring Manager) "
                "about a document. Your task: synthesize the feedback into the 5 MOST IMPORTANT improvements, "
                "sorted by impact. Eliminate overlap. Be specific and action-oriented. "
                "Format: '1. [improvement]' through '5. [improvement]'. Only the list, no introduction."
            )
            user_msg = (
                f"ATS feedback:\n{ats_review}\n\n"
                f"HR feedback:\n{hr_review}\n\n"
                f"Hiring Manager feedback:\n{hm_review}"
            )

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.2,
            max_tokens=400,
        )
        content = response.choices[0].message.content or ""
        ud = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
        usage = AgentUsage(
            prompt_tokens=getattr(ud, "prompt_tokens", 0),
            completion_tokens=getattr(ud, "completion_tokens", 0),
            total_tokens=getattr(ud, "total_tokens", 0),
            model=getattr(response, "model", "unknown"),
        )
        return AgentResult(content=content, usage=usage)
