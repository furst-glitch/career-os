"""
AutomationService — fire-and-forget background workflows.

Workflows:
  1. job_saved(user_id, job_id) → create draft application pipeline entry
  2. cv_uploaded(user_id) → regenerate Master CV + refresh memory snapshot
  3. job_found(user_id, job) → compute match score + emit notification
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def _run_silent(coro, label: str) -> None:
    """Await a coroutine, swallowing all exceptions so the caller never fails."""
    try:
        await coro
    except Exception as exc:
        logger.warning("Automation '%s' failed silently: %s", label, exc)


# ── Workflow 1: Job Saved ─────────────────────────────────────────────────────

async def on_job_saved(user_id: str, job_id: str, supabase) -> None:
    """
    Triggered when a user saves a job.
    Creates a draft application pipeline entry if one doesn't already exist.
    Does NOT auto-generate cover letter — user initiates that.
    """
    try:
        existing = (
            supabase.table("application_pipeline")
            .select("id")
            .eq("user_id", user_id)
            .eq("job_id", job_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return  # Already has a pipeline entry

        supabase.table("application_pipeline").insert({
            "user_id": user_id,
            "job_id": job_id,
            "current_status": "draft",
            "priority": "medium",
            "source": "auto_saved",
        }).execute()

        _emit_notification(supabase, user_id, "job_saved",
                           "Job gemt", "Draft ansøgning oprettet", job_id)
    except Exception as exc:
        logger.warning("on_job_saved failed: %s", exc)


# ── Workflow 2: CV Uploaded ───────────────────────────────────────────────────

async def on_cv_uploaded(user_id: str, supabase) -> None:
    """
    Triggered after a CV upload completes.
    Invalidates stale cache, then refreshes the Career Memory snapshot.
    """
    try:
        from app.services.cache_service import invalidate_user
        await invalidate_user(user_id)  # Purge Redis + L1

        from app.services.memory_snapshot_service import MemorySnapshotService
        snap_svc = MemorySnapshotService(supabase)
        snap_svc.snapshot(user_id, force=True)  # Pre-warm L1 + L2

        _emit_notification(supabase, user_id, "cv_uploaded",
                           "CV analyseret", "Karriere Memory opdateret automatisk")
    except Exception as exc:
        logger.warning("on_cv_uploaded failed: %s", exc)


# ── Workflow 3: Job Discovery Found ──────────────────────────────────────────

async def on_job_discovered(user_id: str, job_title: str, company: str,
                            match_score: int, supabase) -> None:
    """Emit notification when job discovery finds a high-match job."""
    try:
        if match_score >= 70:
            msg = f"{job_title} hos {company} — {match_score}% match"
            _emit_notification(supabase, user_id, "job_found",
                               "Nyt relevant job fundet", msg)
    except Exception as exc:
        logger.warning("on_job_discovered failed: %s", exc)


# ── Notification writer ───────────────────────────────────────────────────────

def _emit_notification(supabase, user_id: str, event_type: str,
                        title: str, body: str, ref_id: str | None = None) -> None:
    """Write a notification row. Swallows failures so callers are never affected."""
    try:
        supabase.table("notifications").insert({
            "user_id": user_id,
            "event_type": event_type,
            "title": title,
            "body": body,
            "ref_id": ref_id,
            "is_read": False,
        }).execute()
    except Exception as exc:
        logger.warning("_emit_notification failed: %s", exc)
