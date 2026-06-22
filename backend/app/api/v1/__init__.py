from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    applications,
    auth,
    billing,
    cache,
    career_coach,
    cv,
    dashboard,
    discovery,
    experience,
    export,
    gdpr,
    interview_center,
    job_discovery,
    jobs,
    labor_coach,
    memory,
    notifications,
    profile,
    providers,
    review,
    salary,
    search,
    templates,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(cache.router)
api_router.include_router(dashboard.router)
api_router.include_router(analytics.router)
api_router.include_router(notifications.router)
api_router.include_router(cv.router)
api_router.include_router(discovery.router)
api_router.include_router(profile.router)
api_router.include_router(experience.router)
api_router.include_router(memory.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(interview_center.router)
api_router.include_router(search.router)
api_router.include_router(salary.router)
api_router.include_router(review.router)
api_router.include_router(billing.router)
api_router.include_router(gdpr.router)
api_router.include_router(providers.router)
api_router.include_router(export.router)
api_router.include_router(career_coach.router)
api_router.include_router(labor_coach.router)
api_router.include_router(job_discovery.router)
api_router.include_router(templates.router)
