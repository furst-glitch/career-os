"""
CrossDocumentAnalysisService — deterministic cross-document fact comparison.

Compares extracted facts across all documents linked to the same Employment.
Produces AnalysisResult with discrepancies → persisted as employment_recommendations.

NO AI calls. No LLM. Purely rule-based comparison of numeric values.

Rules implemented:
  salary_match     : contract.monthly_salary vs payslip.gross_salary  (±5% tolerance)
  pension_pct      : pension_pct_total consistency across documents    (±1 pct-point)
  hours_match      : working_hours_per_week consistency                (±0.5 h/week)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("app.services.cross_document_analysis")

# ── Comparison tolerances ─────────────────────────────────────────────────────
_SALARY_TOLERANCE_PCT = 0.05   # 5 % — payroll rounding, shift differentials
_PENSION_TOLERANCE_PCT = 1.0   # 1 percentage-point
_HOURS_TOLERANCE = 0.5         # 0.5 hours/week

_HIGH_CONFIDENCE = frozenset({"high", "medium"})
_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


# ── Domain objects ────────────────────────────────────────────────────────────


@dataclass
class Discrepancy:
    recommendation_type: str
    severity: str               # high | medium | low | info
    title: str
    description: str
    fact_types: list[str]
    affected_fact_ids: list[str]


@dataclass
class AnalysisResult:
    analysis_id: str
    employment_id: str
    document_ids: list[str]
    discrepancies: list[Discrepancy] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Service ───────────────────────────────────────────────────────────────────


class CrossDocumentAnalysisService:
    """
    Compares document_facts across all documents for a given Employment.
    Persists results to employment_analyses + employment_recommendations.
    """

    def __init__(self, supabase) -> None:
        self._supabase = supabase

    async def analyze(self, user_id: str, employment_id: str) -> AnalysisResult:
        facts = self._fetch_facts(user_id, employment_id)
        document_ids = list({f["document_id"] for f in facts})

        by_type: dict[str, list[dict]] = {}
        for fact in facts:
            by_type.setdefault(fact["fact_type"], []).append(fact)

        discrepancies: list[Discrepancy] = []
        warnings: list[str] = []

        for check in (self._check_salary, self._check_pension_pct, self._check_hours):
            d = check(by_type)
            if d:
                discrepancies.append(d)

        analysis_id = str(uuid.uuid4())
        try:
            self._supabase.table("employment_analyses").insert({
                "id": analysis_id,
                "user_id": user_id,
                "employment_id": employment_id,
                "analysis_type": "cross_document",
                "document_ids": document_ids,
                "discrepancies_found": len(discrepancies),
                "result_json": {
                    "rules_checked": ["salary_match", "pension_pct", "working_hours"],
                    "facts_compared": len(facts),
                },
            }).execute()
        except Exception as exc:
            logger.error(
                "analysis_insert_failed employment=%s error=%s", employment_id, exc
            )
            warnings.append("analysis_persist_failed")

        for disc in discrepancies:
            try:
                self._supabase.table("employment_recommendations").insert({
                    "user_id": user_id,
                    "employment_id": employment_id,
                    "analysis_id": analysis_id,
                    "recommendation_type": disc.recommendation_type,
                    "severity": disc.severity,
                    "title": disc.title,
                    "description": disc.description,
                    "fact_types": disc.fact_types,
                    "affected_fact_ids": disc.affected_fact_ids,
                    "status": "pending",
                }).execute()
            except Exception as exc:
                logger.error(
                    "recommendation_insert_failed type=%s error=%s",
                    disc.recommendation_type, exc,
                )
                warnings.append(f"recommendation_persist_failed:{disc.recommendation_type}")

        return AnalysisResult(
            analysis_id=analysis_id,
            employment_id=employment_id,
            document_ids=document_ids,
            discrepancies=discrepancies,
            warnings=warnings,
        )

    # ── DB access ─────────────────────────────────────────────────────────────

    def _fetch_facts(self, user_id: str, employment_id: str) -> list[dict]:
        try:
            result = (
                self._supabase.table("document_facts")
                .select(
                    "id, document_id, fact_type, value, unit, confidence, source_page"
                )
                .eq("user_id", user_id)
                .eq("employment_id", employment_id)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error(
                "fetch_facts_failed employment=%s error=%s", employment_id, exc
            )
            return []

    # ── Comparison helpers ────────────────────────────────────────────────────

    @staticmethod
    def _best_fact(facts: list[dict]) -> dict | None:
        """Highest-confidence fact from a list; None if empty."""
        if not facts:
            return None
        return min(facts, key=lambda f: _CONFIDENCE_ORDER.get(f.get("confidence", "low"), 2))

    @staticmethod
    def _parse_numeric(value: str) -> float | None:
        """Parse a plain numeric string. AI outputs '42500', '12.5', '37' etc."""
        try:
            return float(str(value).strip().replace(",", ".").replace(" ", ""))
        except (ValueError, TypeError):
            return None

    # ── Comparison rules ──────────────────────────────────────────────────────

    def _check_salary(self, by_type: dict[str, list[dict]]) -> Discrepancy | None:
        """Contract monthly_salary vs payslip gross_salary."""
        contract_fact = self._best_fact(by_type.get("monthly_salary", []))
        payslip_fact = self._best_fact(by_type.get("gross_salary", []))

        if not contract_fact or not payslip_fact:
            return None
        # Skip low-confidence sources for cross-document claims
        if (contract_fact.get("confidence") == "low"
                or payslip_fact.get("confidence") == "low"):
            return None

        cv = self._parse_numeric(contract_fact["value"])
        pv = self._parse_numeric(payslip_fact["value"])
        if cv is None or pv is None or cv == 0:
            return None

        diff_pct = abs(cv - pv) / cv
        if diff_pct <= _SALARY_TOLERANCE_PCT:
            return None

        severity = "high" if diff_pct > 0.10 else "medium" if diff_pct > 0.05 else "low"
        diff_dkk = int(pv - cv)
        sign = "+" if diff_dkk > 0 else ""
        return Discrepancy(
            recommendation_type="salary_mismatch",
            severity=severity,
            title="Grundløn matcher ikke kontrakten",
            description=(
                f"Kontraktens grundløn er {int(cv):,} DKK/måned, "
                f"men lønsedlen viser {int(pv):,} DKK "
                f"({sign}{diff_dkk:,} DKK, {diff_pct:.1%} afvigelse). "
                "Undersøg om differencen skyldes tillæg eller en fejl."
            ),
            fact_types=["monthly_salary", "gross_salary"],
            affected_fact_ids=[contract_fact["id"], payslip_fact["id"]],
        )

    def _check_pension_pct(self, by_type: dict[str, list[dict]]) -> Discrepancy | None:
        """pension_pct_total consistency across all documents."""
        candidates = [
            f for f in by_type.get("pension_pct_total", [])
            if f.get("confidence") in _HIGH_CONFIDENCE
        ]
        if len(candidates) < 2:
            return None

        parsed: list[tuple[float, dict]] = []
        for f in candidates:
            v = self._parse_numeric(f["value"])
            if v is not None:
                parsed.append((v, f))
        if len(parsed) < 2:
            return None

        vals = [v for v, _ in parsed]
        diff = max(vals) - min(vals)
        if diff <= _PENSION_TOLERANCE_PCT:
            return None

        min_f = min(parsed, key=lambda x: x[0])[1]
        max_f = max(parsed, key=lambda x: x[0])[1]
        return Discrepancy(
            recommendation_type="pension_mismatch",
            severity="high" if diff > 2.0 else "medium",
            title="Pensionsprocent er inkonsistent på tværs af dokumenter",
            description=(
                f"Pensionsprocent varierer fra {min(vals):.1f}% til {max(vals):.1f}% "
                f"({diff:.1f} procentpoints forskel). "
                "Kontroller hvilken sats der er gældende i din ansættelse."
            ),
            fact_types=["pension_pct_total"],
            affected_fact_ids=[min_f["id"], max_f["id"]],
        )

    def _check_hours(self, by_type: dict[str, list[dict]]) -> Discrepancy | None:
        """working_hours_per_week consistency across all documents."""
        candidates = [
            f for f in by_type.get("working_hours_per_week", [])
            if f.get("confidence") in _HIGH_CONFIDENCE
        ]
        if len(candidates) < 2:
            return None

        parsed: list[tuple[float, dict]] = []
        for f in candidates:
            v = self._parse_numeric(f["value"])
            if v is not None:
                parsed.append((v, f))
        if len(parsed) < 2:
            return None

        vals = [v for v, _ in parsed]
        diff = max(vals) - min(vals)
        if diff <= _HOURS_TOLERANCE:
            return None

        min_f = min(parsed, key=lambda x: x[0])[1]
        max_f = max(parsed, key=lambda x: x[0])[1]
        return Discrepancy(
            recommendation_type="hours_mismatch",
            severity="medium" if diff > 2.0 else "low",
            title="Ugentlig arbejdstid stemmer ikke overens",
            description=(
                f"Arbejdstiden varierer fra {min(vals):.1f} til {max(vals):.1f} timer/uge "
                f"({diff:.1f} timers forskel). "
                "Tjek kontrakten og overenskomsten for den gældende arbejdstid."
            ),
            fact_types=["working_hours_per_week"],
            affected_fact_ids=[min_f["id"], max_f["id"]],
        )
