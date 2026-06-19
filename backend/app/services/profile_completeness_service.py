"""
Profile Completeness Service — beregner fuldstændigheds-score pr. sektion.

Scoring-principper:
  - 0   = Sektionen er tom
  - 1–34 = Mangelfuld (vises som "missing area")
  - 35–69 = Delvist udfyldt
  - 70–89 = God dækning
  - 90–100 = Excellent

Vægtet overall score:
  Experiences   20%  (primær joberfaring)
  Achievements  20%  (kvantificerede resultater — differentiereren)
  Skills        15%  (kompetencer)
  Projects      15%  (konkrete projekter)
  Systems       15%  (teknologier og systemer)
  Leadership    10%  (lederskabserfaring)
  Certifications 5%  (certifikater)
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SECTION_WEIGHTS: dict[str, float] = {
    "experiences":    0.20,
    "achievements":   0.20,
    "skills":         0.15,
    "projects":       0.15,
    "systems":        0.15,
    "leadership":     0.10,
    "certifications": 0.05,
}

MISSING_THRESHOLD = 35  # Score under dette → "missing area"

MISSING_LABELS: dict[str, str] = {
    "experiences":    "Arbejdserfaringer med beskrivelser",
    "achievements":   "Kvantificerede præstationer",
    "projects":       "Projekter",
    "systems":        "Systemer og teknologier",
    "leadership":     "Lederskabserfaring",
    "certifications": "Certifikater",
    "skills":         "Kompetencer",
}

SECTION_LABELS: dict[str, str] = {
    "experiences":    "Erfaringer",
    "achievements":   "Præstationer",
    "projects":       "Projekter",
    "systems":        "Systemer",
    "leadership":     "Lederskab",
    "certifications": "Certifikater",
    "skills":         "Kompetencer",
}


class ProfileCompletenessService:

    # ─── Public API ───────────────────────────────────────────────────────────

    def calculate(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Beregn scores fra en fuld profil-dict. Kræver ingen DB-kald."""
        section_scores = {
            "experiences":    self._score_experiences(profile.get("experiences") or []),
            "achievements":   self._score_achievements(profile.get("achievements") or []),
            "projects":       self._score_projects(profile.get("projects") or []),
            "systems":        self._score_systems(profile.get("systems") or []),
            "leadership":     self._score_leadership(profile.get("leadership") or []),
            "certifications": self._score_certifications(profile.get("certifications") or []),
            "skills":         self._score_skills(profile.get("skills") or []),
        }

        overall = int(
            sum(section_scores[k] * w for k, w in SECTION_WEIGHTS.items())
        )

        missing_areas = [
            MISSING_LABELS[k]
            for k, v in section_scores.items()
            if v < MISSING_THRESHOLD
        ]

        return {
            "sections": section_scores,
            "overall": overall,
            "missing_areas": missing_areas,
        }

    async def calculate_and_save(self, user_id: str, supabase: Any) -> dict[str, Any]:
        """Beregn scores fra DB og gem/opdater profile_scores-tabellen."""
        from app.services.cv_service import CVService

        profile = await CVService(supabase).get_full_profile(user_id)
        result = self.calculate(profile)

        supabase.table("profile_scores").upsert({
            "user_id": user_id,
            "experiences":    result["sections"]["experiences"],
            "achievements":   result["sections"]["achievements"],
            "projects":       result["sections"]["projects"],
            "systems":        result["sections"]["systems"],
            "leadership":     result["sections"]["leadership"],
            "certifications": result["sections"]["certifications"],
            "skills":         result["sections"]["skills"],
            "overall":        result["overall"],
            "missing_areas":  result["missing_areas"],
            "calculated_at":  datetime.now(UTC).isoformat(),
        }, on_conflict="user_id").execute()

        return result

    def get_stored(self, user_id: str, supabase: Any) -> dict[str, Any] | None:
        """Hent senest beregnede score fra DB. Returnerer None hvis ingen."""
        result = supabase.table("profile_scores").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else None

    # ─── Sektions-scorers ──────────────────────────────────────────────────────

    def _score_experiences(self, items: list[dict]) -> int:
        if not items:
            return 0
        score = 0
        # Volumen
        score += 25 if len(items) >= 1 else 0
        score += 10 if len(items) >= 2 else 0
        score += 5  if len(items) >= 3 else 0
        # Kvalitet
        has_description = any(
            e.get("description") and len(e.get("description", "")) > 40
            for e in items
        )
        has_achievements = any(e.get("achievements") for e in items)
        has_technologies = any(e.get("technologies") for e in items)
        score += 25 if has_achievements   else 0
        score += 20 if has_description    else 0
        score += 15 if has_technologies   else 0
        return min(100, score)

    def _score_achievements(self, items: list[dict]) -> int:
        if not items:
            return 0
        score = 0
        # Volumen
        score += 20 if len(items) >= 1 else 0
        score += 15 if len(items) >= 3 else (7 if len(items) >= 2 else 0)
        # Kvantificering — det vigtigste
        has_metric = any(a.get("metric") and a["metric"].strip() for a in items)
        score += 40 if has_metric else 0
        # Impact-niveau
        has_high = any(a.get("impact_level") == "high" for a in items)
        score += 25 if has_high else 0
        return min(100, score)

    def _score_projects(self, items: list[dict]) -> int:
        if not items:
            return 0
        score = 0
        score += 35 if len(items) >= 1 else 0
        score += 15 if len(items) >= 2 else 0
        has_outcomes     = any(p.get("outcomes") and p["outcomes"].strip() for p in items)
        has_technologies = any(p.get("technologies") for p in items)
        score += 30 if has_outcomes     else 0
        score += 20 if has_technologies else 0
        return min(100, score)

    def _score_systems(self, items: list[dict]) -> int:
        if not items:
            return 0
        count = len(items)
        # Volumen: 10 points per system, max 70
        score = min(70, count * 10)
        # Ekspertise-boost
        has_advanced = any(
            s.get("proficiency") in ("advanced", "expert") for s in items
        )
        score += 30 if has_advanced else 0
        return min(100, score)

    def _score_leadership(self, items: list[dict]) -> int:
        if not items:
            return 0
        score = 50  # Basalscore — lederskab er svært at opnå
        has_reports = any(
            s.get("direct_reports") and int(s["direct_reports"]) > 0
            for s in items
            if s.get("direct_reports") is not None
        )
        has_responsibilities = any(s.get("responsibilities") for s in items)
        score += 30 if has_reports         else 0
        score += 20 if has_responsibilities else 0
        return min(100, score)

    def _score_certifications(self, items: list[dict]) -> int:
        if not items:
            return 0
        score = 0
        score += 50 if len(items) >= 1 else 0
        score += 30 if len(items) >= 2 else 0
        has_issuer = any(c.get("issuer") and c["issuer"].strip() for c in items)
        score += 20 if has_issuer else 0
        return min(100, score)

    def _score_skills(self, items: list[dict]) -> int:
        if not items:
            return 0
        count = len(items)
        # Volumen: 6 points per skill, max 75
        score = min(75, count * 6)
        # Bredde: både teknisk og blød
        categories = {s.get("category") for s in items if s.get("category")}
        has_diversity = len(categories) >= 2
        score += 25 if has_diversity else 0
        return min(100, score)

    # ─── Discovery-integration ────────────────────────────────────────────────

    def build_priority_context(
        self,
        scores: dict[str, Any],
        gaps: list[dict],
    ) -> str:
        """
        Byg en prioriteret kontekst til Discovery Agent-systemprompten.
        Kombinerer sektionsscores med eksisterende gaps.
        """
        section_scores = scores.get("sections") or {}
        overall = scores.get("overall", 0)
        missing = scores.get("missing_areas") or []

        # Sorter sektioner fra laveste til højeste score
        sorted_sections = sorted(
            section_scores.items(),
            key=lambda x: x[1],
        )

        lines = [f"PROFIL-FULDSTÆNDIGHED: {overall}%"]
        lines.append("")
        lines.append("Sektionsscores (lavest → brug mest tid her):")
        for section, score in sorted_sections:
            label = SECTION_LABELS.get(section, section)
            bar = self._score_bar(score)
            lines.append(f"  {bar} {label}: {score}%")

        if missing:
            lines.append("")
            lines.append("Manglende omrader (under 35%):")
            for area in missing:
                lines.append(f"  • {area}")

        # Prioritér gaps med laveste sektionsscore forst
        if gaps:
            priority_gaps = self._sort_gaps_by_score(gaps, section_scores)
            lines.append("")
            lines.append("Gaps sorteret efter behovet (hoejest prioritet forst):")
            for gap in priority_gaps[:6]:
                sec_score = section_scores.get(gap["section"], 50)
                lines.append(
                    f"  [{gap['priority'].upper()} | {gap['section']}: {sec_score}%] "
                    f"{gap['description']}"
                )

        return "\n".join(lines)

    @staticmethod
    def _score_bar(score: int) -> str:
        filled = score // 10
        empty = 10 - filled
        return f"[{'█' * filled}{'░' * empty}]"

    @staticmethod
    def _sort_gaps_by_score(gaps: list[dict], section_scores: dict[str, int]) -> list[dict]:
        """Sorter gaps efter (prioritet × (100 - sektionsscore))."""
        priority_val = {"high": 3, "medium": 2, "low": 1}

        def importance(gap: dict) -> float:
            p = priority_val.get(gap.get("priority", "medium"), 1)
            sec_score = section_scores.get(gap.get("section", ""), 50)
            return p * (100 - sec_score) / 100

        return sorted(gaps, key=importance, reverse=True)
