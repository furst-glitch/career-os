"""
Cache API — Sprint 9

GET /cache/stats  — hit/miss rates, backend info
DELETE /cache/user — invalidate all cached data for the calling user
"""
from fastapi import APIRouter, Depends
from app.core.deps import get_current_user
from app.services.cache_service import get_cache, get_sync_cache, invalidate_user

router = APIRouter(prefix="/cache", tags=["Cache"])


@router.get("/stats")
async def cache_stats(_user=Depends(get_current_user)):
    """Return cache backend info and hit/miss statistics."""
    async_stats = get_cache().stats()
    sync_cache = get_sync_cache()
    return {
        "async_cache": async_stats,
        "sync_cache": sync_cache.stats() if sync_cache else {"backend": "none"},
    }


@router.delete("/user")
async def invalidate_user_cache(user=Depends(get_current_user)):
    """Purge all cached data for the calling user (snapshot, matches, coach)."""
    await invalidate_user(user["id"])
    return {"ok": True, "user_id": user["id"]}
