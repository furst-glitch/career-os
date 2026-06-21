"""
Memory Snapshot Engine — samler al brugerspecifik viden til et agent-optimeret kontekstdokument.

Standardinput til:
  Career Coach Agent · Application Agent · Job Agent
  Salary Agent · Interview Agent · Review Board

Cache-strategi:
  L1 = process-level dict (0ms, same-process only)
  L2 = Redis sync (1-2ms, shared across Render instances)
  L3 = Supabase DB (50-200ms, always authoritative)
"""
from __future__ import annotations

import time
from datetime import UTC, datetime

from supabase import Client

from app.services.cache_service import (
    TTL_SNAPSHOT,
    get_sync_cache,
    key_snapshot,
)
from app.services.memory_service import MemoryService


def _clean_url(url: str | None) -> str:
    """Decode URL encoding and strip protocol/www prefix for display."""
    if not url:
        return ""
    from urllib.parse import unquote
    url = unquote(url)
    for prefix in ("https://", "http://"):
        if url.lower().startswith(prefix):
            url = url[len(prefix):]
    if url.lower().startswith("www."):
        url = url[4:]
    return url.rstrip("/")


# L1: process-level dict  {user_id: (snapshot, expires_monotonic)}
_L1: dict[str, tuple[dict, float]] = {}


class MemorySnapshotService:
    def __init__(self, supabase: Client) -> None:
        self.db = supabase
        self.mem = MemoryService(supabase)

    def invalidate(self, user_id: str) -> None:
        """Purge L1 + L2 cache for this user."""
        _L1.pop(user_id, None)
        rc = get_sync_cache()
        if rc:
            rc.delete_pattern(f"snapshot:{user_id}*")

    def snapshot(self, user_id: str, force: bool = False) -> dict:
        """Return career snapshot — L1 → L2 (Redis) → DB fallback."""
        now = time.monotonic()

        # L1 hit
        if not force:
            l1 = _L1.get(user_id)
            if l1 and now < l1[1]:
                return l1[0]

        # L2 hit (Redis)
        rc = get_sync_cache()
        if not force and rc:
            cached = rc.get(key_snapshot(user_id))
            if cached:
                _L1[user_id] = (cached, now + TTL_SNAPSHOT)  # warm L1
                return cached

        # L3: full DB fetch
        mcv_id = self._mcv_id(user_id)

        profile      = self._profile(user_id, mcv_id)
        experience   = self._experience(mcv_id)
        education    = self._education(mcv_id)
        skills       = self._skills(mcv_id)
        systems      = self._systems(mcv_id)
        leadership   = self._leadership(mcv_id)
        achievements = self._achievements(mcv_id)
        certs        = self._certs(mcv_id)
        projects     = self._projects(mcv_id)
        goals        = [g for g in self.mem.list_goals(user_id) if g.get("status") == "active"]
        milestones   = self.mem.list_milestones(user_id)[:5]
        preferences  = self.mem.get_preferences(user_id)
        memories     = self.mem.list_memories(user_id, limit=15)

        result = {
            "generated_at":    datetime.now(UTC).isoformat(),
            "user_id":         user_id,
            "profile":         profile,
            "experience":      experience,
            "education":       education,
            "skills":          skills,
            "systems":         systems,
            "leadership":      leadership,
            "achievements":    achievements,
            "certifications":  certs,
            "projects":        projects,
            "goals":           goals,
            "milestones":      milestones,
            "preferences":     preferences,
            "recent_memories": memories,
            "text_summary":    self._text_summary(
                profile, experience, education, skills, systems,
                leadership, achievements, certs, goals, preferences, milestones,
            ),
        }

        # Populate L2 (Redis) then L1
        if rc:
            rc.set(key_snapshot(user_id), result, ttl=TTL_SNAPSHOT)
        _L1[user_id] = (result, now + TTL_SNAPSHOT)
        return result

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _mcv_id(self, user_id: str) -> str | None:
        row = self.db.table("master_cvs").select("id").eq("user_id", user_id).limit(1).execute()
        return row.data[0]["id"] if row.data else None

    def _profile(self, user_id: str, mcv_id: str | None) -> dict:
        mcv = {}
        if mcv_id:
            row = self.db.table("master_cvs").select(
                "target_title, summary, language"
            ).eq("id", mcv_id).limit(1).execute()
            mcv = row.data[0] if row.data else {}
        upr = self.db.table("user_profiles").select(
            "full_name, display_name, email, phone, location, linkedin_url, language, "
            "default_ai_provider, address, city, postal_code, website, "
            "salary_expectation, notice_period"
        ).eq("user_id", user_id).limit(1).execute()
        up = upr.data[0] if upr.data else {}
        return {
            "full_name":           up.get("full_name") or up.get("display_name"),
            "display_name":        up.get("display_name"),
            "email":               up.get("email"),
            "phone":               up.get("phone"),
            "location":            up.get("location"),
            "linkedin_url":        up.get("linkedin_url"),
            "linkedin_display":    _clean_url(up.get("linkedin_url")),
            "address":             up.get("address"),
            "city":                up.get("city"),
            "postal_code":         up.get("postal_code"),
            "website":             up.get("website"),
            "salary_expectation":  up.get("salary_expectation"),
            "notice_period":       up.get("notice_period"),
            "target_title":        mcv.get("target_title"),
            "summary":             mcv.get("summary"),
            "language":            mcv.get("language") or up.get("language") or "da",
            "default_ai_provider": up.get("default_ai_provider"),
        }

    def _experience(self, mcv_id: str | None) -> list[dict]:
        if not mcv_id:
            return []
        rows = (
            self.db.table("cv_experiences")
            .select("title, company, period_start, period_end, is_current, description, achievements, technologies")
            .eq("master_cv_id", mcv_id)
            .order("period_start", desc=True)
            .execute()
            .data
        )
        return rows or []

    def _skills(self, mcv_id: str | None) -> list[dict]:
        if not mcv_id:
            return []
        rows = (
            self.db.table("cv_skills")
            .select("name, level, category")
            .eq("master_cv_id", mcv_id)
            .order("sort_order")
            .execute()
            .data
        )
        return rows or []

    def _education(self, mcv_id: str | None) -> list[dict]:
        if not mcv_id:
            return []
        rows = (
            self.db.table("cv_educations")
            .select("degree, institution, period_start, period_end, description")
            .eq("master_cv_id", mcv_id)
            .order("period_start", desc=True)
            .execute()
            .data
        )
        return rows or []

    def _certs(self, mcv_id: str | None) -> list[dict]:
        if not mcv_id:
            return []
        rows = (
            self.db.table("cv_certifications")
            .select("name, issuer, issued_at, expires_at")
            .eq("master_cv_id", mcv_id)
            .execute()
            .data
        )
        return rows or []

    def _projects(self, mcv_id: str | None) -> list[dict]:
        if not mcv_id:
            return []
        rows = (
            self.db.table("cv_projects")
            .select("name, role, technologies, outcomes, description")
            .eq("master_cv_id", mcv_id)
            .order("sort_order")
            .limit(5)
            .execute()
            .data
        )
        return rows or []

    def _systems(self, mcv_id: str | None) -> list[dict]:
        if not mcv_id:
            return []
        rows = (
            self.db.table("cv_systems")
            .select("name, category, proficiency")
            .eq("master_cv_id", mcv_id)
            .order("sort_order")
            .execute()
            .data
        )
        return rows or []

    def _leadership(self, mcv_id: str | None) -> list[dict]:
        if not mcv_id:
            return []
        rows = (
            self.db.table("cv_leadership")
            .select("title, scope, direct_reports, period_start, period_end, responsibilities")
            .eq("master_cv_id", mcv_id)
            .order("sort_order")
            .execute()
            .data
        )
        return rows or []

    def _achievements(self, mcv_id: str | None) -> list[dict]:
        if not mcv_id:
            return []
        rows = (
            self.db.table("cv_achievements")
            .select("title, description, metric, impact_level, year")
            .eq("master_cv_id", mcv_id)
            .order("impact_level", desc=True)
            .limit(20)
            .execute()
            .data
        )
        return rows or []

    def _text_summary(
        self,
        profile: dict,
        experience: list,
        education: list,
        skills: list,
        systems: list,
        leadership: list,
        achievements: list,
        certs: list,
        goals: list,
        prefs: dict,
        milestones: list,
    ) -> str:
        lines: list[str] = []

        # ── Kontaktprofil ────────────────────────────────────────────────────
        if profile.get("full_name"):
            lines.append(f"NAVN: {profile['full_name']}")
        if profile.get("email"):
            lines.append(f"EMAIL: {profile['email']}")
        if profile.get("phone"):
            lines.append(f"TELEFON: {profile['phone']}")
        if profile.get("location"):
            lines.append(f"LOKATION: {profile['location']}")
        li = profile.get("linkedin_display") or profile.get("linkedin_url")
        if li:
            lines.append(f"LINKEDIN: {li}")
        if profile.get("website"):
            lines.append(f"WEBSITE: {profile['website']}")
        if profile.get("salary_expectation"):
            lines.append(f"LØNFORVENTNING: {profile['salary_expectation']:,} DKK/år".replace(",", "."))
        if profile.get("notice_period"):
            lines.append(f"OPSIGELSESVARSEL: {profile['notice_period']}")
        if profile.get("target_title"):
            lines.append(f"KANDIDAT: {profile['target_title']}")
        if profile.get("summary"):
            lines.append(f"SAMMENFATNING: {profile['summary']}")

        # ── Erfaring ─────────────────────────────────────────────────────────
        if experience:
            exp_parts = []
            for i, e in enumerate(experience):
                start = (e.get("period_start") or "")[:7]
                end = "nu" if e.get("is_current") else (e.get("period_end") or "")[:7]
                period = f"{start}–{end}" if start else ("nu" if e.get("is_current") else "")
                entry = f"{e['title']} @ {e['company']} [{period}]"
                if i < 5:
                    desc = e.get("description") or ""
                    achiev = "; ".join((e.get("achievements") or [])[:2])
                    detail = (achiev or desc)[:120]
                    if detail:
                        entry += f": {detail}"
                exp_parts.append(entry)
            lines.append("ERFARING:\n" + "\n".join(f"  - {p}" for p in exp_parts))

        # ── Uddannelse ───────────────────────────────────────────────────────
        if education:
            edu_parts = []
            for e in education:
                degree = e.get("degree") or ""
                institution = e.get("institution") or ""
                start = (e.get("period_start") or "")[:4]
                end = (e.get("period_end") or "")[:4]
                period = f"{start}-{end}" if start and end else (start or end or "")
                entry = f"{degree} - {institution}" if degree and institution else (degree or institution)
                if period:
                    entry += f" [{period}]"
                if entry.strip(" -"):
                    edu_parts.append(entry)
            if edu_parts:
                lines.append("UDDANNELSE:\n" + "\n".join(f"  - {p}" for p in edu_parts))

        # ── Kompetencer ──────────────────────────────────────────────────────
        if skills:
            domain = [s["name"] for s in skills if s.get("category") not in ("language", "technical")]
            tech   = [s["name"] for s in skills if s.get("category") == "technical"]
            langs  = [s["name"] for s in skills if s.get("category") == "language"]
            if domain:
                lines.append("KOMPETENCER: " + ", ".join(domain))
            if tech:
                lines.append("TEKNISKE FÆRDIGHEDER: " + ", ".join(tech))
            if langs:
                lines.append("SPROG: " + ", ".join(langs))

        # ── Systemer ─────────────────────────────────────────────────────────
        if systems:
            sys_names = ", ".join(s["name"] for s in systems)
            lines.append(f"SYSTEMER: {sys_names}")

        # ── Lederskab ────────────────────────────────────────────────────────
        if leadership:
            ldr_parts = []
            for l in leadership:
                start = (l.get("period_start") or "")[:4]
                end = (l.get("period_end") or "")[:4]
                period = f"{start}-{end}" if start and end else (start or end or "")
                entry = f"{l['title']}" + (f" [{period}]" if period else "")
                if l.get("scope"):
                    entry += f": {l['scope'][:100]}"
                ldr_parts.append(entry)
            lines.append("LEDERSKAB:\n" + "\n".join(f"  - {p}" for p in ldr_parts))

        # ── Præstationer ─────────────────────────────────────────────────────
        if achievements:
            ach_parts = []
            for a in achievements[:10]:
                entry = a.get("title", "")
                if a.get("metric"):
                    entry += f" [{a['metric']}]"
                ach_parts.append(entry)
            lines.append("PRÆSTATIONER:\n" + "\n".join(f"  - {p}" for p in ach_parts))

        # ── Certifikater ─────────────────────────────────────────────────────
        if certs:
            cert_parts = [
                f"{c['name']}" + (f" ({c['issuer']})" if c.get("issuer") else "")
                for c in certs
            ]
            lines.append("CERTIFIKATER:\n" + "\n".join(f"  - {p}" for p in cert_parts))

        # ── Karrieremål og præferencer ───────────────────────────────────────
        if goals:
            goal_str = "; ".join(g["title"] for g in goals[:3])
            lines.append(f"AKTIVE MÅL: {goal_str}")

        if milestones:
            ms_str = "; ".join(f"{m['title']} ({m.get('occurred_at', '')[:7]})" for m in milestones[:3])
            lines.append(f"MILEPÆLE: {ms_str}")

        if prefs:
            parts = []
            if prefs.get("industries"):
                parts.append("Brancher: " + ", ".join(prefs["industries"][:3]))
            if prefs.get("remote_preference"):
                parts.append("Arbejdsstil: " + prefs["remote_preference"])
            if prefs.get("salary_min") or prefs.get("salary_max"):
                sal = f"{prefs.get('salary_min', '?')}–{prefs.get('salary_max', '?')} {prefs.get('salary_currency', 'DKK')}"
                parts.append(f"Løn: {sal}")
            if parts:
                lines.append("PRÆFERENCER: " + " | ".join(parts))

        return "\n".join(lines)
