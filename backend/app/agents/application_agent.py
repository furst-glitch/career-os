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

        writing_brief = input_data.get("writing_brief", "")

        if language == "da":
            system = (
                f"Du er en ekspert ansøgningsskriver med {style_da} tone.\n\n"
                "NØJAGTIGHEDSREGLER (HÅRD BEGRÆNSNING — aldrig overskrid):\n"
                "- Brug KUN fakta, tal og eksempler der kan verificeres i kandidatprofilen\n"
                "- 'bidragede til X' ≠ 'var ansvarlig for X'\n"
                "- Opfind ALDRIG eksempler, beløb, datoer eller resultater\n"
                "- Nedtone eller fjern påstande der ikke kan underbygges\n\n"
                "DANSK ANSØGNINGSSTRUKTUR (4 afsnit — streng rækkefølge):\n\n"
                "Afsnit 1 — HVORFOR DENNE ROLLE (2-3 sætninger):\n"
                "Specifik årsag til ansøgning. Referer til noget konkret fra jobopslaget. Ikke generisk begejstring.\n\n"
                "Afsnit 2 — STÆRKESTE MATCH (3-4 sætninger):\n"
                "Én kompetence med konkret eksempel og verificeret resultat. Inkludér tal, DKK-beløb eller specifikt outcome.\n\n"
                "Afsnit 3 — SEKUNDÆR VÆRDI ELLER GAP (2-3 sætninger):\n"
                "Enten: andet differentierende aspekt CV'et ikke viser fuldt ud.\n"
                "Eller: ærlig anerkendelse af et gap med selvsikkerhed om at bygge bro.\n\n"
                "Afsnit 4 — FREMAD (1-2 sætninger):\n"
                "Selvsikker afslutning. Nævn virksomhedsnavnet specifikt.\n"
                "'Jeg ser frem til en dialog om, hvordan jeg kan bidrage til [VIRKSOMHED].'\n\n"
                "ALDRIG BRUG:\n"
                "- 'Jeg er en struktureret og analytisk person'\n"
                "- 'Jeg brænder for...'\n"
                "- 'Det vil jeg meget gerne bidrage til'\n"
                "- Lister eller bullet points\n"
                "- Mere end 450 ord total\n"
                "- Generiske fraser uden specifik understøttelse\n\n"
                "BRUG ALTID:\n"
                "- Ansættende leders navn hvis det fremgår af jobopslaget\n"
                "- Én specifik reference til jobopslagets indhold\n"
                "- Aktive verber: driver, udarbejder, fremlægger, styrer, sikrer\n"
                "- Selvsikker nutid for nuværende rolle\n\n"
                "Skriv med korrekte danske bogstaver: æ, ø, å, Æ, Ø, Å.\n"
                "Ingen markdown, ingen fed, ingen bullets. Ren tekst i afsnit.\n"
                "Afslut med 'Med venlig hilsen' på separat linje efterfulgt af kandidatens fulde navn."
            )
            candidate_block = candidate_summary
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Jobkrav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"Kandidatprofil (brug KUN disse fakta — opfind intet):\n{candidate_block}"
            )
            if writing_brief:
                user_msg += f"\n\nSkriveguide (følg disse instruktioner præcist):\n{writing_brief}"
            if focus_areas:
                user_msg += f"\n\nFokusér særligt på: {focus_areas}"
        else:
            system = (
                f"You are an expert cover letter writer with a {style_en} tone.\n\n"
                "ACCURACY RULES (HARD CONSTRAINT — never violate):\n"
                "- Use ONLY facts, numbers and examples verifiable in the candidate profile\n"
                "- 'contributed to X' ≠ 'was responsible for X'\n"
                "- NEVER invent examples, amounts, dates or results\n"
                "- Downgrade or remove claims that cannot be substantiated\n\n"
                "COVER LETTER STRUCTURE (4 paragraphs — strict order):\n\n"
                "Paragraph 1 — WHY THIS ROLE (2-3 sentences):\n"
                "Specific reason for applying. Reference something concrete from the job posting. Not generic enthusiasm.\n\n"
                "Paragraph 2 — STRONGEST MATCH (3-4 sentences):\n"
                "Single most relevant competency with concrete example and verified result. Include a number or specific outcome.\n\n"
                "Paragraph 3 — SECONDARY VALUE OR GAP (2-3 sentences):\n"
                "Either: second differentiating angle the CV does not fully show.\n"
                "Or: honest acknowledgment of a gap with confidence about bridging it.\n\n"
                "Paragraph 4 — FORWARD (1-2 sentences):\n"
                "Confident close. Mention company name specifically.\n"
                "'I look forward to discussing how I can contribute to [COMPANY].'\n\n"
                "NEVER USE:\n"
                "- 'I am a structured and analytical person'\n"
                "- 'I am passionate about...'\n"
                "- 'I would very much like to contribute'\n"
                "- Lists or bullet points\n"
                "- More than 450 words total\n"
                "- Generic phrases without specific backing\n\n"
                "ALWAYS USE:\n"
                "- Hiring manager name if available in the job posting\n"
                "- One specific reference to job posting content\n"
                "- Active verbs: drive, develop, present, manage, ensure\n"
                "- Confident present tense for current role\n\n"
                "No markdown, no bold, no bullets. Plain paragraph text.\n"
                "Close with 'Yours sincerely' on a separate line followed by the candidate's full name."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}\n\n"
                f"Candidate Profile (use ONLY these facts — invent nothing):\n{candidate_summary}"
            )
            if writing_brief:
                user_msg += f"\n\nWriting brief (follow these instructions precisely):\n{writing_brief}"
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
        await self.log_usage(usage, operation=self.name, used_user_key=provider.used_user_key)
        return AgentResult(content=content, usage=usage, metadata={"language": language, "doc_type": doc_type})
