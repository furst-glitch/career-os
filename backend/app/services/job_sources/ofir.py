"""
Ofir.dk provider — public RSS feed.
Feed: https://www.ofir.dk/rss/?q={query}
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from .base import BaseJobSource, JobResult

logger = logging.getLogger(__name__)

_RSS_URL = "https://www.ofir.dk/rss/"
_HEADERS = {
    "Accept": "application/rss+xml, application/xml, text/xml",
    "User-Agent": "CareerOS/1.0 (job search aggregator)",
}


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class OfirSource(BaseJobSource):
    name = "ofir"
    display_name = "Ofir"
    requires_api_key = False

    async def search(
        self,
        query: str,
        location: str | None = None,
        limit: int = 20,
    ) -> list[JobResult]:
        params: dict = {"q": query}
        if location:
            params["area"] = location

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(_RSS_URL, params=params, headers=_HEADERS)
                if resp.status_code != 200:
                    logger.warning("Ofir RSS returned HTTP %s", resp.status_code)
                    return []
                xml_text = resp.text
        except Exception as exc:
            logger.warning("Ofir search failed: %s", exc)
            return []

        # Ofir.dk was acquired by Jobindex — their RSS now returns HTML
        if xml_text.lstrip().startswith("<!DOCTYPE") or "<html" in xml_text[:300]:
            logger.info("Ofir RSS returned HTML (merged into Jobindex) — skipping")
            return []

        def _parse_et(xml: str) -> list[JobResult]:
            root = ET.fromstring(xml)
            out = []
            for item in root.findall(".//item")[:limit]:
                def _t(tag: str) -> str:
                    el = item.find(tag)
                    return (el.text or "").strip() if el is not None else ""
                title = _t("title")
                link = _t("link")
                description = _strip_html(_t("description"))
                company = _t("author") or _t("{http://purl.org/dc/elements/1.1/}publisher") or "Ukendt"
                category = _t("category") or None
                out.append(JobResult(
                    title=title, company=company, location=category,
                    url=link or None, description=description or None, source="ofir",
                ))
            return out

        def _parse_regex(xml: str) -> list[JobResult]:
            """Fallback parser for malformed XML with unescaped & etc."""
            def _field(tag: str, text: str) -> str:
                m = re.search(rf"<{tag}[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", text, re.DOTALL)
                return (m.group(1) or "").strip() if m else ""
            out = []
            for raw in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)[:limit]:
                title = _field("title", raw)
                link = _field("link", raw)
                description = _strip_html(_field("description", raw))
                company = _field("author", raw) or "Ukendt"
                category = _field("category", raw) or None
                if title:
                    out.append(JobResult(
                        title=title, company=company, location=category,
                        url=link or None, description=description or None, source="ofir",
                    ))
            return out

        try:
            return _parse_et(xml_text)
        except ET.ParseError:
            logger.info("Ofir RSS not well-formed — using regex extraction")
            return _parse_regex(xml_text)
