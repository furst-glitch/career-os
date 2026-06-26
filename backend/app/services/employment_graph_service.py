"""
EmploymentGraphService — aggregates the complete Employment Graph.

Returns all data tied to one Employment (experiences row):
  employment        — the experiences row (Work Graph anchor)
  documents         — coach_documents linked to this employment
  facts             — document_facts extracted from those documents
  analyses          — employment_analyses (cross-document comparison results)
  recommendations   — employment_recommendations derived from analyses

All sub-queries are independent; a DB error on one layer returns an empty list
for that layer without aborting the whole graph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("app.services.employment_graph")


# ── Domain object ─────────────────────────────────────────────────────────────


@dataclass
class EmploymentGraph:
    employment: dict
    documents: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)
    analyses: list[dict] = field(default_factory=list)
    recommendations: list[dict] = field(default_factory=list)
    # Aggregate counts — convenience for the API layer
    facts_total: int = 0
    facts_requiring_confirmation: int = 0
    open_recommendations: int = 0


# ── Service ───────────────────────────────────────────────────────────────────


class EmploymentGraphService:
    """
    Read-only aggregator. Never writes data.
    Call get_graph() to retrieve the full Employment Graph for one employment_id.
    """

    def __init__(self, supabase) -> None:
        self._supabase = supabase

    async def get_graph(
        self, user_id: str, employment_id: str
    ) -> EmploymentGraph | None:
        """
        Return the complete graph or None if the employment doesn't exist
        (or doesn't belong to user_id).
        """
        employment = self._fetch_employment(user_id, employment_id)
        if not employment:
            return None

        documents = self._fetch_documents(user_id, employment_id)
        facts = self._fetch_facts(user_id, employment_id)
        analyses = self._fetch_analyses(user_id, employment_id)
        recommendations = self._fetch_recommendations(user_id, employment_id)

        return EmploymentGraph(
            employment=employment,
            documents=documents,
            facts=facts,
            analyses=analyses,
            recommendations=recommendations,
            facts_total=len(facts),
            facts_requiring_confirmation=sum(
                1 for f in facts if f.get("requires_confirmation")
            ),
            open_recommendations=sum(
                1 for r in recommendations if r.get("status") == "pending"
            ),
        )

    # ── Private fetchers ──────────────────────────────────────────────────────

    def _fetch_employment(self, user_id: str, employment_id: str) -> dict | None:
        try:
            result = (
                self._supabase.table("experiences")
                .select(
                    "id, title, organisation, experience_type, "
                    "period_start, period_end, description"
                )
                .eq("user_id", user_id)
                .eq("id", employment_id)
                .limit(1)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.error(
                "fetch_employment_failed id=%s error=%s", employment_id, exc
            )
            return None

    def _fetch_documents(self, user_id: str, employment_id: str) -> list[dict]:
        try:
            result = (
                self._supabase.table("coach_documents")
                .select("id, doc_type, file_name, file_size, created_at")
                .eq("user_id", user_id)
                .eq("employment_id", employment_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error(
                "fetch_documents_failed employment=%s error=%s", employment_id, exc
            )
            return []

    def _fetch_facts(self, user_id: str, employment_id: str) -> list[dict]:
        try:
            result = (
                self._supabase.table("document_facts")
                .select(
                    "id, fact_type, value, unit, confidence, requires_confirmation, "
                    "source_text, source_page, document_id, career_memory_id, "
                    "ai_model, extraction_run_id, created_at, "
                    "verified_by, verified_at, previous_value, verification_reason"
                )
                .eq("user_id", user_id)
                .eq("employment_id", employment_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error(
                "fetch_facts_failed employment=%s error=%s", employment_id, exc
            )
            return []

    def _fetch_analyses(self, user_id: str, employment_id: str) -> list[dict]:
        try:
            result = (
                self._supabase.table("employment_analyses")
                .select(
                    "id, analysis_type, discrepancies_found, result_json, created_at"
                )
                .eq("user_id", user_id)
                .eq("employment_id", employment_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error(
                "fetch_analyses_failed employment=%s error=%s", employment_id, exc
            )
            return []

    def _fetch_recommendations(self, user_id: str, employment_id: str) -> list[dict]:
        try:
            result = (
                self._supabase.table("employment_recommendations")
                .select(
                    "id, recommendation_type, severity, title, description, "
                    "fact_types, affected_fact_ids, analysis_id, status, created_at"
                )
                .eq("user_id", user_id)
                .eq("employment_id", employment_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error(
                "fetch_recommendations_failed employment=%s error=%s",
                employment_id, exc,
            )
            return []
