"""
Application Agent — genererer ansøgninger og CV med et kraftfuldt enkelt-kald prompt
der integrerer ATS-, HR- og hiring manager-perspektiver direkte i genereringen.

Tidligere multi-agent pipeline (draft→review→rewrite) tog 90-150 sekunder.
Dette single-call design leverer samme kvalitet på 25-40 sekunder.
"""
from __future__ import annotations

import asyncio

from app.agents.base import AgentResult, AgentUsage, BaseAgent
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
        """
        doc_type = input_data.get("doc_type", "cover_letter")

        if queue is not None:
            await queue.put(("progress", {
                "step": "generating",
                "pct": 20,
                "msg": "AI skriver dit dokument..." if input_data.get("language", "da") == "da" else "AI is writing your document...",
            }))

        if doc_type == "cv":
            result = await self._run_cv(input_data)
        else:
            result = await self._run_cover_letter(input_data)

        if queue is not None:
            await queue.put(("progress", {
                "step": "done",
                "pct": 95,
                "msg": "Næsten færdig..." if input_data.get("language", "da") == "da" else "Almost done...",
            }))

        return result

    async def _run_cv(self, input_data: dict) -> AgentResult:
        language = input_data.get("language", "da")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:3000]
        requirements = input_data.get("job_requirements", [])
        candidate_summary = input_data.get("candidate_summary", "")
        req_text = "\n".join(f"- {r}" for r in requirements[:15]) if requirements else "Ikke angivet"

        if language == "da":
            system = (
                "Du er en ekspert CV-skribent der skriver CV'er som:\n"
                "• PASSERER ATS-scanning: Brug præcise nøgleord fra jobannoncen, undgå tabeller og spalter der forvirrer ATS-systemer\n"
                "• ENGAGERER HR: Tydelig struktur, professionel tone, klar kommunikation af value proposition\n"
                "• IMPONERER HIRING MANAGER: Konkrete resultater med tal og procenter, direkte match til kravene, fremhæv det mest relevante øverst\n\n"
                f"Generér et målrettet CV på dansk til stillingen {job_title} hos {job_company}.\n"
                "Fremhæv de kompetencer og erfaringer der matcher jobkravene.\n"
                "Brug bullet-points, kvantificér resultater. Maks 600 ord.\n\n"
                "VIGTIGT: Skriv altid med korrekte danske bogstaver: æ, ø, å, Æ, Ø, Å. Brug IKKE ae, oe, aa.\n"
                "Brug IKKE markdown-formatering (ingen **, *, # eller andre symboler). Skriv ren tekst."
            )
            user_msg = (
                f"Jobkrav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"Kandidatprofil:\n{candidate_summary}"
            )
        else:
            system = (
                "You are an expert CV writer who creates CVs that:\n"
                "• PASS ATS SCANNING: Use exact keywords from the job posting, avoid tables/columns that confuse ATS systems\n"
                "• ENGAGE HR: Clear structure, professional tone, clear value proposition\n"
                "• IMPRESS HIRING MANAGER: Concrete results with numbers and percentages, direct match to requirements, most relevant experience first\n\n"
                f"Generate a targeted CV in English for the {job_title} position at {job_company}.\n"
                "Highlight skills and experience matching the job requirements.\n"
                "Use bullet points, quantify results. Max 600 words."
            )
            user_msg = (
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}\n\n"
                f"Candidate Profile:\n{candidate_summary}"
            )

        return await self._llm_call(user_msg, system, temperature=0.5, max_tokens=1200, language=language, doc_type="cv")

    async def _run_cover_letter(self, input_data: dict) -> AgentResult:
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
            "professional": "professionel og formel",
            "direct": "direkte og konkret uden fyldord",
            "warm": "varm, personlig og engagerende",
            "technical": "teknisk præcis med fokus på specifikke kompetencer",
            "narrative": "fortællende med en sammenhængende karrierefortælling",
        }.get(style, "professionel og formel")

        style_en = {
            "professional": "professional and formal",
            "direct": "direct and concise without filler words",
            "warm": "warm, personal and engaging",
            "technical": "technically precise focusing on specific skills",
            "narrative": "narrative with a cohesive career story",
        }.get(style, "professional and formal")

        if language == "da":
            system = (
                f"Du er en ekspert ansøgningsskriver. Skriv en ansøgning med {style_da} tone der:\n\n"
                "• PASSERER ATS: Inkludér nøgleord fra jobannoncen naturligt i teksten\n"
                "• ENGAGERER HR: Åbn stærkt, vis kulturelt fit, kommunikér klart og personligt\n"
                "• IMPONERER HIRING MANAGER: Fremhæv konkrete resultater med tal, vis direkte match til kravene\n\n"
                "Struktur: Stærk åbning → Konkrete eksempler med tal → Direkte match til jobkrav → Afslutning med call-to-action\n"
                "Undgå klichéer ('jeg er teamplayer', 'passioneret for'). Maks 400 ord.\n\n"
                "VIGTIGT: Skriv altid med korrekte danske bogstaver: æ, ø, å, Æ, Ø, Å. Brug IKKE ae, oe, aa.\n"
                "Brug IKKE markdown-formatering (ingen **, *, # eller andre symboler). Skriv ren tekst.\n"
                "Afslut med 'Med venlig hilsen' efterfulgt af kandidatens fulde navn hvis det fremgår af profilen."
            )
            candidate_block = candidate_summary
            user_msg = (
                f"Stil: {job_title} hos {job_company}\n\n"
                f"Jobkrav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"Kandidatprofil:\n{candidate_block}"
            )
            if focus_areas:
                user_msg += f"\n\nFokusér særligt på: {focus_areas}"
        else:
            system = (
                f"You are an expert cover letter writer. Write a cover letter with {style_en} tone that:\n\n"
                "• PASSES ATS: Include keywords from the job posting naturally in the text\n"
                "• ENGAGES HR: Open strong, show cultural fit, communicate clearly and personally\n"
                "• IMPRESSES HIRING MANAGER: Highlight concrete results with numbers, show direct match to requirements\n\n"
                "Structure: Strong opening → Concrete examples with numbers → Direct match to requirements → Closing with call-to-action\n"
                "Avoid clichés ('team player', 'passionate about'). Max 400 words."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}\n\n"
                f"Candidate Profile:\n{candidate_summary}"
            )
            if focus_areas:
                user_msg += f"\n\nFocus especially on: {focus_areas}"

        return await self._llm_call(user_msg, system, temperature=0.72, max_tokens=900, language=language, doc_type="cover_letter")

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
