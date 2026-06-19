"""
Discovery Service — AI-drevet karriere-interview.

Flow:
  1. start()          → Opret/hent session
  2. stream_welcome() → Streamer AI-velkomst (første gang)
  3. stream_message() → Streamer AI-svar + ekstraherer facts i baggrunden
  4. _extract_and_save() → Parser svar til strukturerede data, opdaterer profil
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from supabase import Client

from app.providers.litellm_provider import LiteLLMProvider
from app.services.experience_service import ExperienceService

COACH_AGENT = "career_coach_agent"
CV_AGENT = "cv_agent"

# ─── System prompts ───────────────────────────────────────────────────────────

# Bruges når kandidaten allerede har et CV uploadet (profil + gaps kendes).
DISCOVERY_SYSTEM_TEMPLATE = """Du er en erfaren karriererådgiver der interviewer {name} for at afdække hans/hendes komplette karriereprofil.

VIGTIG: Kandidaten har ALLEREDE modtaget en velkomst. Genhils IKKE. Svar direkte på det kandidaten har skrevet og fortsæt interviewet.

HVAD VI ALLEREDE VED:
{profile_summary}

GAPS DER SKAL DÆKKES (prioriteret højest-til-lavest):
{gaps_text}

REGLER FOR INTERVIEWET:
- Stil ÉT præcist, åbent spørgsmål ad gangen — aldrig to spørgsmål i samme svar
- Anerkend svaret i 1 sætning inden næste spørgsmål ("Godt!", "Interessant, tak.")
- Grav dybere ved vage svar: spørg om specifikke tal, tidsramme, teamstørrelse, budget
- Kvantificér ALT: "Hvor mange? Hvilken periode? Hvad var resultatet i tal?"
- Arbejd systematisk igennem gaps fra høj til lav prioritet
- Signalér tydeligt ved emne-skift: "Lad os nu tale om dine projekter..."
- Hold svar under 200 ord

ALDRIG: Generer et CV, en rapport eller en opsummering i chatten. Det sker automatisk bagefter.

AFSLUTNING: Når alle gaps er tilstrækkeligt besvaret, afslut med præcis denne linje:
[INTERVIEW_COMPLETE]
Efterfulgt af en 2-3 sætnings positiv opsummering af interviewet.

Tal dansk og vær coachende og nysgerrig."""

# Bruges når kandidaten IKKE har uploadet CV (tom profil).
FRESH_START_SYSTEM = """Du er en erfaren karriererådgiver der interviewer en kandidat for at bygge hans/hendes karriereprofil fra bunden.

VIGTIG: Kandidaten har ALLEREDE modtaget en velkomst og er klar til at svare. Genhils IKKE. Gå direkte til kandidatens svar og fortsæt derfra.

EMNER DER SKAL DÆKKES (i denne rækkefølge):
1. Nuværende stilling (titel, virksomhed, primære ansvarsområder, team)
2. Konkrete præstationer med tal (hvad skete? hvad var din rolle? hvad var resultatet?)
3. Projekter (navn, din rolle, teknologier, outcome)
4. Systemer og teknologier brugt dagligt
5. Lederskabserfaring (teamstørrelse, direkte rapporterende, ansvarsscope)
6. Uddannelse og certifikater
7. Kompetencer og bløde egenskaber

REGLER FOR INTERVIEWET:
- Stil ÉT præcist, åbent spørgsmål ad gangen — aldrig to spørgsmål i samme svar
- Anerkend svaret i 1 sætning inden næste spørgsmål
- Grav dybere ved vage svar: spørg om specifikke tal, tidsramme, teamstørrelse, budget
- Kvantificér ALT: "Hvor mange? Hvilken periode? Hvad var resultatet i tal?"
- Signalér tydeligt ved emne-skift: "Lad os nu tale om dine projekter..."
- Hold svar under 200 ord

ALDRIG: Generer et CV, en rapport eller en opsummering i chatten. Det sker automatisk bagefter.

AFSLUTNING: Når ALLE 7 emner er tilstrækkeligt afdækket, afslut med præcis denne linje:
[INTERVIEW_COMPLETE]
Efterfulgt af en 2-3 sætnings positiv opsummering af interviewet.

Tal dansk og vær coachende og nysgerrig."""


class DiscoveryService:
    def __init__(self, supabase: Client) -> None:
        self.db = supabase
        self.exp_service = ExperienceService(supabase)

    # ─── Session management ───────────────────────────────────────────────────

    async def start(self, user_id: str, upload_id: str | None = None) -> dict:
        """Opret ny session (eller hent aktiv). Returnerer session_id + beskeder."""
        existing = (
            self.db.table("discovery_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if existing.data and not upload_id:
            session = existing.data[0]
            return {
                "session_id": session["id"],
                "status": "resumed",
                "messages": session.get("messages") or [],
            }

        result = self.db.table("discovery_sessions").insert({
            "user_id": user_id,
            "cv_upload_id": upload_id,
            "session_type": "experience_interview",
            "status": "active",
            "messages": [],
            "gaps_total": 0,
            "gaps_resolved": 0,
        }).execute()
        session_id = result.data[0]["id"]

        return {"session_id": session_id, "status": "created", "messages": []}

    async def stream_welcome(
        self,
        session_id: str,
        user_id: str,
    ) -> AsyncGenerator[str, None]:
        """Stream AI's åbningsbesked. Gemmes i session som FØRSTE besked."""
        session = self.get_session(session_id, user_id)
        if not session:
            yield json.dumps({"type": "error", "content": "Session ikke fundet"})
            return

        if session.get("messages"):
            yield json.dumps({"type": "done"})
            return

        try:
            profile = self._build_profile_summary(user_id)
            gaps = self.exp_service.list_open_gaps(user_id)
            system_prompt = (
                self._build_system_prompt(profile, gaps)
                if (gaps or profile.get("has_content"))
                else FRESH_START_SYSTEM
            )
        except Exception as exc:
            yield json.dumps({"type": "error", "content": f"Fejl ved profilhentning: {exc}"})
            return

        WELCOME_TRIGGER = (
            "Start interviewet med en varm åbningsbesked. "
            "Nævn 2-3 konkrete fund fra CV'et (erfaringer, gaps, projekter). "
            "Stil ét konkret åbningsspørgsmål om den vigtigste manglende information. "
            "Hold det under 120 ord."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": WELCOME_TRIGGER},
        ]

        full_response = ""
        try:
            llm = LiteLLMProvider(user_id)
            response = await llm.complete(
                COACH_AGENT, messages, stream=True, temperature=0.7, max_tokens=400,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_response += delta
                    yield json.dumps({"type": "chunk", "content": delta})
        except Exception as exc:
            yield json.dumps({"type": "error", "content": f"AI fejl: {exc}"})
            return

        # Gem som [user: trigger, assistant: response] for korrekt rolle-rækkefølge
        self.db.table("discovery_sessions").update({
            "messages": [
                {"role": "user", "content": WELCOME_TRIGGER},
                {"role": "assistant", "content": full_response},
            ],
        }).eq("id", session_id).execute()

        yield json.dumps({"type": "done"})

    def get_session(self, session_id: str, user_id: str) -> dict | None:
        result = (
            self.db.table("discovery_sessions")
            .select("*")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def save_exchange(self, session_id: str, user_message: str, ai_response: str) -> None:
        session = self.db.table("discovery_sessions").select("messages").eq("id", session_id).execute()
        messages = session.data[0].get("messages") or []
        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "assistant", "content": ai_response})
        if len(messages) > 60:
            # Behold altid de første 2 (trigger + velkomst) + nyeste 58
            messages = messages[:2] + messages[-58:]
        self.db.table("discovery_sessions").update({"messages": messages}).eq("id", session_id).execute()

    # ─── Streaming chat ───────────────────────────────────────────────────────

    async def stream_message(
        self,
        session_id: str,
        user_message: str,
        user_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        Streamer AI-svar token for token.
        Gemmer udveksling og ekstraher facts i baggrunden.
        Emitter {"type": "done", "interview_complete": true} ved [INTERVIEW_COMPLETE].
        """
        session = self.get_session(session_id, user_id)
        if not session:
            yield json.dumps({"type": "error", "content": "Session ikke fundet"})
            return

        try:
            profile = self._build_profile_summary(user_id)
            gaps = self.exp_service.list_open_gaps(user_id)
            system_prompt = (
                self._build_system_prompt(profile, gaps)
                if (gaps or profile.get("has_content"))
                else FRESH_START_SYSTEM
            )
        except Exception as exc:
            yield json.dumps({"type": "error", "content": f"Fejl ved profilhentning: {exc}"})
            return

        prior_messages = session.get("messages") or []

        # Byg samtalehistorik — behold max 30 seneste beskeder for kontekst
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in prior_messages[-30:]
        ]
        # Anthropic kræver at samtalen starter med 'user'. Hvis historik starter
        # med 'assistant' (fx kun velkomst gemt), indsæt neutral user-besked.
        if history and history[0]["role"] == "assistant":
            history = [{"role": "user", "content": "[SESSION_START]"}] + history

        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ]

        full_response = ""
        try:
            llm = LiteLLMProvider(user_id)
            response = await llm.complete(
                COACH_AGENT, messages, stream=True, temperature=0.7, max_tokens=600,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_response += delta
                    yield json.dumps({"type": "chunk", "content": delta})
        except Exception as exc:
            yield json.dumps({"type": "error", "content": f"AI fejl: {exc}"})
            return

        # Detektér interviewafslutning
        interview_done = "[INTERVIEW_COMPLETE]" in full_response
        clean_response = full_response.replace("[INTERVIEW_COMPLETE]", "").strip()

        # Gem altid den rensede version i DB
        self.save_exchange(session_id, user_message, clean_response)

        if interview_done:
            # Marker session som completed
            self.db.table("discovery_sessions").update(
                {"status": "completed", "profile_complete": True}
            ).eq("id", session_id).execute()

        # Ekstraher facts i baggrunden (uanset om interview er done)
        gap_descriptions = [g["description"] for g in gaps]
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(
                self._extract_and_save(
                    session_id, user_id, user_message, clean_response, gap_descriptions
                )
            )
        except RuntimeError:
            pass  # Ingen event loop — ignorer

        if interview_done:
            yield json.dumps({"type": "done", "interview_complete": True})
        else:
            yield json.dumps({"type": "done"})

    # ─── Fakta-ekstraktion ────────────────────────────────────────────────────

    async def _extract_and_save(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
        ai_response: str,
        open_gap_descriptions: list[str],
    ) -> None:
        """Baggrunds-task: parser én udveksling → opdater profil-tabeller."""
        try:
            from app.agents.cv_agent import CVAgent
            from app.core.deps import get_supabase_admin

            agent = CVAgent(user_id=user_id, supabase=get_supabase_admin())
            facts = await agent.extract_facts(user_message, ai_response, open_gap_descriptions)

            if not facts:
                return

            svc = self.exp_service

            if facts.get("achievements"):
                svc.add_achievements_from_discovery(user_id, facts["achievements"])

            if facts.get("projects"):
                svc.add_projects_from_discovery(user_id, facts["projects"])

            if facts.get("systems"):
                svc.add_systems_from_discovery(user_id, facts["systems"])

            if facts.get("skills"):
                svc.add_skills_from_discovery(user_id, facts["skills"])

            if facts.get("leadership"):
                svc.add_leadership_from_discovery(user_id, facts["leadership"])

            if facts.get("certifications"):
                svc.add_certifications_from_discovery(user_id, facts["certifications"])

            if facts.get("experience_additions"):
                svc.apply_experience_additions(user_id, facts["experience_additions"])

            # Marker løste gaps
            if facts.get("gaps_resolved"):
                all_gaps = svc.list_open_gaps(user_id)
                for resolved_desc in facts["gaps_resolved"]:
                    for gap in all_gaps:
                        if resolved_desc.lower() in gap["description"].lower():
                            svc.resolve_gap(gap["id"])
                            self._increment_gaps_resolved(session_id)

            # Genberegn profilscore
            try:
                from app.services.profile_completeness_service import ProfileCompletenessService
                await ProfileCompletenessService().calculate_and_save(user_id, get_supabase_admin())
            except Exception:
                pass

        except Exception:
            pass  # Baggrunds-ekstraktion fejler stille

    def _increment_gaps_resolved(self, session_id: str) -> None:
        session = (
            self.db.table("discovery_sessions")
            .select("gaps_resolved")
            .eq("id", session_id)
            .execute()
        )
        current = session.data[0]["gaps_resolved"] if session.data else 0
        self.db.table("discovery_sessions").update(
            {"gaps_resolved": current + 1}
        ).eq("id", session_id).execute()

    # ─── Master CV generering ─────────────────────────────────────────────────

    async def generate_master_cv(self, user_id: str) -> AsyncGenerator[str, None]:
        """Streamer et komplet Master CV baseret på kandidatens samlede profil."""
        from app.services.cv_service import CVService

        cv_service = CVService(self.db)
        profile = await cv_service.get_full_profile(user_id)

        if not profile:
            yield json.dumps({"type": "error", "content": "Ingen profil fundet"})
            return

        profile_text = self._profile_to_text(profile)

        GENERATE_CV_SYSTEM = """Du genererer et professionelt Master CV på dansk baseret på kandidatens komplette profil.

FORMAT:
[NAVN]
[Titel] | [Lokation] | [Email] | [Telefon]

── PROFIL ────────────────────────────────────────────────────
[3-4 sætninger der fanger essensen af kandidatens styrker]

── ERFARING ──────────────────────────────────────────────────
[For hvert job, nyeste først:]
[Jobtitel] — [Virksomhed], [Lokation]
[Periode: MMM ÅÅÅÅ – MMM ÅÅÅÅ / nuværende]
• [Præstation med kvantificeret resultat]
• [Præstation]
• [Teknologier brugt]

── PROJEKTER ─────────────────────────────────────────────────
[Kun hvis der er projekter]
[Projektnavn] | [Rolle]
[Kort beskrivelse og outcome]
Teknologier: [liste]

── UDDANNELSE ────────────────────────────────────────────────
[Uddannelse] — [Institution] ([Periode])

── KOMPETENCER ───────────────────────────────────────────────
Tekniske: [kommasepareret liste]
Bløde: [kommasepareret liste]
Sprog: [liste med niveau]

── CERTIFIKATER ──────────────────────────────────────────────
[Navn — Udbyder — År]

── LEDERSKAB ─────────────────────────────────────────────────
[Kun hvis relevant]
[Titel — scope og direkte rapporterende]

Tone: Professionel, aktiv stemme, præcis. Ingen klichéer."""

        messages = [
            {"role": "system", "content": GENERATE_CV_SYSTEM},
            {"role": "user", "content": f"Generer Master CV:\n\n{profile_text}"},
        ]

        full_cv = ""
        llm = LiteLLMProvider(user_id)
        response = await llm.complete(CV_AGENT, messages, stream=True, temperature=0.4, max_tokens=3000)
        async for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_cv += delta
                yield json.dumps({"type": "chunk", "content": delta})

        await cv_service.save_master_cv_content(user_id, full_cv)
        yield json.dumps({"type": "done"})

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _build_profile_summary(self, user_id: str) -> dict:
        mcv_result = self.db.table("master_cvs").select("*").eq("user_id", user_id).execute()
        if not mcv_result.data:
            return {"has_content": False}
        mcv = mcv_result.data[0]
        mcv_id = mcv["id"]

        exps = (
            self.db.table("cv_experiences")
            .select("title, company, period_start, period_end")
            .eq("master_cv_id", mcv_id)
            .order("period_start", desc=True)
            .execute()
            .data
        )
        skills = (
            self.db.table("cv_skills")
            .select("name, category, level")
            .eq("master_cv_id", mcv_id)
            .limit(10)
            .execute()
            .data
        )
        projs = (
            self.db.table("cv_projects")
            .select("name, technologies, outcomes")
            .eq("master_cv_id", mcv_id)
            .execute()
            .data
        )

        return {
            "has_content": bool(exps),
            "name": mcv.get("title", "Kandidat"),
            "target_title": mcv.get("target_title"),
            "summary": mcv.get("summary"),
            "experiences": exps,
            "skills": skills,
            "projects": projs,
        }

    @staticmethod
    def _build_system_prompt(profile: dict, gaps: list[dict]) -> str:
        from app.services.profile_completeness_service import ProfileCompletenessService

        pcs = ProfileCompletenessService()
        scores = pcs.calculate(profile)
        priority_context = pcs.build_priority_context(scores, gaps)

        name = profile.get("target_title") or "kandidaten"
        exps = profile.get("experiences") or []
        exp_lines = "\n".join(
            f"  • {e.get('title')} @ {e.get('company')}" for e in exps[:5]
        )
        skills = profile.get("skills") or []
        skills_str = ", ".join(
            s if isinstance(s, str) else s.get("name", "") for s in skills[:10]
        )

        profile_summary = (
            f"Navn/titel: {name}\n"
            f"Erfaringer:\n{exp_lines or '  (ingen endnu)'}\n"
            f"Kompetencer: {skills_str or '(ingen endnu)'}\n"
            f"Projekter: {len(profile.get('projects') or [])} registrerede\n\n"
            f"{priority_context}"
        )

        return DISCOVERY_SYSTEM_TEMPLATE.format(
            name=name,
            profile_summary=profile_summary,
            gaps_text=priority_context,
        )

    @staticmethod
    def _profile_to_text(profile: dict) -> str:
        sections: list[str] = []
        mcv = profile.get("master_cv") or {}

        if mcv.get("target_title"):
            sections.append(f"TITEL: {mcv['target_title']}")
        if mcv.get("summary"):
            sections.append(f"RESUMÉ: {mcv['summary']}")

        exps = profile.get("experiences") or []
        if exps:
            exp_block = "ERFARING:\n" + "\n".join(
                f"  {e.get('title')} @ {e.get('company')} "
                f"({e.get('period_start', '')}–{e.get('period_end') or 'nu'})\n"
                f"  {e.get('description', '')}\n"
                f"  Præstationer: {'; '.join(e.get('achievements') or [])}\n"
                f"  Teknologier: {', '.join(e.get('technologies') or [])}"
                for e in exps
            )
            sections.append(exp_block)

        edus = profile.get("educations") or []
        if edus:
            edu_block = "UDDANNELSE:\n" + "\n".join(
                f"  {e.get('degree')} — {e.get('institution')} ({e.get('end_date', '')})"
                for e in edus
            )
            sections.append(edu_block)

        skills = profile.get("skills") or []
        if skills:
            by_cat: dict[str, list[str]] = {}
            for s in skills:
                cat = s.get("category", "technical")
                by_cat.setdefault(cat, []).append(s["name"])
            skill_lines = "\n".join(
                f"  {cat}: {', '.join(names)}" for cat, names in by_cat.items()
            )
            sections.append(f"KOMPETENCER:\n{skill_lines}")

        projects = profile.get("projects") or []
        if projects:
            proj_block = "PROJEKTER:\n" + "\n".join(
                f"  {p.get('name')} ({p.get('role', '')}): "
                f"{p.get('description', '')}. Outcome: {p.get('outcomes', '')}"
                for p in projects
            )
            sections.append(proj_block)

        achievements = profile.get("achievements") or []
        if achievements:
            ach_block = "PRÆSTATIONER:\n" + "\n".join(
                f"  [{a.get('impact_level', 'medium').upper()}] "
                f"{a.get('title')}: {a.get('description')} {a.get('metric', '')}"
                for a in achievements
            )
            sections.append(ach_block)

        systems = profile.get("systems") or []
        if systems:
            by_sys_cat: dict[str, list[str]] = {}
            for s in systems:
                cat = s.get("category") or "Andet"
                by_sys_cat.setdefault(cat, []).append(f"{s['name']} ({s.get('proficiency', '')})")
            sys_lines = "\n".join(
                f"  {cat}: {', '.join(names)}" for cat, names in by_sys_cat.items()
            )
            sections.append(f"SYSTEMER:\n{sys_lines}")

        leadership = profile.get("leadership") or []
        if leadership:
            ldr_block = "LEDERSKAB:\n" + "\n".join(
                f"  {ldr.get('title')}: {ldr.get('scope', '')} — "
                f"{ldr.get('direct_reports', 0)} direkte rapporterende"
                for ldr in leadership
            )
            sections.append(ldr_block)

        certs = profile.get("certifications") or []
        if certs:
            cert_block = "CERTIFIKATER:\n" + "\n".join(
                f"  {c.get('name')} — {c.get('issuer', '')} ({c.get('issued_at', '')})"
                for c in certs
            )
            sections.append(cert_block)

        return "\n\n".join(sections)
