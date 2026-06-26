"""
EventService — WP1: Platform Event Instrumentation.

Fire-and-forget event emission to platform_events table.
All emit() calls swallow exceptions so event failures never disrupt request flow.

Event naming convention: category.action (lowercase, dot-separated)
  document.uploaded   document.analyzed   document.failed
  fact.verified
  chat.completed
  recommendation.resolved   recommendation.dismissed
  employment.created
  subscription.started      subscription.cancelled
  ai.error
"""
from __future__ import annotations

import logging

logger = logging.getLogger("app.events")

# ── Canonical event type constants (WP1) ─────────────────────────────────────

EV_DOC_UPLOADED            = "document.uploaded"
EV_DOC_ANALYZED            = "document.analyzed"
EV_DOC_FAILED              = "document.failed"
EV_FACT_VERIFIED           = "fact.verified"
EV_CHAT_COMPLETED          = "chat.completed"
EV_REC_RESOLVED            = "recommendation.resolved"
EV_REC_DISMISSED           = "recommendation.dismissed"
EV_EMPLOYMENT_CREATED      = "employment.created"
EV_SUBSCRIPTION_STARTED    = "subscription.started"
EV_SUBSCRIPTION_CANCELLED  = "subscription.cancelled"
EV_AI_ERROR                = "ai.error"


class EventService:
    """
    Append-only event emitter. Synchronous — call from BackgroundTasks or
    directly for fire-and-forget instrumentation in async generators.

    Never raises. All errors are logged at WARNING level and swallowed.
    """

    def __init__(self, supabase) -> None:
        self._supabase = supabase

    def emit(
        self,
        event_type: str,
        user_id: str | None = None,
        employment_id: str | None = None,
        document_id: str | None = None,
        **properties,
    ) -> None:
        """Insert one event row. Thread-safe, never raises."""
        try:
            row: dict = {
                "event_type": event_type,
                "properties": {k: v for k, v in properties.items() if v is not None},
            }
            if user_id:
                row["user_id"] = user_id
            if employment_id:
                row["employment_id"] = employment_id
            if document_id:
                row["document_id"] = document_id
            self._supabase.table("platform_events").insert(row).execute()
        except Exception as exc:
            logger.warning("event_emit_failed type=%s error=%s", event_type, exc)
