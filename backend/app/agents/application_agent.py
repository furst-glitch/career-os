"""
Application Agent — genererer ansøgninger og CV via en multi-agent review-pipeline:
  1. Generer udkast (ApplicationAgent selv)
  2. ATS + HR + HiringManager analyserer parallelt
  3. Critic syntetiserer til prioriteret forbedringsliste
  4. Rewrite med feedback inkorporeret
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.agents.base import BaseAgent, AgentResult, AgentUsage
from app.providers.litellm_provider import LiteLLMProvider, NoProviderKeyError


class ApplicationAgent(BaseAgent):
    name = "application_agent"

    async def run(self, input_data: dict, queue: asyncio.Queue | None = None) -> AgentResult:
        """
        input_data:
          job_title, job_company, job_description, job_requirements (list)
          candidate_summary (text_summary from snapshot)
          language: 'da' | 'en'
          writing_style: 'professional' | 'direct' | 'warm' | 'technical' | 'narrative'
          focus_areas: str (optional)
          doc_type: 'cover_letter' | 'cv'  (default: 'cover_letter')

        queue: optional asyncio.Queue for SSE progress events.
          Agent push'er ("progress", {step, pct, msg}) undervejs.
        """
        doc_type = input_data.get("doc_type", "cover_letter")
        if doc_type == "cv":
            return await self._run_with_review(input_data, queue, is_cv=True)
        return await self._run_with_review(input_data, queue, is_cv=False)

    async def _push(self, queue: asyncio.Queue | None, step: str, pct: int, msg: str) -> None:
        if queue is not None:
            await queue.put(("progress", {"step": step, "pct": pct, "msg": msg}))

    async def _run_with_review(self, input_data: dict, queue: asyncio.Queue | None, is_cv: bool) -> AgentResult:
        language = input_data.get("language", "da")
        doc_type = "cv" if is_cv else "cover_letter"

        # ── Trin 1: Generer udkast ────────────────────────────────────────────
        await self._push(queue, "draft", 10, "Skriver udkast..." if language == "da" else "Writing draft...")
        if is_cv:
            draft_result = await self._generate_cv_draft(input_data)
        else:
            draft_result = await self._generate_cover_letter_draft(input_data)
        draft_text = draft_result.content

        # ── Trin 2: Parallel review (ATS + HR + Hiring Manager) ───────────────
        await self._push(
            queue, "review", 35,
            "ATS, HR og hiring manager analyserer..." if language == "da" else "ATS, HR and hiring manager reviewing...",
        )
        review_input = {
            "draft": draft_text,
            "job_title": input_data.get("job_title", ""),
            "job_company": input_data.get("job_company", ""),
            "job_description": input_data.get("job_description", ""),
            "job_requirements": input_data.get("job_requirements", []),
            "language": language,
            "doc_type": doc_type,
        }

        from app.agents.ats_agent import ATSAgent
        from app.agents.hr_agent import HRAgent
        from app.agents.hiring_manager_agent import HiringManagerAgent
        from app.agents.critic_agent import CriticAgent

        ats_result, hr_result, hm_result = await asyncio.gather(
            ATSAgent(self.user_id, self.supabase).run(review_input),
            HRAgent(self.user_id, self.supabase).run(review_input),
            HiringManagerAgent(self.user_id, self.supabase).run(review_input),
            return_exceptions=True,
        )

        # Hvis en reviewer fejler, brug tom streng (rewrite fortsætter med det den har)
        ats_feedback = ats_result.content if isinstance(ats_result, AgentResult) else ""
        hr_feedback = hr_result.content if isinstance(hr_result, AgentResult) else ""
        hm_feedback = hm_result.content if isinstance(hm_result, AgentResult) else ""

        # ── Trin 3: Critic syntetiserer ───────────────────────────────────────
        await self._push(
            queue, "critique", 62,
            "Syntetiserer feedback..." if language == "da" else "Synthesizing feedback...",
        )
        critique_result = await CriticAgent(self.user_id, self.supabase).run({
            "ats_review": ats_feedback,
            "hr_review": hr_feedback,
            "hm_review": hm_feedback,
            "language": language,
            "doc_type": doc_type,
        })
        prioritized_feedback = critique_result.content

        # ── Trin 4: Rewrite med feedback ─────────────────────────────────────
        await self._push(
            queue, "rewrite", 78,
            "Forbedrer og finpudser..." if language == "da" else "Improving and polishing...",
        )
        final_result = await self._rewrite_with_feedback(
            draft=draft_text,
            feedback=prioritized_feedback,
            input_data=input_data,
            is_cv=is_cv,
        )

        # Akkumulér samlet token-forbrug
        total_usage = AgentUsage(
            prompt_tokens=draft_result.usage.prompt_tokens + final_result.usage.prompt_tokens,
            completion_tokens=draft_result.usage.completion_tokens + final_result.usage.completion_tokens,
            total_tokens=draft_result.usage.total_tokens + final_result.usage.total_tokens,
            model=final_result.usage.model,
        )

        return AgentResult(
            content=final_result.content,
            usage=total_usage,
            metadata={
                "language": language,
                "doc_type": doc_type,
                "review_pipeline": True,
                "ats_feedback": ats_feedback,
                "hr_feedback": hr_feedback,
                "hm_feedback": hm_feedback,
                "prioritized_feedback": prioritized_feedback,
            },
        )

    async def _generate_cv_draft(self, input_data: dict) -> AgentResult:
        language = input_data.get("language", "da")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:3000]
        requirements = input_data.get("job_requirements", [])
        candidate_summary = input_data.get("candidate_summary", "")
        req_text = "\n".join(f"- {r}" for r in requirements[:15]) if requirements else "Ikke angivet"

        if language == "da":
            system = (
                "Du er en ekspert CV-skribent. Generér et professionelt, målrettet CV på dansk "
                f"tilpasset stillingen {job_title} hos {job_company}. "
                "Fremhæv de kompetencer og erfaringer der matcher jobkravene. "
                "Brug bullet-points, kvantificér resultater. Maks 600 ord."
            )
            user_msg = f"Jobkrav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\nKandidatprofil:\n{candidate_summary}"
        else:
            system = (
                f"You are an expert CV writer. Generate a professional, targeted CV in English "
                f"tailored to the {job_title} position at {job_company}. "
                "Highlight skills and experience matching the job requirements. "
                "Use bullet points, quantify results. Max 600 words."
            )
            user_msg = f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}\n\nCandidate Profile:\n{candidate_summary}"

        return await self._llm_call(user_msg, system, temperature=0.5, max_tokens=1200, language=language, doc_type="cv")

    async def _generate_cover_letter_draft(self, input_data: dict) -> AgentResult:
        language = input_data.get("language", "da")
        style = input_data.get("writing_style", "professional")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:3000]
        requirements = input_data.get("job_requirements", [])
        candidate_summary = input_data.get("candidate_summary", "")
        focus_areas = input_data.get("focus_areas", "")
        req_text = "\n".join(f"- {r}" for r in requirements[:15]) if requirements else "Ikke angivet"

        style_da = {
            "professional": "professionel og formel tone",
            "direct": "direkte og konkret tone uden fyldord",
            "warm": "varm, personlig og engagerende tone",
            "technical": "teknisk præcis tone med fokus på specifikke kompetencer",
            "narrative": "fortællende tone der skaber en sammenhængende karrierefortælling",
        }.get(style, "professionel og formel tone")

        style_en = {
            "professional": "professional and formal tone",
            "direct": "direct and concise tone without filler words",
            "warm": "warm, personal and engaging tone",
            "technical": "technically precise tone focusing on specific skills",
            "narrative": "narrative tone that creates a cohesive career story",
        }.get(style, "professional and formal tone")

        if language == "da":
            system = (
                "Du er en ekspert karriere-rådgiver og ansøgningsskriver. "
                "Skriv en overbevisende, personlig ansøgning på dansk. "
                f"Brug {style_da}. "
                "Ansøgningen skal have: åbning der fanger læseren, "
                "klar kobling mellem kandidatens baggrund og jobkravene, "
                "konkrete eksempler og tal, og en stærk afslutning. "
                "Undgå klichéer. Maks 400 ord."
            )
            user_msg = (
                f"Stil: {job_title} hos {job_company}\n\n"
                f"Jobkrav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"Kandidatprofil:\n{candidate_summary}"
            )
            if focus_areas:
                user_msg += f"\n\nFokusér særligt på: {focus_areas}"
        else:
            system = (
                "You are an expert career advisor and cover letter writer. "
                "Write a compelling, personalized cover letter in English. "
                f"Use {style_en}. "
                "The letter should: open with a hook, clearly connect the candidate's background "
                "to the job requirements, include specific examples and numbers, "
                "and close with a strong call to action. Avoid clichés. Max 400 words."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}\n\n"
                f"Candidate Profile:\n{candidate_summary}"
            )
            if focus_areas:
                user_msg += f"\n\nFocus especially on: {focus_areas}"

        return await self._llm_call(user_msg, system, temperature=0.75, max_tokens=800, language=language, doc_type="cover_letter")

    async def _rewrite_with_feedback(
        self, draft: str, feedback: str, input_data: dict, is_cv: bool
    ) -> AgentResult:
        language = input_data.get("language", "da")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        doc_type = "cv" if is_cv else "cover_letter"

        if language == "da":
            system = (
                "Du er en ekspert redaktør. Du modtager et udkast og en prioriteret liste af forbedringer. "
                "Omskriv dokumentet så alle forbedringer er implementeret. "
                "Behold den overordnede struktur og stil, men gør det markant bedre. "
                "Returner KUN det færdige dokument — ingen kommentarer eller forklaringer."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Udkast:\n{draft}\n\n"
                f"Prioriterede forbedringer:\n{feedback}\n\n"
                f"Skriv den forbedrede version af {'CV' if is_cv else 'ansøgningen'}:"
            )
        else:
            system = (
                "You are an expert editor. You receive a draft and a prioritized list of improvements. "
                "Rewrite the document so all improvements are implemented. "
                "Keep the overall structure and style, but make it significantly better. "
                "Return ONLY the finished document — no comments or explanations."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Draft:\n{draft}\n\n"
                f"Prioritized improvements:\n{feedback}\n\n"
                f"Write the improved version of the {'CV' if is_cv else 'cover letter'}:"
            )

        max_tokens = 1400 if is_cv else 900
        return await self._llm_call(user_msg, system, temperature=0.6, max_tokens=max_tokens, language=language, doc_type=doc_type)

    async def _llm_call(
        self, user_msg: str, system: str, temperature: float, max_tokens: int, language: str, doc_type: str
    ) -> AgentResult:
        provider = LiteLLMProvider(self.user_id)
        try:
            response = await provider.complete(
                agent_name=self.name,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except NoProviderKeyError:
            raise

        content = response.choices[0].message.content or ""
        ud = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
        usage = AgentUsage(
            prompt_tokens=getattr(ud, "prompt_tokens", 0),
            completion_tokens=getattr(ud, "completion_tokens", 0),
            total_tokens=getattr(ud, "total_tokens", 0),
            model=getattr(response, "model", "unknown"),
            provider=getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown"),
        )
        return AgentResult(content=content, usage=usage, metadata={"language": language, "doc_type": doc_type})
