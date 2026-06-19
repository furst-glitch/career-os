"""
Experience Service — CRUD for alle 7 kandidat-profil-sektioner.
"""
from __future__ import annotations

from datetime import datetime, timezone

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

    # ─── Skills ───────────────────────────────────────────────────────────────

    def list_skills(self, user_id: str) -> list[dict]:
        mcv = self._master_cv_id(user_id)
        if not mcv:
            return []
        return self.db.table("cv_skills").select("*").eq("master_cv_id", mcv).order("sort_order").execute().data

    def create_skill(self, user_id: str, data: dict) -> dict:
        mcv = self._master_cv_id(user_id)
        result = self.db.table("cv_skills").insert({**data, "master_cv_id": mcv}).execute()
        return result.data[0]

    def update_skill(self, skill_id: str, data: dict) -> dict:
        result = self.db.table("cv_skills").update(data).eq("id", skill_id).execute()
        return result.data[0]

    def delete_skill(self, skill_id: str) -> None:
        self.db.table("cv_skills").delete().eq("id", skill_id).execute()

    # ─── Educations ──────────────────────────────────────────────────────────

    def list_educations(self, user_id: str) -> list[dict]:
        mcv = self._master_cv_id(user_id)
        if not mcv:
            return []
        return (
            self.db.table("cv_educations")
            .select("*")
            .eq("master_cv_id", mcv)
            .order("period_start", desc=True)
            .execute()
            .data
        )

    def create_education(self, user_id: str, data: dict) -> dict:
        mcv = self._master_cv_id(user_id)
        result = self.db.table("cv_educations").insert({**data, "master_cv_id": mcv}).execute()
        return result.data[0]

    def update_education(self, education_id: str, data: dict) -> dict:
        result = self.db.table("cv_educations").update(data).eq("id", education_id).execute()
        return result.data[0]

    def delete_education(self, education_id: str) -> None:
        self.db.table("cv_educations").delete().eq("id", education_id).execute()

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
            "resolved_at": datetime.now(timezone.utc).isoformat(),
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

    def add_certifications_from_discovery(self, user_id: str, certifications: list[dict]) -> None:
        mcv = self._master_cv_id(user_id)
        if not mcv or not certifications:
            return
        rows = [
            {
                "master_cv_id": mcv,
                "name": c.get("name", ""),
                "issuer": c.get("issuer"),
                "issued_at": c.get("issued_at"),
                "expires_at": c.get("expires_at"),
                "credential_id": c.get("credential_id"),
            }
            for c in certifications
        ]
        self.db.table("cv_certifications").insert(rows).execute()

    def apply_experience_additions(self, user_id: str, additions: list[dict]) -> None:
        """Tilføjer nye achievements og teknologier til eksisterende erfaringer."""
        mcv = self._master_cv_id(user_id)
        if not mcv or not additions:
            return
        exps = (
            self.db.table("cv_experiences")
            .select("id, company, achievements, technologies")
            .eq("master_cv_id", mcv)
            .execute()
            .data
        )
        for addition in additions:
            company = (addition.get("company") or "").lower()
            for exp in exps:
                if company and company in (exp.get("company") or "").lower():
                    current_ach = exp.get("achievements") or []
                    new_ach = addition.get("new_achievements") or []
                    current_tech = exp.get("technologies") or []
                    new_tech = addition.get("new_technologies") or []
                    merged_ach = list({*current_ach, *new_ach})
                    merged_tech = list({*current_tech, *new_tech})
                    self.db.table("cv_experiences").update({
                        "achievements": merged_ach,
                        "technologies": merged_tech,
                    }).eq("id", exp["id"]).execute()
                    break
