from fastapi import APIRouter
from app.api.v1 import (
    auth,
    cv,
    discovery,
    experience,
    memory,
    jobs,
    applications,
    interview_center,
    search,
    salary,
    review,
    billing,
    gdpr,
    profile,
)

api_router = APIRouter()

api_router.include_router(auth.router)
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
