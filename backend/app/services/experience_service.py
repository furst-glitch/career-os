"""
Experience Service — CRUD for alle 7 kandidat-profil-sektioner.
"""
from __future__ import annotations

from supabase import Client


class ExperienceService:
    def __init__(self, supabase: Client) -> None:
        self.db = supabase

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _master_cv_id(self, user_id: str) -> str | None:
        result = self.db.table("master_cvs").select("id").eq("user_id", user_id).execute()
        return result.data[0]["id"] if result.data else None

    # ─── Experiences ─────────────────────────────────────────────────────────

    def list_experiences(self, user_id: str) -> list[dict]:
        mcv = self._master_cv_id(user_id)
        if not mcv:
            return []
        return self.db.table("cv_experiences").select("*").eq("master_cv_id", mcv).order("period_start", desc=True).execute().data

    def create_experience(self, user_id: str, data: dict) -> dict:
        mcv = self._master_cv_id(user_id)
        result = self.db.table("cv_experiences").insert({**data, "master_cv_id": mcv}).execute()
        return result.data[0]

    def update_experience(self, experience_id: str, data: dict) -> dict:
        result = self.db.table("cv_experiences").update(data).eq("id", experience_id).execute()
        return result.data[0]

    def delete_experience(self, experience_id: str) -> None:
        self.db.table("cv_experiences").delete().eq("id", experience_id).execute()

    # ─── Projects ────────────────────────────────────────────────────────────

    def list_projects(self, user_id: str) -> list[dict]:
        mcv = self._master_cv_id(user_id)
        if not mcv:
            return []
        return self.db.table("cv_projects").select("*").eq("master_cv_id", mcv).order("sort_order").execute().data

    def create_project(self, user_id: str, data: dict) -> dict:
        mcv = self._master_cv_id(user_id)
        result = self.db.table("cv_projects").insert({**data, "master_cv_id": mcv}).execute()
        return result.data[0]

    def update_project(self, project_id: str, data: dict) -> dict:
        result = self.db.table("cv_projects").update(data).eq("id", project_id).execute()
        return result.data[0]

    def delete_project(self, project_id: str) -> None:
        self.db.table("cv_projects").delete().eq("id", project_id).execute()

    # ─── Achievements ─────────────────────────────────────────────────────────

    def list_achievements(self, user_id: str) -> list[dict]:
        mcv = self._master_cv_id(user_id)
        if not mcv:
            return []
        return self.db.table("cv_achievements").select("*").eq("master_cv_id", mcv).order("sort_order").execute().data

    def create_achievement(self, user_id: str, data: dict) -> dict:
        mcv = self._master_cv_id(user_id)
        result = self.db.table("cv_achievements").insert({**data, "master_cv_id": mcv}).execute()
        return result.data[0]

    def update_achievement(self, achievement_id: str, data: dict) -> dict:
        result = self.db.table("cv_achievements").update(data).eq("id", achievement_id).execute()
        return result.data[0]

    def delete_achievement(self, achievement_id: str) -> None:
        self.db.table("cv_achievements").delete().eq("id", achievement_id).execute()

    # ─── Systems ─────────────────────────────────────────────────────────────

    def list_systems(self, user_id: str) -> list[dict]:
        mcv = self._master_cv_id(user_id)
        if not mcv:
            return []
        return self.db.table("cv_systems").select("*").eq("master_cv_id", mcv).order("category").execute().data

    def create_system(self, user_id: str, data: dict) -> dict:
        mcv = self._master_cv_id(user_id)
        result = self.db.table("cv_systems").insert({**data, "master_cv_id": mcv}).execute()
        return result.data[0]

    def update_system(self, system_id: str, data: dict) -> dict:
        result = self.db.table("cv_systems").update(data).eq("id", system_id).execute()
        return result.data[0]

    def delete_system(self, system_id: str) -> None:
        self.db.table("cv_systems").delete().eq("id", system_id).execute()

    # ─── Leadership ──────────────────────────────────────────────────────────

    def list_leadership(self, user_id: str) -> list[dict]:
        mcv = self._master_cv_id(user_id)
        if not mcv:
            return []
        return self.db.table("cv_leadership").select("*").eq("master_cv_id", mcv).order("sort_order").execute().data

    def create_leadership(self, user_id: str, data: dict) -> dict:
        mcv = self._master_cv_id(user_id)
        result = self.db.table("cv_leadership").insert({**data, "master_cv_id": mcv}).execute()
        return result.data[0]

    def update_leadership(self, leadership_id: str, data: dict) -> dict:
        result = self.db.table("cv_leadership").update(data).eq("id", leadership_id).execute()
        return result.data[0]

    def delete_leadership(self, leadership_id: str) -> None:
        self.db.table("cv_leadership").delete().eq("id", leadership_id).execute()

    # ─── Certifications ───────────────────────────────────────────────────────

    def list_certifications(self, user_id: str) -> list[dict]:
        mcv = self._master_cv_id(user_id)
        if not mcv:
            return []
        return self.db.table("cv_certifications").select("*").eq("master_cv_id", mcv).order("issued_at", desc=True).execute().data

    def create_certification(self, user_id: str, data: dict) -> dict:
        mcv = self._master_cv_id(user_id)
        result = self.db.table("cv_certifications").insert({**data, "master_cv_id": mcv}).execute()
        return result.data[0]

    def update_certification(self, cert_id: str, data: dict) -> dict:
        result = self.db.table("cv_certifications").update(data).eq("id", cert_id).execute()
        return result.data[0]

    def delete_certification(self, cert_id: str) -> None:
        self.db.table("cv_certifications").delete().eq("id", cert_id).execute()

    # ─── Gaps ─────────────────────────────────────────────────────────────────

    def list_open_gaps(self, user_id: str) -> list[dict]:
        return (
            self.db.table("profile_gaps")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_resolved", False)
            .order("priority")
            .execute()
            .data
        )

    def resolve_gap(self, gap_id: str) -> None:
        self.db.table("profile_gaps").update({
            "is_resolved": True,
            "resolved_at": "now()",
        }).eq("id", gap_id).execute()

    def add_achievements_from_discovery(self, user_id: str, achievements: list[dict]) -> None:
        mcv = self._master_cv_id(user_id)
        if not mcv or not achievements:
            return
        rows = [
            {
                "master_cv_id": mcv,
                "title": a.get("title", ""),
                "description": a.get("description"),
                "metric": a.get("metric"),
                "impact_level": a.get("impact_level", "medium"),
                "year": a.get("year"),
            }
            for a in achievements
        ]
        self.db.table("cv_achievements").insert(rows).execute()

    def add_projects_from_discovery(self, user_id: str, projects: list[dict]) -> None:
        mcv = self._master_cv_id(user_id)
        if not mcv or not projects:
            return
        rows = [
            {
                "master_cv_id": mcv,
                "name": p.get("name", ""),
                "description": p.get("description"),
                "role": p.get("role"),
                "technologies": p.get("technologies") or [],
                "outcomes": p.get("outcomes"),
            }
            for p in projects
        ]
        self.db.table("cv_projects").insert(rows).execute()

    def add_systems_from_discovery(self, user_id: str, systems: list[dict]) -> None:
        mcv = self._master_cv_id(user_id)
        if not mcv or not systems:
            return
        rows = [
            {
                "master_cv_id": mcv,
                "name": s.get("name", ""),
                "category": s.get("category"),
                "proficiency": s.get("proficiency") or "intermediate",
            }
            for s in systems
        ]
        self.db.table("cv_systems").insert(rows).execute()

    def add_skills_from_discovery(self, user_id: str, skills: list[dict]) -> None:
        mcv = self._master_cv_id(user_id)
        if not mcv or not skills:
            return
        rows = [
            {
                "master_cv_id": mcv,
                "name": sk.get("name", ""),
                "category": sk.get("category", "technical"),
                "level": sk.get("level"),
            }
            for sk in skills
        ]
        self.db.table("cv_skills").insert(rows).execute()

    def add_leadership_from_discovery(self, user_id: str, leadership: list[dict]) -> None:
        mcv = self._master_cv_id(user_id)
        if not mcv or not leadership:
            return
        rows = [
            {
                "master_cv_id": mcv,
                "title": ldr.get("title", ""),
                "scope": ldr.get("scope"),
                "direct_reports": ldr.get("direct_reports"),
                "responsibilities": ldr.get("responsibilities") or [],
            }
            for ldr in leadership
        ]
        self.db.table("cv_leadership").insert(rows).execute()
