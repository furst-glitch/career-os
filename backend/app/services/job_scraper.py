"""
JobScraper — henter fuld jobtekst fra kildesiderne.

Strategi:
  - Jobnet: springer over (RSS description bruges direkte)
  - Jobindex: hent Jobindex-side → extract teaser → find ATS-link i PaidJob-inner
              → follow ATS-link → hent fuld beskrivelse (typisk 5-8k tegn)
  - Andre kilder: hent HTML, prøv JSON-LD JobPosting, derefter HTML-ekstraktion
  - Fallback: generisk ekstraktion fra <main>/<article>

ATS-platforme vi målrettet følger links til:
  HR Manager / Talentech, Emply, Teamtailor, Greenhouse, Workable,
  Lever, Recruitee, Personio m.fl.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from html.parser import HTMLParser

import httpx

logger = logging.getLogger(__name__)

_MAX_CHARS = 6_000

_SCRAPE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}

_SOURCE_CONTENT_HINTS: dict[str, list[str]] = {
    "jobindex": [
        # Jobindex job content is in class="PaidJob-inner" (teaser, ~600 chars)
        "PaidJob-inner", "jobad-body", "jix_jobtext",
        "PosAdStory", "job-description", "job-text",
    ],
    "ofir": [
        "job-post-body", "job-description", "description-text",
        "job-text", "job_description", "jobtext", "jobad",
    ],
    "jobnet": [
        "job-posting", "jobpostingdescription", "job-description",
        "jobtext", "job-body",
    ],
}

# Substrings that identify known ATS platforms in a URL.
# Ordered by approximate Danish market share.
_ATS_URL_MARKERS: tuple[str, ...] = (
    "hr-manager.net",
    "applicationinit.aspx",   # HR Manager URL pattern
    "emply.com",
    "emply.net",
    "teamtailor.com",
    "greenhouse.io",
    "boards.greenhouse",
    "workable.com",
    "lever.co",
    "recruitee.com",
    "personio.com",
    "talentech.com",
    "hrm.dk",
    "smartrecruiters.com",
    "jobvite.com",
    "icims.com",
    "successfactors",
    "breezy.hr",
    "ashbyhq.com",
)

# Domains to skip when looking for ATS links (stay on job board itself)
_SKIP_DOMAINS_ATS: frozenset[str] = frozenset([
    "jobindex.dk",
    "jobindexkurser.dk",
    "ofir.dk",
    "jobnet.dk",
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "google.com",
    "youtube.com",
    "apple.com",
    "play.google.com",
])


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

    # Void elements have no closing tag in HTML5 — never increment depth for them
    _VOID_ELEMENTS: frozenset[str] = frozenset([
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ])

    def __init__(self, content_hints: list[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._hints = [h.lower() for h in content_hints]
        self._depth = 0
        self._skip_depth = 0
        self._target_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Void elements have no matching endtag — skip depth tracking to avoid drift
        if tag in self._VOID_ELEMENTS:
            return

        self._depth += 1

        if tag in self._ALWAYS_SKIP and self._skip_depth == 0:
            self._skip_depth = self._depth
            return

        if self._skip_depth > 0:
            return

        if self._target_depth == 0 and self._hints:
            attr_dict = {k: (v or "").lower() for k, v in attrs}
            cls = attr_dict.get("class", "")
            elem_id = attr_dict.get("id", "")
            combined = cls + " " + elem_id
            if any(h in combined for h in self._hints):
                self._target_depth = self._depth
                return

        if self._target_depth == 0 and tag in ("main", "article"):
            self._target_depth = self._depth

    def handle_endtag(self, tag: str) -> None:
        if tag in self._VOID_ELEMENTS:
            return
        if self._skip_depth == self._depth:
            self._skip_depth = 0
        if self._target_depth == self._depth:
            self._target_depth = 0
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._target_depth > 0 or not self._hints:
            text = data.strip()
            if len(text) >= 2:
                self._parts.append(text)

    def get_text(self) -> str:
        raw = "\n".join(self._parts)
        raw = re.sub(r" {2,}", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _extract_text(html: str, source: str) -> str:
    """Ekstraher jobtekst fra råt HTML via _ContentExtractor."""
    hints = _SOURCE_CONTENT_HINTS.get(source, [])
    parser = _ContentExtractor(hints)
    try:
        parser.feed(html)
    except Exception:
        pass
    text = parser.get_text()

    if len(text) < 150 and hints:
        fallback = _ContentExtractor([])
        try:
            fallback.feed(html)
        except Exception:
            pass
        text = fallback.get_text()

    return text[:_MAX_CHARS]


def _extract_jsonld_job(html: str) -> str:
    """
    Søg efter JSON-LD <script type="application/ld+json"> med @type JobPosting.
    Returnerer description-feltet (HTML-strips) eller tom streng.
    """
    import json as _json

    blocks = re.findall(
        r'<script[^>]+application/ld\+json[^>]*>([\s\S]*?)</script>',
        html,
        re.IGNORECASE,
    )
    best = ""
    for block in blocks:
        try:
            data = _json.loads(block.strip())
        except Exception:
            continue

        entries = data if isinstance(data, list) else [data]
        flat: list[dict] = []
        for entry in entries:
            if isinstance(entry, dict) and "@graph" in entry:
                flat.extend(entry["@graph"])
            else:
                flat.append(entry)

        for entry in flat:
            if not isinstance(entry, dict):
                continue
            entry_type = entry.get("@type", "")
            types = entry_type if isinstance(entry_type, list) else [entry_type]
            if "JobPosting" not in types:
                continue
            raw = entry.get("description", "")
            if not raw:
                continue
            cleaned = re.sub(r"<[^>]+>", " ", raw)
            cleaned = re.sub(r"&nbsp;", " ", cleaned)
            cleaned = re.sub(r"&amp;", "&", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if len(cleaned) > len(best):
                best = cleaned
    return best


def _find_ats_link(html: str) -> str | None:
    """
    Find link til ATS-platform i en Jobindex PaidJob-inner sektion.

    Jobindex job-sider indlejrer et link til arbejdsgiverens ATS (HR Manager,
    Emply, Teamtailor, Greenhouse m.fl.) direkte i PaidJob-inner-div'en.
    Den fulde jobbeskrivelse er på ATS-platformen.

    Søger i PaidJob-inner-sektionen først, derefter hele HTML som fallback.
    """
    from urllib.parse import urlparse

    # Afgræns søgning til PaidJob-inner hvis muligt
    paidjob_idx = html.lower().find("paidjob-inner")
    chunk = html[paidjob_idx : paidjob_idx + 5000] if paidjob_idx >= 0 else html

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
    for href in hrefs:
        href = href.strip()
        if not href.startswith("http"):
            continue
        try:
            domain = urlparse(href).netloc.lower()
        except Exception:
            continue
        if any(skip in domain for skip in _SKIP_DOMAINS_ATS):
            continue
        href_lower = href.lower()
        if any(marker in href_lower for marker in _ATS_URL_MARKERS):
            return href

    return None


def _find_external_job_url(html: str) -> str | None:
    """
    Find link til den egentlige stillingsannonce fra en landing-/listeside.
    Bruges som fallback når der ikke er et ATS-link og teksten er for kort.
    """
    from urllib.parse import urlparse

    _APPLY_RE = re.compile(
        r"(s[øo]g\s+stillingen|se\s+stillingsopslaget|se\s+opslaget|ansøg\s+nu|apply\s+now|full\s+job|read\s+more)",
        re.IGNORECASE,
    )

    anchors = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        html,
        re.DOTALL | re.IGNORECASE,
    )

    priority: list[str] = []
    fallback: list[str] = []

    for href, raw_text in anchors:
        href = href.strip()
        if not href.startswith("http"):
            continue
        try:
            domain = urlparse(href).netloc.lower().lstrip("www.")
        except Exception:
            continue
        if any(skip in domain for skip in _SKIP_DOMAINS_ATS):
            continue
        clean_text = re.sub(r"<[^>]+>", "", raw_text).strip()
        if _APPLY_RE.search(clean_text):
            priority.append(href)
        else:
            fallback.append(href)

    return (priority or fallback or [None])[0]


# ── Scrape enkelt job ─────────────────────────────────────────────────────────

async def _scrape_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    job: dict,
) -> None:
    """
    Henter fuld jobtekst for ét job in-place.

    For Jobindex:
      1. Hent Jobindex job-side → extract PaidJob-inner teaser
      2. Find ATS-link i PaidJob-inner (HR Manager, Emply, Teamtailor, ...)
      3. Følg ATS-link → hent fuld jobbeskrivelse (typisk 5-8k tegn)

    For andre kilder:
      1. Hent HTML
      2. Prøv JSON-LD JobPosting
      3. HTML-ekstraktion (hints → fallback til <main>/<article>)
      4. Hvis < 400 tegn: følg eventuelt eksternt link
    """
    source = job.get("source", "")
    url = job.get("url")

    if source == "jobnet":
        return
    if not url:
        return

    html: str | None = None
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

    # Ekstraher teaser fra kildesiden
    text = _extract_text(html, source)

    # JSON-LD JobPosting på kildesiden (sjælden for Jobindex, hyppig for andre)
    jsonld_text = _extract_jsonld_job(html)
    if len(jsonld_text) > len(text):
        text = jsonld_text
        logger.debug("JSON-LD JobPosting: %d tegn fra %s", len(text), url[:80])

    # ── Jobindex: følg ATS-link til fuld jobbeskrivelse ──────────────────────
    if source == "jobindex" and html:
        ats_url = _find_ats_link(html)
        if ats_url:
            ats_html: str | None = None
            async with sem:
                try:
                    resp_ats = await client.get(ats_url, headers=_SCRAPE_HEADERS)
                    if resp_ats.status_code == 200:
                        ats_html = resp_ats.text
                        logger.debug("ATS URL: %s → %d chars", ats_url[:60], len(ats_html))
                except Exception as exc:
                    logger.debug("ATS-scrape fejlede for %s: %s", ats_url, exc)

            if ats_html:
                # JSON-LD på ATS-siden foretrækkes
                ats_text = _extract_jsonld_job(ats_html)
                if len(ats_text) < 300:
                    # Generisk HTML-ekstraktion (ingen hints — brug <main>/<article>)
                    ats_text = _extract_text(ats_html, "")
                if len(ats_text) > len(text):
                    text = ats_text
                    logger.debug(
                        "ATS-scrape: %d tegn fra %s", len(text), ats_url[:80]
                    )

    # ── Generisk fallback: følg eksternt link hvis stadig for kort ───────────
    if len(text) < 400 and html:
        followup_url = _find_external_job_url(html)
        if followup_url:
            followup_html: str | None = None
            async with sem:
                try:
                    resp2 = await client.get(followup_url, headers=_SCRAPE_HEADERS)
                    if resp2.status_code == 200:
                        followup_html = resp2.text
                except Exception as exc:
                    logger.debug("Followup-scrape fejlede for %s: %s", followup_url, exc)
            if followup_html:
                text2 = _extract_jsonld_job(followup_html)
                if not text2 or len(text2) < 200:
                    text2 = _extract_text(followup_html, "")
                if len(text2) > len(text):
                    text = text2
                    logger.debug(
                        "Followup-scrape: %d tegn fra %s",
                        len(text), followup_url[:80],
                    )

    if len(text) >= 100:
        job["full_description"] = text
        job["scraped_at"] = datetime.now(UTC).isoformat()
        logger.debug("Scraped %d tegn fra %s (%s)", len(text), source, url[:80])


# ── Batch scraping ────────────────────────────────────────────────────────────

async def scrape_jobs_batch(
    jobs: list[dict],
    max_concurrent: int = 5,
    timeout_per_request: float = 10.0,
    total_timeout: float = 25.0,
) -> None:
    """
    Scraper fuld jobtekst for alle jobs in-place.

    Timeout er sat op ift. at Jobindex-jobs nu kan kræve 2 requests
    (Jobindex-side + ATS-side).
    """
    sem = asyncio.Semaphore(max_concurrent)
    async with httpx.AsyncClient(
        timeout=timeout_per_request,
        follow_redirects=True,
        max_redirects=5,
    ) as client:
        tasks = [_scrape_one(client, sem, job) for job in jobs]
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=total_timeout,
            )
        except TimeoutError:
            logger.info("Scraping batch timed out efter %.0fs — delresultater bruges", total_timeout)
