"""
Job Discovery API

POST /job-discovery/search          - Søg jobs på tværs af sources
GET  /job-discovery/history         - Søgehistorik
POST /job-discovery/save            - Gem et søgeresultat til brugerens jobs
GET  /job-discovery/sources         - Liste tilgængelige sources
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.agents.job_discovery_agent import JobDiscoveryAgent
from app.core.deps import get_current_user, get_supabase_admin
from app.services.automation_service import on_job_discovered
from app.services.job_discovery_service import JobDiscoveryService
from app.services.job_sources import DEFAULT_SOURCES, SOURCES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/job-discovery", tags=["Job Discovery"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    location: str | None = None
    sources: list[str] | None = None
    limit_per_source: int = Field(default=15, ge=5, le=30)
    ai_enrichment: bool = True


class SaveRequest(BaseModel):
    result: dict


@router.post("/search")
async def search_jobs(
    body: SearchRequest,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = JobDiscoveryService(supabase)
    data = await svc.search(
        user_id=user["id"],
        query=body.query,
        location=body.location,
        sources=body.sources,
        limit_per_source=body.limit_per_source,
    )

    # Optional AI enrichment (best-effort, silent on no-key)
    if body.ai_enrichment and data["results"]:
        try:
            from app.services.memory_snapshot_service import MemorySnapshotService
            snapshot = MemorySnapshotService(supabase).snapshot(user["id"])
            agent = JobDiscoveryAgent(user_id=user["id"], supabase=supabase)
            agent_result = await agent.run({
                "results": data["results"],
                "snapshot_text": snapshot.get("text_summary", ""),
            })
            enriched = json.loads(agent_result.content)
            if isinstance(enriched, list) and len(enriched) == len(data["results"]):
                data["results"] = enriched
        except Exception as exc:
            logger.warning("AI enrichment skipped: %s", exc)

    return data


@router.get("/history")
async def get_history(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = JobDiscoveryService(supabase)
    return svc.get_history(user["id"])


@router.post("/save")
async def save_result(
    body: SaveRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = JobDiscoveryService(supabase)
    job = svc.save_result(user["id"], body.result)
    # Emit high-match notification if score known
    match_score = int(body.result.get("match_score") or 0)
    if match_score >= 70:
        background_tasks.add_task(
            on_job_discovered,
            user["id"],
            body.result.get("title", ""),
            body.result.get("company", ""),
            match_score,
            supabase,
        )
    return job


@router.get("/sources")
async def list_sources(_user: dict = Depends(get_current_user)):
    return [
        {
            "name": name,
            "display_name": cls.display_name,
            "requires_api_key": cls.requires_api_key,
            "available": cls().is_available(),
            "is_default": name in DEFAULT_SOURCES,
        }
        for name, cls in SOURCES.items()
    ]
