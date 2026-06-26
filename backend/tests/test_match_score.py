"""
Unit tests for compute_match_score — verificerer intelligent multi-signal scoring.

Kandidatprofil der bruges som testcase:
  - Business Partner / Facility Manager (target_title)
  - Skills: Facility Management, Procurement, ESG, Ledelse, Budgetansvar, Leverandørstyring
  - Erfaring: Business Partner, Facility Manager, Category Manager
"""
import pytest
from app.services.job_service import JobService, _match_term, _tokenise


def _svc() -> JobService:
    return JobService.__new__(JobService)


SNAPSHOT_FULL = {
    "profile": {
        "target_title": "Business Partner / Facility Manager",
        "summary": (
            "Erfaren Business Partner med stærk baggrund inden for Facility Management, "
            "Procurement, ESG-rapportering og ledelse af teams. Bred erfaring med budgetansvar "
            "og leverandørstyring i både offentlige og private organisationer."
        ),
    },
    "skills": [
        {"name": "Facility Management"},
        {"name": "Procurement"},
        {"name": "ESG"},
        {"name": "Ledelse"},
        {"name": "Budgetansvar"},
        {"name": "Leverandørstyring"},
    ],
    "experience": [
        {
            "title": "Business Partner",
            "company": "Novo Nordisk",
            "description": "Ansvarlig for facility management og leverandørstyring. Budgetansvar på 15M DKK.",
        },
        {
            "title": "Category Manager – Procurement",
            "company": "Maersk",
            "description": "Strategisk indkøb, leverandørforhandlinger, ESG-krav i supply chain.",
        },
        {
            "title": "Facility Manager",
            "company": "ISS Danmark",
            "description": "Driftsledelse, vedligehold, serviceleverancer og personaledelse.",
        },
    ],
    "certifications": [],
    "preferences": {
        "industries": ["facility", "procurement", "esg"],
        "role_types": ["teamleder", "manager", "business partner"],
    },
}

SNAPSHOT_EMPTY_SKILLS = {
    **SNAPSHOT_FULL,
    "skills": [],
    "experience": [],
    "certifications": [],
}


# ── _match_term tests ─────────────────────────────────────────────────────────

def test_exact_match():
    tokens = set(_tokenise("facility management og drift"))
    assert _match_term("facility management", "facility management og drift", tokens)


def test_danish_compound_word_ledelse_teamleder():
    """'ledelse' skal matche 'teamleder' via ordniveau: 'leder' er delstreng af 'teamleder'."""
    tokens = set(_tokenise("teamleder til facility afdelingen"))
    assert _match_term("ledelse", "teamleder til facility afdelingen", tokens)


def test_danish_compound_word_leverandoerstyring():
    """'leverandørstyring' skal matche 'leverandør' i jobteksten."""
    tokens = set(_tokenise("du skal styre leverandør og indkøb"))
    assert _match_term("leverandørstyring", "du skal styre leverandør og indkøb", tokens)


def test_stem_match_budgetansvar():
    """'budgetansvar' stem 'budge' matcher 'budgettere' og 'budgetansvarlig'."""
    tokens = set(_tokenise("du har budgetansvarlig for afdelingen"))
    assert _match_term("budgetansvar", "du har budgetansvarlig for afdelingen", tokens)


def test_procurement_english_in_danish_job():
    """'procurement' skal matche direkte i jobtekst."""
    tokens = set(_tokenise("strategisk procurement og indkøbsledelse"))
    assert _match_term("procurement", "strategisk procurement og indkøbsledelse", tokens)


def test_esg_short_term():
    """ESG er kun 3 bogstaver — skal matche eksakt."""
    tokens = set(_tokenise("vi arbejder med esg og bæredygtighed"))
    assert _match_term("esg", "vi arbejder med esg og bæredygtighed", tokens)


def test_no_false_positive():
    """'Budgetansvar' skal IKKE matche 'software engineering' job."""
    tokens = set(_tokenise("senior software engineer react typescript"))
    assert not _match_term("budgetansvar", "senior software engineer react typescript", tokens)


# ── compute_match_score tests ─────────────────────────────────────────────────

async def test_facility_teamleder_job_high_score():
    """Facility/Procurement-profil skal score højt på 'Teamleder Facility Management' job."""
    svc = _svc()
    job = {
        "title": "Teamleder – Facility Management og Drift",
        "description": (
            "Vi søger en erfaren teamleder til vores facility-afdeling. "
            "Du har ansvar for leverandørstyring, budgetansvar og ledelse af 5 medarbejdere. "
            "Kendskab til ESG-krav er en fordel. Procurement-erfaring er et plus."
        ),
        "requirements": [
            "Erfaring med facility management",
            "Ledelseservaring",
            "Budgetansvar",
            "Leverandørstyring",
        ],
        "company": "ISS Danmark",
    }
    result = await svc.compute_match_score(job, SNAPSHOT_FULL)
    assert result["total"] >= 50, f"Forventede ≥50, fik {result['total']} — breakdown: {result['breakdown']}"


async def test_irrelevant_job_low_score():
    """Facility-profil skal score lavt på et software-engineering job."""
    svc = _svc()
    job = {
        "title": "Senior Backend Engineer",
        "description": "We build distributed systems in Go and Rust. Kubernetes, CI/CD, microservices.",
        "requirements": ["Go", "Rust", "Kubernetes", "Docker", "gRPC"],
        "company": "TechStartup ApS",
    }
    result = await svc.compute_match_score(job, SNAPSHOT_FULL)
    assert result["total"] <= 25, f"Forventede ≤25, fik {result['total']} — breakdown: {result['breakdown']}"


async def test_procurement_job_good_score():
    """Profil med Procurement/ESG skal score højt på Indkøbschef job."""
    svc = _svc()
    job = {
        "title": "Indkøbschef – Procurement og ESG",
        "description": (
            "Du leder vores indkøbsfunktion og driver procurement-strategi. "
            "ESG-krav i supply chain, leverandørevalueringer og budgetansvar."
        ),
        "requirements": ["Procurement", "ESG", "Leverandørstyring", "Budgetansvar"],
        "company": "Grundfos",
    }
    result = await svc.compute_match_score(job, SNAPSHOT_FULL)
    # Profil-signal er lavt da target_title er "Business Partner/Facility" ikke "Indkøbschef"
    # — men skills+erfaring+præferencer giver solid score
    assert result["total"] >= 38, f"Forventede ≥38, fik {result['total']} — breakdown: {result['breakdown']}"


async def test_empty_profile_low_but_not_zero():
    """Profil uden skills/erfaring skal score lavt men ikke fejle."""
    svc = _svc()
    job = {
        "title": "Teamleder Facility",
        "description": "Facility management og drift.",
        "requirements": ["Ledelse", "Facility Management"],
        "company": "CBRE",
    }
    result = await svc.compute_match_score(job, SNAPSHOT_EMPTY_SKILLS)
    assert isinstance(result["total"], float)
    assert 0 <= result["total"] <= 100


async def test_target_title_boost():
    """target_title 'Business Partner' skal give boost på Business Partner job."""
    svc = _svc()
    job = {
        "title": "Senior Business Partner – HR",
        "description": "Du arbejder som business partner tæt på ledelsen og HRBPs.",
        "requirements": ["Business Partner erfaring", "Strategisk rådgivning"],
        "company": "Velux",
    }
    result = await svc.compute_match_score(job, SNAPSHOT_FULL)
    assert result["total"] >= 35, f"target_title boost forventet ≥35, fik {result['total']}"


async def test_score_is_bounded():
    """Score skal altid være 0-100."""
    svc = _svc()
    job = {
        "title": "Facility Management Business Partner ESG Procurement Ledelse",
        "description": "leverandørstyring budgetansvar facility management procurement esg",
        "requirements": ["Facility Management", "Procurement", "ESG", "Ledelse",
                         "Budgetansvar", "Leverandørstyring", "Business Partner"],
        "company": "Test A/S",
    }
    result = await svc.compute_match_score(job, SNAPSHOT_FULL)
    assert 0 <= result["total"] <= 100


async def test_breakdown_keys_present():
    """Breakdown skal indeholde de forventede nøgler."""
    svc = _svc()
    job = {"title": "Test", "description": "", "requirements": [], "company": ""}
    result = await svc.compute_match_score(job, SNAPSHOT_FULL)
    assert set(result["breakdown"].keys()) >= {"skills", "experience", "preferences", "certifications"}
