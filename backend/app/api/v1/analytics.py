"""
Analytics API — aggregated career metrics

GET /analytics/summary   — full dashboard metrics
GET /analytics/matchscore — match score history
"""
from fastapi import APIRouter, Depends
from app.core.deps import get_current_user, get_supabase_admin

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
async def get_analytics_summary(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Returns aggregated career metrics:
    - application counts by status
    - interview rate
    - average match score
    - CV completeness
    - job discovery stats
    """
    uid = user["id"]

    # ── Applications ──────────────────────────────────────────────────────────
    apps_result = (
        supabase.table("application_pipeline")
        .select("current_status, created_at")
        .eq("user_id", uid)
        .execute()
    )
    apps = apps_result.data or []

    status_counts: dict[str, int] = {}
    for a in apps:
        s = a.get("current_status") or "draft"
        status_counts[s] = status_counts.get(s, 0) + 1

    total_apps = len(apps)
    submitted = sum(v for k, v in status_counts.items()
                    if k in {"submitted", "screening", "interviewing", "offer", "hired", "rejected"})
    interviewing = sum(v for k, v in status_counts.items()
                       if k in {"interviewing", "offer", "hired"})
    hired = status_counts.get("hired", 0)
    interview_rate = round((interviewing / submitted * 100) if submitted > 0 else 0)
    offer_rate = round((hired / submitted * 100) if submitted > 0 else 0)

    # ── Jobs & match scores ───────────────────────────────────────────────────
    jobs_result = (
        supabase.table("jobs")
        .select("match_score, is_saved, created_at, source")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    jobs = jobs_result.data or []

    scores = [j["match_score"] for j in jobs if j.get("match_score") is not None]
    avg_match = round(sum(scores) / len(scores)) if scores else 0
    top_match = max(scores) if scores else 0
    jobs_saved = sum(1 for j in jobs if j.get("is_saved"))
    jobs_discovered = sum(1 for j in jobs if j.get("source") in ("jobindex", "jobnet", "ofir", "discovery"))

    # Match score trend (last 10 jobs with scores)
    scored_jobs = [j for j in jobs if j.get("match_score") is not None][:10]
    match_trend = [
        {"date": j["created_at"][:10], "score": j["match_score"]}
        for j in reversed(scored_jobs)
    ]

    # ── CV Completeness ───────────────────────────────────────────────────────
    score_result = (
        supabase.table("profile_scores")
        .select("overall, calculated_at")
        .eq("user_id", uid)
        .order("calculated_at", desc=True)
        .limit(1)
        .execute()
    )
    cv_completeness = score_result.data[0]["overall"] if score_result.data else 0

    # ── Master CV ─────────────────────────────────────────────────────────────
    mcv_result = (
        supabase.table("master_cvs")
        .select("is_generated, updated_at")
        .eq("user_id", uid)
        .limit(1)
        .execute()
    )
    has_master_cv = bool(mcv_result.data and mcv_result.data[0].get("is_generated"))

    return {
        "applications": {
            "total": total_apps,
            "by_status": status_counts,
            "submitted": submitted,
            "interviewing": interviewing,
            "hired": hired,
            "interview_rate_pct": interview_rate,
            "offer_rate_pct": offer_rate,
        },
        "jobs": {
            "total": len(jobs),
            "saved": jobs_saved,
            "discovered": jobs_discovered,
            "avg_match_score": avg_match,
            "top_match_score": top_match,
        },
        "match_trend": match_trend,
        "cv": {
            "completeness_pct": cv_completeness,
            "has_master_cv": has_master_cv,
        },
    }


@router.get("/matchscore")
async def get_matchscore_history(
    limit: int = 30,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Return match score history for chart display."""
    jobs_result = (
        supabase.table("jobs")
        .select("title, company, match_score, created_at")
        .eq("user_id", user["id"])
        .not_.is_("match_score", "null")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    jobs = jobs_result.data or []
    return {
        "history": [
            {
                "date": j["created_at"][:10],
                "score": j["match_score"],
                "title": j.get("title", ""),
                "company": j.get("company", ""),
            }
            for j in reversed(jobs)
        ]
    }
