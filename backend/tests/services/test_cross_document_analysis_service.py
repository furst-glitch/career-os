"""
Unit tests for CrossDocumentAnalysisService.

All DB calls mocked. Analysis is purely deterministic rule-based comparison.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.cross_document_analysis_service import CrossDocumentAnalysisService

# ── Helpers ───────────────────────────────────────────────────────────────────


def _fact(fact_type: str, value: str, confidence: str = "high",
          doc_id: str = "doc-1", fact_id: str | None = None) -> dict:
    return {
        "id": fact_id or f"fact-{fact_type}",
        "document_id": doc_id,
        "fact_type": fact_type,
        "value": value,
        "unit": "DKK",
        "confidence": confidence,
        "source_page": 1,
    }


class _SupabaseSpy:
    """Records inserts for assertions."""

    def __init__(self, facts: list[dict]) -> None:
        self._facts = facts
        self.analyses_inserted: list[dict] = []
        self.recs_inserted: list[dict] = []

    def table(self, name: str):
        if name == "document_facts":
            return _FactsTable(self._facts)
        if name == "employment_analyses":
            return _InsertTable(self.analyses_inserted)
        if name == "employment_recommendations":
            return _InsertTable(self.recs_inserted)
        m = MagicMock()
        m.insert.return_value.execute.return_value = MagicMock()
        return m


class _FactsTable:
    def __init__(self, data: list[dict]) -> None:
        self._data = data

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def execute(self):
        return MagicMock(data=self._data)


class _InsertTable:
    def __init__(self, store: list[dict]) -> None:
        self._store = store

    def insert(self, data: dict):
        self._store.append(data)
        m = MagicMock()
        m.execute.return_value = MagicMock()
        return m


def _make_svc(facts: list[dict]) -> tuple[CrossDocumentAnalysisService, _SupabaseSpy]:
    spy = _SupabaseSpy(facts)
    return CrossDocumentAnalysisService(spy), spy


# ── Salary check ──────────────────────────────────────────────────────────────


class TestSalaryCheck:
    @pytest.mark.asyncio
    async def test_identical_salary_no_discrepancy(self):
        svc, _ = _make_svc([
            _fact("monthly_salary", "42500"),
            _fact("gross_salary", "42500", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "salary_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_salary_within_5pct_tolerance_no_discrepancy(self):
        # 2 % difference — within 5 % tolerance
        svc, _ = _make_svc([
            _fact("monthly_salary", "42500"),
            _fact("gross_salary", "43350", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "salary_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_7pct_discrepancy_is_medium_severity(self):
        # 42500 → 45475 = 7 %
        svc, _ = _make_svc([
            _fact("monthly_salary", "42500"),
            _fact("gross_salary", "45475", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        d = next((x for x in result.discrepancies if x.recommendation_type == "salary_mismatch"), None)
        assert d is not None
        assert d.severity == "medium"

    @pytest.mark.asyncio
    async def test_18pct_discrepancy_is_high_severity(self):
        # 42500 → 50000 = 17.6 %
        svc, _ = _make_svc([
            _fact("monthly_salary", "42500"),
            _fact("gross_salary", "50000", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        d = next((x for x in result.discrepancies if x.recommendation_type == "salary_mismatch"), None)
        assert d is not None
        assert d.severity == "high"

    @pytest.mark.asyncio
    async def test_missing_payslip_no_salary_check(self):
        svc, _ = _make_svc([_fact("monthly_salary", "42500")])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "salary_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_missing_contract_no_salary_check(self):
        svc, _ = _make_svc([_fact("gross_salary", "42500")])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "salary_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_low_confidence_salary_skipped(self):
        svc, _ = _make_svc([
            _fact("monthly_salary", "42500", confidence="low"),
            _fact("gross_salary", "50000", doc_id="doc-2", confidence="low"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "salary_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_discrepancy_includes_both_fact_ids(self):
        svc, _ = _make_svc([
            _fact("monthly_salary", "42500", fact_id="fact-a"),
            _fact("gross_salary", "50000", doc_id="doc-2", fact_id="fact-b"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        d = next((x for x in result.discrepancies if x.recommendation_type == "salary_mismatch"), None)
        assert d is not None
        assert "fact-a" in d.affected_fact_ids
        assert "fact-b" in d.affected_fact_ids


# ── Pension check ─────────────────────────────────────────────────────────────


class TestPensionCheck:
    @pytest.mark.asyncio
    async def test_identical_pension_pct_no_discrepancy(self):
        svc, _ = _make_svc([
            _fact("pension_pct_total", "12.0", doc_id="doc-1"),
            _fact("pension_pct_total", "12.0", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "pension_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_4pct_pension_difference_is_high_severity(self):
        svc, _ = _make_svc([
            _fact("pension_pct_total", "12.0", doc_id="doc-1"),
            _fact("pension_pct_total", "8.0", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        d = next((x for x in result.discrepancies if x.recommendation_type == "pension_mismatch"), None)
        assert d is not None
        assert d.severity == "high"

    @pytest.mark.asyncio
    async def test_1_5pct_pension_difference_is_medium_severity(self):
        svc, _ = _make_svc([
            _fact("pension_pct_total", "12.0", doc_id="doc-1"),
            _fact("pension_pct_total", "10.5", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        d = next((x for x in result.discrepancies if x.recommendation_type == "pension_mismatch"), None)
        assert d is not None
        assert d.severity == "medium"

    @pytest.mark.asyncio
    async def test_single_pension_fact_no_check(self):
        svc, _ = _make_svc([_fact("pension_pct_total", "12.0")])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "pension_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_low_confidence_pension_facts_excluded(self):
        # Two low-confidence pension facts — should be excluded from check
        svc, _ = _make_svc([
            _fact("pension_pct_total", "12.0", confidence="low", doc_id="doc-1"),
            _fact("pension_pct_total", "6.0", confidence="low", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "pension_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_pension_within_1pct_tolerance_no_discrepancy(self):
        # 12.0 vs 12.8 = 0.8 pct-point difference
        svc, _ = _make_svc([
            _fact("pension_pct_total", "12.0", doc_id="doc-1"),
            _fact("pension_pct_total", "12.8", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "pension_mismatch" for d in result.discrepancies)


# ── Hours check ───────────────────────────────────────────────────────────────


class TestHoursCheck:
    @pytest.mark.asyncio
    async def test_identical_hours_no_discrepancy(self):
        svc, _ = _make_svc([
            _fact("working_hours_per_week", "37", doc_id="doc-1"),
            _fact("working_hours_per_week", "37", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "hours_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_3h_discrepancy_is_medium_severity(self):
        svc, _ = _make_svc([
            _fact("working_hours_per_week", "37", doc_id="doc-1"),
            _fact("working_hours_per_week", "40", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        d = next((x for x in result.discrepancies if x.recommendation_type == "hours_mismatch"), None)
        assert d is not None
        assert d.severity == "medium"

    @pytest.mark.asyncio
    async def test_1h_discrepancy_is_low_severity(self):
        svc, _ = _make_svc([
            _fact("working_hours_per_week", "37", doc_id="doc-1"),
            _fact("working_hours_per_week", "38", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        d = next((x for x in result.discrepancies if x.recommendation_type == "hours_mismatch"), None)
        assert d is not None
        assert d.severity == "low"

    @pytest.mark.asyncio
    async def test_single_hours_fact_no_check(self):
        svc, _ = _make_svc([_fact("working_hours_per_week", "37")])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "hours_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_hours_within_half_hour_tolerance(self):
        # 37.0 vs 37.4 = 0.4h difference (within 0.5h tolerance)
        svc, _ = _make_svc([
            _fact("working_hours_per_week", "37.0", doc_id="doc-1"),
            _fact("working_hours_per_week", "37.4", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "hours_mismatch" for d in result.discrepancies)


# ── Persistence ───────────────────────────────────────────────────────────────


class TestPersistence:
    @pytest.mark.asyncio
    async def test_analysis_persisted(self):
        svc, spy = _make_svc([
            _fact("monthly_salary", "42500"),
            _fact("gross_salary", "50000", doc_id="doc-2"),
        ])
        await svc.analyze("user-1", "emp-1")
        assert len(spy.analyses_inserted) == 1
        row = spy.analyses_inserted[0]
        assert row["employment_id"] == "emp-1"
        assert row["analysis_type"] == "cross_document"
        assert row["discrepancies_found"] == 1

    @pytest.mark.asyncio
    async def test_recommendation_persisted_for_each_discrepancy(self):
        svc, spy = _make_svc([
            _fact("monthly_salary", "42500"),
            _fact("gross_salary", "50000", doc_id="doc-2"),
            _fact("pension_pct_total", "12.0", doc_id="doc-1"),
            _fact("pension_pct_total", "8.0", doc_id="doc-3"),
        ])
        await svc.analyze("user-1", "emp-1")
        assert len(spy.recs_inserted) == 2
        types = {r["recommendation_type"] for r in spy.recs_inserted}
        assert "salary_mismatch" in types
        assert "pension_mismatch" in types

    @pytest.mark.asyncio
    async def test_recommendation_status_is_pending(self):
        svc, spy = _make_svc([
            _fact("monthly_salary", "42500"),
            _fact("gross_salary", "50000", doc_id="doc-2"),
        ])
        await svc.analyze("user-1", "emp-1")
        assert spy.recs_inserted[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_analysis_persist_failure_adds_warning(self):
        supabase = MagicMock()
        facts_tbl = MagicMock()
        facts_tbl.select.return_value = facts_tbl
        facts_tbl.eq.return_value = facts_tbl
        facts_tbl.execute.return_value = MagicMock(data=[])
        analyses_tbl = MagicMock()
        analyses_tbl.insert.side_effect = RuntimeError("db down")

        def get_table(name):
            if name == "document_facts":
                return facts_tbl
            if name == "employment_analyses":
                return analyses_tbl
            return MagicMock()

        supabase.table.side_effect = get_table
        svc = CrossDocumentAnalysisService(supabase)
        result = await svc.analyze("user-1", "emp-1")
        assert any("analysis_persist_failed" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_recommendation_persist_failure_adds_warning(self):
        supabase = MagicMock()
        facts_data = [
            _fact("monthly_salary", "42500"),
            _fact("gross_salary", "50000", doc_id="doc-2"),
        ]
        facts_tbl = MagicMock()
        facts_tbl.select.return_value = facts_tbl
        facts_tbl.eq.return_value = facts_tbl
        facts_tbl.execute.return_value = MagicMock(data=facts_data)

        analyses_tbl = MagicMock()
        analyses_tbl.insert.return_value = MagicMock(execute=MagicMock(return_value=MagicMock()))

        recs_tbl = MagicMock()
        recs_tbl.insert.side_effect = RuntimeError("recs db down")

        def get_table(name):
            if name == "document_facts":
                return facts_tbl
            if name == "employment_analyses":
                return analyses_tbl
            if name == "employment_recommendations":
                return recs_tbl
            return MagicMock()

        supabase.table.side_effect = get_table
        svc = CrossDocumentAnalysisService(supabase)
        result = await svc.analyze("user-1", "emp-1")
        assert any("recommendation_persist_failed" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_empty_facts_zero_discrepancies(self):
        svc, spy = _make_svc([])
        result = await svc.analyze("user-1", "emp-1")
        assert result.discrepancies == []
        assert result.document_ids == []
        assert spy.analyses_inserted[0]["discrepancies_found"] == 0

    @pytest.mark.asyncio
    async def test_document_ids_collected_from_facts(self):
        svc, spy = _make_svc([
            _fact("monthly_salary", "42500", doc_id="doc-A"),
            _fact("gross_salary", "50000", doc_id="doc-B"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert set(result.document_ids) == {"doc-A", "doc-B"}

    @pytest.mark.asyncio
    async def test_fetch_facts_db_error_returns_empty(self):
        """_fetch_facts exception path (lines 145-149)."""
        supabase = MagicMock()
        facts_tbl = MagicMock()
        facts_tbl.select.return_value = facts_tbl
        facts_tbl.eq.side_effect = RuntimeError("connection lost")

        analyses_tbl = MagicMock()
        analyses_tbl.insert.return_value = MagicMock(execute=MagicMock(return_value=MagicMock()))

        def get_table(name):
            if name == "document_facts":
                return facts_tbl
            if name == "employment_analyses":
                return analyses_tbl
            return MagicMock()

        supabase.table.side_effect = get_table
        svc = CrossDocumentAnalysisService(supabase)
        result = await svc.analyze("user-1", "emp-1")
        # No facts → no discrepancies; pipeline should still produce an analysis row
        assert result.discrepancies == []
        assert result.document_ids == []


# ── Parse numeric ─────────────────────────────────────────────────────────────


class TestParseNumeric:
    def test_plain_integer(self):
        assert CrossDocumentAnalysisService._parse_numeric("42500") == 42500.0

    def test_decimal_with_period(self):
        assert CrossDocumentAnalysisService._parse_numeric("12.5") == 12.5

    def test_decimal_with_comma(self):
        assert CrossDocumentAnalysisService._parse_numeric("12,5") == 12.5

    def test_non_numeric_returns_none(self):
        """ValueError branch in _parse_numeric (line 165-166)."""
        assert CrossDocumentAnalysisService._parse_numeric("not-a-number") is None

    def test_none_value_returns_none(self):
        """TypeError branch in _parse_numeric."""
        assert CrossDocumentAnalysisService._parse_numeric(None) is None  # type: ignore[arg-type]

    def test_empty_string_returns_none(self):
        assert CrossDocumentAnalysisService._parse_numeric("") is None


# ── Unparseable fact values ───────────────────────────────────────────────────


class TestUnparseableValues:
    @pytest.mark.asyncio
    async def test_salary_unparseable_contract_value_skips_check(self):
        """cv is None → line 185 hit."""
        svc, _ = _make_svc([
            _fact("monthly_salary", "n/a"),        # unparseable
            _fact("gross_salary", "42500", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "salary_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_pension_unparseable_reduces_parsed_below_two(self):
        """len(parsed) < 2 branch in _check_pension_pct (line 223)."""
        svc, _ = _make_svc([
            _fact("pension_pct_total", "n/a", doc_id="doc-1"),
            _fact("pension_pct_total", "n/a", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "pension_mismatch" for d in result.discrepancies)

    @pytest.mark.asyncio
    async def test_hours_unparseable_reduces_parsed_below_two(self):
        """len(parsed) < 2 branch in _check_hours (line 260)."""
        svc, _ = _make_svc([
            _fact("working_hours_per_week", "n/a", doc_id="doc-1"),
            _fact("working_hours_per_week", "n/a", doc_id="doc-2"),
        ])
        result = await svc.analyze("user-1", "emp-1")
        assert not any(d.recommendation_type == "hours_mismatch" for d in result.discrepancies)
