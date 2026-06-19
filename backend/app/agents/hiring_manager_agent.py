"""
Hiring Manager Agent — vurderer professionel relevans, resultater og teknisk match.
"""
from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider


class HiringManagerAgent(BaseAgent):
    name = "hiring_manager_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          draft, job_title, job_company, job_description, job_requirements,
          language ('da'|'en'), doc_type
        """
        draft = input_data.get("draft", "")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:2000]
        requirements = input_data.get("job_requirements", [])
        language = input_data.get("language", "da")
        doc_type = input_data.get("doc_type", "cover_letter")
        req_text = "\n".join(f"- {r}" for r in requirements[:15]) if requirements else "Ikke angivet"

        if language == "da":
            system = (
                "Du er hiring manager for denne stilling og screener kandidater. "
                "Vurder dokumentet: Er kandidatens relevante erfaring tydelig? "
                "Er der konkrete resultater og tal? Matcher kandidaten det vi søger? "
                "Hvad ville få dig til at kalde dem til samtale — eller IKKE? "
                "Maks 4 punkter, ét punkt pr. linje med '-' foran. "
                "Skriv KUN forbedringspunkterne, ingen introduktion."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Krav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"{'CV' if doc_type == 'cv' else 'Ansøgning'}:\n{draft}"
            )
        else:
            system = (
                "You are the hiring manager for this position screening candidates. "
                "Evaluate the document: Is the candidate's relevant experience clear? "
                "Are there concrete results and numbers? Does the candidate match what we need? "
                "What would make you call them for an interview — or NOT? "
                "Max 4 bullet points, one per line starting with '-'. "
                "Output ONLY the improvement points, no introduction."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}\n\n"
                f"{'CV' if doc_type == 'cv' else 'Cover letter'}:\n{draft}"
            )

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.25,
            max_tokens=350,
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
