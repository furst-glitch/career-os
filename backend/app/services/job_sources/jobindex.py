"""
Jobindex.dk provider — public RSS feed, no API key required.
Feed: https://www.jobindex.dk/jobsoegning.rss?q={query}&area={area}
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from .base import BaseJobSource, JobResult

logger = logging.getLogger(__name__)

_RSS_URL = "https://www.jobindex.dk/jobsoegning.rss"
_HEADERS = {
    "Accept": "application/rss+xml, application/xml, text/xml",
    "User-Agent": "CareerOS/1.0 (job search aggregator)",
}

# Namespaces used in Jobindex RSS
_NS = {
    "ji": "http://www.jobindex.dk/xmlns/jobindex",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class JobindexSource(BaseJobSource):
    name = "jobindex"
    display_name = "Jobindex"
    requires_api_key = False

    async def search(
        self,
        query: str,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobResult]:
        params: dict = {"q": query, "maxdate": ""}
        if location:
            params["area"] = location

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(_RSS_URL, params=params, headers=_HEADERS)
                if resp.status_code != 200:
                    logger.warning("Jobindex RSS returned HTTP %s", resp.status_code)
                    return []
                xml_text = resp.text
        except Exception as exc:
            logger.warning("Jobindex search failed: %s", exc)
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("Jobindex RSS parse error: %s", exc)
            return []

        items = root.findall(".//item")
        results: list[JobResult] = []

        for item in items[:limit]:
            def _t(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""

            title = _t("title")
            link = _t("link")
            description = _strip_html(_t("description"))

            # Jobindex puts company in dc:publisher or ji:company
            company = (
                _t("dc:publisher")
                or _t("{http://purl.org/dc/elements/1.1/}publisher")
                or _t("{http://www.jobindex.dk/xmlns/jobindex}company")
                or "Ukendt"
            )

            location_str = (
                _t("{http://www.jobindex.dk/xmlns/jobindex}area")
                or _t("dc:coverage")
                or None
            ) or None

            results.append(JobResult(
                title=title,
                company=company,
                location=location_str,
                url=link or None,
                description=description or None,
                source="jobindex",
            ))

        return results
