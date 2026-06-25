"""
EmploymentResolverService — links uploaded documents to Employment records.

Resolution strategy:
  1. Fetch user's job/freelance experiences from Work Graph
  2. Score each candidate by employer name, job title, and period overlap
  3. Return the best match above threshold as "existing", otherwise "unknown"

NEVER auto-merges at low confidence. The caller decides — the UI shows candidates
so the user can confirm or pick manually.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("app.services.employment_resolver")

# Threshold above which we consider the match definitive
_HIGH_CONFIDENCE_THRESHOLD = 0.7

# Experience types considered "employment"
_EMPLOYMENT_TYPES = ["job", "freelance"]


@dataclass
class EmploymentCandidate:
    employment_id: str
    title: str
    organisation: str | None
    period_start: str | None
    period_end: str | None
    confidence: float
    match_reasons: list[str] = field(default_factory=list)


@dataclass
class ResolveResult:
    status: str          # "existing" | "unknown" | "no_employments"
    employment_id: str | None  # set only when status="existing"
    confidence: float
    candidates: list[EmploymentCandidate] = field(default_factory=list)
    hint: str = ""


class EmploymentResolverService:
    """
    Resolves which Employment (experiences row) a document belongs to.
    Read-only — never inserts or updates data.
    """

    def __init__(self, supabase) -> None:
        self._supabase = supabase

    async def resolve(
        self,
        user_id: str,
        employer_name: str | None = None,
        job_title: str | None = None,
        period_start: str | None = None,
    ) -> ResolveResult:
        """
        Resolve a document's employment context.

        Parameters come from facts extracted by FactExtractionAgent
        (employer_name, job_title, contract_start_date from the document).
        All are optional — the resolver degrades gracefully when fewer signals
        are available.
        """
        try:
            result = (
                self._supabase.table("experiences")
                .select("id, title, organisation, period_start, period_end, experience_type")
                .eq("user_id", user_id)
                .in_("experience_type", _EMPLOYMENT_TYPES)
                .execute()
            )
            rows: list[dict] = result.data or []
        except Exception as exc:
            logger.warning(
                "employment_resolve_db_error user=%s error=%s", user_id, exc
            )
            return ResolveResult(
                status="unknown",
                employment_id=None,
                confidence=0.0,
                hint="Kunne ikke hente ansættelsesforhold — prøv igen.",
            )

        if not rows:
            return ResolveResult(
                status="no_employments",
                employment_id=None,
                confidence=0.0,
                hint=(
                    "Ingen registrerede ansættelsesforhold. "
                    "Opret et ansættelsesforhold under Arbejdsgraf for at koble dokumentet."
                ),
            )

        candidates = sorted(
            (self._score(row, employer_name, job_title, period_start) for row in rows),
            key=lambda c: c.confidence,
            reverse=True,
        )

        best = candidates[0]
        if best.confidence >= _HIGH_CONFIDENCE_THRESHOLD:
            return ResolveResult(
                status="existing",
                employment_id=best.employment_id,
                confidence=best.confidence,
                candidates=candidates[:3],
            )

        return ResolveResult(
            status="unknown",
            employment_id=None,
            confidence=best.confidence,
            candidates=candidates[:3],
            hint=(
                "Usikker sammenhæng — vælg ansættelsesforhold manuelt "
                "eller opret et nyt."
            ),
        )

    @staticmethod
    def _score(
        row: dict,
        employer_name: str | None,
        job_title: str | None,
        period_start: str | None,
    ) -> EmploymentCandidate:
        score = 0.0
        reasons: list[str] = []

        org = (row.get("organisation") or "").strip().lower()
        if employer_name and org:
            emp = employer_name.strip().lower()
            if emp == org:
                # Exact employer match is strong enough on its own to reach threshold
                score += 0.75
                reasons.append("employer_exact")
            elif emp in org or org in emp:
                score += 0.30
                reasons.append("employer_partial")

        title = (row.get("title") or "").strip().lower()
        if job_title and title:
            jt = job_title.strip().lower()
            if jt == title:
                score += 0.30
                reasons.append("title_exact")
            elif jt in title or title in jt:
                score += 0.15
                reasons.append("title_partial")

        row_start = row.get("period_start")
        if period_start and row_start:
            # Compare YYYY-MM prefix only (day may differ)
            if str(period_start)[:7] == str(row_start)[:7]:
                score += 0.20
                reasons.append("period_match")

        return EmploymentCandidate(
            employment_id=str(row["id"]),
            title=row.get("title", ""),
            organisation=row.get("organisation"),
            period_start=row.get("period_start"),
            period_end=row.get("period_end"),
            confidence=min(1.0, score),
            match_reasons=reasons,
        )
