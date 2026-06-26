"""
Platform Intelligence Engine API — kun til internt administratorbrug.

WP2  GET /intelligence/analytics?days=30   — produkt-KPI'er
WP3  GET /intelligence/health              — sundhedsscore med komponenter
WP4  GET /intelligence/operational         — fejl, flaskehalse, budgetalerter
WP6  GET /intelligence/priorities          — datadrevne prioriteringsforslag
WP7  GET /intelligence/report              — ugentlig eksekutivrapport
     GET /intelligence/events              — rå event-log (debugging)

Alle endpoints kræver admin-adgang (require_admin dependency).
"""

from fastapi import APIRouter, Depends, Query, Request

from app.core.deps import get_supabase_admin, require_admin
from app.core.rate_limit import limiter
from app.services.intelligence_service import IntelligenceService

router = APIRouter(prefix="/intelligence", tags=["Intelligence (Admin)"])

_LIMIT_ADMIN = "60/minute"


@router.get("/analytics")
@limiter.limit(_LIMIT_ADMIN)
async def get_analytics(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    _admin=Depends(require_admin),
    supabase=Depends(get_supabase_admin),
):
    """WP2 — Produkt-KPI'er: analyser, fakta, anbefalinger, AI-forbrug, omsætning."""
    svc = IntelligenceService(supabase)
    return svc.get_analytics(days=days)


@router.get("/health")
@limiter.limit(_LIMIT_ADMIN)
async def get_health_score(
    request: Request,
    _admin=Depends(require_admin),
    supabase=Depends(get_supabase_admin),
):
    """WP3 — Platformsundhedsscore (0–100) med komponentforklaring."""
    svc = IntelligenceService(supabase)
    return svc.get_health_score()


@router.get("/operational")
@limiter.limit(_LIMIT_ADMIN)
async def get_operational(
    request: Request,
    _admin=Depends(require_admin),
    supabase=Depends(get_supabase_admin),
):
    """WP4 — Driftsanalyse: top fejl, langsomme endpoints, budgetalerter."""
    svc = IntelligenceService(supabase)
    return svc.get_operational()


@router.get("/priorities")
@limiter.limit(_LIMIT_ADMIN)
async def get_priorities(
    request: Request,
    _admin=Depends(require_admin),
    supabase=Depends(get_supabase_admin),
):
    """WP6 — Datadrevne prioriteringsforslag: fejl, UX-forbedringer, muligheder."""
    svc = IntelligenceService(supabase)
    return svc.get_priorities()


@router.get("/report")
@limiter.limit(_LIMIT_ADMIN)
async def get_executive_report(
    request: Request,
    _admin=Depends(require_admin),
    supabase=Depends(get_supabase_admin),
):
    """WP7 — Ugentlig eksekutivrapport: tilstand, highlights, concerns, handlinger."""
    svc = IntelligenceService(supabase)
    return svc.get_executive_report()


@router.get("/events")
@limiter.limit(_LIMIT_ADMIN)
async def list_events(
    request: Request,
    event_type: str | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=1000),
    _admin=Depends(require_admin),
    supabase=Depends(get_supabase_admin),
):
    """Rå event-log til debugging og validering af instrumentering."""
    from datetime import datetime, timedelta, timezone

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = (
        supabase.table("platform_events")
        .select("id, event_type, user_id, employment_id, document_id, properties, occurred_at")
        .gte("occurred_at", since)
        .order("occurred_at", desc=True)
        .limit(limit)
    )
    if event_type:
        q = q.eq("event_type", event_type)
    result = q.execute()
    return {"events": result.data or [], "count": len(result.data or [])}
