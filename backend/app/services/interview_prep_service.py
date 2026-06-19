"""
Interview Preparation Service

Genererer komplet interviewforberedelse når en ansøgning får status samtale_1 eller samtale_2.

Indhold:
  - Virksomhedsanalyse
  - Jobanalyse og nøglekompetencer
  - Interviewguide med typiske spørgsmål
  - STAR-eksempler fra kandidatens baggrund
  - Elevator pitch
  - Mulige spørgsmål til interviewer
  - Lønindsigt
  - Mock interview-tips
"""
from __future__ import annotations

import logging

from supabase import Client

logger = logging.getLogger(__name__)

INTERVIEW_SYSTEM = """Du er en ekspert interviewcoach og karriererådgiver.
Du hjælper kandidater med at forberede sig til jobsamtaler.

Generer en KOMPLET interviewforberedelse på dansk baseret på jobbet og kandidatens profil.

FORMAT (brug disse præcis overskrifter med ##):

## Virksomhedsanalyse
[Hvad virksomheden laver, kultur, værdier, størrelse, konkurrenter — basér på jobbeskrivelsen]

## Jobanalyse
[Nøglekompetencer jobbet kræver, teknologier, senioritet, teamstruktur]

## De 10 mest sandsynlige spørgsmål
[Nummererede spørgsmål baseret på jobkravene]

## Dine STAR-svar
[3-4 konkrete STAR-eksempler fra kandidatens baggrund tilpasset dette job]
Format: **Situation** → **Task** → **Action** → **Result**

## Din elevator pitch (60 sekunder)
[Færdigt script tilpasset denne stilling]

## Spørgsmål du bør stille
[8-10 intelligente spørgsmål der viser interesse og indsigt]

## Lønindsigt
[Estimat baseret på stilling, niveau og marked — brug kandidatens erfaring]

## Mock interview — hurtig forberedelse
[3 praktiske øvelser kandidaten kan gøre inden samtalen]

## Dagens fokuspunkter
[3 bullets: hvad der er vigtigst at kommunikere til DETTE job]

Vær konkret, personlig og direkte. Brug kandidatens faktiske erfaring i STAR-eksemplerne."""


async def generate_interview_prep(
    user_id: str,
    pipeline_id: str,
    interview_status: str,
    supabase: Client,
) -> str:
    """
    Genererer interviewforberedelse og gemmer i interview_prep tabel.
    Returnerer det genererede indhold som string.
    """
    from app.providers.litellm_provider import LiteLLMProvider
    from app.services.memory_snapshot_service import MemorySnapshotService

    try:
        # Hent pipeline + job data
        pipeline_result = (
            supabase.table("application_pipeline")
            .select("*, jobs(*)")
            .eq("id", pipeline_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not pipeline_result.data:
            logger.warning("Interview prep: pipeline %s ikke fundet", pipeline_id)
            return ""

        pipeline = pipeline_result.data[0]
        job = pipeline.get("jobs") or {}

        # Hent kandidat-snapshot
        snapshot = MemorySnapshotService(supabase).snapshot(user_id)
        candidate_summary = snapshot.get("text_summary", "")

        job_title = job.get("title", "Ukendt stilling")
        company = job.get("company", "Ukendt virksomhed")
        description = (job.get("description") or "")[:4000]
        requirements = job.get("requirements") or []
        req_text = "\n".join(f"- {r}" for r in requirements[:20]) if requirements else "Ikke angivet"

        round_label = "første samtale" if interview_status == "samtale_1" else "anden samtale / dybdeinterview"

        user_msg = (
            f"STILLING: {job_title} hos {company}\n"
            f"SAMTALERUNDE: {round_label}\n\n"
            f"JOBKRAV:\n{req_text}\n\n"
            f"JOBBESKRIVELSE:\n{description}\n\n"
            f"KANDIDATPROFIL:\n{candidate_summary or 'Ingen profil tilgængelig endnu.'}"
        )

        llm = LiteLLMProvider(user_id)
        response = await llm.complete(
            agent_name="career_coach_agent",
            messages=[
                {"role": "system", "content": INTERVIEW_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            stream=False,
            temperature=0.6,
            max_tokens=3000,
        )
        content = response.choices[0].message.content or ""

        # Gem i DB (upsert så gen-trigger overskriver)
        supabase.table("interview_prep").upsert(
            {
                "pipeline_id": pipeline_id,
                "user_id": user_id,
                "status": interview_status,
                "content": content,
            },
            on_conflict="pipeline_id,status",
        ).execute()

        logger.info("Interview prep genereret for pipeline %s (%s)", pipeline_id, interview_status)
        return content

    except Exception as exc:
        logger.error("Interview prep fejl for pipeline %s: %s", pipeline_id, exc)
        return ""
