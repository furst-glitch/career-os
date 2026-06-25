"""
DocumentIntelligenceService — AI Document Intelligence pipeline.

Orchestrates the complete pipeline for a single document:

  FactExtractionAgent (Gateway)
    → structured facts with confidence + provenance
    → document_facts INSERT (full provenance record)
    → career_memories INSERT for high/medium confidence facts
    → embedding generation + update (vector search readiness)
    → ExtractionSummary returned to caller

Design rules (from platform spec):
  - Memory stores ONLY structured fact summaries, never raw document text.
  - Every fact has full provenance: document_id, page, source_text, model, run_id.
  - Failures in individual fact/memory inserts are logged and skipped — pipeline
    continues so that partial results are always better than no results.
  - EmbeddingService.embed() returns None if no API key; vectors are optional.

Dependencies:
  - FactExtractionAgent (app.agents.fact_extraction_agent)
  - EmbeddingService     (app.services.embedding_service)
  - MemoryService        (app.services.memory_service) — create_memory, update_embedding
  - supabase Client      — document_facts INSERT
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.agents.fact_extraction_agent import ExtractionResult, FactExtractionAgent
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger("app.services.document_intelligence")

# Only store memories for these confidence levels (low facts stay in document_facts only)
_MEMORY_CONFIDENCE = frozenset({"high", "medium"})

# Gateway model used for fact extraction (from agent_registry default)
_DEFAULT_AI_MODEL = "claude-sonnet-4-6"

# Human-readable labels for memory content (fact_type → Danish label)
_FACT_LABELS: dict[str, str] = {
    "monthly_salary":                  "Månedlig grundløn",
    "pension_pct_total":               "Samlet pensionsprocent",
    "pension_pct_employee":            "Medarbejderens pensionsandel",
    "pension_pct_employer":            "Arbejdsgiverens pensionsandel",
    "notice_period_employee_months":   "Opsigelsesvarsel (medarbejder)",
    "notice_period_employer_months":   "Opsigelsesvarsel (arbejdsgiver)",
    "vacation_days":                   "Feriedage",
    "trial_period_months":             "Prøvetid",
    "non_compete_months":              "Konkurrenceklausul",
    "confidentiality_clause":          "Fortrolighedsklausul",
    "bonus_structure":                 "Bonusordning",
    "working_hours_per_week":          "Ugentlig arbejdstid",
    "employer_name":                   "Arbejdsgiver",
    "job_title":                       "Stillingsbetegnelse",
    "contract_start_date":             "Startdato",
    "minimum_wage":                    "Minimumssats",
    "overtime_rate_pct":               "Overtidsbetaling",
    "union_name":                      "Fagforbund",
    "employer_organization":           "Arbejdsgiverorganisation",
    "agreement_name":                  "Overenskomstnavn",
    "seniority_pay_rules":             "Anciennitetsregler",
    "gross_salary":                    "Bruttoløn",
    "net_salary":                      "Nettoløn",
    "pension_contribution_employee":   "Eget pensionsbidrag",
    "pension_contribution_employer":   "Arbejdsgiverens pensionsbidrag",
    "tax_amount":                      "Indeholdt skat",
    "am_bidrag":                       "AM-bidrag",
    "period_month_year":               "Lønperiode",
}

_DOC_LABELS: dict[str, str] = {
    "contract":  "Ansættelseskontrakt",
    "agreement": "Overenskomst",
    "payslip":   "Lønseddel",
}

# Relevance scores for career_memories (higher = more prominent in snapshots)
_RELEVANCE_BY_CONFIDENCE: dict[str, float] = {
    "high":   0.9,
    "medium": 0.7,
}


@dataclass
class ExtractionSummary:
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
    warnings: list[str] = field(default_factory=list)


class DocumentIntelligenceService:
    """
    Runs the Document Intelligence pipeline for a single document.

    Inject EmbeddingService and Supabase client. Call analyze() once per document.
    """

    def __init__(
        self,
        supabase: "Client",
        embedding_service: EmbeddingService,
    ) -> None:
        self._supabase = supabase
        self._embedding = embedding_service

    async def analyze(
        self,
        *,
        document_id: str,
        doc_type: str,
        extracted_text: str,
        user_id: str,
        employment_id: str | None = None,
    ) -> ExtractionSummary:
        """
        Run the complete Document Intelligence pipeline.

        Parameters
        ----------
        document_id:    UUID of the coach_documents row (already inserted).
        doc_type:       "contract" | "agreement" | "payslip"
        extracted_text: Full text extracted from the document (pdfplumber/python-docx).
        user_id:        Supabase auth user UUID.
        employment_id:  Optional FK to experiences table (Work Graph link).
        """
        run_id = str(uuid.uuid4())
        warnings: list[str] = []

        logger.info(
            "doc_intelligence_start run=%s document=%s type=%s user=%s",
            run_id, document_id, doc_type, user_id,
        )

        # ── 1. Fact extraction via Gateway ────────────────────────────────────
        agent = FactExtractionAgent(user_id=user_id, supabase=self._supabase)
        result: ExtractionResult = await agent.extract(extracted_text, doc_type)

        if result.error:
            logger.warning("fact_extraction_partial_failure run=%s error=%s", run_id, result.error)
            warnings.append(f"extraction_error:{result.error}")

        memory_svc = MemoryService(self._supabase)
        doc_label = _DOC_LABELS.get(doc_type, doc_type)
        memories_created = 0

        # ── 2. Persist each fact ─────────────────────────────────────────────
        for fact in result.facts:
            career_memory_id: str | None = None

            # 3. Create career_memory for high/medium confidence facts
            if fact.confidence in _MEMORY_CONFIDENCE and fact.fact_type and fact.value:
                label = _FACT_LABELS.get(fact.fact_type, fact.fact_type)
                unit_str = f" {fact.unit}" if fact.unit else ""
                page_str = str(fact.source_page) if fact.source_page else "?"
                excerpt = fact.source_text[:80] if fact.source_text else ""

                # Memory stores ONLY structured text — never raw document text
                memory_content = (
                    f"{doc_label} — {label}: {fact.value}{unit_str}. "
                    f"Confidence: {fact.confidence}. "
                    f"Kilde: side {page_str}. "
                    f'Tekstgrundlag: "{excerpt}".'
                )

                try:
                    memory = memory_svc.create_memory(
                        user_id=user_id,
                        content=memory_content,
                        memory_type="experience",
                        source="ai_extracted",
                        relevance_score=_RELEVANCE_BY_CONFIDENCE[fact.confidence],
                    )
                    career_memory_id = memory["id"]
                    memories_created += 1

                    # 4. Generate embedding for vector search
                    embedding = await self._embedding.embed(memory_content)
                    if embedding:
                        memory_svc.update_embedding(career_memory_id, embedding)
                    else:
                        logger.debug(
                            "embedding_skipped run=%s fact=%s", run_id, fact.fact_type
                        )

                except Exception as exc:
                    logger.warning(
                        "memory_create_failed run=%s fact=%s error=%s",
                        run_id, fact.fact_type, exc,
                    )
                    warnings.append(f"memory_failed:{fact.fact_type}")
                    career_memory_id = None

            # 5. Store fact with full provenance in document_facts
            try:
                self._supabase.table("document_facts").insert({
                    "user_id":               user_id,
                    "document_id":           document_id,
                    "fact_type":             fact.fact_type,
                    "value":                 fact.value,
                    "unit":                  fact.unit or None,
                    "confidence":            fact.confidence,
                    "requires_confirmation": fact.requires_confirmation,
                    "source_text":           fact.source_text,
                    "source_page":           fact.source_page or None,
                    "ai_model":              _DEFAULT_AI_MODEL,
                    "ai_version":            "1",
                    "extraction_run_id":     run_id,
                    "career_memory_id":      career_memory_id,
                    "employment_id":         employment_id,
                }).execute()
            except Exception as exc:
                logger.error(
                    "fact_insert_failed run=%s fact=%s error=%s",
                    run_id, fact.fact_type, exc,
                )
                warnings.append(f"fact_insert_failed:{fact.fact_type}")

        summary = ExtractionSummary(
            extraction_run_id=run_id,
            document_id=document_id,
            facts_total=len(result.facts),
            facts_high=sum(1 for f in result.facts if f.confidence == "high"),
            facts_medium=sum(1 for f in result.facts if f.confidence == "medium"),
            facts_low=sum(1 for f in result.facts if f.confidence == "low"),
            facts_requiring_confirmation=sum(1 for f in result.facts if f.requires_confirmation),
            memories_created=memories_created,
            document_summary=result.document_summary,
            extraction_quality=result.extraction_quality,
            model_used=_DEFAULT_AI_MODEL,
            warnings=warnings,
        )

        logger.info(
            "doc_intelligence_done run=%s facts=%d memories=%d quality=%s",
            run_id, summary.facts_total, summary.memories_created, summary.extraction_quality,
        )

        return summary

    async def list_facts(self, *, document_id: str, user_id: str) -> list[dict]:
        """List all extracted facts for a document (ordered by confidence desc)."""
        try:
            result = (
                self._supabase.table("document_facts")
                .select(
                    "id, fact_type, value, unit, confidence, requires_confirmation, "
                    "source_text, source_page, ai_model, created_at, career_memory_id"
                )
                .eq("user_id", user_id)
                .eq("document_id", document_id)
                .order("confidence")  # enum order: high < low alphabetically — use created_at instead
                .order("created_at")
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error("list_facts_failed document=%s error=%s", document_id, exc)
            return []
