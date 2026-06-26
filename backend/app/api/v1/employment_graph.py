"""
Employment Graph API — Sprint 6/7.

Endpoints:
  POST  /employment-graph/resolve                      — resolve document → Employment
  GET   /employment-graph/employments                  — list Work Graph employments
  POST  /employment-graph/employments                  — create Work Graph employment
  PATCH /employment-graph/recommendations/{rec_id}     — update recommendation status
  GET   /employment-graph/{employment_id}              — full Employment Graph
  POST  /employment-graph/{employment_id}/analyze      — cross-document analysis
  GET   /employment-graph/{employment_id}/recommendations — open recommendations
  POST  /employment-graph/{employment_id}/chat         — AI chat with employment context (SSE)
"""

from __future__ import annotations

import json as _json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.core.rate_limit import LIMIT_COACH, limiter
from app.services.cross_document_analysis_service import CrossDocumentAnalysisService
from app.services.employment_graph_service import EmploymentGraphService
from app.services.employment_resolver import EmploymentResolverService

logger = logging.getLogger("app.employment_graph")
router = APIRouter(prefix="/employment-graph", tags=["Employment Graph"])

_ALLOWED_EXPERIENCE_TYPES = frozenset({"job", "freelance"})
_ALLOWED_REC_STATUSES = frozenset({"confirmed", "dismissed", "resolved"})


def _sse_stream(generator):
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def _build_employment_system_prompt(graph) -> str:
    emp = graph.employment
    lines = [
        "Du er en AI-assistent der hjælper med spørgsmål om et specifikt ansættelsesforhold.",
        "",
        f"ANSÆTTELSESFORHOLD: {emp.get('title', 'Ukendt stilling')} hos {emp.get('organisation', 'Ukendt virksomhed')}",
        f"Periode: {emp.get('period_start', '?')} – {emp.get('period_end') or 'nu'}",
        "",
        "KENDTE FAKTA FRA DOKUMENTER:",
    ]
    if graph.facts:
        for fact in graph.facts:
            conf = fact.get("confidence", "?")
            val = fact.get("value", "?")
            unit = f" {fact['unit']}" if fact.get("unit") else ""
            fact_type = fact.get("fact_type", "")
            page = fact.get("source_page")
            req = " [kræver bekræftelse]" if fact.get("requires_confirmation") else ""
            page_str = f", side {page}" if page else ""
            lines.append(f"  • {fact_type}: {val}{unit} (confidence: {conf}{page_str}{req})")
    else:
        lines.append("  Ingen fakta ekstraheret endnu.")

    pending_recs = [r for r in graph.recommendations if r.get("status") == "pending"]
    if pending_recs:
        lines.extend(["", "ÅBNE ANBEFALINGER:"])
        for rec in pending_recs:
            lines.append(f"  ⚠️ [{rec.get('severity', '').upper()}] {rec['title']}: {rec['description']}")

    if graph.analyses:
        lines.extend(["", "ANALYSERESULTATER:"])
        for a in graph.analyses:
            lines.append(f"  • {a.get('analysis_type', '')}: {a.get('discrepancies_found', 0)} afvigelser")

    lines.extend([
        "",
        "INSTRUKTIONER:",
        "- Svar udelukkende baseret på de ovenstående kendte fakta fra ansættelsesforholdet",
        "- Henvis til konkrete fakta, når du svarer",
        "- Sig eksplicit 'det fremgår ikke af de uploadede dokumenter' hvis oplysningen ikke er tilgængelig",
        "- Giv ikke generel juridisk rådgivning — henvis til fagforening eller advokat ved konkrete tvister",
    ])
    return "\n".join(lines)


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


class EmploymentIn(BaseModel):
    title: str
    organisation: str | None = None
    experience_type: str = "job"
    period_start: str | None = None
    period_end: str | None = None
    description: str | None = None


class RecommendationUpdateRequest(BaseModel):
    status: str


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


class EmploymentChatRequest(BaseModel):
    messages: list[dict] = []


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
        user_id=user["id"],
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


@router.get("/employments")
async def list_employments(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """List all Work Graph employments (job + freelance) for the current user."""
    result = (
        supabase.table("experiences")
        .select("id, title, organisation, experience_type, period_start, period_end, description, created_at")
        .eq("user_id", user["id"])
        .in_("experience_type", ["job", "freelance"])
        .order("period_start", desc=True)
        .execute()
    )
    return result.data or []


@router.post("/employments", status_code=201)
async def create_employment(
    body: EmploymentIn,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Create a new Work Graph employment (inserts into experiences table)."""
    if body.experience_type not in _ALLOWED_EXPERIENCE_TYPES:
        raise HTTPException(422, detail="experience_type must be job or freelance")

    row: dict = {
        "user_id": user["id"],
        "title": body.title,
        "experience_type": body.experience_type,
    }
    if body.organisation is not None:
        row["organisation"] = body.organisation
    if body.period_start is not None:
        row["period_start"] = body.period_start
    if body.period_end is not None:
        row["period_end"] = body.period_end
    if body.description is not None:
        row["description"] = body.description

    result = supabase.table("experiences").insert(row).execute()
    if not result.data:
        raise HTTPException(500, detail="Failed to create employment")
    return result.data[0]


@router.patch("/recommendations/{rec_id}")
async def update_recommendation(
    rec_id: str,
    body: RecommendationUpdateRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Update the status of a recommendation (confirmed / dismissed / resolved)."""
    if body.status not in _ALLOWED_REC_STATUSES:
        raise HTTPException(
            422,
            detail=f"status must be one of: {', '.join(sorted(_ALLOWED_REC_STATUSES))}",
        )

    existing = (
        supabase.table("employment_recommendations")
        .select("id")
        .eq("id", rec_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(404, detail="Recommendation not found")

    result = (
        supabase.table("employment_recommendations")
        .update({"status": body.status})
        .eq("id", rec_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(500, detail="Update failed")
    return result.data[0]


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
    graph = await svc.get_graph(user_id=user["id"], employment_id=employment_id)
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
    result = await svc.analyze(user_id=user["id"], employment_id=employment_id)
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
    """Return all Recommendations for an Employment, newest first."""
    svc = EmploymentGraphService(supabase)
    graph = await svc.get_graph(user_id=user["id"], employment_id=employment_id)
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


@router.post("/{employment_id}/chat")
@limiter.limit(LIMIT_COACH)
async def chat_with_employment(
    request: Request,
    employment_id: str,
    body: EmploymentChatRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    AI chat with full Employment context (SSE streaming).

    The system prompt is built automatically from the Employment Graph —
    all known facts, analyses, and open recommendations are injected.
    The AI agent never looks up data itself; all context is pre-built here.
    """
    import asyncio

    from app.agents.employment_chat_agent import EmploymentChatAgent
    from app.providers.litellm_provider import NoProviderKeyError

    svc = EmploymentGraphService(supabase)
    graph = await svc.get_graph(user_id=user["id"], employment_id=employment_id)
    if graph is None:
        raise HTTPException(404, detail="Employment not found")

    system_prompt = _build_employment_system_prompt(graph)
    agent = EmploymentChatAgent(user_id=user["id"], supabase=supabase)

    async def event_stream():
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def producer():
            try:
                result = await agent.run({"system_prompt": system_prompt, "messages": body.messages})
                stream = result.metadata.get("stream")
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        await queue.put(("data", _json.dumps({"type": "chunk", "content": delta})))
            except NoProviderKeyError as exc:
                await queue.put(("data", _json.dumps({"type": "error", "code": "no_api_key", "content": str(exc)})))
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error("employment_chat_error employment=%s error=%s", employment_id, exc)
                await queue.put(("data", _json.dumps({"type": "error", "content": str(exc)})))
            finally:
                try:
                    queue.put_nowait(("done", ""))
                except asyncio.QueueFull:
                    pass

        task = asyncio.create_task(producer())
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                if kind == "done":
                    yield f"data: {_json.dumps({'type': 'done'})}\n\n"
                    break
                yield f"data: {payload}\n\n"
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return _sse_stream(event_stream())
