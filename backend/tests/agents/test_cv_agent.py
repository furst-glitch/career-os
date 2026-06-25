"""
Tests for the migrated CVAgent (app.agents.cv_agent).

The Gateway is mocked at CVAgent._get_gateway. We verify each LLM-calling method
routes through the Gateway with the correct task_capability and returns an
AgentResult, and that GatewayAuthError propagates.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AgentResult
from app.agents.cv_agent import CVAgent
from app.gateway.exceptions import GatewayAuthError
from app.gateway.schemas import GatewayResponse, GatewayUsage


def _gateway_response(content: str) -> GatewayResponse:
    return GatewayResponse(
        content=content,
        usage=GatewayUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=Decimal("0.0012"),
            latency_ms=200,
            model="claude-sonnet-4-6",
            provider="anthropic",
        ),
        request_id="11111111-1111-1111-1111-111111111111",
        model_used="claude-sonnet-4-6",
        provider_used="anthropic",
        latency_ms=200,
        used_platform_key=True,
    )


def _agent() -> CVAgent:
    return CVAgent(user_id="user-1", supabase=MagicMock())


def _mock_gateway(content: str):
    gw = MagicMock()
    gw.complete = AsyncMock(return_value=_gateway_response(content))
    return gw


@pytest.mark.asyncio
async def test_cv_agent_parse_uses_gateway():
    agent = _agent()
    parsed = {"personal": {"name": "Ada"}, "gaps": []}
    gw = _mock_gateway(json.dumps(parsed))
    with patch.object(CVAgent, "_get_gateway", return_value=gw):
        result = await agent.run({"raw_text": "Ada Lovelace, engineer"})

    gw.complete.assert_awaited_once()
    request = gw.complete.await_args.args[0]
    assert request.task_capability == "cv_parsing"
    assert request.response_format == {"type": "json_object"}
    assert isinstance(result, AgentResult)
    assert result.metadata["parsed_data"]["personal"]["name"] == "Ada"


@pytest.mark.asyncio
async def test_cv_agent_generate_uses_gateway():
    agent = _agent()
    gw = _mock_gateway("## Professionel profil\nStærk kandidat.")
    with patch.object(CVAgent, "_get_gateway", return_value=gw):
        result = await agent.generate(
            {
                "language": "da",
                "job_title": "Controller",
                "job_company": "Acme",
                "candidate_summary": "10 års erfaring",
            }
        )

    gw.complete.assert_awaited_once()
    request = gw.complete.await_args.args[0]
    assert request.task_capability == "cv_generation"
    assert isinstance(result, AgentResult)
    payload = json.loads(result.content)
    assert payload["_structured_cv_v2"] is True
    assert "Stærk kandidat" in payload["cv_text"]


@pytest.mark.asyncio
async def test_cv_agent_extract_facts_uses_gateway():
    agent = _agent()
    facts = {"achievements": [{"title": "Cut cost", "description": "x"}]}
    gw = _mock_gateway(json.dumps(facts))
    with patch.object(CVAgent, "_get_gateway", return_value=gw):
        out = await agent.extract_facts("I cut costs", "Tell me more", ["achievements"])

    gw.complete.assert_awaited_once()
    request = gw.complete.await_args.args[0]
    assert request.task_capability == "cv_parsing"
    assert out["achievements"][0]["title"] == "Cut cost"


@pytest.mark.asyncio
async def test_cv_agent_returns_agent_result_with_usage():
    agent = _agent()
    gw = _mock_gateway(json.dumps({"gaps": []}))
    with patch.object(CVAgent, "_get_gateway", return_value=gw):
        result = await agent.run({"raw_text": "some cv"})
    assert isinstance(result, AgentResult)
    assert result.usage.total_tokens == 150
    assert result.usage.cost_usd == pytest.approx(0.0012)
    assert result.usage.provider == "anthropic"


@pytest.mark.asyncio
async def test_cv_agent_empty_text_skips_gateway():
    agent = _agent()
    gw = _mock_gateway("{}")
    with patch.object(CVAgent, "_get_gateway", return_value=gw):
        result = await agent.run({"raw_text": "   "})
    gw.complete.assert_not_called()
    assert result.metadata["error"]


@pytest.mark.asyncio
async def test_cv_agent_auth_error_propagated():
    agent = _agent()
    gw = MagicMock()
    gw.complete = AsyncMock(side_effect=GatewayAuthError("no key", code="no_api_key"))
    with patch.object(CVAgent, "_get_gateway", return_value=gw):
        with pytest.raises(GatewayAuthError):
            await agent.run({"raw_text": "cv text"})
