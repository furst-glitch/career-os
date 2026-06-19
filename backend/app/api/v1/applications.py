"""
Applications API — Pipeline CRUD + AI Cover Letter Generation

GET    /applications                    - Liste alle pipeline entries
POST   /applications                    - Opret pipeline entry (kræver job_id)
GET    /applications/{id}               - Hent enkelt pipeline entry
PUT    /applications/{id}               - Opdater status, prioritet, deadline, noter
DELETE /applications/{id}               - Slet pipeline entry
GET    /applications/{id}/history       - Status-historik
GET    /applications/{id}/documents     - Tilknyttede dokumenter
POST   /applications/{id}/documents     - Tilknyt eksisterende document til pipeline
POST   /applications/{id}/generate      - Generer cover letter med AI
GET    /applications/documents/{doc_id} - Hent dokument-indhold
PUT    /applications/documents/{doc_id} - Rediger dokument-indhold
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.agents.application_agent import ApplicationAgent
from app.core.deps import get_current_user, get_supabase_admin
from app.core.rate_limit import LIMIT_APP_GEN, limiter
from app.providers.litellm_provider import NoProviderKeyError
from app.services.application_service import ApplicationService
from app.services.memory_snapshot_service import MemorySnapshotService

router = APIRouter(prefix="/applications", tags=["Applications"])

VALID_STATUSES = {
    # Pipeline 1.0 (bevaret for bagudkompatibilitet)
    "draft", "preparing", "ready", "submitted",
    "screening", "interviewing", "offer", "rejected", "withdrawn", "hired",
    # Pipeline 2.0
    "fundet", "gemt", "cv_genereret", "ansoegning_genereret",
    "ansoegt", "samtale_1", "samtale_2", "case_stadie",
    "tilbud", "ansat", "afslag",
}

INTERVIEW_STATUSES = {"samtale_1", "samtale_2"}
VALID_PRIORITIES = {"low", "medium", "high", "dream"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreatePipelineRequest(BaseModel):
    job_id: str
    status: str = "draft"
    priority: str = "medium"
    deadline: str | None = None
    notes: str | None = None
    source: str | None = None


class UpdatePipelineRequest(BaseModel):
    current_status: str | None = None
    priority: str | None = None
    deadline: str | None = None
    notes: str | None = None


class AddDocumentRequest(BaseModel):
    document_id: str
    role: str = "cover_letter"


class GenerateCoverLetterRequest(BaseModel):
    language: str = "da"
    writing_style: str = "professional"
    focus_areas: str | None = None
    doc_type: str = "cover_letter"  # "cover_letter" | "cv"


class UpdateDocumentRequest(BaseModel):
    content: str
    title: str | None = None


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_applications(
    status: str | None = None,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    if status and status not in VALID_STATUSES:
        raise HTTPException(400, f"Ugyldig status: {status}")
    return {"applications": svc.list_pipeline(user["id"], status)}


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_application(
    body: CreatePipelineRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Ugyldig status: {body.status}")
    if body.priority not in VALID_PRIORITIES:
        raise HTTPException(400, f"Ugyldig prioritet: {body.priority}")
    svc = ApplicationService(supabase)
    try:
        app = svc.create_pipeline(user["id"], body.job_id, body.model_dump())
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(409, "Der er allerede en ansøgning for dette job")
        raise HTTPException(500, str(exc))
    return app


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{pipeline_id}")
async def get_application(
    pipeline_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    app = svc.get_pipeline(user["id"], pipeline_id)
    if not app:
        raise HTTPException(404, "Ansøgning ikke fundet")
    return app


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{pipeline_id}")
async def update_application(
    pipeline_id: str,
    body: UpdatePipelineRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    app = svc.get_pipeline(user["id"], pipeline_id)
    if not app:
        raise HTTPException(404, "Ansøgning ikke fundet")
    if body.current_status and body.current_status not in VALID_STATUSES:
        raise HTTPException(400, f"Ugyldig status: {body.current_status}")
    if body.priority and body.priority not in VALID_PRIORITIES:
        raise HTTPException(400, f"Ugyldig prioritet: {body.priority}")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = svc.update_pipeline(user["id"], pipeline_id, data)

    # Auto-generer interviewforberedelse ved samtale 1 og 2
    if body.current_status in INTERVIEW_STATUSES:
        from fastapi import BackgroundTasks
        from app.services.interview_prep_service import generate_interview_prep
        import asyncio
        asyncio.create_task(
            generate_interview_prep(user["id"], pipeline_id, body.current_status, supabase)
        )

    return updated


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{pipeline_id}", status_code=204)
async def delete_application(
    pipeline_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    app = svc.get_pipeline(user["id"], pipeline_id)
    if not app:
        raise HTTPException(404, "Ansøgning ikke fundet")
    svc.delete_pipeline(user["id"], pipeline_id)


# ── Status History ────────────────────────────────────────────────────────────

@router.get("/{pipeline_id}/history")
async def get_application_history(
    pipeline_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    history = svc.get_status_history(user["id"], pipeline_id)
    return {"history": history}


# ── Documents ─────────────────────────────────────────────────────────────────

@router.get("/{pipeline_id}/documents")
async def list_documents(
    pipeline_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    docs = svc.list_documents(user["id"], pipeline_id)
    return {"documents": docs}


@router.post("/{pipeline_id}/documents", status_code=201)
async def add_document(
    pipeline_id: str,
    body: AddDocumentRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    app = svc.get_pipeline(user["id"], pipeline_id)
    if not app:
        raise HTTPException(404, "Ansøgning ikke fundet")
    doc = svc.add_document(user["id"], pipeline_id, body.document_id, body.role)
    return doc


# ── AI Cover Letter Generation ────────────────────────────────────────────────

@router.post("/{pipeline_id}/generate")
@limiter.limit(LIMIT_APP_GEN)
async def generate_cover_letter(
    request: Request,
    pipeline_id: str,
    body: GenerateCoverLetterRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Generer en AI-ansøgning/CV baseret på jobdetaljer og karriere-snapshot.
    Returnerer SSE-stream med keep-alive pings og et enkelt 'done'-event.

    SSE events:
      : ping                                    (keep-alive mens AI tænker)
      data: {"type": "done",   "document_id": ..., "content": ..., ...}
      data: {"type": "error",  "message": ..., "code"?: "no_api_key"}
    """
    import asyncio
    import json as _json

    svc = ApplicationService(supabase)
    app_entry = svc.get_pipeline(user["id"], pipeline_id)
    if not app_entry:
        raise HTTPException(404, "Ansøgning ikke fundet")

    job = app_entry.get("jobs") or {}
    if not job:
        raise HTTPException(422, "Pipeline-entry mangler job-data")

    snapshot_svc = MemorySnapshotService(supabase)
    snapshot = snapshot_svc.snapshot(user["id"])
    candidate_summary = snapshot.get("text_summary", "")

    lang = body.language
    is_cv = body.doc_type == "cv"
    title = (
        (f"CV — {job.get('title', 'Stilling')} hos {job.get('company', '')}" if is_cv
         else f"Ansøgning — {job.get('title', 'Stilling')} hos {job.get('company', '')}")
        if lang == "da"
        else
        (f"CV — {job.get('title', 'Position')} at {job.get('company', '')}" if is_cv
         else f"Cover Letter — {job.get('title', 'Position')} at {job.get('company', '')}")
    )

    async def process():
        queue: asyncio.Queue = asyncio.Queue()

        async def run_agent():
            try:
                agent = ApplicationAgent(user_id=user["id"], supabase=supabase)
                r = await agent.run({
                    "job_title": job.get("title", ""),
                    "job_company": job.get("company", ""),
                    "job_description": job.get("description", ""),
                    "job_requirements": job.get("requirements", []),
                    "candidate_summary": candidate_summary,
                    "language": lang,
                    "writing_style": body.writing_style,
                    "focus_areas": body.focus_areas,
                    "doc_type": body.doc_type,
                }, queue=queue)
                await queue.put(("ok", r))
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
            except asyncio.TimeoutError:
                yield ": ping\n\n"

        doc = svc.save_cover_letter(
            user_id=user["id"],
            pipeline_id=pipeline_id,
            title=title,
            content=result.content,
            language=lang,
        )

        yield f"data: {_json.dumps({'type': 'done', 'document_id': doc['id'], 'title': doc['title'], 'content': result.content, 'language': lang, 'version_number': doc['version_number']})}\n\n"

    from fastapi.responses import StreamingResponse as SR
    return SR(
        process(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── Document Content ──────────────────────────────────────────────────────────

@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    doc = svc.get_document_content(user["id"], document_id)
    if not doc:
        raise HTTPException(404, "Dokument ikke fundet")
    return doc


@router.put("/documents/{document_id}")
async def update_document(
    document_id: str,
    body: UpdateDocumentRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = ApplicationService(supabase)
    doc = svc.get_document_content(user["id"], document_id)
    if not doc:
        raise HTTPException(404, "Dokument ikke fundet")
    return svc.update_document_content(user["id"], document_id, body.content, body.title)


# ── Interview Preparation ─────────────────────────────────────────────────────

@router.get("/{pipeline_id}/interview-prep")
async def get_interview_prep(
    pipeline_id: str,
    status: str | None = None,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Hent interviewforberedelse for en ansøgning."""
    svc = ApplicationService(supabase)
    app = svc.get_pipeline(user["id"], pipeline_id)
    if not app:
        raise HTTPException(404, "Ansøgning ikke fundet")
    q = supabase.table("interview_prep").select("*").eq("pipeline_id", pipeline_id).eq("user_id", user["id"])
    if status:
        q = q.eq("status", status)
    result = q.order("generated_at", desc=True).execute()
    return {"preps": result.data or []}


@router.post("/{pipeline_id}/interview-prep")
async def trigger_interview_prep(
    pipeline_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Manuel trigger af interviewforberedelse (kræver status samtale_1 eller samtale_2)."""
    svc = ApplicationService(supabase)
    app = svc.get_pipeline(user["id"], pipeline_id)
    if not app:
        raise HTTPException(404, "Ansøgning ikke fundet")
    status = app.get("current_status", "")
    if status not in INTERVIEW_STATUSES:
        raise HTTPException(400, f"Interviewforberedelse kræver status samtale_1 eller samtale_2 (nuværende: {status})")

    from app.services.interview_prep_service import generate_interview_prep
    content = await generate_interview_prep(user["id"], pipeline_id, status, supabase)
    return {"content": content, "status": status}
