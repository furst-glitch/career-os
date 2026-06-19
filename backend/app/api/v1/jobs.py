"""
Jobs API — Sprint 3.1

GET    /jobs                  — list alle jobs (saved_only param)
GET    /jobs/saved            — kun gemte jobs
POST   /jobs                  — tilføj job + beregn match score
GET    /jobs/{id}             — hent job
PUT    /jobs/{id}             — opdater job
DELETE /jobs/{id}             — slet job
POST   /jobs/{id}/save        — toggle is_saved
GET    /jobs/{id}/match       — beregn frisk match score
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.core.deps import get_current_user, get_supabase_admin
from app.services.automation_service import on_job_saved
from app.services.job_service import JobService
from app.services.memory_snapshot_service import MemorySnapshotService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _svc(supabase) -> JobService:
    return JobService(supabase)


def _snapshot(user_id: str, supabase) -> dict:
    """Henter karriere-snapshot til match-beregning. Returnerer tomt dict ved fejl."""
    try:
        return MemorySnapshotService(supabase).snapshot(user_id)
    except Exception:
        return {}


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_jobs(
    saved_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return _svc(supabase).list_jobs(user["id"], saved_only=saved_only, limit=limit)


@router.get("/saved")
async def list_saved_jobs(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return _svc(supabase).list_jobs(user["id"], saved_only=True)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_job(
    body: dict,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = _svc(supabase)
    job = svc.create_job(user["id"], body)

    # Beregn og gem match score i baggrunden (fejler stille)
    try:
        snap = _snapshot(user["id"], supabase)
        if snap:
            result = svc.compute_match_score(job, snap)
            svc.store_match_score(job["id"], result["total"])
            job["match_score"] = result["total"]
            job["match_breakdown"] = result
    except Exception:
        pass

    return job


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{job_id}")
async def get_job(
    job_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    job = _svc(supabase).get_job(job_id, user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job ikke fundet")
    return job


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{job_id}")
async def update_job(
    job_id: str,
    body: dict,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = _svc(supabase)
    job = svc.update_job(job_id, user["id"], body)

    # Genberegn match score hvis beskrivelse/krav ændret
    if any(k in body for k in ("title", "description", "requirements")):
        try:
            snap = _snapshot(user["id"], supabase)
            if snap:
                result = svc.compute_match_score(job, snap)
                svc.store_match_score(job_id, result["total"])
                job["match_score"] = result["total"]
        except Exception:
            pass

    return job


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    _svc(supabase).delete_job(job_id, user["id"])


# ── Save toggle ───────────────────────────────────────────────────────────────

@router.post("/{job_id}/save")
async def toggle_save(
    job_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    try:
        result = _svc(supabase).toggle_save(job_id, user["id"])
        # Auto-create draft pipeline entry when job is saved
        if result.get("is_saved"):
            background_tasks.add_task(on_job_saved, user["id"], job_id, supabase)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Match score ───────────────────────────────────────────────────────────────

@router.get("/{job_id}/match")
async def get_match_score(
    job_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = _svc(supabase)
    job = svc.get_job(job_id, user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job ikke fundet")
    snap = _snapshot(user["id"], supabase)
    result = svc.compute_match_score(job, snap)
    svc.store_match_score(job_id, result["total"])
    return result
