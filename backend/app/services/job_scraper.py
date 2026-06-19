"""
JobScraper — henter fuld jobtekst fra kildesiderne.

Strategi:
  - Jobnet: API returnerer allerede fuld beskrivelse — springes over
  - Jobindex: Hent HTML fra job-URL, ekstraher tekstindhold
  - Ofir: Hent HTML fra job-URL, ekstraher tekstindhold
  - Fallback: Generisk ekstraktion fra <main>/<article>

Ekstraktion sker med Pythons built-in HTMLParser.
Nav, header, footer, script og style springes over.
Maks 5 samtidige HTTP-requests (Semaphore).
Maks 8 sekunder pr. request.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from html.parser import HTMLParser

import httpx

logger = logging.getLogger(__name__)

# Maksimal antal tegn at gemme (resten afskæres for at holde DB-størrelse nede)
_MAX_CHARS = 6_000

_SCRAPE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (compatible; CareerOS/1.0; +https://careeros.dk)",
}

# Kildespecifikke klasser/tags der typisk indeholder jobbeskrivelse
# Listet i prioriteret rækkefølge
_SOURCE_CONTENT_HINTS: dict[str, list[str]] = {
    "jobindex": [
        "PosAdStory", "jobad-body", "jobad-content", "job-description",
        "job-text", "job-body", "description",
    ],
    "ofir": [
        "job-post-body", "job-description", "description-text",
        "job-text", "job_description", "jobtext",
    ],
}


# ── HTMLParser ekstraktor ─────────────────────────────────────────────────────

class _ContentExtractor(HTMLParser):
    """
    Ekstraktor der:
      1. Springer script/style/nav/header/footer/aside over
      2. Finder første container der matcher source-hints
      3. Falder tilbage til <main>, <article>, eller hele body
    """

    _ALWAYS_SKIP: frozenset[str] = frozenset([
        "script", "style", "nav", "header", "footer",
        "aside", "noscript", "template", "iframe",
    ])

    def __init__(self, content_hints: list[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._hints = [h.lower() for h in content_hints]
        self._depth = 0
        self._skip_depth = 0          # ignore subtree when > 0
        self._target_depth = 0        # capture subtree when > 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._depth += 1

        # Altid springer disse tags over (og deres undertræ)
        if tag in self._ALWAYS_SKIP and self._skip_depth == 0:
            self._skip_depth = self._depth
            return

        if self._skip_depth > 0:
            return

        # Aktivér hinting-baseret opsamling
        if self._target_depth == 0 and self._hints:
            attr_dict = {k: (v or "").lower() for k, v in attrs}
            cls = attr_dict.get("class", "")
            elem_id = attr_dict.get("id", "")
            combined = cls + " " + elem_id
            if any(h in combined for h in self._hints):
                self._target_depth = self._depth
                return

        # Generiske fallbacks
        if self._target_depth == 0 and tag in ("main", "article"):
            self._target_depth = self._depth

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth == self._depth:
            self._skip_depth = 0
        if self._target_depth == self._depth:
            self._target_depth = 0
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        # Kun opsaml hvis vi er inde i target-container (eller ingen container fundet)
        if self._target_depth > 0 or not self._hints:
            text = data.strip()
            if len(text) >= 2:
                self._parts.append(text)

    def get_text(self) -> str:
        raw = "\n".join(self._parts)
        # Normaliser whitespace: bevar linjeskift, fjern gentagne blanke linjer
        raw = re.sub(r" {2,}", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _extract_text(html: str, source: str) -> str:
    """Ekstraher jobtekst fra råt HTML. Returner op til _MAX_CHARS tegn."""
    hints = _SOURCE_CONTENT_HINTS.get(source, [])
    parser = _ContentExtractor(hints)
    try:
        parser.feed(html)
    except Exception:
        pass
    text = parser.get_text()

    # Fallback: ingen content fundet via hints → kør uden hints
    if len(text) < 150 and hints:
        fallback = _ContentExtractor([])
        try:
            fallback.feed(html)
        except Exception:
            pass
        text = fallback.get_text()

    return text[:_MAX_CHARS]


# ── Scrape enkelt job ─────────────────────────────────────────────────────────

async def _scrape_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    job: dict,
) -> None:
    """
    Henter fuld jobtekst for ét job in-place.
    Springer Jobnet over (har allerede API-data).
    """
    source = job.get("source", "")
    url = job.get("url")

    if source == "jobnet":
        # Jobnet API returnerer JobPostingDescription — allerede i description
        return
    if not url:
        return

    async with sem:
        try:
            resp = await client.get(url, headers=_SCRAPE_HEADERS)
            if resp.status_code != 200:
                logger.debug("Scrape HTTP %s for %s", resp.status_code, url)
                return
            html = resp.text
        except Exception as exc:
            logger.debug("Scrape fejlede for %s: %s", url, exc)
            return

    text = _extract_text(html, source)
    if len(text) >= 100:
        job["full_description"] = text
        job["scraped_at"] = datetime.now(UTC).isoformat()
        logger.debug(
            "Scraped %d tegn fra %s (%s)",
            len(text), source, url[:80],
        )


# ── Batch scraping ────────────────────────────────────────────────────────────

async def scrape_jobs_batch(
    jobs: list[dict],
    max_concurrent: int = 5,
    timeout_per_request: float = 8.0,
    total_timeout: float = 15.0,
) -> None:
    """
    Scraper fuld jobtekst for alle jobs in-place.

    Args:
        jobs:               Liste af job-dicts (muteres in-place med full_description)
        max_concurrent:     Maks antal samtidige HTTP-requests
        timeout_per_request: Timeout per request (sekunder)
        total_timeout:      Total timeout for hele batchen (sekunder)
    """
    sem = asyncio.Semaphore(max_concurrent)
    async with httpx.AsyncClient(
        timeout=timeout_per_request,
        follow_redirects=True,
        max_redirects=3,
    ) as client:
        tasks = [_scrape_one(client, sem, job) for job in jobs]
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=total_timeout,
            )
        except TimeoutError:
            logger.info("Scraping batch timed out efter %.0fs — delresultater bruges", total_timeout)
