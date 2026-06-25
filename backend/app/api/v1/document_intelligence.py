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
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.core.rate_limit import LIMIT_COACH, limiter

logger = logging.getLogger("app.document_intelligence")
router = APIRouter(prefix="/document-intelligence", tags=["Document Intelligence"])

_ALLOWED_DOC_TYPES = frozenset({"contract", "agreement", "payslip"})
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF/DOCX/TXT. Reuses pdfplumber + python-docx (already in deps)."""
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            import pdfplumber
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
        logger.warning("text_extraction_failed file=%s error=%s", filename, exc)
        return file_bytes.decode("utf-8", errors="replace")


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


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(LIMIT_COACH)
async def analyze_document(
    request: Request,
    doc_type: str = Form(..., description="contract | agreement | payslip"),
    file: UploadFile = File(...),
    employment_id: str | None = Form(None, description="Optional FK to experiences table (Work Graph)"),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Upload a document and extract structured facts into Memory and Work Graph.

    Runs the full Document Intelligence pipeline:
    1. Extract text (PDF/DOCX/TXT)
    2. Fact extraction via AI Gateway (typed facts + confidence + provenance)
    3. Store all facts in document_facts (with provenance)
    4. Store high/medium facts as career_memories (vector-searchable by agents)
    """
    if doc_type not in _ALLOWED_DOC_TYPES:
        raise HTTPException(
            422,
            detail=f"doc_type must be one of: {', '.join(sorted(_ALLOWED_DOC_TYPES))}",
        )

    content = await file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(413, detail="File exceeds 10 MB limit")

    # 1. Extract text
    extracted_text = _extract_text(content, file.filename or "")
    if not extracted_text.strip():
        raise HTTPException(
            422,
            detail="Could not extract text from document. Ensure the PDF has a text layer.",
        )

    # 2. Persist document in coach_documents (source of truth for provenance)
    doc_row = supabase.table("coach_documents").insert({
        "user_id":        user["id"],
        "doc_type":       doc_type,
        "file_name":      file.filename or "document",
        "file_size":      len(content),
        "extracted_text": extracted_text,
        "metadata":       {"source": "document_intelligence"},
    }).execute()

    if not doc_row.data:
        raise HTTPException(500, detail="Failed to save document metadata")

    document_id: str = doc_row.data[0]["id"]

    # 3. Run pipeline
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
        )
    except Exception as exc:
        logger.error(
            "document_intelligence_failed document=%s error=%s", document_id, exc
        )
        raise HTTPException(500, detail=f"Analysis pipeline failed: {exc}")

    return AnalyzeResponse(
        extraction_run_id=summary.extraction_run_id,
        document_id=document_id,
        facts_total=summary.facts_total,
        facts_high=summary.facts_high,
        facts_medium=summary.facts_medium,
        facts_low=summary.facts_low,
        facts_requiring_confirmation=summary.facts_requiring_confirmation,
        memories_created=summary.memories_created,
        document_summary=summary.document_summary,
        extraction_quality=summary.extraction_quality,
        model_used=summary.model_used,
        warnings=summary.warnings,
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
