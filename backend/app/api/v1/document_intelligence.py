"""
Document Intelligence API

POST /document-intelligence/analyze
  Upload a document and run the full AI fact-extraction pipeline.
  Extracts typed facts with confidence + provenance into document_facts.
  High/medium facts are also stored as career_memories (vector-searchable by agents).

GET  /document-intelligence/facts/{document_id}
  List all extracted facts for a document.
"""

from __future__ import annotations

import io
import json as _json
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.core.rate_limit import LIMIT_COACH, limiter
from app.services.event_service import (
    EV_DOC_ANALYZED, EV_DOC_FAILED, EV_DOC_UPLOADED, EV_FACT_VERIFIED,
    EventService,
)

logger = logging.getLogger("app.document_intelligence")
router = APIRouter(prefix="/document-intelligence", tags=["Document Intelligence"])

_ALLOWED_DOC_TYPES = frozenset({"contract", "agreement", "payslip", "pension"})
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF/DOCX/TXT. Reuses pdfplumber + python-docx (already in deps)."""
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            import pdfplumber
            import pdfplumber.utils
            if not file_bytes.startswith(b"%PDF"):
                logger.warning("invalid_pdf_magic_bytes file=%s", filename)
                return ""
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            return "\n".join(p for p in pages if p.strip())
        elif name.endswith(".docx"):
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        else:
            return file_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        exc_name = type(exc).__name__
        if "NotPermitted" in exc_name or "PermissionError" in exc_name or "encrypted" in str(exc).lower():
            logger.warning("pdf_protected file=%s error=%s", filename, exc)
            raise ValueError("PDF er kodeordsbeskyttet — fjern kodeordet og prøv igen")
        logger.warning("text_extraction_failed file=%s error=%s", filename, exc)
        return ""


# ── Schemas ───────────────────────────────────────────────────────────────────


class AnalyzeResponse(BaseModel):
    extraction_run_id: str
    document_id: str
    facts_total: int
    facts_high: int
    facts_medium: int
    facts_low: int
    facts_requiring_confirmation: int
    memories_created: int
    document_summary: str
    extraction_quality: str
    model_used: str
    warnings: list[str]


class FactItem(BaseModel):
    id: str
    fact_type: str
    value: str
    unit: str | None
    confidence: str
    requires_confirmation: bool
    source_text: str
    source_page: int | None
    ai_model: str
    created_at: str
    career_memory_id: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/analyze")
@limiter.limit(LIMIT_COACH)
async def analyze_document(
    request: Request,
    background_tasks: BackgroundTasks,
    doc_type: str = Form(..., description="contract | agreement | payslip | pension"),
    file: UploadFile = File(...),
    employment_id: str | None = Form(None, description="Optional FK to experiences table (Work Graph)"),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Upload a document and extract structured facts into Memory and Work Graph.

    Returns an SSE stream with progress events, then a final "done" event
    containing the full AnalyzeResponse payload. Embeddings are generated
    as a BackgroundTask after the stream completes (reduces wait from ~20s to ~8s).
    """
    import time as _time

    def _evt(type_: str, **kw: object) -> str:
        return f"data: {_json.dumps({'type': type_, **kw})}\n\n"

    async def event_stream():
        nonlocal employment_id
        _events = EventService(supabase)
        t_start = _time.monotonic()

        yield _evt("progress", step="validating", pct=5, message="Validerer dokument...")

        if doc_type not in _ALLOWED_DOC_TYPES:
            _events.emit(EV_DOC_FAILED, user_id=user["id"], doc_type=doc_type, error_step="validation", employment_id=employment_id)
            yield _evt("error", message=f"Ugyldig dokumenttype. Tilladt: {', '.join(sorted(_ALLOWED_DOC_TYPES))}")
            return

        if file.size and file.size > _MAX_FILE_BYTES:
            yield _evt("error", message="Filen er for stor — maks 10 MB")
            return

        content = await file.read()
        if len(content) > _MAX_FILE_BYTES:
            yield _evt("error", message="Filen er for stor — maks 10 MB")
            return

        yield _evt("progress", step="extracting", pct=20, message="Udtrækker tekst fra dokument...")

        try:
            extracted_text = _extract_text(content, file.filename or "")
        except ValueError as exc:
            _events.emit(EV_DOC_FAILED, user_id=user["id"], doc_type=doc_type, error_step="extraction", employment_id=employment_id)
            yield _evt("error", message=str(exc))
            return

        if not extracted_text.strip():
            _events.emit(EV_DOC_FAILED, user_id=user["id"], doc_type=doc_type, error_step="empty_text", employment_id=employment_id)
            yield _evt("error", message="Kunne ikke udtrække tekst — sikr at PDF'en har et tekstlag (ikke skannet billede)")
            return

        yield _evt("progress", step="saving", pct=30, message="Gemmer dokument...")

        doc_insert: dict = {
            "user_id":        user["id"],
            "doc_type":       doc_type,
            "file_name":      file.filename or "document",
            "file_size":      len(content),
            "extracted_text": extracted_text,
            "metadata":       {"source": "document_intelligence"},
        }
        if employment_id:
            doc_insert["employment_id"] = employment_id

        doc_row = supabase.table("coach_documents").insert(doc_insert).execute()

        if not doc_row.data:
            yield _evt("error", message="Kunne ikke gemme dokumentet — prøv igen")
            return

        document_id: str = doc_row.data[0]["id"]

        # WP1: Emit document.uploaded after save
        _events.emit(
            EV_DOC_UPLOADED,
            user_id=user["id"],
            document_id=document_id,
            employment_id=employment_id,
            doc_type=doc_type,
            file_size=len(content),
        )

        yield _evt("progress", step="ai", pct=45, message="AI analyserer fakta (tager typisk 10-20 sekunder)...")

        from app.core.config import settings
        from app.services.document_intelligence_service import DocumentIntelligenceService
        from app.services.embedding_service import EmbeddingService

        embedding_svc = EmbeddingService.from_settings(settings)
        svc = DocumentIntelligenceService(supabase=supabase, embedding_service=embedding_svc)

        try:
            summary = await svc.analyze(
                document_id=document_id,
                doc_type=doc_type,
                extracted_text=extracted_text,
                user_id=user["id"],
                employment_id=employment_id,
                defer_embeddings=True,
            )
        except Exception as exc:
            logger.error("document_intelligence_failed document=%s error=%s", document_id, exc, exc_info=True)
            _events.emit(EV_DOC_FAILED, user_id=user["id"], document_id=document_id, doc_type=doc_type, error_step="ai_analysis", employment_id=employment_id)
            yield _evt("error", message="Dokumentanalyse fejlede — prøv igen")
            return

        # Embeddings run after the stream is fully sent (BackgroundTasks fire after generator exhausts)
        if summary.pending_embeddings:
            background_tasks.add_task(svc.compute_pending_embeddings, summary.pending_embeddings)

        # WP1: Emit document.analyzed with full metrics
        duration_ms = round((_time.monotonic() - t_start) * 1000)
        _events.emit(
            EV_DOC_ANALYZED,
            user_id=user["id"],
            document_id=document_id,
            employment_id=employment_id,
            doc_type=doc_type,
            facts_total=summary.facts_total,
            facts_high=summary.facts_high,
            facts_medium=summary.facts_medium,
            facts_low=summary.facts_low,
            memories_created=summary.memories_created,
            duration_ms=duration_ms,
        )

        yield _evt(
            "progress", step="storing", pct=88,
            message=f"{summary.facts_total} fakta gemt — søgeindeks opdateres i baggrunden...",
        )
        yield _evt("done", data={
            "extraction_run_id":          summary.extraction_run_id,
            "document_id":                document_id,
            "facts_total":                summary.facts_total,
            "facts_high":                 summary.facts_high,
            "facts_medium":               summary.facts_medium,
            "facts_low":                  summary.facts_low,
            "facts_requiring_confirmation": summary.facts_requiring_confirmation,
            "memories_created":           summary.memories_created,
            "document_summary":           summary.document_summary,
            "extraction_quality":         summary.extraction_quality,
            "model_used":                 summary.model_used,
            "warnings":                   summary.warnings,
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.get("/facts/{document_id}", response_model=list[FactItem])
@limiter.limit(LIMIT_COACH)
async def list_document_facts(
    request: Request,
    document_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """List all extracted facts for a document (ordered by created_at)."""
    from app.services.document_intelligence_service import DocumentIntelligenceService
    from app.services.embedding_service import EmbeddingService

    svc = DocumentIntelligenceService(
        supabase=supabase,
        embedding_service=EmbeddingService(),  # no embedding needed for listing
    )
    facts = await svc.list_facts(document_id=document_id, user_id=user["id"])
    return [FactItem(**f) for f in facts]


class FactUpdateRequest(BaseModel):
    value: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    requires_confirmation: bool | None = None
    reason: str | None = None  # Human verification reason — stored in verification_reason


@router.patch("/facts/{fact_id}")
@limiter.limit(LIMIT_COACH)
async def update_fact(
    request: Request,
    fact_id: str,
    body: FactUpdateRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Human in the Loop: update a fact's value, confidence, or confirmation state.

    User decisions are final — the AI extraction pipeline never overwrites verified facts.
    Audit trail: verified_by, verified_at, previous_value, verification_reason saved automatically.
    """
    from datetime import datetime, timezone

    existing = (
        supabase.table("document_facts")
        .select("id, value, fact_type, employment_id")
        .eq("id", fact_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(404, detail="Fact not found")

    updates: dict = {}
    if body.value is not None:
        updates["value"] = body.value
        # Save old value for audit trail
        updates["previous_value"] = existing.data[0]["value"]
    if body.confidence is not None:
        updates["confidence"] = body.confidence
    if body.requires_confirmation is not None:
        updates["requires_confirmation"] = body.requires_confirmation

    if not updates:
        raise HTTPException(422, detail="No fields to update")

    # Mark as human-verified — user decisions always take priority over AI
    updates["verified_by"] = user["id"]
    updates["verified_at"] = datetime.now(timezone.utc).isoformat()
    if body.reason:
        updates["verification_reason"] = body.reason

    result = (
        supabase.table("document_facts")
        .update(updates)
        .eq("id", fact_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(500, detail="Update failed")

    # WP1: Emit fact.verified event
    existing_row = existing.data[0]
    EventService(supabase).emit(
        EV_FACT_VERIFIED,
        user_id=user["id"],
        employment_id=existing_row.get("employment_id"),
        fact_type=existing_row.get("fact_type"),
        had_value_change=body.value is not None,
        confidence=body.confidence or result.data[0].get("confidence"),
    )

    return result.data[0]
