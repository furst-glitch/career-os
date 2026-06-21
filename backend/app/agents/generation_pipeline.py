"""
GenerationPipeline — multi-agent dokumentgenerering.

CV Pipeline (CVAgent → ATSAgent → CriticAgent → DesignerAgent → ReviewBoardAgent):
  1. CVAgent.generate()           → udkast CV                       ~25-35s
  2. ATSAgent                     → ATS-feedback på udkast          ~10-15s
  3. CriticAgent                  → top-5 forbedringer              ~8-12s
  4. DesignerAgent                → template-specifik stilguide     ~8-10s
  5. ReviewBoardAgent (rewrite)   → endeligt CV                     ~25-35s
  Estimeret total: ~80-110s  (vs. 25-40s single-call)

Application Pipeline (JobAgent → HRAgent → HiringManagerAgent → ATSAgent
                      → CriticAgent → DesignerAgent → ReviewBoardAgent → ApplicationAgent):
  1. JobAgent                     → jobanalyse                      ~10-15s
  2-4. HRAgent + HMAgent + ATS    → parallelle perspektiver         ~15-25s
  5. CriticAgent                  → must-haves                      ~8-12s
  6. DesignerAgent                → template-specifik stilguide     ~8-10s
  7. ReviewBoardAgent (brief)     → skrivebrief                     ~8-12s
  8. ApplicationAgent             → endelig ansøgning               ~25-35s
  Estimeret total: ~75-110s  (vs. 25-40s single-call)

Template-integration:
  Brugerens valgte template (fra Indstillinger → Layout) sendes som 'template'
  i input_data og bruges af DesignerAgent til at producere template-specifikke
  stilinstruktioner der fodres ind i ReviewBoardAgent / ApplicationAgent.
"""
from __future__ import annotations

import asyncio

from app.agents.application_agent import ApplicationAgent
from app.agents.ats_agent import ATSAgent
from app.agents.critic_agent import CriticAgent
from app.agents.cv_agent import CVAgent
from app.agents.designer_agent import DesignerAgent
from app.agents.hiring_manager_agent import HiringManagerAgent
from app.agents.hr_agent import HRAgent
from app.agents.job_agent import JobAgent
from app.agents.review_board_agent import ReviewBoardAgent


class GenerationPipeline:
    def __init__(self, user_id: str, supabase) -> None:
        self.user_id = user_id
        self.supabase = supabase

    # ── CV Pipeline ───────────────────────────────────────────────────────────

    async def generate_cv(self, input_data: dict, queue: asyncio.Queue | None = None) -> str:
        """
        CVAgent → ATSAgent → CriticAgent → DesignerAgent → ReviewBoardAgent
        Returnerer endeligt CV som JSON-string (structured_cv_v2) eller plaintext string.

        CVAgent returnerer struktureret JSON: {"_structured_cv_v2": true, "cv_text": "...", ...}
        Downstream agenter (ATS, Critic, ReviewBoard) modtager kun cv_text (plain text).
        Strukturelle sektioner (education, competencies, systems, languages) bevares fra CV-agentens
        snapshot-build og gensammensættes EFTER pipeline med den forbedrede cv_text.
        """
        import json as _json

        uid, db = self.user_id, self.supabase
        job_ctx = self._job_ctx(input_data)
        lang = input_data.get("language", "da")
        template = input_data.get("template", "nordic_executive")
        da = lang == "da"

        # Trin 1: CVAgent skriver udkast (returnerer structured JSON eller plain text)
        await self._emit(queue, 5, "Udarbejder CV-udkast..." if da else "Drafting CV...")
        draft_result = await CVAgent(uid, db).generate(input_data)
        draft_raw = draft_result.content

        # Detektér struktureret JSON-format og udtræk cv_text til downstream agenter
        draft_json: dict | None = None
        try:
            parsed = _json.loads(draft_raw)
            if isinstance(parsed, dict) and parsed.get("_structured_cv_v2"):
                draft_json = parsed
                draft_text = parsed.get("cv_text", "")
            else:
                draft_text = draft_raw
        except (ValueError, TypeError):
            draft_text = draft_raw

        # Trin 2: ATSAgent gennemgår kun cv_text (ikke JSON)
        await self._emit(queue, 30, "Analyserer ATS-nøgleord..." if da else "Analyzing ATS keywords...")
        ats_feedback = (await ATSAgent(uid, db).run({
            **job_ctx,
            "draft": draft_text,
            "doc_type": "cv",
        })).content

        # Trin 3: CriticAgent syntetiserer
        await self._emit(queue, 50, "Syntetiserer feedback..." if da else "Synthesizing feedback...")
        improvements = (await CriticAgent(uid, db).run({
            "ats_review": ats_feedback,
            "hr_review": "",
            "hm_review": "",
            "language": lang,
            "doc_type": "cv",
        })).content

        # Trin 4: DesignerAgent producerer template-specifik stilguide
        await self._emit(queue, 65, f"Tilpasser til {template}-template..." if da else f"Applying {template} template...")
        design_guide = (await DesignerAgent(uid, db).run({
            "template": template,
            "doc_type": "cv",
            "language": lang,
            "critic_feedback": improvements,
            "draft": draft_text,
        })).content

        # Trin 5: ReviewBoardAgent omskriver til endeligt CV med stilguide
        await self._emit(queue, 78, "Omskriver til endeligt CV..." if da else "Rewriting to final CV...")
        final_text = (await ReviewBoardAgent(uid, db).run({
            "mode": "rewrite",
            "draft": draft_text,
            "critic_feedback": improvements,
            "design_guide": design_guide,
            **job_ctx,
        })).content

        await self._emit(queue, 95, "Færdiggør..." if da else "Finishing...")

        # Gensammenbyg struktureret JSON med forbedret cv_text fra ReviewBoard
        if draft_json is not None:
            final_structured = {**draft_json, "cv_text": final_text}
            return _json.dumps(final_structured, ensure_ascii=False)
        return final_text

    # ── Application Pipeline ──────────────────────────────────────────────────

    async def generate_application(self, input_data: dict, queue: asyncio.Queue | None = None) -> str:
        """
        JobAgent → HRAgent + HMAgent + ATSAgent → CriticAgent
        → DesignerAgent → ReviewBoardAgent → ApplicationAgent
        Returnerer endelig ansøgning som plaintext string.
        """
        uid, db = self.user_id, self.supabase
        job_ctx = self._job_ctx(input_data)
        lang = input_data.get("language", "da")
        template = input_data.get("template", "corporate")
        da = lang == "da"

        # Trin 1: JobAgent analyserer jobopslaget
        await self._emit(queue, 5, "Analyserer jobopslag..." if da else "Analyzing job posting...")
        job_analysis = (await JobAgent(uid, db).run(job_ctx)).content

        # Trin 2-4: HR, HM og ATS analyserer hvad den ideelle ansøgning skal indeholde (parallelt)
        await self._emit(
            queue, 18,
            "Perspektiverer fra HR, Hiring Manager og ATS..." if da
            else "Gathering HR, HM and ATS perspectives...",
        )
        analyze_draft = (
            "[Endnu intet udkast — identificer hvad den ideelle ansøgning til denne stilling SKAL indeholde]"
            if da else
            "[No draft yet — identify what an ideal application for this role MUST contain]"
        )
        analyze_in = {**job_ctx, "draft": analyze_draft}
        hr_out, hm_out, ats_out = await asyncio.gather(
            HRAgent(uid, db).run(analyze_in),
            HiringManagerAgent(uid, db).run(analyze_in),
            ATSAgent(uid, db).run({**analyze_in, "doc_type": "cover_letter"}),
        )

        # Trin 5: CriticAgent syntetiserer til must-haves
        await self._emit(queue, 45, "Syntetiserer krav..." if da else "Synthesizing requirements...")
        must_haves = (await CriticAgent(uid, db).run({
            "ats_review": ats_out.content,
            "hr_review": hr_out.content,
            "hm_review": hm_out.content,
            "language": lang,
            "doc_type": "cover_letter",
        })).content

        # Trin 6: DesignerAgent producerer template-specifik stilguide
        await self._emit(
            queue, 60,
            f"Tilpasser til {template}-template..." if da else f"Applying {template} template...",
        )
        design_guide = (await DesignerAgent(uid, db).run({
            "template": template,
            "doc_type": "cover_letter",
            "language": lang,
            "critic_feedback": must_haves,
        })).content

        # Trin 7: ReviewBoardAgent producerer skrivebrief
        await self._emit(
            queue, 72,
            "Udformer skriveinstruktioner..." if da else "Preparing writing brief...",
        )
        writing_brief = (await ReviewBoardAgent(uid, db).run({
            "mode": "brief",
            "job_analysis": job_analysis,
            "must_haves": must_haves,
            "design_guide": design_guide,
            **job_ctx,
        })).content

        # Trin 8: ApplicationAgent skriver den endelige ansøgning
        await self._emit(
            queue, 83,
            "Skriver endelig ansøgning..." if da else "Writing final application...",
        )
        final = (await ApplicationAgent(uid, db).run(
            {**input_data, "writing_brief": writing_brief},
            queue=None,
        )).content

        await self._emit(queue, 95, "Færdiggør..." if da else "Finishing...")
        return final

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _job_ctx(data: dict) -> dict:
        return {
            "job_title": data.get("job_title", ""),
            "job_company": data.get("job_company", ""),
            "job_description": data.get("job_description", ""),
            "job_requirements": data.get("job_requirements", []),
            "language": data.get("language", "da"),
        }

    @staticmethod
    async def _emit(queue: asyncio.Queue | None, pct: int, msg: str) -> None:
        if queue is not None:
            await queue.put(("progress", {"step": "pipeline", "pct": pct, "msg": msg}))
