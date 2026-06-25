"""
Unit tests for DocumentIntelligenceService (app.services.document_intelligence_service).

Supabase, FactExtractionAgent, and EmbeddingService are all mocked.
Tests verify: pipeline orchestration, fact persistence, memory creation,
embedding generation, confidence filtering, and resilience under failures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.fact_extraction_agent import ExtractionResult, ExtractedFact
from app.services.document_intelligence_service import DocumentIntelligenceService, ExtractionSummary
from app.services.embedding_service import EmbeddingService


# ── Test helpers ──────────────────────────────────────────────────────────────


def _make_fact(
    fact_type="monthly_salary",
    value="42500",
    unit="DKK",
    confidence="high",
    requires_confirmation=False,
    source_text="månedlig grundløn på 42.500 kr.",
    source_page=2,
) -> ExtractedFact:
    return ExtractedFact(
        fact_type=fact_type,
        value=value,
        unit=unit,
        confidence=confidence,
        requires_confirmation=requires_confirmation,
        source_text=source_text,
        source_page=source_page,
    )


def _make_extraction_result(
    facts: list[ExtractedFact] | None = None,
    summary: str = "Kontrakt fra ABC A/S.",
    quality: str = "high",
    error: str | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        facts=facts or [],
        document_summary=summary,
        extraction_quality=quality,
        raw_response='{"facts": []}',
        error=error,
    )


class _SupabaseSpy:
    """Records table inserts and routes selects to canned data."""

    def __init__(self):
        self.inserted: dict[str, list] = {}

    def table(self, name: str):
        return _TableSpy(self, name)

    def rpc(self, *a, **k):
        return MagicMock()


class _TableSpy:
    def __init__(self, sb: _SupabaseSpy, name: str):
        self._sb = sb
        self._name = name

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, row: dict):
        self._sb.inserted.setdefault(self._name, []).append(row)
        return self

    def update(self, row: dict):
        return self

    def execute(self):
        return MagicMock(data=[{"id": "mem-uuid-1234"}])


def _make_embedding_svc(return_value=None) -> EmbeddingService:
    svc = MagicMock(spec=EmbeddingService)
    svc.embed = AsyncMock(return_value=return_value)
    return svc


def _make_service(supabase, embedding_svc) -> DocumentIntelligenceService:
    return DocumentIntelligenceService(supabase=supabase, embedding_service=embedding_svc)


# ── analyze() ─────────────────────────────────────────────────────────────────


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_facts_inserted_to_document_facts(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(), _make_fact(fact_type="vacation_days")])

        with patch(
            "app.services.document_intelligence_service.FactExtractionAgent"
        ) as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch("app.services.document_intelligence_service.MemoryService"):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        assert summary.facts_total == 2

    @pytest.mark.asyncio
    async def test_high_confidence_creates_career_memory(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(confidence="high")])

        mock_memory_svc = MagicMock()
        mock_memory_svc.create_memory.return_value = {"id": "mem-id-1"}
        mock_memory_svc.update_embedding = MagicMock()

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        mock_memory_svc.create_memory.assert_called_once()
        assert summary.memories_created == 1

    @pytest.mark.asyncio
    async def test_medium_confidence_also_creates_memory(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(confidence="medium")])

        mock_memory_svc = MagicMock()
        mock_memory_svc.create_memory.return_value = {"id": "mem-id-2"}

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        assert summary.memories_created == 1

    @pytest.mark.asyncio
    async def test_low_confidence_does_not_create_memory(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(confidence="low")])

        mock_memory_svc = MagicMock()

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        mock_memory_svc.create_memory.assert_not_called()
        assert summary.memories_created == 0
        assert summary.facts_low == 1

    @pytest.mark.asyncio
    async def test_embedding_generated_and_stored_for_memory(self):
        supabase = _SupabaseSpy()
        fake_embedding = [0.1] * 1536
        embedding = _make_embedding_svc(return_value=fake_embedding)
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(confidence="high")])

        mock_memory_svc = MagicMock()
        mock_memory_svc.create_memory.return_value = {"id": "mem-embed-1"}
        mock_memory_svc.update_embedding = MagicMock()

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        embedding.embed.assert_awaited_once()
        mock_memory_svc.update_embedding.assert_called_once_with("mem-embed-1", fake_embedding)

    @pytest.mark.asyncio
    async def test_no_embedding_update_when_embed_returns_none(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc(return_value=None)
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(confidence="high")])
        mock_memory_svc = MagicMock()
        mock_memory_svc.create_memory.return_value = {"id": "mem-no-embed"}
        mock_memory_svc.update_embedding = MagicMock()

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        mock_memory_svc.update_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_continues_when_memory_creation_fails(self):
        """Memory failure must not abort the pipeline — fact is still stored."""
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(confidence="high")])
        mock_memory_svc = MagicMock()
        mock_memory_svc.create_memory.side_effect = RuntimeError("db down")

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        assert summary.memories_created == 0
        assert any("memory_failed" in w for w in summary.warnings)

    @pytest.mark.asyncio
    async def test_empty_facts_returns_zero_counts(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[])

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch("app.services.document_intelligence_service.MemoryService"):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        assert summary.facts_total == 0
        assert summary.memories_created == 0
        assert summary.facts_high == 0

    @pytest.mark.asyncio
    async def test_summary_counts_are_accurate(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        facts = [
            _make_fact(fact_type="f1", confidence="high"),
            _make_fact(fact_type="f2", confidence="high"),
            _make_fact(fact_type="f3", confidence="medium"),
            _make_fact(fact_type="f4", confidence="low", requires_confirmation=True),
        ]
        extraction = _make_extraction_result(facts=facts)

        mock_memory_svc = MagicMock()
        mock_memory_svc.create_memory.return_value = {"id": "m"}

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        assert summary.facts_total == 4
        assert summary.facts_high == 2
        assert summary.facts_medium == 1
        assert summary.facts_low == 1
        assert summary.facts_requiring_confirmation == 1
        assert summary.memories_created == 3  # 2 high + 1 medium

    @pytest.mark.asyncio
    async def test_extraction_error_recorded_in_warnings(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[], error="json_parse_error")

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch("app.services.document_intelligence_service.MemoryService"):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        assert any("extraction_error" in w for w in summary.warnings)

    @pytest.mark.asyncio
    async def test_employment_id_passed_to_fact_row(self):
        """employment_id is stored in every fact row for Work Graph linking."""
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(confidence="low")])

        mock_memory_svc = MagicMock()

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                    employment_id="exp-uuid-123",
                )

        inserted_rows = supabase.inserted.get("document_facts", [])
        assert len(inserted_rows) == 1
        assert inserted_rows[0]["employment_id"] == "exp-uuid-123"

    @pytest.mark.asyncio
    async def test_document_id_included_in_fact_rows(self):
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        extraction = _make_extraction_result(facts=[_make_fact(confidence="low")])

        mock_memory_svc = MagicMock()

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                await svc.analyze(
                    document_id="my-doc-id", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        assert supabase.inserted["document_facts"][0]["document_id"] == "my-doc-id"

    @pytest.mark.asyncio
    async def test_memory_content_does_not_contain_raw_document_text(self):
        """Memory stores structured summaries, never raw document text."""
        supabase = _SupabaseSpy()
        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        raw_doc_text = "DETTE ER DET RÅ DOKUMENT SOM IKKE MÅ GEMMES I MEMORY"
        fact = _make_fact(
            confidence="high",
            source_text="månedlig grundløn på 42.500 kr.",
        )
        extraction = _make_extraction_result(facts=[fact])

        mock_memory_svc = MagicMock()
        mock_memory_svc.create_memory.return_value = {"id": "m"}
        memory_content_captured = []

        def capture_create(*args, **kwargs):
            memory_content_captured.append(kwargs.get("content", ""))
            return {"id": "m"}

        mock_memory_svc.create_memory.side_effect = capture_create

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text=raw_doc_text, user_id="user-1",
                )

        assert len(memory_content_captured) == 1
        # Raw document text must NOT appear in memory
        assert raw_doc_text not in memory_content_captured[0]
        # Structured fact content must appear
        assert "Månedlig grundløn" in memory_content_captured[0]
        assert "42500" in memory_content_captured[0]


# ── list_facts() ──────────────────────────────────────────────────────────────


class TestListFacts:
    @pytest.mark.asyncio
    async def test_returns_empty_list_on_db_error(self):
        supabase = MagicMock()
        supabase.table.side_effect = RuntimeError("db down")
        svc = _make_service(supabase, _make_embedding_svc())
        result = await svc.list_facts(document_id="doc-1", user_id="user-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_facts_on_success(self):
        supabase = _SupabaseSpy()
        svc = _make_service(supabase, _make_embedding_svc())
        # _SupabaseSpy.execute() returns data=[{"id": "mem-uuid-1234"}] for any table
        result = await svc.list_facts(document_id="doc-1", user_id="user-1")
        # Returns whatever the DB returned (non-empty list from spy)
        assert isinstance(result, list)


class TestAnalyzeFactInsertFailure:
    @pytest.mark.asyncio
    async def test_pipeline_continues_when_fact_insert_fails(self):
        """document_facts INSERT failure must not abort the pipeline."""
        supabase = MagicMock()

        # subscriptions/agent_registry: return minimal data so agent init works
        table_mock = MagicMock()
        table_mock.select.return_value = table_mock
        table_mock.eq.return_value = table_mock
        table_mock.order.return_value = table_mock
        table_mock.limit.return_value = table_mock
        table_mock.execute.return_value = MagicMock(data=[])
        insert_mock = MagicMock()
        insert_mock.execute.side_effect = RuntimeError("insert db down")
        table_mock.insert.return_value = insert_mock
        supabase.table.return_value = table_mock
        supabase.rpc.return_value = MagicMock()

        embedding = _make_embedding_svc()
        svc = _make_service(supabase, embedding)

        facts = [_make_fact(confidence="low")]
        extraction = _make_extraction_result(facts=facts)

        mock_memory_svc = MagicMock()

        with patch("app.services.document_intelligence_service.FactExtractionAgent") as MockAgent:
            MockAgent.return_value.extract = AsyncMock(return_value=extraction)
            with patch(
                "app.services.document_intelligence_service.MemoryService",
                return_value=mock_memory_svc,
            ):
                summary = await svc.analyze(
                    document_id="doc-1", doc_type="contract",
                    extracted_text="text", user_id="user-1",
                )

        assert any("fact_insert_failed" in w for w in summary.warnings)
