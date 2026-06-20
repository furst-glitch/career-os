"""
CV Service — filhåndtering, tekst-ekstraktion, profilopbygning og Master CV-generering.
"""
from __future__ import annotations

import hashlib
import io
from typing import Any

from supabase import Client


def extract_text_from_pdf(content: bytes) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(p for p in pages if p.strip())
    except Exception as exc:
        raise ValueError(f"Kunne ikke læse PDF: {exc}") from exc


def extract_text_from_docx(content: bytes) -> str:
    try:
        from docx import Document

        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        raise ValueError(f"Kunne ikke læse DOCX: {exc}") from exc


def extract_text(content: bytes, mime_type: str) -> str:
    if "pdf" in mime_type:
        return extract_text_from_pdf(content)
    if "word" in mime_type or mime_type.endswith(".document"):
        return extract_text_from_docx(content)
    # Plain text fallback
    return content.decode("utf-8", errors="replace")


class CVService:
    def __init__(self, supabase: Client) -> None:
        self.db = supabase

    # ─── Upload & Parse ──────────────────────────────────────────────────────

    async def create_upload(self, user_id: str, file_name: str, mime_type: str) -> str:
        """Opret upload-record og returnér id."""
        result = self.db.table("cv_uploads").insert({
            "user_id": user_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "status": "pending",
        }).execute()
        return result.data[0]["id"]

    async def save_parsed(
        self,
        upload_id: str,
        raw_text: str,
        parsed_data: dict,
    ) -> None:
        self.db.table("cv_uploads").update({
            "raw_text": raw_text,
            "parsed_data": parsed_data,
            "status": "completed",
        }).eq("id", upload_id).execute()

    async def mark_failed(self, upload_id: str, error: str) -> None:
        self.db.table("cv_uploads").update({
            "status": "failed",
            "error": error,
        }).eq("id", upload_id).execute()

    # ─── Populate profil fra parsed CV ───────────────────────────────────────

    async def populate_profile_from_parsed(
        self,
        user_id: str,
        upload_id: str,
        parsed: dict,
    ) -> str:
        """Opbygger alle profiltabeller fra parsed CV. Returnerer session_id."""
        master_cv_id = await self._get_or_create_master_cv_id(user_id)

        # Ryd eksisterende CV-data inden genimport — undgår duplikater ved genupload
        self.db.table("cv_experiences").delete().eq("master_cv_id", master_cv_id).execute()
        self.db.table("cv_educations").delete().eq("master_cv_id", master_cv_id).execute()
        self.db.table("cv_skills").delete().eq("master_cv_id", master_cv_id).execute()
        self.db.table("cv_projects").delete().eq("master_cv_id", master_cv_id).execute()
        self.db.table("cv_certifications").delete().eq("master_cv_id", master_cv_id).execute()
        self.db.table("cv_systems").delete().eq("master_cv_id", master_cv_id).execute()
        self.db.table("cv_leadership").delete().eq("master_cv_id", master_cv_id).execute()

        # Erfaringer
        for exp in parsed.get("experiences") or []:
            await self._insert_experience(master_cv_id, exp)

        # Uddannelse
        for edu in parsed.get("educations") or []:
            await self._insert_education(master_cv_id, edu)

        # Kompetencer
        for skill in parsed.get("skills") or []:
            await self._insert_skill(master_cv_id, skill)

        # Projekter
        for project in parsed.get("projects") or []:
            await self._insert_project(master_cv_id, project)

        # Certifikater
        for cert in parsed.get("certifications") or []:
            await self._insert_certification(master_cv_id, cert)

        # Systemer
        for system in parsed.get("systems") or []:
            await self._insert_system(master_cv_id, system)

        # Lederskab
        for leadership in parsed.get("leadership") or []:
            await self._insert_leadership(master_cv_id, leadership)

        # Gaps
        gaps = parsed.get("gaps") or []
        session_id = await self._create_discovery_session(user_id, upload_id, gaps)

        # Opdater master CV summary
        personal = parsed.get("personal") or {}
        summary = parsed.get("summary")
        if summary or personal.get("current_title"):
            self.db.table("master_cvs").update({
                "target_title": personal.get("current_title"),
                "summary": summary,
            }).eq("id", master_cv_id).execute()

        return session_id

    async def _get_or_create_master_cv_id(self, user_id: str) -> str:
        result = self.db.table("master_cvs").select("id").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]["id"]
        result = self.db.table("master_cvs").insert({
            "user_id": user_id,
            "title": "Mit Master CV",
            "language": "da",
        }).execute()
        return result.data[0]["id"]

    async def _insert_experience(self, master_cv_id: str, exp: dict) -> None:
        self.db.table("cv_experiences").insert({
            "master_cv_id": master_cv_id,
            "title": exp.get("title", ""),
            "company": exp.get("company", ""),
            "location": exp.get("location"),
            "period_start": self._parse_date(exp.get("period_start")) or "1900-01-01",
            "period_end": self._parse_date(exp.get("period_end")),
            "is_current": exp.get("is_current", False),
            "description": exp.get("description"),
            "technologies": exp.get("technologies") or [],
            "achievements": exp.get("achievements") or [],
        }).execute()

    async def _insert_education(self, master_cv_id: str, edu: dict) -> None:
        self.db.table("cv_educations").insert({
            "master_cv_id": master_cv_id,
            "degree": edu.get("degree", ""),
            "institution": edu.get("institution", ""),
            "period_start": self._parse_date(edu.get("period_start")),
            "period_end": self._parse_date(edu.get("period_end")),
            "description": edu.get("description"),
        }).execute()

    async def _insert_skill(self, master_cv_id: str, skill: dict) -> None:
        self.db.table("cv_skills").insert({
            "master_cv_id": master_cv_id,
            "name": skill.get("name", ""),
            "category": skill.get("category", "technical"),
            "level": skill.get("level"),
        }).execute()

    async def _insert_project(self, master_cv_id: str, project: dict) -> None:
        self.db.table("cv_projects").insert({
            "master_cv_id": master_cv_id,
            "name": project.get("name", ""),
            "description": project.get("description"),
            "role": project.get("role"),
            "technologies": project.get("technologies") or [],
            "outcomes": project.get("outcomes"),
            "period_start": self._parse_date(project.get("period_start")),
            "period_end": self._parse_date(project.get("period_end")),
        }).execute()

    async def _insert_certification(self, master_cv_id: str, cert: dict) -> None:
        self.db.table("cv_certifications").insert({
            "master_cv_id": master_cv_id,
            "name": cert.get("name", ""),
            "issuer": cert.get("issuer"),
            "issued_at": self._parse_date(cert.get("issued_at")),
            "expires_at": self._parse_date(cert.get("expires_at")),
            "credential_id": cert.get("credential_id"),
        }).execute()

    async def _insert_system(self, master_cv_id: str, system: dict) -> None:
        self.db.table("cv_systems").insert({
            "master_cv_id": master_cv_id,
            "name": system.get("name", ""),
            "category": system.get("category"),
            "proficiency": system.get("proficiency") or "intermediate",
        }).execute()

    async def _insert_leadership(self, master_cv_id: str, leadership: dict) -> None:
        self.db.table("cv_leadership").insert({
            "master_cv_id": master_cv_id,
            "title": leadership.get("title", ""),
            "scope": leadership.get("scope"),
            "direct_reports": leadership.get("direct_reports"),
            "period_start": self._parse_date(leadership.get("period_start")),
            "period_end": self._parse_date(leadership.get("period_end")),
            "responsibilities": leadership.get("responsibilities") or [],
        }).execute()

    async def _create_discovery_session(
        self, user_id: str, upload_id: str, gaps: list[dict]
    ) -> str:
        result = self.db.table("discovery_sessions").insert({
            "user_id": user_id,
            "cv_upload_id": upload_id,
            "session_type": "experience_interview",
            "status": "active",
            "messages": [],
            "gaps_total": len(gaps),
            "gaps_resolved": 0,
        }).execute()
        session_id = result.data[0]["id"]

        # Gem gaps
        for gap in gaps:
            self.db.table("profile_gaps").insert({
                "user_id": user_id,
                "session_id": session_id,
                "section": gap.get("section", "experiences"),
                "description": gap.get("description", ""),
                "priority": gap.get("priority", "medium"),
            }).execute()

        # Beregn initial completeness score
        try:
            from app.services.profile_completeness_service import ProfileCompletenessService
            await ProfileCompletenessService().calculate_and_save(user_id, self.db)
        except Exception:
            pass  # Score-fejl stopper ikke upload-flowet

        return session_id

    # ─── Master CV hentning ────────────────────────────────────────────────────

    async def get_full_profile(self, user_id: str) -> dict[str, Any]:
        """Henter komplet profil med alle sektioner."""
        master = self.db.table("master_cvs").select("*").eq("user_id", user_id).execute()
        if not master.data:
            return {}
        master_cv_id = master.data[0]["id"]

        experiences = self.db.table("cv_experiences").select("*").eq("master_cv_id", master_cv_id).order("period_start", desc=True).execute()
        educations  = self.db.table("cv_educations").select("*").eq("master_cv_id", master_cv_id).order("period_end", desc=True).execute()
        skills      = self.db.table("cv_skills").select("*").eq("master_cv_id", master_cv_id).order("sort_order").execute()
        projects    = self.db.table("cv_projects").select("*").eq("master_cv_id", master_cv_id).order("sort_order").execute()
        achievements = self.db.table("cv_achievements").select("*").eq("master_cv_id", master_cv_id).order("impact_level").execute()
        systems     = self.db.table("cv_systems").select("*").eq("master_cv_id", master_cv_id).order("sort_order").execute()
        leadership  = self.db.table("cv_leadership").select("*").eq("master_cv_id", master_cv_id).order("sort_order").execute()
        certs       = self.db.table("cv_certifications").select("*").eq("master_cv_id", master_cv_id).order("sort_order").execute()
        gaps        = self.db.table("profile_gaps").select("*").eq("user_id", user_id).eq("is_resolved", False).order("priority").execute()

        return {
            "master_cv": master.data[0],
            "experiences": experiences.data,
            "educations": educations.data,
            "skills": skills.data,
            "projects": projects.data,
            "achievements": achievements.data,
            "systems": systems.data,
            "leadership": leadership.data,
            "certifications": certs.data,
            "open_gaps": gaps.data,
        }

    async def save_master_cv_content(self, user_id: str, content: str) -> None:
        row = self.db.table("master_cvs").select("language").eq("user_id", user_id).limit(1).execute()
        language = (row.data[0].get("language") or "da") if row.data else "da"
        self.db.table("master_cvs").update({
            "raw_content": content,
            "is_generated": True,
        }).eq("user_id", user_id).execute()
        try:
            self.create_version(user_id, content, "ai", language)
        except Exception:
            pass  # Version-fejl stopper ikke generate-flowet

    # ─── Versioner ────────────────────────────────────────────────────────────

    def create_version(
        self, user_id: str, content: str, generated_by: str = "user", language: str = "da"
    ) -> dict:
        row = (
            self.db.table("document_versions")
            .select("version_number")
            .eq("user_id", user_id)
            .eq("document_type", "master_cv")
            .order("version_number", desc=True)
            .limit(1)
            .execute()
        )
        next_num = (row.data[0]["version_number"] + 1) if row.data else 1
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        result = self.db.table("document_versions").insert({
            "user_id": user_id,
            "document_type": "master_cv",
            "version_number": next_num,
            "title": f"Master CV v{next_num}",
            "content": content,
            "content_hash": content_hash,
            "language": language,
            "generated_by": generated_by,
        }).execute()
        return result.data[0]

    def list_versions(self, user_id: str) -> list[dict]:
        result = (
            self.db.table("document_versions")
            .select("id, version_number, title, language, generated_by, created_at")
            .eq("user_id", user_id)
            .eq("document_type", "master_cv")
            .order("version_number", desc=True)
            .execute()
        )
        return result.data or []

    def get_version_content(self, version_id: str, user_id: str) -> str | None:
        result = (
            self.db.table("document_versions")
            .select("content")
            .eq("id", version_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0]["content"] if result.data else None

    @staticmethod
    def _parse_date(value: str | None) -> str | None:
        """Konverterer YYYY-MM til YYYY-MM-01 for Postgres date-type."""
        if not value:
            return None
        if len(value) == 7 and "-" in value:
            return f"{value}-01"
        return value
