from fastapi import Depends, Header, HTTPException
from supabase import Client, create_client

from app.core.config import settings


def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_supabase_admin() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Ugyldig authorization header")

    token = authorization.removeprefix("Bearer ")
    supabase = get_supabase_admin()

    try:
        user = supabase.auth.get_user(token)
        if not user or not user.user:
            raise HTTPException(status_code=401, detail="Ugyldig token")
        return {"id": user.user.id, "email": user.user.email}
    except Exception:
        raise HTTPException(status_code=401, detail="Token kunne ikke valideres")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Gater adgang til interne admin-endpoints (CTO Dashboard, Intelligence Engine)."""
    if not settings.admin_email or user.get("email") != settings.admin_email:
        raise HTTPException(status_code=403, detail="Admin-adgang krævet")
    return user


PLAN_HIERARCHY = {"free": 0, "pro": 1, "professional": 2, "enterprise": 3}


def require_plan(minimum_plan: str):
    async def check_plan(
        user: dict = Depends(get_current_user),
        supabase: Client = Depends(get_supabase_admin),
    ) -> dict:
        result = (
            supabase.table("subscriptions")
            .select("plan")
            .eq("user_id", user["id"])
            .single()
            .execute()
        )

        user_plan = result.data.get("plan", "free") if result.data else "free"

        if PLAN_HIERARCHY.get(user_plan, 0) < PLAN_HIERARCHY.get(minimum_plan, 0):
            raise HTTPException(
                status_code=402,
                detail=f"Denne funktion kræver {minimum_plan}-abonnement",
            )
        return user

    return check_plan
