"""
Application Service — CRUD for application_pipeline, documents og cover letters.
"""
from __future__ import annotations

from supabase import Client


class ApplicationService:
    def __init__(self, db: Client) -> None:
        self.db = db

    # ── Pipeline CRUD ─────────────────────────────────────────────────────────

    def list_pipeline(self, user_id: str, status: str | None = None) -> list[dict]:
        q = (
            self.db.table("application_pipeline")
            .select(
                "id, current_status, priority, deadline, notes, source, created_at, updated_at,"
                "jobs(id, title, company, location, url, salary_min, salary_max, match_score, job_type, remote_type)"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
        if status:
            q = q.eq("current_status", status)
        return q.execute().data or []

    def get_pipeline(self, user_id: str, pipeline_id: str) -> dict | None:
        result = (
            self.db.table("application_pipeline")
            .select("*, jobs(*)")
            .eq("id", pipeline_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def create_pipeline(self, user_id: str, job_id: str, data: dict) -> dict:
        payload = {
            "user_id": user_id,
            "job_id": job_id,
            "current_status": data.get("status", "draft"),
            "priority": data.get("priority", "medium"),
            "deadline": data.get("deadline"),
            "source": data.get("source"),
            "notes": data.get("notes"),
        }
        result = self.db.table("application_pipeline").insert(payload).execute()
        return result.data[0]

    def update_pipeline(self, user_id: str, pipeline_id: str, data: dict) -> dict:
        allowed = {"current_status", "priority", "deadline", "notes"}
        payload = {k: v for k, v in data.items() if k in allowed}
        result = (
            self.db.table("application_pipeline")
            .update(payload)
            .eq("id", pipeline_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0]

    def delete_pipeline(self, user_id: str, pipeline_id: str) -> None:
        self.db.table("application_pipeline").delete().eq("id", pipeline_id).eq("user_id", user_id).execute()

    # ── Status History ─────────────────────────────────────────────────────────

    def get_status_history(self, user_id: str, pipeline_id: str) -> list[dict]:
        pipeline = self.get_pipeline(user_id, pipeline_id)
        if not pipeline:
            return []
        result = (
            self.db.table("application_status_history")
            .select("*")
            .eq("pipeline_id", pipeline_id)
            .order("changed_at", desc=True)
            .execute()
        )
        return result.data or []

    # ── Documents ──────────────────────────────────────────────────────────────

    def list_documents(self, user_id: str, pipeline_id: str) -> list[dict]:
        pipeline = self.get_pipeline(user_id, pipeline_id)
        if not pipeline:
            return []
        result = (
            self.db.table("pipeline_documents")
            .select(
                "id, document_role, added_at,"
                "document_versions(id, title, version_number, language, document_type, generated_by, created_at, content)"
            )
            .eq("pipeline_id", pipeline_id)
            .execute()
        )
        return result.data or []

    def add_document(self, user_id: str, pipeline_id: str, document_id: str, role: str) -> dict:
        result = self.db.table("pipeline_documents").upsert(
            {"pipeline_id": pipeline_id, "document_id": document_id, "document_role": role},
            on_conflict="pipeline_id,document_id",
        ).execute()
        return result.data[0]

    # ── Cover Letter ───────────────────────────────────────────────────────────

    def save_cover_letter(
        self,
        user_id: str,
        pipeline_id: str,
        title: str,
        content: str,
        language: str,
    ) -> dict:
        """Gemmer AI-genereret ansøgning som document_version og tilknytter til pipeline."""
        import hashlib
        mcv = self.db.table("master_cvs").select("id").eq("user_id", user_id).limit(1).execute()
        mcv_id = mcv.data[0]["id"] if mcv.data else None

        existing = (
            self.db.table("document_versions")
            .select("version_number")
            .eq("pipeline_id", pipeline_id)
            .eq("document_type", "cover_letter")
            .order("version_number", desc=True)
            .limit(1)
            .execute()
        )
        next_version = (existing.data[0]["version_number"] + 1) if existing.data else 1

        doc = self.db.table("document_versions").insert({
            "user_id": user_id,
            "master_cv_id": mcv_id,
            "pipeline_id": pipeline_id,
            "title": title,
            "content": content,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "language": language,
            "version_number": next_version,
            "document_type": "cover_letter",
            "generated_by": "ai",
        }).execute()
        doc_id = doc.data[0]["id"]
        self.add_document(user_id, pipeline_id, doc_id, "cover_letter")
        return doc.data[0]

    def get_document_content(self, user_id: str, document_id: str) -> dict | None:
        result = (
            self.db.table("document_versions")
            .select("*")
            .eq("id", document_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def update_document_content(
        self, user_id: str, document_id: str, content: str, title: str | None = None
    ) -> dict:
        payload: dict = {"content": content}
        if title:
            payload["title"] = title
        result = (
            self.db.table("document_versions")
            .update(payload)
            .eq("id", document_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0]
