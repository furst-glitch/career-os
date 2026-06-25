from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    applications,
    # auth,           # SKELETON — auth is handled by Supabase Auth directly; no backend endpoints needed
    # billing,        # SKELETON — Stripe webhook/portal not yet implemented
    cache,
    career_coach,
    cv,
    dashboard,
    discovery,
    document_intelligence,
    employment_graph,
    # experience,     # SKELETON — Experience Discovery module not yet implemented
    export,
    # gdpr,           # SKELETON — GDPR export/delete endpoints not yet implemented
    # interview_center,  # SKELETON — Interview Center module not yet implemented
    job_discovery,
    jobs,
    labor_coach,
    memory,
    notifications,
    profile,
    providers,
    # review,         # SKELETON — Multi-agent review API not yet implemented (pipeline exists, API wrapper does not)
    # salary,         # SKELETON — Salary module endpoints not yet implemented
    # search,         # SKELETON — Search Intelligence module not yet implemented
    templates,
)

api_router = APIRouter()

# auth.router is intentionally not registered — Supabase handles auth (login/logout/refresh/me)
api_router.include_router(cache.router)
api_router.include_router(dashboard.router)
api_router.include_router(analytics.router)
api_router.include_router(notifications.router)
api_router.include_router(cv.router)
api_router.include_router(discovery.router)
api_router.include_router(profile.router)
# experience.router is intentionally not registered — module is skeleton only
api_router.include_router(memory.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
# interview_center.router is intentionally not registered — module is skeleton only
# search.router is intentionally not registered — module is skeleton only
# salary.router is intentionally not registered — module is skeleton only
# review.router is intentionally not registered — module is skeleton only
# billing.router is intentionally not registered — module is skeleton only
# gdpr.router is intentionally not registered — module is skeleton only
api_router.include_router(providers.router)
api_router.include_router(export.router)
api_router.include_router(career_coach.router)
api_router.include_router(labor_coach.router)
api_router.include_router(document_intelligence.router)
api_router.include_router(employment_graph.router)
api_router.include_router(job_discovery.router)
api_router.include_router(templates.router)
