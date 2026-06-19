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
    "draft", "preparing", "ready", "submitted",
    "screening", "interviewing", "offer", "rejected", "withdrawn", "hired",
}
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
    return svc.update_pipeline(user["id"], pipeline_id, data)


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
    Generer en AI-ansøgning baseret på jobdetaljer og karriere-snapshot.
    Gemmer resultatet som document_version og returnerer content + document_id.
    """
    svc = ApplicationService(supabase)
    app = svc.get_pipeline(user["id"], pipeline_id)
    if not app:
        raise HTTPException(404, "Ansøgning ikke fundet")

    job = app.get("jobs") or {}
    if not job:
        raise HTTPException(422, "Pipeline-entry mangler job-data")

    # Hent karriere-snapshot
    snapshot_svc = MemorySnapshotService(supabase)
    snapshot = snapshot_svc.snapshot(user["id"])
    candidate_summary = snapshot.get("text_summary", "")

    # AI-generation
    agent = ApplicationAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run({
            "job_title": job.get("title", ""),
            "job_company": job.get("company", ""),
            "job_description": job.get("description", ""),
            "job_requirements": job.get("requirements", []),
            "candidate_summary": candidate_summary,
            "language": body.language,
            "writing_style": body.writing_style,
            "focus_areas": body.focus_areas,
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
        raise HTTPException(500, f"AI-generering fejlede: {exc}")

    lang = body.language
    title = (
        f"Ansøgning — {job.get('title', 'Stilling')} hos {job.get('company', '')}"
        if lang == "da"
        else f"Cover Letter — {job.get('title', 'Position')} at {job.get('company', '')}"
    )

    doc = svc.save_cover_letter(
        user_id=user["id"],
        pipeline_id=pipeline_id,
        title=title,
        content=result.content,
        language=lang,
    )

    return {
        "document_id": doc["id"],
        "title": doc["title"],
        "content": result.content,
        "language": lang,
        "version_number": doc["version_number"],
    }


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
