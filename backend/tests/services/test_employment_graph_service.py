"""
Unit tests for EmploymentGraphService (app.services.employment_graph_service).
All DB calls mocked. Tests verify aggregation logic and error resilience.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.employment_graph_service import EmploymentGraph, EmploymentGraphService

# ── Helpers ───────────────────────────────────────────────────────────────────

_EMPLOYMENT = {
    "id": "emp-1",
    "title": "Senior Controller",
    "organisation": "ABC A/S",
    "experience_type": "job",
    "period_start": "2023-01-01",
    "period_end": None,
    "description": "Økonomiansvarlig",
}


def _make_svc(
    employment: dict | None,
    documents: list[dict] | None = None,
    facts: list[dict] | None = None,
    analyses: list[dict] | None = None,
    recs: list[dict] | None = None,
) -> EmploymentGraphService:
    supabase = MagicMock()

    def table_factory(name: str):
        m = MagicMock()
        m.select.return_value = m
        m.eq.return_value = m
        m.limit.return_value = m
        m.order.return_value = m
        if name == "experiences":
            m.execute.return_value = MagicMock(
                data=[employment] if employment else []
            )
        elif name == "coach_documents":
            m.execute.return_value = MagicMock(data=documents or [])
        elif name == "document_facts":
            m.execute.return_value = MagicMock(data=facts or [])
        elif name == "employment_analyses":
            m.execute.return_value = MagicMock(data=analyses or [])
        elif name == "employment_recommendations":
            m.execute.return_value = MagicMock(data=recs or [])
        else:
            m.execute.return_value = MagicMock(data=[])
        return m

    supabase.table.side_effect = table_factory
    return EmploymentGraphService(supabase)


# ── get_graph — basic ─────────────────────────────────────────────────────────


class TestGetGraph:
    @pytest.mark.asyncio
    async def test_returns_none_when_employment_not_found(self):
        svc = _make_svc(employment=None)
        result = await svc.get_graph("user-1", "emp-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_graph_when_employment_exists(self):
        svc = _make_svc(_EMPLOYMENT)
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph is not None
        assert isinstance(graph, EmploymentGraph)

    @pytest.mark.asyncio
    async def test_employment_data_included(self):
        svc = _make_svc(_EMPLOYMENT)
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph.employment["id"] == "emp-1"
        assert graph.employment["organisation"] == "ABC A/S"

    @pytest.mark.asyncio
    async def test_documents_included(self):
        docs = [{"id": "doc-1", "doc_type": "contract", "file_name": "k.pdf"}]
        svc = _make_svc(_EMPLOYMENT, documents=docs)
        graph = await svc.get_graph("user-1", "emp-1")
        assert len(graph.documents) == 1
        assert graph.documents[0]["doc_type"] == "contract"

    @pytest.mark.asyncio
    async def test_facts_included(self):
        facts = [
            {"id": "f-1", "fact_type": "monthly_salary", "requires_confirmation": False},
        ]
        svc = _make_svc(_EMPLOYMENT, facts=facts)
        graph = await svc.get_graph("user-1", "emp-1")
        assert len(graph.facts) == 1
        assert graph.facts[0]["fact_type"] == "monthly_salary"

    @pytest.mark.asyncio
    async def test_analyses_included(self):
        analyses = [{"id": "a-1", "analysis_type": "cross_document", "discrepancies_found": 2}]
        svc = _make_svc(_EMPLOYMENT, analyses=analyses)
        graph = await svc.get_graph("user-1", "emp-1")
        assert len(graph.analyses) == 1
        assert graph.analyses[0]["discrepancies_found"] == 2

    @pytest.mark.asyncio
    async def test_recommendations_included(self):
        recs = [
            {"id": "r-1", "recommendation_type": "salary_mismatch",
             "severity": "high", "status": "pending"},
        ]
        svc = _make_svc(_EMPLOYMENT, recs=recs)
        graph = await svc.get_graph("user-1", "emp-1")
        assert len(graph.recommendations) == 1
        assert graph.recommendations[0]["severity"] == "high"


# ── Aggregate counts ──────────────────────────────────────────────────────────


class TestAggregateCounts:
    @pytest.mark.asyncio
    async def test_facts_total(self):
        facts = [
            {"id": "f-1", "fact_type": "monthly_salary", "requires_confirmation": False},
            {"id": "f-2", "fact_type": "pension_pct_total", "requires_confirmation": False},
        ]
        svc = _make_svc(_EMPLOYMENT, facts=facts)
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph.facts_total == 2

    @pytest.mark.asyncio
    async def test_facts_requiring_confirmation_count(self):
        facts = [
            {"id": "f-1", "fact_type": "monthly_salary", "requires_confirmation": False},
            {"id": "f-2", "fact_type": "bonus_structure", "requires_confirmation": True},
            {"id": "f-3", "fact_type": "non_compete_months", "requires_confirmation": True},
        ]
        svc = _make_svc(_EMPLOYMENT, facts=facts)
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph.facts_requiring_confirmation == 2

    @pytest.mark.asyncio
    async def test_open_recommendations_counts_only_pending(self):
        recs = [
            {"id": "r-1", "status": "pending"},
            {"id": "r-2", "status": "resolved"},
            {"id": "r-3", "status": "pending"},
            {"id": "r-4", "status": "dismissed"},
        ]
        svc = _make_svc(_EMPLOYMENT, recs=recs)
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph.open_recommendations == 2

    @pytest.mark.asyncio
    async def test_empty_graph_counts_are_zero(self):
        svc = _make_svc(_EMPLOYMENT)
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph.facts_total == 0
        assert graph.facts_requiring_confirmation == 0
        assert graph.open_recommendations == 0


# ── Error resilience ──────────────────────────────────────────────────────────


class TestErrorResilience:
    def _make_partial_error_svc(self, failing_table: str) -> EmploymentGraphService:
        supabase = MagicMock()

        def table_factory(name: str):
            m = MagicMock()
            m.select.return_value = m
            m.eq.return_value = m
            m.limit.return_value = m
            m.order.return_value = m
            if name == failing_table:
                m.execute.side_effect = RuntimeError("db down")
            elif name == "experiences":
                m.execute.return_value = MagicMock(data=[_EMPLOYMENT])
            else:
                m.execute.return_value = MagicMock(data=[])
            return m

        supabase.table.side_effect = table_factory
        return EmploymentGraphService(supabase)

    @pytest.mark.asyncio
    async def test_documents_db_error_returns_empty_list(self):
        svc = self._make_partial_error_svc("coach_documents")
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph is not None
        assert graph.documents == []

    @pytest.mark.asyncio
    async def test_facts_db_error_returns_empty_list(self):
        svc = self._make_partial_error_svc("document_facts")
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph is not None
        assert graph.facts == []

    @pytest.mark.asyncio
    async def test_analyses_db_error_returns_empty_list(self):
        svc = self._make_partial_error_svc("employment_analyses")
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph is not None
        assert graph.analyses == []

    @pytest.mark.asyncio
    async def test_recommendations_db_error_returns_empty_list(self):
        svc = self._make_partial_error_svc("employment_recommendations")
        graph = await svc.get_graph("user-1", "emp-1")
        assert graph is not None
        assert graph.recommendations == []

    @pytest.mark.asyncio
    async def test_employment_db_error_returns_none(self):
        supabase = MagicMock()
        supabase.table.side_effect = RuntimeError("db catastrophic")
        svc = EmploymentGraphService(supabase)
        result = await svc.get_graph("user-1", "emp-1")
        assert result is None
