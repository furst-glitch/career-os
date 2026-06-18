"""
Memory Service — CRUD for career_memories, career_goals, career_milestones, career_preferences.
Bruges af Memory API og Memory Snapshot Engine.
"""
from __future__ import annotations

from supabase import Client

MEMORY_TYPE_VALUES = frozenset({
    "milestone", "insight", "preference", "goal", "lesson", "achievement",
    "experience", "skill", "project", "reflection", "career_note",
})
GOAL_TYPE_VALUES    = frozenset({"short_term", "long_term", "aspirational"})
GOAL_STATUS_VALUES  = frozenset({"active", "achieved", "abandoned"})
IMPACT_VALUES       = frozenset({"low", "medium", "high", "defining"})
MILESTONE_CATS      = frozenset({"promotion", "award", "project", "pivot", "skill", "education", "personal"})
SOURCE_VALUES       = frozenset({"user_input", "ai_extracted", "behavioral"})
REMOTE_VALUES       = frozenset({"remote", "hybrid", "onsite", "flexible"})


class MemoryService:
    def __init__(self, supabase: Client) -> None:
        self.db = supabase

    # ─── Career Memories ─────────────────────────────────────────────────────

    def create_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "career_note",
        source: str = "user_input",
        relevance_score: float = 0.5,
    ) -> dict:
        result = self.db.table("career_memories").insert({
            "user_id":         user_id,
            "content":         content,
            "memory_type":     memory_type if memory_type in MEMORY_TYPE_VALUES else "career_note",
            "source":          source if source in SOURCE_VALUES else "user_input",
            "relevance_score": max(0.0, min(1.0, float(relevance_score))),
        }).execute()
        return result.data[0]

    def update_memory(self, memory_id: str, data: dict) -> dict:
        allowed = {"content", "memory_type", "source", "relevance_score"}
        update = {k: v for k, v in data.items() if k in allowed}
        result = self.db.table("career_memories").update(update).eq("id", memory_id).execute()
        return result.data[0]

    def delete_memory(self, memory_id: str) -> None:
        self.db.table("career_memories").delete().eq("id", memory_id).execute()

    def list_memories(
        self,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        q = (
            self.db.table("career_memories")
            .select("id, content, memory_type, source, relevance_score, created_at, updated_at")
            .eq("user_id", user_id)
        )
        if memory_type and memory_type in MEMORY_TYPE_VALUES:
            q = q.eq("memory_type", memory_type)
        return q.order("created_at", desc=True).limit(limit).execute().data or []

    def search_memories_keyword(self, user_id: str, query: str, limit: int = 20) -> list[dict]:
        """Keyword fallback-søgning via ilike."""
        result = (
            self.db.table("career_memories")
            .select("id, content, memory_type, source, relevance_score, created_at")
            .eq("user_id", user_id)
            .ilike("content", f"%{query}%")
            .order("relevance_score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def search_memories_semantic(
        self,
        user_id: str,
        embedding: list[float],
        match_count: int = 10,
        match_threshold: float = 0.5,
    ) -> list[dict]:
        """pgvector cosine-søgning via match_memories RPC."""
        try:
            result = self.db.rpc("match_memories", {
                "query_embedding": embedding,
                "p_user_id":       user_id,
                "match_count":     match_count,
                "match_threshold": match_threshold,
            }).execute()
            return result.data or []
        except Exception:
            return []

    def update_embedding(self, memory_id: str, embedding: list[float]) -> None:
        self.db.table("career_memories").update({"embedding": embedding}).eq("id", memory_id).execute()

    # ─── Career Goals ─────────────────────────────────────────────────────────

    def list_goals(self, user_id: str) -> list[dict]:
        return (
            self.db.table("career_goals")
            .select("*")
            .eq("user_id", user_id)
            .order("priority")
            .order("created_at", desc=True)
            .execute()
            .data or []
        )

    def create_goal(self, user_id: str, data: dict) -> dict:
        payload = {
            "user_id":     user_id,
            "title":       data.get("title", ""),
            "description": data.get("description"),
            "goal_type":   data.get("goal_type", "short_term") if data.get("goal_type") in GOAL_TYPE_VALUES else "short_term",
            "target_date": data.get("target_date") or None,
            "status":      "active",
            "priority":    max(1, min(5, int(data.get("priority", 3)))),
        }
        result = self.db.table("career_goals").insert(payload).execute()
        return result.data[0]

    def update_goal(self, goal_id: str, data: dict) -> dict:
        allowed = {"title", "description", "goal_type", "target_date", "status", "priority"}
        update = {k: v for k, v in data.items() if k in allowed}
        if "goal_type" in update and update["goal_type"] not in GOAL_TYPE_VALUES:
            del update["goal_type"]
        if "status" in update and update["status"] not in GOAL_STATUS_VALUES:
            del update["status"]
        if "priority" in update:
            update["priority"] = max(1, min(5, int(update["priority"])))
        result = self.db.table("career_goals").update(update).eq("id", goal_id).execute()
        return result.data[0]

    def delete_goal(self, goal_id: str) -> None:
        self.db.table("career_goals").delete().eq("id", goal_id).execute()

    # ─── Career Milestones ────────────────────────────────────────────────────

    def list_milestones(self, user_id: str) -> list[dict]:
        return (
            self.db.table("career_milestones")
            .select("*")
            .eq("user_id", user_id)
            .order("occurred_at", desc=True)
            .execute()
            .data or []
        )

    def create_milestone(self, user_id: str, data: dict) -> dict:
        payload = {
            "user_id":      user_id,
            "title":        data.get("title", ""),
            "description":  data.get("description"),
            "occurred_at":  data.get("occurred_at") or "2024-01-01",
            "impact_level": data.get("impact_level", "medium") if data.get("impact_level") in IMPACT_VALUES else "medium",
            "category":     data.get("category", "project") if data.get("category") in MILESTONE_CATS else "project",
        }
        result = self.db.table("career_milestones").insert(payload).execute()
        return result.data[0]

    def update_milestone(self, milestone_id: str, data: dict) -> dict:
        allowed = {"title", "description", "occurred_at", "impact_level", "category"}
        update = {k: v for k, v in data.items() if k in allowed}
        if "impact_level" in update and update["impact_level"] not in IMPACT_VALUES:
            del update["impact_level"]
        if "category" in update and update["category"] not in MILESTONE_CATS:
            del update["category"]
        result = self.db.table("career_milestones").update(update).eq("id", milestone_id).execute()
        return result.data[0]

    def delete_milestone(self, milestone_id: str) -> None:
        self.db.table("career_milestones").delete().eq("id", milestone_id).execute()

    # ─── Career Preferences ───────────────────────────────────────────────────

    _PREF_DEFAULTS: dict = {
        "industries":       [],
        "company_sizes":    [],
        "work_styles":      [],
        "values":           [],
        "location_prefs":   {},
        "deal_breakers":    [],
        "salary_min":       None,
        "salary_max":       None,
        "salary_currency":  "DKK",
        "role_types":       [],
        "remote_preference":"hybrid",
        "ai_preferences":   {},
    }

    def get_preferences(self, user_id: str) -> dict:
        result = (
            self.db.table("career_preferences")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
        return {"user_id": user_id, **self._PREF_DEFAULTS}

    def upsert_preferences(self, user_id: str, data: dict) -> dict:
        allowed = {
            "industries", "company_sizes", "work_styles", "values",
            "location_prefs", "deal_breakers", "salary_min", "salary_max",
            "salary_currency", "role_types", "remote_preference", "ai_preferences",
        }
        payload = {k: v for k, v in data.items() if k in allowed}
        if "remote_preference" in payload and payload["remote_preference"] not in REMOTE_VALUES:
            payload["remote_preference"] = "hybrid"
        existing = (
            self.db.table("career_preferences")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            result = self.db.table("career_preferences").update(payload).eq("user_id", user_id).execute()
        else:
            result = self.db.table("career_preferences").insert({"user_id": user_id, **payload}).execute()
        return result.data[0]
