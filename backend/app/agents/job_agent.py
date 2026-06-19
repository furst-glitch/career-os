"""
JobAgent — dybdegående analyse af jobopslag.

Input:  job_title, job_company, job_description, job_requirements, language
Output: struktureret jobanalyse med nøglekrav, kulturelle signaler,
        ATS-nøgleord og hvad der adskiller vinderkandidater.
"""
from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider


class JobAgent(BaseAgent):
    name = "job_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          job_title, job_company, job_description, job_requirements, language
        """
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:3000]
        requirements = input_data.get("job_requirements", [])
        language = input_data.get("language", "da")
        req_text = "\n".join(f"- {r}" for r in requirements[:20]) if requirements else "Ikke angivet"

        if language == "da":
            system = (
                "Du er en ekspert rekrutteringsstrateg. Analysér jobopslaget og producér en præcis jobanalyse.\n\n"
                "Format (brug disse præcise overskrifter):\n"
                "NØGLEKRAV: [De 5 vigtigste krav — hvad der SKAL matche]\n"
                "KULTURELLE SIGNALER: [Virksomhedskultur, arbejdsstil, tone i opslaget]\n"
                "ATS-NØGLEORD: [Præcise ord og sætninger fra opslaget der SKAL fremgå i ansøgningen]\n"
                "VINDERKVALITETER: [Hvad adskiller den ideelle kandidat fra en middelmådig ansøger]\n"
                "RØDE FLAG: [Krav der typisk eliminerer kandidater — vær ærlig]\n\n"
                "Vær konkret og kortfattet. Maks 250 ord total."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Krav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}"
            )
        else:
            system = (
                "You are an expert recruiting strategist. Analyze the job posting and produce a precise job analysis.\n\n"
                "Format (use these exact headings):\n"
                "KEY REQUIREMENTS: [The 5 most important requirements — what MUST match]\n"
                "CULTURAL SIGNALS: [Company culture, work style, tone in the posting]\n"
                "ATS KEYWORDS: [Exact words and phrases from the posting that MUST appear in the application]\n"
                "WINNER QUALITIES: [What separates the ideal candidate from an average applicant]\n"
                "RED FLAGS: [Requirements that typically eliminate candidates — be honest]\n\n"
                "Be concrete and concise. Max 250 words total."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}"
            )

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.2,
            max_tokens=450,
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
