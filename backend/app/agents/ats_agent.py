"""
ATS Agent — analyserer om et dokument passerer Applicant Tracking Systems.
Returnerer konkrete forbedringer: manglende nøgleord, formatering, matchprocent.
"""
from app.agents.base import BaseAgent, AgentResult, AgentUsage
from app.providers.litellm_provider import LiteLLMProvider


class ATSAgent(BaseAgent):
    name = "ats_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          draft, job_title, job_company, job_description, job_requirements,
          language ('da'|'en'), doc_type ('cover_letter'|'cv')
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
                "Du er en ATS-ekspert (Applicant Tracking System). "
                "Analyser dokumentet og identificer præcist hvad der mangler eller skal forbedres "
                "for at bestå ATS-scanning og matche stillingen bedst muligt. "
                "Vær konkret og kortfattet. Maks 5 punkter, ét punkt pr. linje med '-' foran. "
                "Skriv KUN forbedringspunkterne, ingen introduktion eller opsummering."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Krav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"{'CV' if doc_type == 'cv' else 'Ansøgning'}:\n{draft}"
            )
        else:
            system = (
                "You are an ATS expert (Applicant Tracking System). "
                "Analyze the document and identify exactly what is missing or must improve "
                "to pass ATS scanning and best match the position. "
                "Be specific and concise. Max 5 bullet points, one per line starting with '-'. "
                "Output ONLY the improvement points, no intro or summary."
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
            temperature=0.2,
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
