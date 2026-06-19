"""
Notifications API

GET    /notifications           — list unread (+ recent read)
POST   /notifications/{id}/read — mark as read
POST   /notifications/read-all  — mark all as read
DELETE /notifications/{id}      — delete
GET    /notifications/count     — unread count (for badge)
"""
from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user, get_supabase_admin

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/count")
async def get_unread_count(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    result = (
        supabase.table("notifications")
        .select("id", count="exact")
        .eq("user_id", user["id"])
        .eq("is_read", False)
        .execute()
    )
    return {"count": result.count or 0}


@router.get("")
async def list_notifications(
    limit: int = 30,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    result = (
        supabase.table("notifications")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"notifications": result.data or []}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    supabase.table("notifications").update({"is_read": True}).eq(
        "id", notification_id
    ).eq("user_id", user["id"]).execute()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    supabase.table("notifications").update({"is_read": True}).eq(
        "user_id", user["id"]
    ).eq("is_read", False).execute()
    return {"ok": True}


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    supabase.table("notifications").delete().eq(
        "id", notification_id
    ).eq("user_id", user["id"]).execute()
