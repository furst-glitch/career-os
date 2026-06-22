"""
JobScraper — henter fuld jobtekst fra kildesiderne.

Strategi:
  - Jobnet: scraper jobnet-siden direkte hvis RSS-beskrivelsen er < 400 tegn
  - Jobindex: hent Jobindex vis-job-side → find link til fuld beskrivelse:
      a) Eksternt ATS-link (HR Manager, Emply, Teamtailor, Greenhouse, ...)
         inkl. Jobindex-interne redirect-URLs (/api/click?url=...)
      b) Jobindex-hostet jobannonce (/jobannonce/-URL)
      URL gemmes i job["ats_url"] for begge tilfælde.
  - Andre kilder: hent HTML, prøv JSON-LD JobPosting, derefter HTML-ekstraktion
  - Fallback: følg eksternt link hvis tekst < 600 tegn
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
    # Stor dansk andel
    "hr-manager.net",
    "applicationinit.aspx",   # HR Manager URL pattern
    "emply.com",
    "emply.net",
    "hr-on.com",
    "teamtailor.com",
    "talentech.com",
    "hrm.dk",
    # Internationale — udbredt i DK
    "greenhouse.io",
    "boards.greenhouse",
    "workable.com",
    "lever.co",
    "recruitee.com",
    "personio.com",
    "smartrecruiters.com",
    "jobvite.com",
    "icims.com",
    "successfactors",
    "taleo.net",
    "oraclecloud.com/hcm",
    "bamboohr.com",
    "workday.com",
    "breezy.hr",
    "ashbyhq.com",
    "pinpointhq.com",
    "rippling.com",
    "radancy.com",
    "jobteaser.com",
    "rexx-systems.com",
    "lumesse.com",
    "talentsoft.com",
    "cornerstone",
    # Jobindex-interne redirect-mønstre (trackede ATS-links)
    "jobindex.dk/api/click",
    "jobindex.dk/cm/v2",
)

# Domains to skip when looking for ATS links (stay on job board itself).
# Bemærk: jobindex.dk er IKKE her — vi skal kunne følge jobindex.dk/jobannonce/...
# og vi håndterer nu jobindex.dk/api/click redirect-URLs separat.
_SKIP_DOMAINS_ATS: frozenset[str] = frozenset([
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

# Platform-specifikke content-selectors til brug ved ATS-sider.
# Supplerer de generiske HTML-hints med kendte klassenavne.
_ATS_CONTENT_HINTS: dict[str, list[str]] = {
    "hr-manager.net": ["job-description", "vacancy-description", "job-content", "jobad-text"],
    "emply.com":      ["job-ad-description", "jobad", "job-body", "jobdescription"],
    "emply.net":      ["job-ad-description", "jobad", "job-body", "jobdescription"],
    "teamtailor.com": ["job-description__text", "job-description", "body-text"],
    "greenhouse.io":  ["job-post-body", "content", "job-description"],
    "boards.greenhouse": ["job-post-body", "content"],
    "workable.com":   ["job-description", "JobDescription", "description"],
    "recruitee.com":  ["job-description", "description", "content"],
    "smartrecruiters.com": ["jobad-desc-container", "job-description"],
    "bamboohr.com":   ["BambooHR-ATS-body", "description", "job-description"],
    "ashbyhq.com":    ["ashby-job-posting-brief__description", "posting-description"],
    "hr-on.com":      ["job-description", "jobdescription", "jobbody"],
    "talentech.com":  ["job-description", "vacancy-description"],
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


def _extract_text(html: str, source: str, extra_hints: list[str] | None = None) -> str:
    """
    Ekstraher jobtekst fra råt HTML via _ContentExtractor.

    `extra_hints` tilføjes foran kildehints — bruges til ATS-platform-specifikke
    selectors der er mere præcise end de generiske source-hints.
    """
    base_hints = _SOURCE_CONTENT_HINTS.get(source, [])
    hints = list(extra_hints or []) + base_hints
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


def _ats_hints_for_url(url: str) -> list[str]:
    """Returner platform-specifikke content-hints for en ATS-URL."""
    url_lower = url.lower()
    for marker, hints in _ATS_CONTENT_HINTS.items():
        if marker in url_lower:
            return hints
    return []


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


def _extract_redirect_target(href: str) -> str | None:
    """
    Udpak den reelle URL fra Jobindex redirect/tracking-links.

    Jobindex bruger interne redirect-URLs som:
      /api/click?url=https://hr-manager.net/...
      /cm/v2/jobclick?url=https://emply.com/...
    Disse er på jobindex.dk og ville ellers skippes.
    """
    from urllib.parse import parse_qs, urlparse
    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        for param in ("url", "redirecturl", "redirect", "target", "link"):
            if param in params:
                target = params[param][0]
                if target.startswith("http"):
                    return target
    except Exception:
        pass
    return None


def _find_ats_link(html: str) -> str | None:
    """
    Find link til ATS-platform i en Jobindex PaidJob-inner sektion.

    Jobindex job-sider indlejrer et link til arbejdsgiverens ATS (HR Manager,
    Emply, Teamtailor, Greenhouse m.fl.) direkte i PaidJob-inner-div'en.
    Den fulde jobbeskrivelse er på ATS-platformen.

    Håndterer:
    - Direkte ATS-links (hr-manager.net, emply.com, ...)
    - Jobindex redirect-URLs (/api/click?url=https://...)
    - Udvidet søgning til hele HTML hvis PaidJob-inner ikke indeholder link

    Søger i PaidJob-inner-sektionen først, derefter hele HTML som fallback.
    """
    from urllib.parse import urlparse

    # Afgræns søgning til PaidJob-inner hvis muligt — prøv 8000 tegn (var 5000)
    paidjob_idx = html.lower().find("paidjob-inner")
    chunk = html[paidjob_idx : paidjob_idx + 8000] if paidjob_idx >= 0 else html

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
    for href in hrefs:
        href = href.strip()
        if not href.startswith("http"):
            continue
        try:
            domain = urlparse(href).netloc.lower()
        except Exception:
            continue

        href_lower = href.lower()

        # Jobindex interne redirect-links: udpak den egentlige URL
        if "jobindex.dk" in domain:
            if "/api/click" in href_lower or "/cm/v2" in href_lower or "redirect" in href_lower:
                target = _extract_redirect_target(href)
                if target:
                    href = target
                    href_lower = href.lower()
                    try:
                        domain = urlparse(href).netloc.lower()
                    except Exception:
                        continue
                else:
                    continue  # jobindex.dk link uden redirect-target — skip

        if any(skip in domain for skip in _SKIP_DOMAINS_ATS):
            continue
        if any(marker in href_lower for marker in _ATS_URL_MARKERS):
            return href

    return None


def _find_jobindex_annonce_link(html: str) -> str | None:
    """
    Find Jobindex jobannonce-link i PaidJob-inner.

    Mange virksomheder (fx Immeo) hoster deres stillingsopslag direkte på
    Jobindex via /jobannonce/-URL'er i stedet for eksternt ATS.
    Disse links er på jobindex.dk og skippes normalt af _find_ats_link.
    """
    paidjob_idx = html.lower().find("paidjob-inner")
    chunk = html[paidjob_idx : paidjob_idx + 5000] if paidjob_idx >= 0 else html

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
    for href in hrefs:
        href = href.strip()
        if "jobindex.dk/jobannonce/" in href.lower():
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

    For Jobnet:
      Scraper jobnet-siden direkte medmindre RSS-beskrivelsen allerede er >= 400 tegn.

    For Jobindex:
      1. Hent Jobindex job-side → extract PaidJob-inner teaser
      2. Find ATS-link (inkl. redirect-URLs) eller Jobindex jobannonce-link
      3. Følg link → brug ATS-platform-specifikke selectors + JSON-LD

    For andre kilder:
      1. Hent HTML
      2. Prøv JSON-LD JobPosting
      3. HTML-ekstraktion (hints → fallback til <main>/<article>)
      4. Hvis < 600 tegn: følg eventuelt eksternt link
    """
    source = job.get("source", "")
    url = job.get("url")

    if not url:
        return

    # Jobnet: spring over hvis RSS-beskrivelsen allerede er tilstrækkelig
    if source == "jobnet":
        existing = job.get("full_description") or job.get("description") or ""
        if len(existing) >= 400:
            return
        # Ellers: scraper jobnet-siden for fuld beskrivelse

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

    # Ekstraher tekst fra kildesiden
    text = _extract_text(html, source)

    # JSON-LD JobPosting på kildesiden (sjælden for Jobindex, hyppig for andre)
    jsonld_text = _extract_jsonld_job(html)
    if len(jsonld_text) > len(text):
        text = jsonld_text
        logger.debug("JSON-LD JobPosting: %d tegn fra %s", len(text), url[:80])

    # ── Jobindex: følg ATS-link eller Jobindex jobannonce-link ───────────────
    if source == "jobindex" and html:
        # Prioritér eksternt ATS-link (inkl. redirect), ellers Jobindex-hostet annonce
        followup_source_url = _find_ats_link(html) or _find_jobindex_annonce_link(html)
        if followup_source_url:
            followup_html: str | None = None
            async with sem:
                try:
                    resp_fu = await client.get(followup_source_url, headers=_SCRAPE_HEADERS)
                    if resp_fu.status_code == 200:
                        followup_html = resp_fu.text
                        logger.debug(
                            "Job source URL: %s → %d chars",
                            followup_source_url[:60], len(followup_html),
                        )
                except Exception as exc:
                    logger.debug("Followup-scrape fejlede for %s: %s", followup_source_url, exc)

            if followup_html:
                # JSON-LD foretrækkes; dernæst ATS-platform-specifikke hints
                fu_text = _extract_jsonld_job(followup_html)
                if len(fu_text) < 300:
                    ats_hints = _ats_hints_for_url(followup_source_url)
                    fu_text = _extract_text(followup_html, "jobindex", extra_hints=ats_hints)
                if len(fu_text) < 300:
                    fu_text = _extract_text(followup_html, "")
                if len(fu_text) > len(text):
                    text = fu_text
                    job["ats_url"] = followup_source_url
                    logger.debug(
                        "Job source scrape: %d tegn fra %s",
                        len(text), followup_source_url[:80],
                    )

    # ── Generisk fallback: følg eksternt link hvis stadig for kort ───────────
    # Tærskel hævet til 600 — mange teasere er 400-600 tegn men ufuldstændige
    if len(text) < 600 and html:
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
                    ats_hints = _ats_hints_for_url(followup_url)
                    text2 = _extract_text(followup_html, "", extra_hints=ats_hints)
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
