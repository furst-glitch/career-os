"""
Profile API — CRUD for alle kandidatprofil-sektioner + Completeness Score.

GET/POST  /profile/experiences
PUT/DEL   /profile/experiences/{id}
GET/POST  /profile/projects
PUT/DEL   /profile/projects/{id}
GET/POST  /profile/achievements
PUT/DEL   /profile/achievements/{id}
GET/POST  /profile/systems
PUT/DEL   /profile/systems/{id}
GET/POST  /profile/skills
PUT/DEL   /profile/skills/{id}
GET/POST  /profile/leadership
PUT/DEL   /profile/leadership/{id}
GET/POST  /profile/certifications
PUT/DEL   /profile/certifications/{id}
GET       /profile/gaps
GET       /profile/score
POST      /profile/score/recalculate
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, get_supabase_admin
from app.services.experience_service import ExperienceService
from app.services.profile_completeness_service import ProfileCompletenessService

router = APIRouter(prefix="/profile", tags=["Kandidatprofil"])


def _svc(supabase) -> ExperienceService:
    return ExperienceService(supabase)


# ── Educations ────────────────────────────────────────────────────────────────

@router.get("/educations")
async def list_educations(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_educations(user["id"])


@router.post("/educations", status_code=201)
async def create_education(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_education(user["id"], body)


@router.put("/educations/{education_id}")
async def update_education(education_id: str, body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).update_education(education_id, body)


@router.delete("/educations/{education_id}", status_code=204)
async def delete_education(education_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_education(education_id)


# ── Experiences ──────────────────────────────────────────────────────────────

@router.get("/experiences")
async def list_experiences(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_experiences(user["id"])


@router.post("/experiences", status_code=201)
async def create_experience(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_experience(user["id"], body)


@router.put("/experiences/{experience_id}")
async def update_experience(experience_id: str, body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).update_experience(experience_id, body)


@router.delete("/experiences/{experience_id}", status_code=204)
async def delete_experience(experience_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_experience(experience_id)


# ── Projects ─────────────────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_projects(user["id"])


@router.post("/projects", status_code=201)
async def create_project(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_project(user["id"], body)


@router.put("/projects/{project_id}")
async def update_project(project_id: str, body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).update_project(project_id, body)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_project(project_id)


# ── Achievements ──────────────────────────────────────────────────────────────

@router.get("/achievements")
async def list_achievements(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_achievements(user["id"])


@router.post("/achievements", status_code=201)
async def create_achievement(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_achievement(user["id"], body)


@router.put("/achievements/{achievement_id}")
async def update_achievement(achievement_id: str, body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).update_achievement(achievement_id, body)


@router.delete("/achievements/{achievement_id}", status_code=204)
async def delete_achievement(achievement_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_achievement(achievement_id)


# ── Systems ───────────────────────────────────────────────────────────────────

@router.get("/systems")
async def list_systems(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_systems(user["id"])


@router.post("/systems", status_code=201)
async def create_system(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_system(user["id"], body)


@router.put("/systems/{system_id}")
async def update_system(system_id: str, body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).update_system(system_id, body)


@router.delete("/systems/{system_id}", status_code=204)
async def delete_system(system_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_system(system_id)


# ── Skills ───────────────────────────────────────────────────────────────────

@router.get("/skills")
async def list_skills(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_skills(user["id"])


@router.post("/skills", status_code=201)
async def create_skill(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_skill(user["id"], body)


@router.put("/skills/{skill_id}")
async def update_skill(skill_id: str, body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).update_skill(skill_id, body)


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_skill(skill_id)


# ── Leadership ────────────────────────────────────────────────────────────────

@router.get("/leadership")
async def list_leadership(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_leadership(user["id"])


@router.post("/leadership", status_code=201)
async def create_leadership(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_leadership(user["id"], body)


@router.put("/leadership/{leadership_id}")
async def update_leadership(leadership_id: str, body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).update_leadership(leadership_id, body)


@router.delete("/leadership/{leadership_id}", status_code=204)
async def delete_leadership(leadership_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_leadership(leadership_id)


# ── Certifications ────────────────────────────────────────────────────────────

@router.get("/certifications")
async def list_certifications(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_certifications(user["id"])


@router.post("/certifications", status_code=201)
async def create_certification(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_certification(user["id"], body)


@router.put("/certifications/{cert_id}")
async def update_certification(cert_id: str, body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).update_certification(cert_id, body)


@router.delete("/certifications/{cert_id}", status_code=204)
async def delete_certification(cert_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_certification(cert_id)


# ── Gaps ──────────────────────────────────────────────────────────────────────

@router.get("/gaps")
async def list_gaps(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    """Returnerer åbne gaps sorteret efter prioritet."""
    return _svc(supabase).list_open_gaps(user["id"])


# ── Completeness Score ────────────────────────────────────────────────────────

@router.get("/score")
async def get_score(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    """
    Hent senest beregnede profil-score fra databasen.
    Returnerer score pr. sektion, samlet score og manglende områder.
    Returnerer 404 hvis score endnu ikke er beregnet — kald /score/recalculate.
    """
    pcs = ProfileCompletenessService()
    stored = pcs.get_stored(user["id"], supabase)
    if not stored:
        raise HTTPException(
            404,
            "Ingen score endnu — kald POST /profile/score/recalculate for at beregne.",
        )
    return {
        "overall": stored["overall"],
        "sections": {
            "experiences":    stored["experiences"],
            "achievements":   stored["achievements"],
            "projects":       stored["projects"],
            "systems":        stored["systems"],
            "leadership":     stored["leadership"],
            "certifications": stored["certifications"],
            "skills":         stored["skills"],
        },
        "missing_areas": stored["missing_areas"],
        "calculated_at": stored["calculated_at"],
    }


@router.post("/score/recalculate")
async def recalculate_score(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Beregn profil-fuldstændighed nu og gem i databasen.
    Returnerer øjeblikkelig score uden at kræve en reload.
    """
    pcs = ProfileCompletenessService()
    result = await pcs.calculate_and_save(user["id"], supabase)
    return {
        "overall": result["overall"],
        "sections": result["sections"],
        "missing_areas": result["missing_areas"],
    }
