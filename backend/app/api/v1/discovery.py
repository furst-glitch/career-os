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
        import asyncio

        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def producer():
            try:
                async for chunk in service.stream_welcome(session_id, user["id"]):
                    await queue.put(("data", chunk))
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                await queue.put(("data", f'{{"type":"error","content":"{exc}"}}'))
            finally:
                try:
                    queue.put_nowait(("done", ""))
                except asyncio.QueueFull:
                    pass

        task = asyncio.create_task(producer())
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if kind == "done":
                    break
                yield f"data: {payload}\n\n"
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
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
      : ping  (keep-alive — sendes hvert 5. sekund mens AI tænker)
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
        import asyncio
        import json as _json

        # Queue-based keep-alive: stream_message() runs in a background task
        # and puts chunks into a queue. The event_stream generator reads from
        # the queue with a 5-second timeout and sends SSE ping comments while
        # waiting. This avoids the asyncio.wait_for/CancelledError problem
        # that would otherwise kill the async generator prematurely.
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def producer():
            try:
                async for chunk in service.stream_message(session_id, body.message, user["id"]):
                    await queue.put(("data", chunk))
            except asyncio.CancelledError:
                pass  # Client disconnected — stop silently
            except Exception as exc:
                try:
                    await queue.put(("error", _json.dumps({"type": "error", "content": f"Stream fejl: {exc}"})))
                except Exception:
                    pass
            finally:
                try:
                    queue.put_nowait(("done", ""))  # Non-blocking; avoids awaiting in finally
                except asyncio.QueueFull:
                    pass

        task = asyncio.create_task(producer())
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Still waiting for LLM — send SSE comment to keep connection open
                    yield ": ping\n\n"
                    continue
                if kind == "done":
                    break
                yield f"data: {payload}\n\n"
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
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
