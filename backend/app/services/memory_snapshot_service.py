"""
Memory Snapshot Engine — samler al brugerspecifik viden til et agent-optimeret kontekstdokument.

Standardinput til:
  Career Coach Agent · Application Agent · Job Agent
  Salary Agent · Interview Agent · Review Board
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from supabase import Client

from app.services.memory_service import MemoryService

# Process-level TTL cache: {user_id: (snapshot_dict, expires_at_ts)}
_SNAPSHOT_CACHE: dict[str, tuple[dict, float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


class MemorySnapshotService:
    def __init__(self, supabase: Client) -> None:
        self.db = supabase
        self.mem = MemoryService(supabase)

    def invalidate(self, user_id: str) -> None:
        _SNAPSHOT_CACHE.pop(user_id, None)

    def snapshot(self, user_id: str, force: bool = False) -> dict:
        """Returner komplet, agent-optimeret snapshot af brugerens karriereviden.
        Cached for _CACHE_TTL_SECONDS. Pass force=True to bypass cache."""
        now = time.monotonic()
        if not force and user_id in _SNAPSHOT_CACHE:
            cached, expires = _SNAPSHOT_CACHE[user_id]
            if now < expires:
                return cached

        """Returner komplet, agent-optimeret snapshot af brugerens karriereviden."""
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
            "generated_at": datetime.now(timezone.utc).isoformat(),
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
            # Kompakt tekstrepræsentation til prompt-injection
            "text_summary": self._text_summary(profile, experience, skills, goals, preferences, milestones),
        }
        # Store in cache
        _SNAPSHOT_CACHE[user_id] = (result, now + _CACHE_TTL_SECONDS)
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
            "display_name, language, default_ai_provider"
        ).eq("user_id", user_id).limit(1).execute()
        up = upr.data[0] if upr.data else {}
        return {
            "display_name":      up.get("display_name"),
            "target_title":      mcv.get("target_title"),
            "summary":           mcv.get("summary"),
            "language":          mcv.get("language") or up.get("language") or "da",
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
