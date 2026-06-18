"""
CV API — Upload, parsing, profil-populering og Master CV.

POST /cv/upload               Upload CV-fil (PDF/DOCX)
GET  /cv/master               Hent komplet profil-data
GET  /cv/master/content       Hent genereret Master CV-tekst
POST /cv/master/generate      Generer Master CV (SSE streaming)
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.agents.cv_agent import CVAgent
from app.core.deps import get_current_user, get_supabase_admin
from app.services.cv_service import CVService, extract_text
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/cv", tags=["CV Studio"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_cv(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Upload et eksisterende CV (PDF/DOCX/TXT).
    Parser det med AI, populerer profil-tabeller og opretter en discovery-session.
    Returnerer: { upload_id, session_id, parsed_sections, gaps }
    """
    # Validering
    mime = file.content_type or "application/octet-stream"
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, f"Filtype ikke understøttet: {mime}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Fil for stor (max 10 MB)")

    user_id = user["id"]
    cv_service = CVService(supabase)

    # Opret upload-record
    upload_id = await cv_service.create_upload(user_id, file.filename or "cv", mime)

    try:
        # Ekstraher tekst
        raw_text = extract_text(content, mime)
        if not raw_text.strip():
            await cv_service.mark_failed(upload_id, "Kunne ikke ekstraherer tekst fra filen")
            raise HTTPException(422, "Filen ser ud til at være tom eller ikke-læsbar")

        # Parse med CV Agent
        agent = CVAgent(user_id=user_id, supabase=supabase)
        result = await agent.run({"raw_text": raw_text})
        parsed = result.metadata.get("parsed_data", {})
        gaps = result.metadata.get("gaps", [])

        # Gem parsed data
        await cv_service.save_parsed(upload_id, raw_text, parsed)

        # Populér profil-tabeller + opret discovery session
        session_id = await cv_service.populate_profile_from_parsed(user_id, upload_id, parsed)

        return {
            "upload_id": upload_id,
            "session_id": session_id,
            "parsed_sections": {
                "experiences": len(parsed.get("experiences") or []),
                "educations": len(parsed.get("educations") or []),
                "skills": len(parsed.get("skills") or []),
                "projects": len(parsed.get("projects") or []),
                "certifications": len(parsed.get("certifications") or []),
                "systems": len(parsed.get("systems") or []),
                "leadership": len(parsed.get("leadership") or []),
            },
            "gaps": gaps,
            "personal": parsed.get("personal") or {},
        }

    except HTTPException:
        raise
    except Exception as exc:
        await cv_service.mark_failed(upload_id, str(exc))
        raise HTTPException(500, f"Fejl under parsing: {exc}") from exc


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
    """Henter den senest genererede Master CV-tekst."""
    result = supabase.table("master_cvs").select("raw_content, is_generated, updated_at").eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(404, "Ingen Master CV fundet")
    mcv = result.data[0]
    if not mcv.get("is_generated") or not mcv.get("raw_content"):
        raise HTTPException(404, "Master CV er endnu ikke genereret — kald POST /cv/master/generate")
    return {"content": mcv["raw_content"], "updated_at": mcv["updated_at"]}


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
    """Opdater felter på master_cv-tabellen (target_title, summary, language)."""
    allowed = {"target_title", "summary", "language"}
    update = {k: v for k, v in body.items() if k in allowed}
    if not update:
        raise HTTPException(400, "Ingen gyldige felter at opdatere")
    supabase.table("master_cvs").update(update).eq("user_id", user["id"]).execute()
    return {"status": "updated"}
