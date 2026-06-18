"""
Discovery Service — AI-drevet karriere-interview.

Flow:
  1. start()          → Opret session + returnér første AI-velkomst
  2. stream_message() → Async generator der streamer AI-svar token for token
  3. extract_*()      → Ekstraher strukturerede facts og opdater profil (baggrund)
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

import litellm
from supabase import Client

from app.services.experience_service import ExperienceService

DISCOVERY_MODEL = "gpt-4o"

DISCOVERY_SYSTEM_TEMPLATE = """Du er en erfaren karriererådgiver der hjælper {name} med at afdække sin fulde karriereprofil.

HVAD VI VED FRA CV:
{profile_summary}

ÅBNE GAPS DER SKAL DÆKKES (prioriteret):
{gaps_text}

REGLER:
- Stil ét præcist, åbent spørgsmål ad gangen
- Arbejd dig igennem gaps fra høj til lav prioritet
- Grav dybere når du hører om præstationer: "Hvad var dit specifikke bidrag?", "Hvilke tal kan du sætte på?", "Hvad skete der efterfølgende?"
- Kvantificér ALT: tal, procenter, tidsramme, teamstørrelse, budget
- Anerkend svar positivt inden næste spørgsmål
- Signalér tydeligt ved emne-skift: "Lad os nu tale om..."
- Når alle gaps er dækket: "Vi har nu en stærk profil. Er du klar til at generere dit Master CV?"

Du er coachende, nysgerrig og professionel. Tal dansk medmindre kandidaten skifter til engelsk."""

FRESH_START_SYSTEM = """Du er en erfaren karriererådgiver der hjælper en kandidat med at opbygge sin karriereprofil fra bunden.

Du skal systematisk afdække:
1. Nuværende og tidligere stillinger (titel, virksomhed, periode, ansvarsområder)
2. Konkrete præstationer og resultater (med tal og procenter)
3. Projekter (navn, rolle, teknologier, outcome)
4. Systemer og teknologier der bruges dagligt
5. Lederskabserfaring
6. Uddannelse og certifikater
7. Kompetencer (tekniske og bløde)

Regler:
- Start med at hilse og spørge til nuværende stilling
- Stil ét spørgsmål ad gangen
- Grav dybere efter hvert svar
- Kvantificér alt
- Afslut med Master CV-forslag

Tal dansk og coachende."""

GENERATE_CV_SYSTEM = """Du genererer et professionelt Master CV på dansk baseret på kandidatens komplette profil.

FORMAT:
[NAVN]
[Titel] | [Lokation] | [Email] | [Telefon]
[LinkedIn URL]

── PROFIL ─────────────────────────────────────────────
[3-4 sætninger der fanger essensen af kandidatens styrker og erfaring]

── ERFARING ───────────────────────────────────────────
[For hvert job, nyeste først:]
[Jobtitel] — [Virksomhed], [Lokation]
[Periode: MMM ÅÅÅÅ – MMM ÅÅÅÅ / nuværende]
• [Præstation/ansvar med kvantificeret resultat]
• [Præstation/ansvar]
• [Teknologier brugt]

── PROJEKTER ──────────────────────────────────────────
[Kun hvis der er projekter:]
[Projektnavn] | [Rolle]
[Kort beskrivelse og outcome]
Teknologier: [liste]

── UDDANNELSE ─────────────────────────────────────────
[Uddannelse] — [Institution]
[Periode]

── KOMPETENCER ────────────────────────────────────────
Tekniske: [kommasepareret liste]
Bløde: [kommasepareret liste]
Sprog: [liste med niveau]

── SYSTEMER & TEKNOLOGIER ─────────────────────────────
[Kategoriseret liste: Cloud, CRM, ERP, DevOps, etc.]

── LEDERSKAB ──────────────────────────────────────────
[Kun hvis relevant:]
[Tittel — scope og direkte rapporterende]

── CERTIFIKATER ───────────────────────────────────────
[Navn — Udbyder — År]

Tone: Professionel, aktiv stemme, præcis. Undgå klichéer som "resultatorienteret" og "teamplayer"."""


class DiscoveryService:
    def __init__(self, supabase: Client) -> None:
        self.db = supabase
        self.exp_service = ExperienceService(supabase)

    # ─── Session management ───────────────────────────────────────────────────

    async def start(self, user_id: str, upload_id: str | None = None) -> dict:
        """Opret ny session (eller hent aktiv). Returnerer session_id + beskeder."""
        # Tjek for eksisterende aktiv session
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

        # Opret ny session
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
        """Stream AI's åbningsbesked. Gemmer KUN AI-svaret (ikke en user-besked)."""
        session = self.get_session(session_id, user_id)
        if not session:
            yield json.dumps({"type": "error", "content": "Session ikke fundet"})
            return

        # Allerede har beskeder — ingen grund til ny velkomst
        if session.get("messages"):
            yield json.dumps({"type": "done"})
            return

        profile = self._build_profile_summary(user_id)
        gaps = self.exp_service.list_open_gaps(user_id)

        if gaps or profile.get("has_content"):
            system_prompt = self._build_system_prompt(profile, gaps)
        else:
            system_prompt = FRESH_START_SYSTEM

        WELCOME_TRIGGER = (
            "Start interviewet med en varm, professionel velkomst. "
            "Nævn kort 2-3 vigtige fund fra CV'et, og hvad du gerne vil afdække. "
            "Stil ét konkret åbningsspørgsmål. Hold det under 150 ord."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": WELCOME_TRIGGER},
        ]

        full_response = ""
        try:
            response = await litellm.acompletion(
                model=DISCOVERY_MODEL,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=400,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_response += delta
                    yield json.dumps({"type": "chunk", "content": delta})
        except Exception as exc:
            yield json.dumps({"type": "error", "content": f"AI fejl: {exc}"})
            return

        # Gem KUN AI-svaret (velkomsten er ikke et svar på brugerens besked)
        session_data = self.db.table("discovery_sessions").select("messages").eq("id", session_id).execute()
        existing = session_data.data[0].get("messages") or []
        existing.append({"role": "assistant", "content": full_response})
        self.db.table("discovery_sessions").update({"messages": existing}).eq("id", session_id).execute()

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
        # Behold max 40 beskeder (20 udvekslinger)
        if len(messages) > 40:
            messages = messages[-40:]
        self.db.table("discovery_sessions").update({"messages": messages}).eq("id", session_id).execute()

    # ─── Streaming chat ───────────────────────────────────────────────────────

    async def stream_message(
        self,
        session_id: str,
        user_message: str,
        user_id: str,
    ) -> AsyncGenerator[str, None]:
        """Async generator: streamer AI-svar token for token.
        Gemmer udveksling og trigger faktaekstraktion i baggrunden.
        """
        session = self.get_session(session_id, user_id)
        if not session:
            yield json.dumps({"type": "error", "content": "Session ikke fundet"})
            return

        profile = self._build_profile_summary(user_id)
        gaps = self.exp_service.list_open_gaps(user_id)

        # Byg system prompt baseret på om der er en profil
        if gaps or profile.get("has_content"):
            system_prompt = self._build_system_prompt(profile, gaps)
        else:
            system_prompt = FRESH_START_SYSTEM

        prior_messages = session.get("messages") or []
        messages = [
            {"role": "system", "content": system_prompt},
            *[{"role": m["role"], "content": m["content"]} for m in prior_messages[-30:]],
            {"role": "user", "content": user_message},
        ]

        full_response = ""
        try:
            response = await litellm.acompletion(
                model=DISCOVERY_MODEL,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=1024,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_response += delta
                    yield json.dumps({"type": "chunk", "content": delta})
        except Exception as exc:
            yield json.dumps({"type": "error", "content": f"AI fejl: {exc}"})
            return

        # Gem udveksling synkront (ikke blocking for client)
        self.save_exchange(session_id, user_message, full_response)

        # Ekstraher facts i baggrunden
        gap_descriptions = [g["description"] for g in gaps]
        asyncio.create_task(
            self._extract_and_save(session_id, user_id, user_message, full_response, gap_descriptions)
        )

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
        """Baggrunds-task: Ekstraher facts og opdater profil."""
        try:
            from app.agents.cv_agent import CVAgent
            from app.core.deps import get_supabase_admin

            agent = CVAgent(user_id=user_id, supabase=get_supabase_admin())
            facts = await agent.extract_facts(user_message, ai_response, open_gap_descriptions)

            if not facts:
                return

            # Opdater profil-tabeller
            if facts.get("achievements"):
                self.exp_service.add_achievements_from_discovery(user_id, facts["achievements"])
            if facts.get("projects"):
                self.exp_service.add_projects_from_discovery(user_id, facts["projects"])
            if facts.get("systems"):
                self.exp_service.add_systems_from_discovery(user_id, facts["systems"])
            if facts.get("skills"):
                self.exp_service.add_skills_from_discovery(user_id, facts["skills"])
            if facts.get("leadership"):
                self.exp_service.add_leadership_from_discovery(user_id, facts["leadership"])

            # Marker løste gaps
            if facts.get("gaps_resolved"):
                all_gaps = self.exp_service.list_open_gaps(user_id)
                for resolved_desc in facts["gaps_resolved"]:
                    for gap in all_gaps:
                        if resolved_desc.lower() in gap["description"].lower():
                            self.exp_service.resolve_gap(gap["id"])
                            self._increment_gaps_resolved(session_id)

            # Recalculate completeness score efter profil-opdatering
            try:
                from app.services.profile_completeness_service import ProfileCompletenessService
                await ProfileCompletenessService().calculate_and_save(user_id, self.db)
            except Exception:
                pass

        except Exception:
            pass  # Baggrunds-ekstraktion fejler stilstående

    def _increment_gaps_resolved(self, session_id: str) -> None:
        session = self.db.table("discovery_sessions").select("gaps_resolved").eq("id", session_id).execute()
        current = session.data[0]["gaps_resolved"] if session.data else 0
        self.db.table("discovery_sessions").update({"gaps_resolved": current + 1}).eq("id", session_id).execute()

    # ─── Master CV generering ─────────────────────────────────────────────────

    async def generate_master_cv(self, user_id: str) -> AsyncGenerator[str, None]:
        """Streamer et komplet Master CV baseret på kandidatens profil."""
        from app.services.cv_service import CVService
        cv_service = CVService(self.db)
        profile = await cv_service.get_full_profile(user_id)

        if not profile:
            yield json.dumps({"type": "error", "content": "Ingen profil fundet"})
            return

        profile_text = self._profile_to_text(profile)
        messages = [
            {"role": "system", "content": GENERATE_CV_SYSTEM},
            {"role": "user", "content": f"Generer Master CV for denne kandidat:\n\n{profile_text}"},
        ]

        full_cv = ""
        response = await litellm.acompletion(
            model=DISCOVERY_MODEL,
            messages=messages,
            stream=True,
            temperature=0.4,
            max_tokens=3000,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_cv += delta
                yield json.dumps({"type": "chunk", "content": delta})

        # Gem det genererede CV
        await cv_service.save_master_cv_content(user_id, full_cv)
        yield json.dumps({"type": "done"})

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _build_profile_summary(self, user_id: str) -> dict:
        mcv_result = self.db.table("master_cvs").select("*").eq("user_id", user_id).execute()
        if not mcv_result.data:
            return {"has_content": False}
        mcv = mcv_result.data[0]
        mcv_id = mcv["id"]

        exps = self.db.table("cv_experiences").select("title, company, period_start, period_end").eq("master_cv_id", mcv_id).order("period_start", desc=True).execute().data
        skills = self.db.table("cv_skills").select("name").eq("master_cv_id", mcv_id).limit(10).execute().data
        projs = self.db.table("cv_projects").select("name").eq("master_cv_id", mcv_id).execute().data

        return {
            "has_content": bool(exps),
            "name": mcv.get("title", "Kandidat"),
            "target_title": mcv.get("target_title"),
            "summary": mcv.get("summary"),
            "experiences": exps,
            "skills": [s["name"] for s in skills],
            "projects": [p["name"] for p in projs],
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
            f"  • {e.get('title')} @ {e.get('company')}"
            for e in exps[:5]
        )
        skills = profile.get("skills") or []
        # _build_profile_summary returnerer skills som en liste af strings
        skills_str = ", ".join(
            s if isinstance(s, str) else s.get("name", "")
            for s in skills[:10]
        )

        profile_summary = (
            f"Navn/titel: {name}\n"
            f"Erfaringer:\n{exp_lines or '  (ingen endnu)'}\n"
            f"Kompetencer: {skills_str or '(ingen endnu)'}\n"
            f"Projekter: {len(profile.get('projects') or [])} registrerede\n\n"
            f"{priority_context}"
        )

        # Brug score-sorterede gaps (allerede i priority_context) men send rå gaps
        # så agenten kan formulere naturlige spørgsmål om dem
        gaps_text = priority_context  # Indeholder allerede sorterede gaps

        return DISCOVERY_SYSTEM_TEMPLATE.format(
            name=name,
            profile_summary=profile_summary,
            gaps_text=gaps_text,
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
                f"  {e.get('title')} @ {e.get('company')} ({e.get('period_start', '')}–{e.get('period_end') or 'nu'})\n"
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
            skill_lines = "\n".join(f"  {cat}: {', '.join(names)}" for cat, names in by_cat.items())
            sections.append(f"KOMPETENCER:\n{skill_lines}")

        projects = profile.get("projects") or []
        if projects:
            proj_block = "PROJEKTER:\n" + "\n".join(
                f"  {p.get('name')} ({p.get('role', '')}): {p.get('description', '')}. Outcome: {p.get('outcomes', '')}"
                for p in projects
            )
            sections.append(proj_block)

        achievements = profile.get("achievements") or []
        if achievements:
            ach_block = "PRÆSTATIONER:\n" + "\n".join(
                f"  [{a.get('impact_level', 'medium').upper()}] {a.get('title')}: {a.get('description')} {a.get('metric', '')}"
                for a in achievements
            )
            sections.append(ach_block)

        systems = profile.get("systems") or []
        if systems:
            by_sys_cat: dict[str, list[str]] = {}
            for s in systems:
                cat = s.get("category") or "Andet"
                by_sys_cat.setdefault(cat, []).append(f"{s['name']} ({s.get('proficiency', '')})")
            sys_lines = "\n".join(f"  {cat}: {', '.join(names)}" for cat, names in by_sys_cat.items())
            sections.append(f"SYSTEMER:\n{sys_lines}")

        leadership = profile.get("leadership") or []
        if leadership:
            ldr_block = "LEDERSKAB:\n" + "\n".join(
                f"  {l.get('title')}: {l.get('scope', '')} — {l.get('direct_reports', 0)} direkte rapporterende"
                for l in leadership
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
