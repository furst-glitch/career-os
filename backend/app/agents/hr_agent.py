"""
HR Agent — vurderer tone, kulturelt fit og kommunikationsstil i ansøgning/CV.
"""
from app.agents.base import AgentResult, AgentUsage, BaseAgent
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
                "tone, kulturelt fit, kommunikationsstil og personlig gennemslagskraft.\n\n"
                "DANSK TONE-KALIBRERING:\n"
                "- Direkte og selvsikker, ikke ydmyg eller undskyldende\n"
                "- Aldrig: 'Jeg er en struktureret og analytisk person' (generisk)\n"
                "- Aldrig: 'Jeg brænder for...' (overbrugt i det danske marked)\n"
                "- Aldrig: 'Det vil jeg meget gerne' (for ivrig)\n"
                "- Aldrig: 'teamplayer', 'resultatorienteret', 'proaktiv' uden konkret eksempel\n"
                "- Foretruk: Specifikt, konkret, underbygget af eksempel\n"
                "- Ansøgning: INGEN fed skrift nogen steder\n"
                "- CV: Fed kun til stillingstitler og DKK/%-metrics\n\n"
                "KULTURELLE FIT-SIGNALER I JOBOPSLAGET — flag relevante:\n"
                "- 'Uformel omgangstone' = afslappet tone OK\n"
                "- 'Høj faglighed' = fremhæv ekspertise og præcision\n"
                "- 'The extra mile' / 'Ordentlighed' = kvalitet og opfølgning\n"
                "- 'Tæt på forretningen' = operationel nærhed værdsat\n"
                "- 'Korte beslutningsveje' = agilitet og ejerskab værdsat\n\n"
                "NØJAGTIGHEDSREGEL: Flag enhver påstand der overvurderer kandidatens faktiske erfaring.\n\n"
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
                "tone, cultural fit, communication style, and personal impact.\n\n"
                "TONE CALIBRATION:\n"
                "- Direct and confident, not humble or apologetic\n"
                "- Never: 'I am a structured and analytical person' (generic)\n"
                "- Never: 'I am passionate about...' (overused)\n"
                "- Never: 'I would very much like to...' (too eager)\n"
                "- Never: 'team player', 'results-driven', 'proactive' without a concrete example\n"
                "- Preferred: Specific, concrete, backed by example\n"
                "- Cover letters: NO bold text anywhere\n"
                "- CVs: Bold only for titles and key amounts/percentages\n\n"
                "CULTURAL FIT SIGNALS — flag if present in the job posting:\n"
                "- Informal culture signals = casual tone is appropriate\n"
                "- 'High professionalism' = emphasise expertise and precision\n"
                "- 'Going the extra mile' / 'thoroughness' = quality and follow-through\n"
                "- 'Close to the business' = operational proximity valued\n"
                "- 'Short decision paths' = agility and ownership valued\n\n"
                "ACCURACY RULE: Flag any claim overstating the candidate's actual experience.\n\n"
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
            provider=getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown"),
        )
        await self.log_usage(usage, operation=self.name, used_user_key=provider.used_user_key)
        return AgentResult(content=content, usage=usage)
