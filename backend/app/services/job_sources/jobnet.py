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


_JOBNET_RSS = "https://job.jobnet.dk/CV/FindWork/rss"


class JobnetSource(BaseJobSource):
    name = "jobnet"
    display_name = "Jobnet"
    requires_api_key = False

    def is_available(self) -> bool:
        return True

    async def search(
        self,
        query: str,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobResult]:
        """
        Jobnet.dk via RSS feed (public, no auth required).
        Falls back to empty list on any error.
        """
        import xml.etree.ElementTree as ET

        params: dict = {"SearchString": query, "Offset": 0}
        if location:
            params["Area"] = location

        rss_headers = {
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "da-DK,da;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=False) as client:
                resp = await client.get(_JOBNET_RSS, params=params, headers=rss_headers)
                # Jobnet now requires auth for /CV/ prefix — try public RSS
                if resp.status_code in (301, 302, 307, 308):
                    # Redirect to auth page — API unavailable without login
                    logger.info("Jobnet RSS requires auth (redirect %s) — skipping", resp.status_code)
                    return []
                if resp.status_code != 200:
                    logger.warning("Jobnet RSS returned HTTP %s", resp.status_code)
                    return []
                xml_text = resp.text
        except Exception as exc:
            logger.warning("Jobnet search failed: %s", exc)
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("Jobnet RSS parse error: %s", exc)
            return []

        items = root.findall(".//item")
        results: list[JobResult] = []

        for item in items[:limit]:
            def _t(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""

            title = _t("title")
            link = _t("link")
            desc = _strip_html(_t("description"))

            # Try dc:publisher for company name
            company = (
                _t("{http://purl.org/dc/elements/1.1/}publisher")
                or _t("author")
                or "Ukendt"
            )
            location_str = _t("{http://purl.org/dc/elements/1.1/}coverage") or None

            results.append(JobResult(
                title=title,
                company=company,
                location=location_str,
                url=link or None,
                description=desc or None,
                source="jobnet",
            ))

        logger.info("Jobnet RSS: %d results for '%s'", len(results), query)
        return results
