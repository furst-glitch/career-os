"""
CV API — Upload, parsing, profil-populering og Master CV.

POST /cv/upload               Upload CV-fil (PDF/DOCX)
GET  /cv/master               Hent komplet profil-data
GET  /cv/master/content       Hent genereret Master CV-tekst
POST /cv/master/generate      Generer Master CV (SSE streaming)
"""
import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.agents.cv_agent import CVAgent
from app.core.deps import get_current_user, get_supabase_admin
from app.core.rate_limit import LIMIT_UPLOAD, limiter
from app.services.automation_service import on_cv_uploaded
from app.services.cv_service import CVService, extract_text
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/cv", tags=["CV Studio"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}
EXT_MIME_MAP = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
@limiter.limit(LIMIT_UPLOAD)
async def upload_cv(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Upload et eksisterende CV (PDF/DOCX/TXT).
    Parser det med AI og returnerer SSE-stream med progress-events.

    SSE events:
      data: {"type": "progress", "step": str, "pct": int, "message": str}
      data: {"type": "done",     "data": {upload_id, session_id, parsed_sections, gaps, personal}}
      data: {"type": "error",    "message": str}
      : ping   (keep-alive mens AI tænker)
    """
    import asyncio
    import json as _json

    # Validering — fald tilbage på extension hvis browser ikke sender korrekt MIME-type
    mime = file.content_type or "application/octet-stream"
    if mime not in ALLOWED_MIME_TYPES and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        mime = EXT_MIME_MAP.get(ext, mime)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, f"Filtype ikke understøttet: {mime}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Fil for stor (max 10 MB)")

    user_id = user["id"]
    filename = file.filename or "cv"
    cv_service = CVService(supabase)

    def _prog(step: str, pct: int, message: str) -> str:
        return f"data: {_json.dumps({'type': 'progress', 'step': step, 'pct': pct, 'message': message})}\n\n"

    async def process():
        upload_id = await cv_service.create_upload(user_id, filename, mime)
        try:
            # Trin 1: Ekstraher tekst
            yield _prog("extract", 10, "Læser fil...")
            raw_text = extract_text(content, mime)
            if not raw_text.strip():
                await cv_service.mark_failed(upload_id, "Ingen tekst fundet")
                yield f"data: {_json.dumps({'type': 'error', 'message': 'Filen ser ud til at være tom eller ikke-læsbar'})}\n\n"
                return

            # Trin 2: AI-analyse — kør i baggrunden med ping keep-alive
            yield _prog("ai_parse", 20, "AI analyserer dit CV... (dette tager typisk 30-90 sekunder)")

            queue: asyncio.Queue = asyncio.Queue()

            async def run_agent():
                try:
                    agent = CVAgent(user_id=user_id, supabase=supabase)
                    r = await agent.run({"raw_text": raw_text})
                    await queue.put(("ok", r))
                except Exception as exc:
                    await queue.put(("err", str(exc)))

            task = asyncio.create_task(run_agent())
            agent_result = None
            ping_count = 0
            while True:
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                    if kind == "ok":
                        agent_result = payload
                    else:
                        await cv_service.mark_failed(upload_id, payload)
                        yield f"data: {_json.dumps({'type': 'error', 'message': f'Analyse fejlede: {payload}'})}\n\n"
                        task.cancel()
                        return
                    break
                except asyncio.TimeoutError:
                    ping_count += 1
                    pct = min(20 + ping_count * 3, 70)
                    yield f": ping\n\n"
                    # Update progress pct every ~15s (every 3rd ping)
                    if ping_count % 3 == 0:
                        yield _prog("ai_parse", pct, f"AI analyserer... ({ping_count * 5}s)")

            # Trin 3: Gem til database
            yield _prog("saving", 82, "Gemmer din profil...")
            parsed = agent_result.metadata.get("parsed_data", {})
            gaps = agent_result.metadata.get("gaps", [])
            await cv_service.save_parsed(upload_id, raw_text, parsed)
            session_id = await cv_service.populate_profile_from_parsed(user_id, upload_id, parsed)

            # Refresh career memory (fire-and-forget — no BackgroundTasks inside generator)
            asyncio.create_task(on_cv_uploaded(user_id, supabase))

            yield _prog("done", 100, "Analyse færdig!")
            yield f"data: {_json.dumps({'type': 'done', 'data': {'upload_id': upload_id, 'session_id': session_id, 'parsed_sections': {'experiences': len(parsed.get('experiences') or []), 'educations': len(parsed.get('educations') or []), 'skills': len(parsed.get('skills') or []), 'projects': len(parsed.get('projects') or []), 'certifications': len(parsed.get('certifications') or []), 'systems': len(parsed.get('systems') or []), 'leadership': len(parsed.get('leadership') or [])}, 'gaps': gaps, 'personal': parsed.get('personal') or {}}})}\n\n"

        except Exception as exc:
            try:
                await cv_service.mark_failed(upload_id, str(exc))
            except Exception:
                pass
            yield f"data: {_json.dumps({'type': 'error', 'message': f'Uventet fejl: {exc}'})}\n\n"

    return StreamingResponse(
        process(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/master")
async def get_full_profile(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Returnerer hele kandidatprofilen med alle sektioner."""
    profile = await CVService(supabase).get_full_profile(user["id"])
    if not profile:
        return {"master_cv": None, "experiences": [], "educations": [], "skills": [],
                "projects": [], "achievements": [], "systems": [], "leadership": [],
                "certifications": [], "open_gaps": []}
    return profile


@router.get("/master/content")
async def get_master_cv_content(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Henter den senest genererede Master CV-tekst + sprog."""
    result = supabase.table("master_cvs").select("raw_content, is_generated, language, updated_at").eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(404, "Ingen Master CV fundet")
    mcv = result.data[0]
    return {
        "content": mcv.get("raw_content") or "",
        "is_generated": bool(mcv.get("is_generated")),
        "language": mcv.get("language") or "da",
        "updated_at": mcv.get("updated_at"),
    }


@router.post("/master/generate")
async def generate_master_cv(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Genererer et Master CV fra kandidatprofilen. SSE streaming."""
    discovery_service = DiscoveryService(supabase)

    async def event_stream():
        async for chunk in discovery_service.generate_master_cv(user["id"]):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.put("/master")
async def update_master_cv(
    body: dict,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Opdater felter på master_cv-tabellen (target_title, summary, language, raw_content)."""
    allowed = {"target_title", "summary", "language", "raw_content"}
    update = {k: v for k, v in body.items() if k in allowed}
    if not update:
        raise HTTPException(400, "Ingen gyldige felter at opdatere")
    supabase.table("master_cvs").update(update).eq("user_id", user["id"]).execute()
    return {"status": "updated"}


@router.get("/master/versions")
async def list_versions(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Versionshistorik for Master CV."""
    return CVService(supabase).list_versions(user["id"])


@router.post("/master/version", status_code=201)
async def save_version(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Gem nuværende Master CV-indhold som navngiven version."""
    result = supabase.table("master_cvs").select("raw_content, language").eq("user_id", user["id"]).limit(1).execute()
    if not result.data or not result.data[0].get("raw_content"):
        raise HTTPException(400, "Ingen indhold at gemme som version")
    cv = result.data[0]
    version = CVService(supabase).create_version(
        user["id"], cv["raw_content"], "user", cv.get("language") or "da"
    )
    return version


@router.get("/master/versions/{version_id}")
async def get_version(
    version_id: str,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Hent indhold fra en specifik version (til gendannelse)."""
    content = CVService(supabase).get_version_content(version_id, user["id"])
    if content is None:
        raise HTTPException(404, "Version ikke fundet")
    return {"content": content}
