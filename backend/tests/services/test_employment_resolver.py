"""
Unit tests for EmploymentResolverService (app.services.employment_resolver).

DB is mocked. All comparisons are against the scoring/resolution logic only.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.employment_resolver import (
    EmploymentResolverService,
    _HIGH_CONFIDENCE_THRESHOLD,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_EXP = {
    "id": "exp-1",
    "title": "Senior Controller",
    "organisation": "ABC A/S",
    "period_start": "2023-01-01",
    "period_end": None,
    "experience_type": "job",
}


def _make_svc(experiences: list[dict]) -> EmploymentResolverService:
    supabase = MagicMock()
    tbl = MagicMock()
    tbl.select.return_value = tbl
    tbl.eq.return_value = tbl
    tbl.in_.return_value = tbl
    tbl.execute.return_value = MagicMock(data=experiences)
    supabase.table.return_value = tbl
    return EmploymentResolverService(supabase)


def _make_svc_db_error() -> EmploymentResolverService:
    supabase = MagicMock()
    supabase.table.side_effect = RuntimeError("db down")
    return EmploymentResolverService(supabase)


# ── Status codes ──────────────────────────────────────────────────────────────


class TestStatus:
    @pytest.mark.asyncio
    async def test_no_experiences_returns_no_employments(self):
        svc = _make_svc([])
        result = await svc.resolve("user-1")
        assert result.status == "no_employments"
        assert result.employment_id is None

    @pytest.mark.asyncio
    async def test_db_error_returns_unknown(self):
        svc = _make_svc_db_error()
        result = await svc.resolve("user-1", employer_name="ABC A/S")
        assert result.status == "unknown"
        assert result.employment_id is None
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_exact_employer_name_returns_existing(self):
        svc = _make_svc([_EXP])
        result = await svc.resolve("user-1", employer_name="ABC A/S")
        assert result.status == "existing"
        assert result.employment_id == "exp-1"

    @pytest.mark.asyncio
    async def test_unknown_employer_returns_unknown(self):
        svc = _make_svc([_EXP])
        result = await svc.resolve("user-1", employer_name="XYZ GmbH")
        assert result.status == "unknown"
        assert result.employment_id is None

    @pytest.mark.asyncio
    async def test_no_signals_returns_unknown(self):
        svc = _make_svc([_EXP])
        result = await svc.resolve("user-1")
        # Zero score → below threshold
        assert result.status == "unknown"
        assert result.employment_id is None


# ── Scoring ───────────────────────────────────────────────────────────────────


class TestScoring:
    @pytest.mark.asyncio
    async def test_partial_employer_name_yields_existing_if_above_threshold(self):
        svc = _make_svc([_EXP])
        # "ABC" is contained in "ABC A/S" → 0.30 score — below threshold (0.70)
        result = await svc.resolve("user-1", employer_name="ABC")
        # partial match alone is not enough
        assert result.status == "unknown"

    @pytest.mark.asyncio
    async def test_employer_plus_title_reaches_threshold(self):
        svc = _make_svc([_EXP])
        result = await svc.resolve(
            "user-1",
            employer_name="ABC A/S",       # +0.50
            job_title="Senior Controller",  # +0.30
        )
        assert result.status == "existing"
        assert result.confidence >= _HIGH_CONFIDENCE_THRESHOLD

    @pytest.mark.asyncio
    async def test_title_adds_to_confidence(self):
        svc = _make_svc([_EXP])
        r_without = await svc.resolve("user-1", employer_name="ABC A/S")
        r_with = await svc.resolve(
            "user-1", employer_name="ABC A/S", job_title="Senior Controller"
        )
        assert r_with.confidence > r_without.confidence

    @pytest.mark.asyncio
    async def test_period_start_adds_to_confidence(self):
        svc = _make_svc([_EXP])
        r_without = await svc.resolve("user-1", employer_name="ABC A/S")
        r_with = await svc.resolve(
            "user-1", employer_name="ABC A/S", period_start="2023-01-15"
        )
        assert r_with.confidence > r_without.confidence

    @pytest.mark.asyncio
    async def test_period_start_matches_on_year_month_only(self):
        # Day-level difference should still match
        svc = _make_svc([_EXP])  # period_start = "2023-01-01"
        r = await svc.resolve(
            "user-1", employer_name="ABC A/S", period_start="2023-01-28"
        )
        # Both have 2023-01 prefix → period match counted
        assert r.confidence > (await _make_svc([_EXP]).resolve("user-1", employer_name="ABC A/S")).confidence

    @pytest.mark.asyncio
    async def test_score_capped_at_one(self):
        svc = _make_svc([_EXP])
        r = await svc.resolve(
            "user-1",
            employer_name="ABC A/S",       # +0.50
            job_title="Senior Controller",  # +0.30
            period_start="2023-01-15",      # +0.20
        )
        assert r.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_partial_title_gives_partial_score(self):
        svc = _make_svc([_EXP])
        r_partial = await svc.resolve(
            "user-1", employer_name="ABC A/S", job_title="Controller"
        )
        r_exact = await svc.resolve(
            "user-1", employer_name="ABC A/S", job_title="Senior Controller"
        )
        assert r_partial.confidence < r_exact.confidence


# ── Candidates ────────────────────────────────────────────────────────────────


class TestCandidates:
    @pytest.mark.asyncio
    async def test_candidates_returned_on_unknown_status(self):
        svc = _make_svc([_EXP])
        result = await svc.resolve("user-1", employer_name="XYZ")
        assert isinstance(result.candidates, list)

    @pytest.mark.asyncio
    async def test_candidates_sorted_by_confidence_descending(self):
        exps = [
            {**_EXP, "id": "exp-1", "organisation": "ABC A/S"},
            {**_EXP, "id": "exp-2", "organisation": "XYZ Corp"},
        ]
        svc = _make_svc(exps)
        result = await svc.resolve("user-1", employer_name="ABC A/S")
        if len(result.candidates) >= 2:
            assert result.candidates[0].confidence >= result.candidates[1].confidence

    @pytest.mark.asyncio
    async def test_candidates_capped_at_three(self):
        exps = [
            {**_EXP, "id": f"exp-{i}", "organisation": f"Corp {i}"}
            for i in range(6)
        ]
        svc = _make_svc(exps)
        result = await svc.resolve("user-1")
        assert len(result.candidates) <= 3

    @pytest.mark.asyncio
    async def test_candidate_fields_populated(self):
        svc = _make_svc([_EXP])
        result = await svc.resolve("user-1", employer_name="ABC A/S")
        assert len(result.candidates) >= 1
        c = result.candidates[0]
        assert c.employment_id == "exp-1"
        assert c.title == "Senior Controller"
        assert c.organisation == "ABC A/S"

    @pytest.mark.asyncio
    async def test_match_reasons_populated_on_exact_match(self):
        svc = _make_svc([_EXP])
        result = await svc.resolve("user-1", employer_name="ABC A/S")
        reasons = result.candidates[0].match_reasons
        assert "employer_exact" in reasons
