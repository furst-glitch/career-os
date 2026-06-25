"""
Interview Prep Agent — genererer forberedelsespakke til jobsamtaler.

Producerer 3 dele via separate LLM-kald:
  1. company_research   — virksomhedsanalyse baseret på jobopslaget
  2. role_description   — rolleforståelse + gængse termer
  3. interview_guide    — samtaleforberedelse med spørgsmål og notatplads
"""
from __future__ import annotations

import asyncio

from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider


class InterviewPrepAgent(BaseAgent):
    name = "interview_prep_agent"

    async def run(self, input_data: dict, queue: asyncio.Queue | None = None) -> AgentResult:
        """
        input_data:
          job_title, job_company, job_description, job_requirements (list)
          candidate_summary (text_summary from snapshot)
          language: 'da' | 'en'
          cv_sent: str (CV sendt til virksomheden, valgfri)
          application_sent: str (ansøgning sendt, valgfri)
        """
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:4000]
        requirements = input_data.get("job_requirements", [])
        candidate_summary = input_data.get("candidate_summary", "")
        language = input_data.get("language", "da")
        cv_sent = input_data.get("cv_sent", "")
        application_sent = input_data.get("application_sent", "")
        req_text = "\n".join(f"- {r}" for r in requirements[:20]) if requirements else "Ikke angivet"

        async def progress(step: str, pct: int, msg: str):
            if queue:
                await queue.put(("progress", {"step": step, "pct": pct, "msg": msg}))

        await progress("company", 10, "Undersøger virksomheden...")
        company_result = await self._company_research(job_company, job_description, req_text, language)

        await progress("role", 40, "Analyserer rollen...")
        role_result = await self._role_description(job_title, job_company, job_description, req_text, language)

        await progress("guide", 70, "Bygger samtaleforberedelsesskema...")
        guide_result = await self._interview_guide(job_title, job_company, req_text, candidate_summary, cv_sent, application_sent, language)

        await progress("done", 95, "Næsten færdig...")

        combined = {
            "company_research": company_result.content,
            "role_description": role_result.content,
            "interview_guide": guide_result.content,
        }

        total_usage = AgentUsage(
            prompt_tokens=company_result.usage.prompt_tokens + role_result.usage.prompt_tokens + guide_result.usage.prompt_tokens,
            completion_tokens=company_result.usage.completion_tokens + role_result.usage.completion_tokens + guide_result.usage.completion_tokens,
            total_tokens=company_result.usage.total_tokens + role_result.usage.total_tokens + guide_result.usage.total_tokens,
            model=company_result.usage.model,
            provider=company_result.usage.provider,
        )
        return AgentResult(content=str(combined), usage=total_usage, metadata=combined)

    async def _company_research(self, company: str, description: str, req_text: str, language: str) -> AgentResult:
        if language == "da":
            system = (
                "Du er en erhvervsjournalist der laver grundig virksomhedsresearch til jobsøgere."
                " Baseret på jobopslaget skal du give et præcist overblik over virksomheden."
                " Skriv på dansk med korrekte æ, ø, å. Ingen markdown, ren tekst."
                " Maks 350 ord."
            )
            user_msg = (
                f"Virksomhed: {company}\n\nJobopslag:\n{description}\n\nKrav:\n{req_text}\n\n"
                "Skriv om:\n"
                "- Hvad virksomheden laver (forretningsmodel, produkter/services)\n"
                "- Branche og marked (konkurrenter, position)\n"
                "- Kultur og værdier (hvad der typisk kendetegner denne type virksomhed)\n"
                "- Aktuelle tendenser i branchen der er relevante for rollen\n"
                "- 3-5 gode spørgsmål kandidaten kan stille virksomheden til samtalen"
            )
        else:
            system = (
                "You are a business journalist doing thorough company research for job seekers."
                " Based on the job posting, provide an accurate overview of the company."
                " Max 350 words."
            )
            user_msg = (
                f"Company: {company}\n\nJob posting:\n{description}\n\nRequirements:\n{req_text}\n\n"
                "Cover: business model, industry position, culture, trends, and 3-5 questions to ask the interviewer."
            )
        return await self._llm(user_msg, system, 0.5, 700)

    async def _role_description(self, title: str, company: str, description: str, req_text: str, language: str) -> AgentResult:
        if language == "da":
            system = (
                "Du er en karriererådgiver der hjælper kandidater med at forstå en rolle i dybden."
                " Skriv på dansk med korrekte æ, ø, å. Ingen markdown, ren tekst. Maks 300 ord."
            )
            user_msg = (
                f"Stilling: {title} hos {company}\n\nJobopslag:\n{description}\n\nKrav:\n{req_text}\n\n"
                "Beskriv:\n"
                "- Hvad rollen typisk indebærer dag-til-dag\n"
                "- Centrale ansvarsområder og forventninger\n"
                "- Faglige nøgletermer og begreber i funktionen der er godt at kende\n"
                "- Hvilke kompetencer der typisk differentierer en god kandidat fra en fremragende"
            )
        else:
            system = (
                "You are a career advisor helping candidates deeply understand a role."
                " Max 300 words."
            )
            user_msg = (
                f"Position: {title} at {company}\n\nJob posting:\n{description}\n\nRequirements:\n{req_text}\n\n"
                "Describe: daily responsibilities, key terms in the field, what makes a standout candidate."
            )
        return await self._llm(user_msg, system, 0.5, 600)

    async def _interview_guide(self, title: str, company: str, req_text: str, candidate_summary: str, cv_sent: str, application_sent: str, language: str) -> AgentResult:
        context_parts = [f"Kandidatprofil:\n{candidate_summary}"]
        if cv_sent:
            context_parts.append(f"CV sendt:\n{cv_sent[:1500]}")
        if application_sent:
            context_parts.append(f"Ansøgning sendt:\n{application_sent[:1500]}")
        context = "\n\n".join(context_parts)

        if language == "da":
            system = (
                "Du er en erfaren interviewcoach der laver individuelle samtaleforberedelsesguides."
                " Skriv på dansk med korrekte æ, ø, å. Ingen markdown, ren tekst. Maks 500 ord."
            )
            user_msg = (
                f"Stilling: {title} hos {company}\nKrav:\n{req_text}\n\n{context}\n\n"
                "Lav en samtaleforberedelsesguide med:\n"
                "1. 5-7 spørgsmål kandidaten sandsynligvis bliver stillet (baseret på kravene) med korte hints til svar\n"
                "2. 3-4 STAR-eksempler kandidaten bør forberede (Situation, Task, Action, Result)\n"
                "3. Notatplads: tomme linjer til candidatens egne noter under samtalen\n"
                "4. Tjekliste: hvad du skal huske at medbringe/forberede inden samtalen"
            )
        else:
            system = (
                "You are an experienced interview coach creating personalized interview prep guides."
                " Max 500 words."
            )
            user_msg = (
                f"Position: {title} at {company}\nRequirements:\n{req_text}\n\n{context}\n\n"
                "Create: 5-7 likely interview questions with answer hints, 3-4 STAR examples to prepare, "
                "space for notes, and a pre-interview checklist."
            )
        return await self._llm(user_msg, system, 0.65, 1000)

    async def _llm(self, user_msg: str, system: str, temperature: float, max_tokens: int) -> AgentResult:
        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
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
        return AgentResult(content=content, usage=usage, metadata={})
