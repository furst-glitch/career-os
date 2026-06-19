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
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.services.automation_service import on_job_saved
from app.services.cache_service import TTL_MATCH, get_cache, key_match
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
    cache = get_cache()
    ck = key_match(user["id"], job_id)

    cached = await cache.get(ck)
    if cached:
        return cached

    svc = _svc(supabase)
    job = svc.get_job(job_id, user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job ikke fundet")
    snap = _snapshot(user["id"], supabase)
    result = svc.compute_match_score(job, snap)
    svc.store_match_score(job_id, result["total"])
    await cache.set(ck, result, ttl=TTL_MATCH)
    return result


# ── Quick Generate (CV eller ansøgning direkte fra job-card) ──────────────────

class QuickGenRequest(BaseModel):
    doc_type: str = "cover_letter"  # "cover_letter" | "cv"
    language: str = "da"
    writing_style: str = "professional"
    focus_areas: str | None = None


@router.post("/{job_id}/quickgen")
async def quickgen(
    job_id: str,
    body: QuickGenRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Generer et dokument (CV eller ansøgning) direkte fra et job-kort.
    Returnerer SSE-stream med keep-alive pings og et enkelt 'done'-event til sidst.

    SSE events:
      : ping                                    (keep-alive mens AI tænker)
      data: {"type": "done",   "document_id": ..., "content": ..., ...}
      data: {"type": "error",  "message": ..., "code"?: "no_api_key"}
    """
    import asyncio
    import json as _json

    from fastapi.responses import StreamingResponse

    from app.agents.generation_pipeline import GenerationPipeline
    from app.providers.litellm_provider import NoProviderKeyError
    from app.services.application_service import ApplicationService

    if body.doc_type not in ("cover_letter", "cv"):
        raise HTTPException(400, "doc_type skal være 'cover_letter' eller 'cv'")

    svc = _svc(supabase)
    job = svc.get_job(job_id, user["id"])
    if not job:
        raise HTTPException(404, "Job ikke fundet")

    app_svc = ApplicationService(supabase)
    pipeline_id = job.get("pipeline_id")
    if not pipeline_id:
        new_entry = app_svc.create_pipeline(user["id"], job_id, {"status": "gemt", "priority": "medium"})
        pipeline_id = new_entry["id"]

    snapshot = _snapshot(user["id"], supabase)
    candidate_summary = snapshot.get("text_summary", "")

    is_cv = body.doc_type == "cv"
    new_status = "cv_genereret" if is_cv else "ansoegning_genereret"
    title = (
        f"CV — {job.get('title')} hos {job.get('company')}"
        if is_cv
        else f"Ansøgning — {job.get('title')} hos {job.get('company')}"
    )

    # Hent brugerens valgte template fra Indstillinger → Layout
    try:
        prefs_row = supabase.table("user_profiles").select(
            "default_cv_template, default_app_template"
        ).eq("user_id", user["id"]).limit(1).execute()
        prefs = prefs_row.data[0] if prefs_row.data else {}
    except Exception:
        prefs = {}
    user_template = prefs.get("default_cv_template" if is_cv else "default_app_template") or (
        "ats_professional" if is_cv else "corporate"
    )

    async def process():
        queue: asyncio.Queue = asyncio.Queue()

        async def run_agent():
            try:
                pipeline = GenerationPipeline(user_id=user["id"], supabase=supabase)
                full_desc = job.get("full_description") or job.get("description") or ""
                gen_input = {
                    "job_title": job.get("title", ""),
                    "job_company": job.get("company", ""),
                    "job_description": full_desc,
                    "job_requirements": job.get("requirements", []),
                    "candidate_summary": candidate_summary,
                    "language": body.language,
                    "writing_style": body.writing_style,
                    "focus_areas": body.focus_areas,
                    "doc_type": body.doc_type,
                    "template": user_template,
                }
                if is_cv:
                    content = await pipeline.generate_cv(gen_input, queue=queue)
                else:
                    content = await pipeline.generate_application(gen_input, queue=queue)
                from app.agents.base import AgentResult, AgentUsage
                await queue.put(("ok", AgentResult(content=content, usage=AgentUsage())))
            except NoProviderKeyError as exc:
                await queue.put(("no_key", str(exc)))
            except Exception as exc:
                await queue.put(("err", str(exc)))

        task = asyncio.create_task(run_agent())
        result = None
        while True:
            try:
                kind, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                if kind == "progress":
                    yield f"data: {_json.dumps({'type': 'progress', **payload})}\n\n"
                    continue
                elif kind == "ok":
                    result = payload
                elif kind == "no_key":
                    yield f"data: {_json.dumps({'type': 'error', 'code': 'no_api_key', 'message': payload})}\n\n"
                    task.cancel()
                    return
                else:
                    yield f"data: {_json.dumps({'type': 'error', 'message': f'AI fejlede: {payload}'})}\n\n"
                    task.cancel()
                    return
                break
            except TimeoutError:
                yield ": ping\n\n"

        try:
            doc = app_svc.save_cover_letter(
                user_id=user["id"],
                pipeline_id=pipeline_id,
                title=title,
                content=result.content,
                language=body.language,
            )
            app_svc.update_pipeline(user["id"], pipeline_id, {"current_status": new_status})
        except Exception as exc:
            yield f"data: {_json.dumps({'type': 'error', 'message': f'Kunne ikke gemme dokument: {exc}'})}\n\n"
            return

        yield f"data: {_json.dumps({'type': 'done', 'document_id': doc['id'], 'title': title, 'content': result.content, 'pipeline_id': pipeline_id, 'pipeline_status': new_status})}\n\n"

    return StreamingResponse(
        process(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
