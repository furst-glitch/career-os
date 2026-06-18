"""
Application Agent — genererer ansøgninger (cover letters) baseret på karriere-snapshot og jobdetaljer.
"""
from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, AgentUsage
from app.providers.litellm_provider import LiteLLMProvider, NoProviderKeyError


class ApplicationAgent(BaseAgent):
    name = "application_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          job_title, job_company, job_description, job_requirements (list)
          candidate_summary (text_summary from snapshot)
          language: 'da' | 'en'
          writing_style: 'professional' | 'direct' | 'warm' | 'technical' | 'narrative'
          focus_areas: str (optional)
        """
        language = input_data.get("language", "da")
        style = input_data.get("writing_style", "professional")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:3000]
        requirements = input_data.get("job_requirements", [])
        candidate_summary = input_data.get("candidate_summary", "")
        focus_areas = input_data.get("focus_areas", "")

        req_text = "\n".join(f"- {r}" for r in requirements[:15]) if requirements else "Ikke angivet"

        style_instructions = {
            "professional": "professionel og formel tone",
            "direct": "direkte og konkret tone uden fyldord",
            "warm": "varm, personlig og engagerende tone",
            "technical": "teknisk præcis tone med fokus på specifikke kompetencer",
            "narrative": "fortællende tone der skaber en sammenhængende karrierefortælling",
        }.get(style, "professionel og formel tone")

        if language == "da":
            system = (
                "Du er en ekspert karriere-rådgiver og ansøgningsskriver. "
                "Skriv en overbevisende, personlig ansøgning på dansk. "
                f"Brug {style_instructions}. "
                "Ansøgningen skal have: åbning der fanger læseren, "
                "klar kobling mellem kandidatens baggrund og jobkravene, "
                "konkrete eksempler og tal, og en stærk afslutning. "
                "Undgå klichéer. Maks 400 ord."
            )
            user_msg = (
                f"Stil: {job_title} hos {job_company}\n\n"
                f"Jobkrav:\n{req_text}\n\n"
                f"Jobbeskrivelse:\n{job_description}\n\n"
                f"Kandidatprofil:\n{candidate_summary}"
            )
            if focus_areas:
                user_msg += f"\n\nFokusér særligt på: {focus_areas}"
        else:
            system = (
                "You are an expert career advisor and cover letter writer. "
                "Write a compelling, personalized cover letter in English. "
                f"Use {style_instructions}. "
                "The letter should: open with a hook, clearly connect the candidate's background "
                "to the job requirements, include specific examples and numbers, "
                "and close with a strong call to action. Avoid clichés. Max 400 words."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Requirements:\n{req_text}\n\n"
                f"Job Description:\n{job_description}\n\n"
                f"Candidate Profile:\n{candidate_summary}"
            )
            if focus_areas:
                user_msg += f"\n\nFocus especially on: {focus_areas}"

        provider = LiteLLMProvider(self.user_id)
        try:
            response = await provider.complete(
                agent_name=self.name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                stream=False,
                temperature=0.75,
                max_tokens=800,
            )
        except NoProviderKeyError as exc:
            raise exc

        content = response.choices[0].message.content or ""
        usage_data = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()

        usage = AgentUsage(
            prompt_tokens=getattr(usage_data, "prompt_tokens", 0),
            completion_tokens=getattr(usage_data, "completion_tokens", 0),
            total_tokens=getattr(usage_data, "total_tokens", 0),
            model=getattr(response, "model", "unknown"),
            provider=getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown"),
        )

        return AgentResult(
            content=content,
            usage=usage,
            metadata={"language": language, "style": style},
        )
