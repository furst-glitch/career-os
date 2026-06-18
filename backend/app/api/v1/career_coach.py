"""
Career Coach API

POST /career-coach/analyze     - Komplet karriereanalyse
POST /career-coach/skills-gap  - Kompetencegab-analyse
POST /career-coach/career-path - Karrierevej-analyse
POST /career-coach/next-steps  - Næste skridt (30 dage)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.career_coach_agent import CareerCoachAgent
from app.core.deps import get_current_user, get_supabase_admin
from app.providers.litellm_provider import NoProviderKeyError
from app.services.memory_snapshot_service import MemorySnapshotService

router = APIRouter(prefix="/career-coach", tags=["Career Coach"])


class CoachRequest(BaseModel):
    analysis_type: str = "full"
    question: str | None = None
    target_role: str | None = None
    language: str = "da"


async def _run_analysis(
    analysis_type: str,
    user: dict,
    supabase,
    question: str | None = None,
    target_role: str | None = None,
    language: str = "da",
) -> dict:
    snapshot_svc = MemorySnapshotService(supabase)
    snapshot = snapshot_svc.snapshot(user["id"])
    text_summary = snapshot.get("text_summary", "")

    if not text_summary.strip():
        raise HTTPException(
            422,
            "Din karriereprofil er tom — upload dit CV og udfyld din profil først.",
        )

    agent = CareerCoachAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run({
            "snapshot_text": text_summary,
            "question": question or "",
            "analysis_type": analysis_type,
            "language": language,
            "target_role": target_role or "",
        })
    except NoProviderKeyError as exc:
        raise HTTPException(
            402,
            detail={
                "error": "no_api_key",
                "message": str(exc),
                "action": "Tilføj din API-nøgle under Indstillinger → API-nøgler",
            },
        )
    except Exception as exc:
        raise HTTPException(500, f"Analyse fejlede: {exc}")

    return {
        "content": result.content,
        "analysis_type": analysis_type,
        "language": language,
        "profile_summary": {
            "target_title": (snapshot.get("profile") or {}).get("target_title"),
            "skills_count": len(snapshot.get("skills") or []),
            "experience_count": len(snapshot.get("experience") or []),
            "goals_count": len(snapshot.get("goals") or []),
        },
    }


@router.post("/analyze")
async def analyze(
    body: CoachRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return await _run_analysis(
        analysis_type=body.analysis_type,
        user=user,
        supabase=supabase,
        question=body.question,
        target_role=body.target_role,
        language=body.language,
    )


@router.post("/skills-gap")
async def skills_gap(
    body: CoachRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return await _run_analysis("skills_gap", user, supabase, body.question, body.target_role, body.language)


@router.post("/career-path")
async def career_path(
    body: CoachRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return await _run_analysis("career_path", user, supabase, body.question, body.target_role, body.language)


@router.post("/next-steps")
async def next_steps(
    body: CoachRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return await _run_analysis("next_steps", user, supabase, body.question, body.target_role, body.language)
