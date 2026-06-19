"""
HR Agent — vurderer tone, kulturelt fit og kommunikationsstil i ansøgning/CV.
"""
from app.agents.base import BaseAgent, AgentResult, AgentUsage
from app.providers.litellm_provider import LiteLLMProvider


class HRAgent(BaseAgent):
    name = "hr_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          draft, job_title, job_company, job_description, job_requirements,
          language ('da'|'en'), doc_type, writing_style
        """
        draft = input_data.get("draft", "")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:1500]
        language = input_data.get("language", "da")
        doc_type = input_data.get("doc_type", "cover_letter")

        if language == "da":
            system = (
                "Du er en erfaren HR-chef. Vurder dokumentet fra et HR-perspektiv: "
                "tone, kulturelt fit, kommunikationsstil og personlig gennemslagskraft. "
                "Identificer specifikt hvad der gør dokumentet stærkere eller svagere. "
                "Maks 4 punkter, ét punkt pr. linje med '-' foran. "
                "Skriv KUN forbedringspunkterne, ingen introduktion."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"{'CV' if doc_type == 'cv' else 'Ansøgning'}:\n{draft}"
            )
        else:
            system = (
                "You are an experienced HR director. Evaluate the document from an HR perspective: "
                "tone, cultural fit, communication style, and personal impact. "
                "Identify specifically what makes the document stronger or weaker. "
                "Max 4 bullet points, one per line starting with '-'. "
                "Output ONLY the improvement points, no introduction."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\nJob Description:\n{job_description}\n\n"
                f"{'CV' if doc_type == 'cv' else 'Cover letter'}:\n{draft}"
            )

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.3,
            max_tokens=300,
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
