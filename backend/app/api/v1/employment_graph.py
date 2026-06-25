"""
Employment Graph API — Sprint 6.

Endpoints:
  POST  /employment-graph/resolve              — resolve document → Employment
  GET   /employment-graph/{employment_id}      — full Employment Graph
  POST  /employment-graph/{employment_id}/analyze       — cross-document analysis
  GET   /employment-graph/{employment_id}/recommendations — open recommendations
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.services.cross_document_analysis_service import CrossDocumentAnalysisService
from app.services.employment_graph_service import EmploymentGraphService
from app.services.employment_resolver import EmploymentResolverService

router = APIRouter(prefix="/employment-graph", tags=["Employment Graph"])


# ── Request / Response schemas ────────────────────────────────────────────────


class ResolveRequest(BaseModel):
    employer_name: str | None = None
    job_title: str | None = None
    period_start: str | None = None


class EmploymentCandidateOut(BaseModel):
    employment_id: str
    title: str
    organisation: str | None
    period_start: str | None
    period_end: str | None
    confidence: float
    match_reasons: list[str]


class ResolveResponse(BaseModel):
    status: str
    employment_id: str | None
    confidence: float
    candidates: list[EmploymentCandidateOut]
    hint: str


class DiscrepancyOut(BaseModel):
    recommendation_type: str
    severity: str
    title: str
    description: str
    fact_types: list[str]
    affected_fact_ids: list[str]


class AnalyzeResponse(BaseModel):
    analysis_id: str
    employment_id: str
    document_ids: list[str]
    discrepancies_found: int
    discrepancies: list[DiscrepancyOut]
    warnings: list[str]


class RecommendationOut(BaseModel):
    id: str
    recommendation_type: str
    severity: str
    title: str
    description: str
    fact_types: list[str]
    status: str
    created_at: str


class RecommendationsResponse(BaseModel):
    recommendations: list[RecommendationOut]
    open_count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/resolve", response_model=ResolveResponse)
async def resolve_employment(
    request: ResolveRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Resolve which Employment a document belongs to, based on facts extracted
    from the document (employer_name, job_title, contract_start_date).

    Returns the best-matching Employment at high confidence, or a list of
    candidates for the user to confirm manually.
    """
    svc = EmploymentResolverService(supabase)
    result = await svc.resolve(
        user_id=user.id,
        employer_name=request.employer_name,
        job_title=request.job_title,
        period_start=request.period_start,
    )
    return ResolveResponse(
        status=result.status,
        employment_id=result.employment_id,
        confidence=result.confidence,
        candidates=[
            EmploymentCandidateOut(
                employment_id=c.employment_id,
                title=c.title,
                organisation=c.organisation,
                period_start=str(c.period_start) if c.period_start else None,
                period_end=str(c.period_end) if c.period_end else None,
                confidence=c.confidence,
                match_reasons=c.match_reasons,
            )
            for c in result.candidates
        ],
        hint=result.hint,
    )


@router.get("/{employment_id}", response_model=dict)
async def get_employment_graph(
    employment_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Return the complete Employment Graph for one Employment:
    employment + documents + facts + analyses + recommendations.
    """
    svc = EmploymentGraphService(supabase)
    graph = await svc.get_graph(user_id=user.id, employment_id=employment_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Employment not found")
    return {
        "employment": graph.employment,
        "documents": graph.documents,
        "facts": graph.facts,
        "analyses": graph.analyses,
        "recommendations": graph.recommendations,
        "summary": {
            "facts_total": graph.facts_total,
            "facts_requiring_confirmation": graph.facts_requiring_confirmation,
            "open_recommendations": graph.open_recommendations,
        },
    }


@router.post("/{employment_id}/analyze", response_model=AnalyzeResponse)
async def analyze_employment(
    employment_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Run cross-document analysis for an Employment.

    Compares facts across all linked documents (contract vs payslip vs agreement)
    and creates Recommendations for any discrepancies found.

    Deterministic — no AI calls. Safe to run multiple times.
    """
    svc = CrossDocumentAnalysisService(supabase)
    result = await svc.analyze(user_id=user.id, employment_id=employment_id)
    return AnalyzeResponse(
        analysis_id=result.analysis_id,
        employment_id=result.employment_id,
        document_ids=result.document_ids,
        discrepancies_found=len(result.discrepancies),
        discrepancies=[
            DiscrepancyOut(
                recommendation_type=d.recommendation_type,
                severity=d.severity,
                title=d.title,
                description=d.description,
                fact_types=d.fact_types,
                affected_fact_ids=d.affected_fact_ids,
            )
            for d in result.discrepancies
        ],
        warnings=result.warnings,
    )


@router.get("/{employment_id}/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    employment_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Return all Recommendations for an Employment, newest first.
    open_count is the number of pending (unresolved) recommendations.
    """
    svc = EmploymentGraphService(supabase)
    graph = await svc.get_graph(user_id=user.id, employment_id=employment_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Employment not found")
    return RecommendationsResponse(
        recommendations=[
            RecommendationOut(
                id=r["id"],
                recommendation_type=r["recommendation_type"],
                severity=r["severity"],
                title=r["title"],
                description=r["description"],
                fact_types=r.get("fact_types", []),
                status=r["status"],
                created_at=str(r["created_at"]),
            )
            for r in graph.recommendations
        ],
        open_count=graph.open_recommendations,
    )
