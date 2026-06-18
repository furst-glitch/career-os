"""
Memory API — Career Memory Foundation.

GET/POST   /memory/memories             — career_memories CRUD
PUT/DELETE /memory/memories/{id}
GET        /memory/memories/search      — semantisk + keyword søgning

GET/POST   /memory/goals               — career_goals CRUD
PUT/DELETE /memory/goals/{id}

GET/POST   /memory/milestones          — career_milestones CRUD
PUT/DELETE /memory/milestones/{id}

GET/PUT    /memory/preferences         — career_preferences upsert

GET        /memory/snapshot            — komplet agent-snapshot (F5)
"""
import asyncio

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_supabase_admin
from app.services.memory_service import MemoryService
from app.services.memory_snapshot_service import MemorySnapshotService

router = APIRouter(prefix="/memory", tags=["Career Memory"])


def _svc(supabase) -> MemoryService:
    return MemoryService(supabase)


# ── Embedding helper ──────────────────────────────────────────────────────────

async def _generate_embedding(text: str, user_id: str, supabase) -> list[float] | None:
    """Genererer embedding via litellm. Returnerer None ved fejl / manglende nøgle."""
    try:
        from app.providers.key_manager import KeyManager
        import litellm

        km = KeyManager(supabase)
        api_key = km.get_key(user_id, "openai")
        if not api_key:
            return None

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: litellm.embedding(
                model="text-embedding-3-small",
                input=text,
                api_key=api_key,
            ),
        )
        return resp.data[0]["embedding"]
    except Exception:
        return None


# ── Memories ──────────────────────────────────────────────────────────────────

@router.get("/memories")
async def list_memories(
    memory_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return _svc(supabase).list_memories(user["id"], memory_type=memory_type, limit=limit)


@router.post("/memories", status_code=201)
async def create_memory(
    body: dict,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = _svc(supabase)
    mem = svc.create_memory(
        user_id=user["id"],
        content=body.get("content", ""),
        memory_type=body.get("memory_type", "career_note"),
        source=body.get("source", "user_input"),
        relevance_score=body.get("relevance_score", 0.5),
    )
    embedding = await _generate_embedding(mem["content"], user["id"], supabase)
    if embedding:
        svc.update_embedding(mem["id"], embedding)
        mem["embedding"] = embedding
    return mem


@router.put("/memories/{memory_id}")
async def update_memory(
    memory_id: str,
    body: dict,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = _svc(supabase)
    mem = svc.update_memory(memory_id, body)
    if "content" in body:
        embedding = await _generate_embedding(body["content"], user["id"], supabase)
        if embedding:
            svc.update_embedding(memory_id, embedding)
    return mem


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    _svc(supabase).delete_memory(memory_id)


@router.get("/memories/search")
async def search_memories(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Semantisk pgvector-søgning med keyword-fallback."""
    svc = _svc(supabase)
    embedding = await _generate_embedding(q, user["id"], supabase)
    if embedding:
        results = svc.search_memories_semantic(user["id"], embedding, match_count=limit, match_threshold=0.4)
        if results:
            return {"results": results, "method": "semantic"}
    results = svc.search_memories_keyword(user["id"], q, limit=limit)
    return {"results": results, "method": "keyword"}


# ── Goals ─────────────────────────────────────────────────────────────────────

@router.get("/goals")
async def list_goals(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_goals(user["id"])


@router.post("/goals", status_code=201)
async def create_goal(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_goal(user["id"], body)


@router.put("/goals/{goal_id}")
async def update_goal(
    goal_id: str, body: dict,
    user=Depends(get_current_user), supabase=Depends(get_supabase_admin)
):
    return _svc(supabase).update_goal(goal_id, body)


@router.delete("/goals/{goal_id}", status_code=204)
async def delete_goal(goal_id: str, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    _svc(supabase).delete_goal(goal_id)


# ── Milestones ────────────────────────────────────────────────────────────────

@router.get("/milestones")
async def list_milestones(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).list_milestones(user["id"])


@router.post("/milestones", status_code=201)
async def create_milestone(body: dict, user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).create_milestone(user["id"], body)


@router.put("/milestones/{milestone_id}")
async def update_milestone(
    milestone_id: str, body: dict,
    user=Depends(get_current_user), supabase=Depends(get_supabase_admin)
):
    return _svc(supabase).update_milestone(milestone_id, body)


@router.delete("/milestones/{milestone_id}", status_code=204)
async def delete_milestone(
    milestone_id: str,
    user=Depends(get_current_user), supabase=Depends(get_supabase_admin)
):
    _svc(supabase).delete_milestone(milestone_id)


# ── Preferences ───────────────────────────────────────────────────────────────

@router.get("/preferences")
async def get_preferences(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    return _svc(supabase).get_preferences(user["id"])


@router.put("/preferences")
async def upsert_preferences(
    body: dict,
    user=Depends(get_current_user), supabase=Depends(get_supabase_admin)
):
    return _svc(supabase).upsert_preferences(user["id"], body)


# ── Memory Snapshot ───────────────────────────────────────────────────────────

@router.get("/snapshot")
async def get_snapshot(user=Depends(get_current_user), supabase=Depends(get_supabase_admin)):
    """
    Komplet karrieresnapshot til agent-forbrug (F5).
    Inkluderer: profil, erfaring, skills, certifikater, projekter,
    aktive mål, præferencer, seneste minder og milepæle.
    """
    return MemorySnapshotService(supabase).snapshot(user["id"])
