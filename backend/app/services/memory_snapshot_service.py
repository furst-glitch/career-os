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

        profile     = self._profile(user_id, mcv_id)
        experience  = self._experience(mcv_id)
        skills      = self._skills(mcv_id)
        certs       = self._certs(mcv_id)
        projects    = self._projects(mcv_id)
        goals       = [g for g in self.mem.list_goals(user_id) if g.get("status") == "active"]
        milestones  = self.mem.list_milestones(user_id)[:5]
        preferences = self.mem.get_preferences(user_id)
        memories    = self.mem.list_memories(user_id, limit=15)

        result = {
            "generated_at": datetime.now(UTC).isoformat(),
            "user_id":      user_id,
            "profile":      profile,
            "experience":   experience,
            "skills":       skills,
            "certifications": certs,
            "projects":     projects,
            "goals":        goals,
            "milestones":   milestones,
            "preferences":  preferences,
            "recent_memories": memories,
            "text_summary": self._text_summary(profile, experience, skills, goals, preferences, milestones),
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
            .limit(5)
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

    def _text_summary(
        self,
        profile: dict,
        experience: list,
        skills: list,
        goals: list,
        prefs: dict,
        milestones: list,
    ) -> str:
        lines: list[str] = []

        if profile.get("full_name"):
            lines.append(f"NAVN: {profile['full_name']}")
        if profile.get("email"):
            lines.append(f"EMAIL: {profile['email']}")
        if profile.get("phone"):
            lines.append(f"TELEFON: {profile['phone']}")
        if profile.get("location"):
            lines.append(f"LOKATION: {profile['location']}")
        if profile.get("linkedin_url"):
            lines.append(f"LINKEDIN: {profile['linkedin_url']}")
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

        if experience:
            exp_str = "; ".join(
                f"{e['title']} @ {e['company']}" + (" (nu)" if e.get("is_current") else "")
                for e in experience[:3]
            )
            lines.append(f"ERFARING: {exp_str}")

        if skills:
            skill_names = ", ".join(s["name"] for s in skills[:12])
            lines.append(f"KOMPETENCER: {skill_names}")

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
