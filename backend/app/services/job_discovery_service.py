"""
JobDiscoveryService — søger jobs fra multiple providers parallelt,
deduplikerer, scraper fuld jobtekst, beregner match score og gemmer søgehistorik.

Pipeline:
  1. Fetch   — alle sources parallelt (Jobnet API + Jobindex/Ofir RSS)
  2. Dedup   — fjern dubletter (title+company nøgle)
  3. Score   — initial match-scoring på teaser-data
  4. Scrape  — hent fuld jobtekst for top-20 ikke-Jobnet jobs
  5. Rescore — genberegn match med fuld tekst
  6. Enrich  — AI-berigelse (requirements, ai_summary) via JobDiscoveryAgent
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from supabase import Client

from app.services.job_scraper import scrape_jobs_batch
from app.services.job_service import JobService
from app.services.job_sources import DEFAULT_SOURCES, SOURCES, JobResult
from app.services.memory_snapshot_service import MemorySnapshotService

logger = logging.getLogger(__name__)

# Maks jobs der scrapes for fuld tekst (performance-styring)
_SCRAPE_TOP_N = 20


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
        Søg på tværs af sources, dedupliker, scraper fuld tekst, beregn match scores.
        Returns dict med results, source_stats, total, search_id.
        """
        active_sources = [s for s in (sources or DEFAULT_SOURCES) if s in SOURCES]

        # Fetch career memory snapshot for match scoring
        snapshot = MemorySnapshotService(self.db).snapshot(user_id)

        # ── Trin 1: Fetch alle sources parallelt ─────────────────────────────
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

        # ── Trin 2: Deduplication ─────────────────────────────────────────────
        seen: set[str] = set()
        all_results: list[JobResult] = []
        for name in active_sources:
            for r in results_by_source.get(name, []):
                key = r.dedup_key()
                if key not in seen:
                    seen.add(key)
                    all_results.append(r)

        # ── Trin 3: Initial match scoring på teaser-data ─────────────────────
        job_svc = JobService(self.db)
        enriched: list[dict] = []
        for r in all_results:
            d = r.to_dict()
            match = job_svc.compute_match_score(d, snapshot)
            d["match_score"] = match["total"]
            d["match_breakdown"] = match["breakdown"]
            d["matched_skills"] = match["matched_skills"]
            d["missing_requirements"] = match["missing_requirements"]
            d["text_chars_used"] = match["text_chars_used"]
            enriched.append(d)

        # Sort by initial score (best candidates for scraping)
        enriched.sort(key=lambda x: x["match_score"], reverse=True)

        # ── Trin 4: Scrape fuld jobtekst for top-N ───────────────────────────
        # Jobnet springes over i scraperen (har allerede API-data)
        to_scrape = enriched[:_SCRAPE_TOP_N]
        scraped_count_before = sum(1 for j in to_scrape if j.get("full_description"))

        try:
            await scrape_jobs_batch(to_scrape, max_concurrent=5, total_timeout=15.0)
        except Exception as exc:
            logger.warning("Scraping batch fejlede: %s", exc)

        scraped_count_after = sum(1 for j in to_scrape if j.get("full_description"))
        new_scraped = scraped_count_after - scraped_count_before
        logger.info(
            "Scraping: %d/%d nye resultater scraped (top %d)",
            new_scraped, len(to_scrape), _SCRAPE_TOP_N,
        )

        # ── Trin 5: Genberegn match med fuld tekst ───────────────────────────
        for job in enriched:
            if job.get("full_description"):
                match = job_svc.compute_match_score(job, snapshot)
                job["match_score"] = match["total"]
                job["match_breakdown"] = match["breakdown"]
                job["matched_skills"] = match["matched_skills"]
                job["missing_requirements"] = match["missing_requirements"]
                job["text_chars_used"] = match["text_chars_used"]

        # Sorter igen efter opdaterede scores
        enriched.sort(key=lambda x: x["match_score"], reverse=True)

        source_stats = {
            name: len(results_by_source.get(name, []))
            for name in active_sources
        }

        # Gem søgehistorik
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
            "scraped_count": scraped_count_after,
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
        """Gem et opdaget job-resultat i brugerens jobs-tabel (inkl. fuld jobtekst og matchscore)."""
        job_svc = JobService(self.db)
        # Gem match_score til genbrug efter create_job
        match_score = result.get("match_score")
        payload = {
            **result,
            "is_saved": True,
            "source": result.get("source", "discovery"),
        }
        # Fjern discovery-only felter (ikke databasekolonner)
        for key in (
            "match_score", "match_breakdown", "matched_skills",
            "missing_requirements", "text_chars_used",
            "external_id", "deadline", "ai_summary",
        ):
            payload.pop(key, None)
        job = job_svc.create_job(user_id, payload)
        # Gem matchscore fra discovery (undgår re-beregning)
        if match_score is not None:
            try:
                job_svc.store_match_score(job["id"], int(match_score))
                job["match_score"] = int(match_score)
            except Exception:
                pass
        return job
