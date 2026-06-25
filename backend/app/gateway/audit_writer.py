"""
AuditWriter — writes audit events for AI Gateway requests.

Purpose: Maintain an audit trail of all AI gateway requests.
Strategy: Phase 1 stub — writes to audit_logs table.
          Phase 2 (Release 0.3): migrate to work_life_events table.
Responsibility: Fire-and-forget audit event writing. Non-critical path.
Dependencies: Supabase (audit_logs table).
Limitations:
  - PII must NEVER appear in audit records.
  - metadata dict must be sanitized before reaching this method.
  - The caller (AIGateway) is responsible for PII-free metadata.

Schema notes (from 00013_audit_gdpr.sql):
  - audit_logs columns: action (text NOT NULL), resource_type (text NOT NULL),
    resource_id (uuid, nullable), metadata (jsonb), user_id (uuid, nullable).
    There is NO `details` column — payload goes into `metadata`.
  - `resource_id` is a uuid. request_id values that are not valid uuids (e.g. the
    'denied-<user_id>' synthetic id used on policy denial) are stored as NULL to
    avoid an invalid-input-syntax error; the real id is also kept in `metadata`.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger("app.gateway.audit")


def _as_uuid_or_none(value: str) -> str | None:
    """Return value if it is a valid uuid string, else None (for uuid columns)."""
    try:
        return str(_uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


class AuditWriter:
    """Writes Gateway audit events to audit_logs. Errors logged, never raised."""

    def __init__(self, supabase: "Client") -> None:
        self._supabase = supabase

    async def write(
        self,
        request_id: str,
        outcome: str,  # "success" | "policy_denied" | "provider_error" | "auth_error"
        metadata: dict,  # Must be PII-free
    ) -> None:
        """Write audit event. Errors are logged but never raised."""
        try:
            payload = {**metadata, "request_id": request_id}
            row: dict = {
                "action": f"gateway.request.{outcome}",
                "resource_type": "ai_request",
                "resource_id": _as_uuid_or_none(request_id),
                "metadata": payload,
            }
            user_id = metadata.get("user_id")
            if user_id:
                row["user_id"] = user_id
            self._supabase.table("audit_logs").insert(row).execute()
        except Exception as exc:
            logger.error("audit_write_failed request_id=%s error=%s", request_id, exc)
