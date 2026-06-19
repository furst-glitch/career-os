"""
JobDiscoveryService — søger jobs fra multiple providers parallelt,
deduplikerer, beregner match score og gemmer søgehistorik.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from supabase import Client

from app.services.job_service import JobService
from app.services.job_sources import DEFAULT_SOURCES, SOURCES, JobResult
from app.services.memory_snapshot_service import MemorySnapshotService

logger = logging.getLogger(__name__)


class JobDiscoveryService:
    def __init__(self, db: Client) -> None:
        self.db = db

    async def search(
        self,
        user_id: str,
        query: str,
        location: str | None = None,
        sources: list[str] | None = None,
        limit_per_source: int = 15,
    ) -> dict[str, Any]:
        """
        Søg på tværs af sources, dedupliker, beregn match scores.
        Returns dict with results, source_stats, total, search_id.
        """
        active_sources = [s for s in (sources or DEFAULT_SOURCES) if s in SOURCES]

        # Fetch career memory snapshot for match scoring
        snapshot = MemorySnapshotService(self.db).snapshot(user_id)

        # Run all sources in parallel
        tasks = {
            name: SOURCES[name]().search(query, location, limit_per_source)
            for name in active_sources
        }
        results_by_source: dict[str, list[JobResult]] = {}
        for name, coro in tasks.items():
            try:
                results_by_source[name] = await asyncio.wait_for(coro, timeout=12.0)
            except Exception as exc:
                logger.warning("Source %s failed: %s", name, exc)
                results_by_source[name] = []

        # Deduplicate across sources (keep first occurrence)
        seen: set[str] = set()
        all_results: list[JobResult] = []
        for name in active_sources:
            for r in results_by_source.get(name, []):
                key = r.dedup_key()
                if key not in seen:
                    seen.add(key)
                    all_results.append(r)

        # Match scoring
        job_svc = JobService(self.db)
        enriched: list[dict] = []
        for r in all_results:
            d = r.to_dict()
            match = job_svc.compute_match_score(d, snapshot)
            d["match_score"] = match["total"]
            d["match_breakdown"] = match["breakdown"]
            d["matched_skills"] = match["matched_skills"]
            enriched.append(d)

        # Sort by match score descending
        enriched.sort(key=lambda x: x["match_score"], reverse=True)

        source_stats = {
            name: len(results_by_source.get(name, []))
            for name in active_sources
        }

        # Persist search history
        try:
            row = self.db.table("job_search_history").insert({
                "user_id": user_id,
                "query": query,
                "location": location,
                "sources": active_sources,
                "results_count": len(enriched),
            }).execute()
            search_id = (row.data or [{}])[0].get("id")
        except Exception as exc:
            logger.warning("Could not save search history: %s", exc)
            search_id = None

        return {
            "search_id": search_id,
            "query": query,
            "location": location,
            "total": len(enriched),
            "source_stats": source_stats,
            "results": enriched,
        }

    def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        try:
            rows = (
                self.db.table("job_search_history")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data or []
            )
            return rows
        except Exception as exc:
            logger.warning("Could not fetch search history: %s", exc)
            return []

    def save_result(self, user_id: str, result: dict) -> dict:
        """Save a discovered job result to the user's jobs table."""
        job_svc = JobService(self.db)
        payload = {
            **result,
            "is_saved": True,
            "source": result.get("source", "discovery"),
        }
        # Drop discovery-only fields
        for key in ("match_score", "match_breakdown", "matched_skills", "external_id", "deadline"):
            payload.pop(key, None)
        return job_svc.create_job(user_id, payload)
