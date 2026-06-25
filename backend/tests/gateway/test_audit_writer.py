"""
Unit tests for AuditWriter (app.gateway.audit_writer).

Supabase is mocked. Verifies the INSERT maps to the actual audit_logs schema
(metadata column, uuid-safe resource_id) and that failures are swallowed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.gateway.audit_writer import AuditWriter


class _SupabaseSpy:
    def __init__(self, raise_on_insert=False):
        self.inserted: dict | None = None
        self._raise = raise_on_insert

    def table(self, name):
        assert name == "audit_logs"
        return self

    def insert(self, row):
        if self._raise:
            raise RuntimeError("db down")
        self.inserted = row
        return self

    def execute(self):
        return MagicMock(data=[self.inserted])


@pytest.mark.asyncio
async def test_write_inserts_to_audit_logs():
    spy = _SupabaseSpy()
    writer = AuditWriter(spy)
    rid = "11111111-1111-1111-1111-111111111111"
    await writer.write(rid, "success", {"user_id": "u1", "model": "claude"})
    row = spy.inserted
    assert row["action"] == "gateway.request.success"
    assert row["resource_type"] == "ai_request"
    assert row["resource_id"] == rid
    assert row["metadata"]["model"] == "claude"
    assert row["metadata"]["request_id"] == rid
    assert row["user_id"] == "u1"


@pytest.mark.asyncio
async def test_write_outcome_in_action_field():
    spy = _SupabaseSpy()
    writer = AuditWriter(spy)
    await writer.write(
        "11111111-1111-1111-1111-111111111111", "policy_denied", {"user_id": "u"}
    )
    assert spy.inserted["action"] == "gateway.request.policy_denied"


@pytest.mark.asyncio
async def test_non_uuid_request_id_stored_as_null_resource_id():
    spy = _SupabaseSpy()
    writer = AuditWriter(spy)
    await writer.write("denied-user-123", "policy_denied", {"user_id": "user-123"})
    assert spy.inserted["resource_id"] is None
    # The synthetic id is still recoverable from metadata.
    assert spy.inserted["metadata"]["request_id"] == "denied-user-123"


@pytest.mark.asyncio
async def test_write_does_not_raise_on_db_error():
    spy = _SupabaseSpy(raise_on_insert=True)
    writer = AuditWriter(spy)
    await writer.write(
        "11111111-1111-1111-1111-111111111111", "success", {"user_id": "u"}
    )  # must not raise


@pytest.mark.asyncio
async def test_write_without_user_id_omits_column():
    spy = _SupabaseSpy()
    writer = AuditWriter(spy)
    await writer.write("11111111-1111-1111-1111-111111111111", "success", {"foo": "bar"})
    assert "user_id" not in spy.inserted
