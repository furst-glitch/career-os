"""
Jobnet.dk provider — Danish government job portal (public API, no key required).
Endpoint: https://job.jobnet.dk/CV/FindWork/Results
"""
from __future__ import annotations

import logging
import re

import httpx

from .base import BaseJobSource, JobResult

logger = logging.getLogger(__name__)

_BASE = "https://job.jobnet.dk/CV/FindWork"
_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "da-DK,da;q=0.9",
    "User-Agent": "CareerOS/1.0 (job search aggregator)",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    return re.sub(r"\s+", " ", text).strip()


def _map_employment(emp: str) -> str:
    emp_l = (emp or "").lower()
    if "deltid" in emp_l or "part" in emp_l:
        return "part_time"
    if "freelance" in emp_l:
        return "freelance"
    if "praktik" in emp_l or "trainee" in emp_l:
        return "internship"
    if "kontrakt" in emp_l or "contract" in emp_l:
        return "contract"
    return "full_time"


class JobnetSource(BaseJobSource):
    name = "jobnet"
    display_name = "Jobnet"
    requires_api_key = False

    async def search(
        self,
        query: str,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobResult]:
        params: dict = {
            "SearchString": query,
            "Offset": 0,
            "SortBy": "BestMatch",
            "WorkPlaceNotStuffed": "false",
        }
        if location:
            params["PostalCode"] = location

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE}/Results",
                    params=params,
                    headers=_HEADERS,
                )
                if resp.status_code != 200:
                    logger.warning("Jobnet returned HTTP %s", resp.status_code)
                    return []
                data = resp.json()
        except Exception as exc:
            logger.warning("Jobnet search failed: %s", exc)
            return []

        postings = data.get("JobPositionPostings") or []
        results: list[JobResult] = []

        for p in postings[:limit]:
            title = p.get("Heading") or p.get("Title") or ""
            company = p.get("HiringOrgName") or p.get("WorkPlaceName") or "Ukendt"
            job_id = p.get("JobPositionPostingID") or ""
            url = f"https://job.jobnet.dk/CV/FindWork/Detail/{job_id}" if job_id else p.get("Url")

            loc_obj = p.get("Location") or p.get("WorkAddress") or {}
            city = (
                loc_obj.get("CityName")
                or loc_obj.get("PostalDistrict")
                or loc_obj.get("Municipality")
                or ""
            )
            postal = loc_obj.get("PostalCode") or ""
            location_str = ", ".join(filter(None, [city, postal])) or None

            description = _strip_html(p.get("JobPostingDescription") or "") or None
            employment = p.get("Employment") or ""
            deadline = (p.get("LastDateApplication") or "")[:10] or None

            results.append(JobResult(
                title=title,
                company=company,
                location=location_str,
                url=url,
                description=description,
                job_type=_map_employment(employment),
                remote_type="hybrid",
                source="jobnet",
                external_id=job_id,
                deadline=deadline,
            ))

        return results
