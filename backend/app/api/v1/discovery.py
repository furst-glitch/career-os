"""
Discovery API — AI-drevet interview til kandidatprofil-opbygning.

POST /discovery/start              Start (eller fortsæt) session
POST /discovery/{id}/welcome       Stream initial AI-velkomst (ingen user-besked nødvendig)
POST /discovery/{id}/message       Send besked, stream svar (SSE)
GET  /discovery/{id}               Hent session-status
GET  /discovery/{id}/messages      Hent konversationshistorik
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["Discovery Interview"])


class StartRequest(BaseModel):
    upload_id: str | None = None


class MessageRequest(BaseModel):
    message: str


@router.post("/start")
async def start_session(
    body: StartRequest,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Start en ny discovery-session eller fortsæt en aktiv."""
    service = DiscoveryService(supabase)
    result = await service.start(user["id"], body.upload_id)
    return result


@router.post("/{session_id}/welcome")
async def welcome_message(
    session_id: str,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Stream AI's åbningsbesked (velkomst) for en ny session.
    Bruges når sessionen netop er oprettet og der endnu ingen beskeder er.
    Kræver ingen user-besked.
    """
    service = DiscoveryService(supabase)
    session = service.get_session(session_id, user["id"])
    if not session:
        raise HTTPException(404, "Session ikke fundet")
    if session.get("status") != "active":
        raise HTTPException(400, "Sessionen er ikke aktiv")

    async def event_stream():
        async for chunk in service.stream_welcome(session_id, user["id"]):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/message")
async def send_message(
    session_id: str,
    body: MessageRequest,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Send en besked i discovery-interviewet.
    Returnerer SSE-stream med AI-svar.

    Format:
      data: {"type": "chunk", "content": "..."}
      data: {"type": "done"}
      data: {"type": "error", "content": "..."}
    """
    if not body.message.strip():
        raise HTTPException(400, "Beskeden må ikke være tom")

    service = DiscoveryService(supabase)

    # Verificér at session tilhører brugeren
    session = service.get_session(session_id, user["id"])
    if not session:
        raise HTTPException(404, "Session ikke fundet")
    if session.get("status") != "active":
        raise HTTPException(400, "Sessionen er ikke aktiv")

    async def event_stream():
        async for chunk in service.stream_message(session_id, body.message, user["id"]):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Hent session-status, beskedantal og gap-fremskridt."""
    service = DiscoveryService(supabase)
    session = service.get_session(session_id, user["id"])
    if not session:
        raise HTTPException(404, "Session ikke fundet")

    messages = session.get("messages") or []
    return {
        "id": session["id"],
        "status": session["status"],
        "message_count": len(messages),
        "gaps_total": session.get("gaps_total", 0),
        "gaps_resolved": session.get("gaps_resolved", 0),
        "profile_complete": session.get("profile_complete", False),
        "created_at": session["created_at"],
    }


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Hent konversationshistorik for sessionen (bruges ved genoptagelse)."""
    service = DiscoveryService(supabase)
    session = service.get_session(session_id, user["id"])
    if not session:
        raise HTTPException(404, "Session ikke fundet")
    return {"messages": session.get("messages") or []}
