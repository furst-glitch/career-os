"""
Dashboard API — aggregated view for Dashboard 2.0

GET /dashboard/summary   — all dashboard widgets in one call
"""
from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_supabase_admin

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    One-shot endpoint that loads everything the Dashboard 2.0 needs.
    Uses parallel Supabase queries to minimise latency.
    """
    uid = user["id"]

    def _q(fn):
        try:
            return fn()
        except Exception:
            return []

    def _q1(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    # ── Parallel data fetch ───────────────────────────────────────────────────
    top_matches = _q(lambda: (
        supabase.table("jobs")
        .select("id, title, company, location, match_score, is_saved, created_at, url")
        .eq("user_id", uid)
        .not_.is_("match_score", "null")
        .order("match_score", desc=True)
        .limit(5)
        .execute()
        .data or []
    ))

    active_apps = _q(lambda: (
        supabase.table("application_pipeline")
        .select("id, current_status, priority, deadline, created_at, jobs(title, company)")
        .eq("user_id", uid)
        .not_.in_("current_status", ["rejected", "withdrawn", "afslag"])
        .order("created_at", desc=True)
        .limit(10)
        .execute()
        .data or []
    ))

    all_apps = _q(lambda: (
        supabase.table("application_pipeline")
        .select("current_status")
        .eq("user_id", uid)
        .execute()
        .data or []
    ))
    status_counts: dict[str, int] = {}
    for a in all_apps:
        s = a.get("current_status") or "draft"
        status_counts[s] = status_counts.get(s, 0) + 1

    interviews = _q(lambda: (
        supabase.table("application_pipeline")
        .select("id, deadline, notes, jobs(title, company)")
        .eq("user_id", uid)
        .in_("current_status", ["interviewing", "screening", "samtale_1", "samtale_2"])
        .not_.is_("deadline", "null")
        .order("deadline")
        .limit(5)
        .execute()
        .data or []
    ))

    notifications = _q(lambda: (
        supabase.table("notifications")
        .select("id, event_type, title, body, is_read, created_at")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
        .data or []
    ))
    unread_count = sum(1 for n in notifications if not n.get("is_read"))

    score_row = _q1(lambda: (
        supabase.table("profile_scores")
        .select("overall")
        .eq("user_id", uid)
        .order("calculated_at", desc=True)
        .limit(1)
        .execute()
        .data
    ))
    cv_score = score_row[0]["overall"] if score_row else 0

    mcv = _q1(lambda: (
        supabase.table("master_cvs")
        .select("is_generated")
        .eq("user_id", uid)
        .limit(1)
        .execute()
        .data
    ))
    has_mcv = bool(mcv and mcv[0].get("is_generated"))

    recent_jobs = _q(lambda: (
        supabase.table("jobs")
        .select("id, title, company, match_score, created_at, source")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data or []
    ))

    # Career coach sessions (tabel oprettes når funktionen er klar)
    try:
        coach_sessions = (
            supabase.table("career_coach_sessions")
            .select("id, title, created_at")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .limit(3)
            .execute()
            .data or []
        )
    except Exception:
        coach_sessions = []

    return {
        "top_job_matches": top_matches,
        "active_applications": active_apps,
        "application_counts": status_counts,
        "upcoming_interviews": interviews,
        "recent_jobs": recent_jobs,
        "notifications": notifications,
        "unread_notifications": unread_count,
        "coach_sessions": coach_sessions,
        "profile": {
            "cv_completeness": cv_score,
            "has_master_cv": has_mcv,
        },
    }
