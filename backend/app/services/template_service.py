"""P3: Document Template Service."""
from __future__ import annotations

from datetime import UTC, datetime

from supabase import Client


class TemplateService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def list_templates(
        self,
        user_id: str,
        template_type: str | None = None,
    ) -> list[dict]:
        q = (
            self.db.table("document_templates")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
        if template_type:
            q = q.eq("type", template_type)
        return q.execute().data or []

    def get_template(self, user_id: str, template_id: str) -> dict | None:
        rows = (
            self.db.table("document_templates")
            .select("*")
            .eq("id", template_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None

    def create_template(self, user_id: str, data: dict) -> dict:
        payload = {
            "user_id": user_id,
            "name": data["name"],
            "type": data.get("type", "cover_letter"),
            "language": data.get("language", "da"),
            "content": data.get("content", ""),
            "writing_style": data.get("writing_style", "professional"),
            "focus_areas": data.get("focus_areas", []),
        }
        return self.db.table("document_templates").insert(payload).execute().data[0]

    def update_template(self, user_id: str, template_id: str, data: dict) -> dict | None:
        allowed = {"name", "type", "language", "content", "writing_style", "focus_areas"}
        patch = {k: v for k, v in data.items() if k in allowed}
        patch["updated_at"] = datetime.now(UTC).isoformat()
        rows = (
            self.db.table("document_templates")
            .update(patch)
            .eq("id", template_id)
            .eq("user_id", user_id)
            .execute()
            .data or []
        )
        return rows[0] if rows else None

    def delete_template(self, user_id: str, template_id: str) -> bool:
        result = (
            self.db.table("document_templates")
            .delete()
            .eq("id", template_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(result.data)
