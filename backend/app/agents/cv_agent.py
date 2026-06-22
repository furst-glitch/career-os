"""
CV Agent — parser CV-tekst til struktureret kandidatprofil og identificerer gaps.

Input:  { raw_text: str }
Output: AgentResult med parsed_data og gaps i metadata
"""
import json
import re
import time

from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

PARSE_SYSTEM_PROMPT = """Du er en præcis CV-analysator. Analyser CV-teksten og returner UDELUKKENDE et JSON-objekt.

JSON-struktur (alle felter obligatoriske, brug null hvis mangler):
{
  "personal": {
    "name": string | null,
    "email": string | null,
    "phone": string | null,
    "location": string | null,
    "linkedin": string | null,
    "current_title": string | null
  },
  "summary": string | null,
  "experiences": [
    {
      "title": string,
      "company": string,
      "location": string | null,
      "period_start": "YYYY-MM" | null,
      "period_end": "YYYY-MM" | null,
      "is_current": boolean,
      "description": string | null,
      "achievements": string[],
      "technologies": string[]
    }
  ],
  "educations": [
    {
      "degree": string,
      "institution": string,
      "period_start": "YYYY-MM" | null,
      "period_end": "YYYY-MM" | null,
      "description": string | null
    }
  ],
  "skills": [
    {
      "name": string,
      "category": "technical" | "soft" | "language" | "domain",
      "level": "beginner" | "intermediate" | "advanced" | "expert" | null
    }
  ],
  "projects": [
    {
      "name": string,
      "description": string | null,
      "role": string | null,
      "technologies": string[],
      "outcomes": string | null,
      "period_start": "YYYY-MM" | null,
      "period_end": "YYYY-MM" | null
    }
  ],
  "certifications": [
    {
      "name": string,
      "issuer": string | null,
      "issued_at": "YYYY-MM" | null,
      "expires_at": "YYYY-MM" | null,
      "credential_id": string | null
    }
  ],
  "systems": [
    {
      "name": string,
      "category": string | null,
      "proficiency": "beginner" | "intermediate" | "advanced" | "expert" | null
    }
  ],
  "leadership": [
    {
      "title": string,
      "scope": string | null,
      "direct_reports": number | null,
      "period_start": "YYYY-MM" | null,
      "period_end": "YYYY-MM" | null,
      "responsibilities": string[]
    }
  ],
  "gaps": [
    {
      "section": "experiences" | "achievements" | "projects" | "skills" | "systems" | "leadership" | "certifications",
      "description": string,
      "priority": "high" | "medium" | "low"
    }
  ]
}

Identificer gaps baseret på:
- Erfaringer uden kvantificerede resultater → "achievements", HIGH
- Korte/vage jobbeskrivelser → "experiences", HIGH
- Ingen systemer/teknologier til trods for teknisk rolle → "systems", MEDIUM
- Ingen projekter beskrevet → "projects", MEDIUM
- Senior-titel uden lederskabsbeskrivelse → "leadership", MEDIUM
- Manglende certifikater for relevante brancher → "certifications", LOW

Returner KUN valid JSON. INGEN tekst udenfor JSON-objektet."""

EXTRACTION_SYSTEM_PROMPT = """Du ekstraherer strukturerede facts fra én udveksling i et karriere-interview.

Returner KUN et JSON-objekt med NYE facts fra dette specifikke svar:
{
  "achievements": [
    { "title": string, "description": string, "metric": string | null, "impact_level": "low"|"medium"|"high", "year": number | null }
  ],
  "projects": [
    { "name": string, "description": string, "role": string | null, "technologies": string[], "outcomes": string | null }
  ],
  "systems": [
    { "name": string, "category": string | null, "proficiency": "beginner"|"intermediate"|"advanced"|"expert" | null }
  ],
  "skills": [
    { "name": string, "category": "technical"|"soft"|"language"|"domain", "level": string | null }
  ],
  "leadership": [
    { "title": string, "scope": string | null, "direct_reports": number | null, "responsibilities": string[] }
  ],
  "certifications": [
    { "name": string, "issuer": string | null, "issued_at": "YYYY-MM" | null, "expires_at": "YYYY-MM" | null, "credential_id": string | null }
  ],
  "experience_additions": [
    { "company": string, "new_achievements": string[], "new_technologies": string[] }
  ],
  "gaps_resolved": string[]
}

Regler:
- Inkludér KUN eksplicit nævnte facts fra dette specifikke kandidatsvar
- Brug tomme arrays for sektioner uden nye facts
- certifications: kun hvis kandidaten eksplicit nævner et certifikat ved navn
- gaps_resolved: beskrivelser af gaps der nu er tilstrækkeligt besvaret
- Returner KUN valid JSON uden markdown-blokke"""


class CVAgent(BaseAgent):
    name = "cv_agent"

    async def generate(self, input_data: dict) -> AgentResult:
        """
        Genererer et CV-udkast til brug i GenerationPipeline (trin 1 af CV-pipeline).

        LLM genererer KUN: Professionel profil + Erhvervserfaring + Udvalgte resultater.
        Hardcoded fra snapshot (bypasser LLM): Kompetencer, Systemer, Uddannelse, Sprog.

        Returnerer AgentResult med JSON-string som content:
          { "_structured_cv_v2": true, "cv_text": "...", "education": [...],
            "competencies": [...], "systems": [...], "languages": [...], "language": "da" }

        Den strukturerede JSON serialiseres til document_versions.content.
        Ved PDF-render detekteres JSON-format og renderer via structured pipeline.
        """
        import json as _json

        language = input_data.get("language", "da")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:3000]
        requirements = input_data.get("job_requirements", [])
        candidate_summary = input_data.get("candidate_summary", "")
        req_text = "\n".join(f"- {r}" for r in requirements[:15]) if requirements else "Ikke angivet"

        # Fetch snapshot — source of truth for hardcoded sections
        try:
            from app.services.memory_snapshot_service import MemorySnapshotService
            snapshot = MemorySnapshotService(self.supabase).snapshot(self.user_id)
        except Exception:
            snapshot = {}

        job_dict = {"title": job_title, "description": job_description, "requirements": requirements}

        # Build hardcoded structured sections — these NEVER go through LLM
        education_list   = self._build_structured_education(snapshot)
        skills_data      = self._build_structured_skills(snapshot, job_dict)
        languages_list   = [
            {"language": s.get("name", ""), "level": s.get("level", "")}
            for s in (snapshot.get("skills") or [])
            if s.get("category") == "language" and s.get("name")
        ]

        da = language == "da"
        if da:
            system = (
                f"Du er en ekspert CV-skribent. Skriv et stærkt, jobspecifikt CV til stillingen "
                f"{job_title} hos {job_company}.\n\n"
                "VIGTIGT — BEGRÆNSEDE SEKTIONER:\n"
                "Du skriver KUN to sektioner i dette svar:\n"
                "  1. ## Professionel profil\n"
                "  2. ## Erhvervserfaring\n"
                "  3. ## Udvalgte resultater (kun hvis kandidaten har kvantificerede præstationer)\n\n"
                "Skriv IKKE: Kompetencer, Systemer, Uddannelse, Certifikater, Sprog, Kontakt.\n"
                "Disse sektioner tilføjes automatisk fra databasen og må ALDRIG duplikeres her.\n\n"
                "PRÆCISIONSTJEK (gennemfør mentalt inden du skriver):\n"
                "1. Har kandidaten formel personaleledelse (direkte rapporteringer) — eller kun faglig/projektledelse?\n"
                "   Skriv ALDRIG 'ledelse' uden at specificere typen.\n"
                "2. Er alle DKK-beløb, procenter og headcount bekræftet i profilen?\n"
                "3. Er kandidaten enebidragsyder eller del af et team?\n\n"
                "PRÆCISIONSREGLER — TO FEJLTYPER:\n"
                "Type A — Overstatement (aldrig tilladt):\n"
                "- 'drev implementeringen' ≠ 'var IT-ansvarlig'\n"
                "- 'bidragede til X' ≠ 'var ansvarlig for X'\n"
                "- Opfind ALDRIG eksempler, beløb, datoer eller resultater\n"
                "Type B — Understatement (også en fejl):\n"
                "- Erfaringer i profilen SKAL inkluderes — afkort aldrig karrierehistorik\n"
                "- Brug hæmmet sprog for afledt data ('sandsynligvis') men inkludér det\n"
                "Bekræftet data: inkludér altid. Afledt data: hæmmet sprog. Opfundet: aldrig.\n\n"
                "LEDERSKABSSPROG:\n"
                "- Formel personaleledelse: 'personaleleder med X direkte rapporteringer'\n"
                "- Faglig ledelse: 'faglig leder / rådgiver for X'\n"
                "- Projektledelse: 'projektleder for X'\n"
                "Skriv ALDRIG bare 'ledelse' uden type.\n\n"
                "## Professionel profil\n"
                "4-5 sætninger der præcist matcher kandidaten til netop dette job. "
                "Inkludér IKKE målvirksomhedens navn — profilteksten skal være portabel. "
                "Nævn kernekompetencer, årstal erfaring, og hvad kandidaten bringer som unik værdi.\n\n"
                "## Erhvervserfaring\n"
                "Omvendt kronologisk. Inkludér ALLE stillinger — afkort aldrig karrierehistorik.\n"
                "For HVER stilling SKAL alle tre elementer være til stede:\n\n"
                "ELEMENT 1 — OVERSKRIFT:\n"
                "  [Stillingsbetegnelse] – [Virksomhed] | [Startår] – [Slutår eller nu]\n\n"
                "ELEMENT 2 — KONTEKSTLINJE (altid, 1-2 sætninger — IKKE et bullet):\n"
                "  Hvad rollen indebar på et overordnet niveau. "
                "  Inkludér scope: antal lokationer, medarbejdere, budget.\n"
                "  Spring ALDRIG Element 2 over.\n\n"
                "ELEMENT 3 — BULLETS:\n"
                "  Nuværende rolle: 12-15 bullets. Sekundære: 4-6. Ældre: 1-2.\n"
                "  Aktivt sprog: 'styrede', 'opbyggede', 'drev'.\n"
                "  IKKE passivt: 'understøttede', 'bidragede til at understøtte'.\n\n"
                "## Udvalgte resultater\n"
                "Hent fra PRÆSTATIONER i kandidatprofilen. 5-8 stærkeste kvantificerede resultater. "
                "Udelad sektionen hvis ingen præstationer er oplyst.\n\n"
                "REGLER:\n"
                "- Brug KUN de eksakte datoer fra kandidatprofilen. Opfind ALDRIG datoer.\n"
                "- Nuværende stilling: slutår = 'nu'.\n"
                "- ESG: specificér Scope-kategori og præcis rolle.\n"
                "- Skriv med korrekte danske bogstaver: æ, ø, å, Æ, Ø, Å.\n"
                "- CO2 skrives altid som 'CO2'.\n"
                "- Brug IKKE **, *, eller andre markdown-symboler — kun ## til sektionshoveder og - til bullets.\n"
                "- Brug ALDRIG '---' som tekstseparator.\n"
                "- Skriv INGEN overskrift/navn øverst — det tilføjes automatisk."
            )
            user_msg = (
                f"Jobkrav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"Kandidatprofil (brug KUN disse datoer og fakta — opfind intet):\n{candidate_summary}"
            )
        else:
            system = (
                f"You are an expert CV writer. Write a strong, job-specific CV for the "
                f"{job_title} position at {job_company}.\n\n"
                "IMPORTANT — RESTRICTED SECTIONS:\n"
                "Write ONLY these sections in this response:\n"
                "  1. ## Professional Profile\n"
                "  2. ## Work Experience\n"
                "  3. ## Selected Achievements (only if the candidate has quantified results)\n\n"
                "Do NOT write: Skills, Systems, Education, Certifications, Languages, Contact.\n"
                "These sections are injected automatically from the database.\n\n"
                "PRECISION CHECK (perform mentally before writing):\n"
                "1. Does the candidate have formal people management — or only functional/project leadership?\n"
                "   NEVER write 'management' without specifying the type.\n"
                "2. Are all amounts, percentages and headcount confirmed in the profile?\n"
                "3. Is the candidate a sole contributor or part of a team?\n\n"
                "PRECISION RULES — TWO ERROR TYPES:\n"
                "Type A — Overstatement (never allowed):\n"
                "- 'drove the implementation' ≠ 'was IT responsible'\n"
                "- 'contributed to X' ≠ 'was responsible for X'\n"
                "- NEVER invent examples, amounts, dates or results\n"
                "Type B — Understatement (also an error):\n"
                "- Experience in the profile MUST be included — never truncate career history\n"
                "- Use hedged language for inferred data ('likely') but include it\n"
                "Confirmed data: always include. Inferred: hedge. Invented: never.\n\n"
                "LEADERSHIP LANGUAGE:\n"
                "- Formal people management: 'people manager with X direct reports'\n"
                "- Functional leadership: 'functional lead / advisor for X'\n"
                "- Project leadership: 'project lead for X'\n"
                "NEVER write just 'management' without specifying the type.\n\n"
                "## Professional Profile\n"
                "4-5 sentences precisely matching the candidate to this job. "
                "Do NOT include the target company name. "
                "Mention core competencies, years of experience, and unique value.\n\n"
                "## Work Experience\n"
                "Reverse chronological. Include ALL roles — never truncate.\n"
                "For EACH role include:\n"
                "  HEADER: [Job Title] – [Company] | [Start year] – [End year or Present]\n"
                "  CONTEXT LINE (1-2 sentences, never a bullet): role scope at a high level.\n"
                "  BULLETS: Current role: 12-15. Secondary: 4-6. Older: 1-2.\n"
                "  Active language: 'managed', 'built', 'drove'. NOT passive.\n\n"
                "## Selected Achievements\n"
                "Pull from ACHIEVEMENTS in candidate profile. 5-8 strongest quantified results. "
                "Omit section if no achievements are documented.\n\n"
                "RULES:\n"
                "- Use ONLY exact dates from the candidate profile. NEVER invent dates.\n"
                "- Current role end = 'present'.\n"
                "- Do NOT use **, * or other markdown symbols.\n"
                "- NEVER output '---' as a separator.\n"
                "- Do NOT write name/header at top — added automatically."
            )
            user_msg = (
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}\n\n"
                f"Candidate Profile (use ONLY these dates and facts — invent nothing):\n{candidate_summary}"
            )

        llm = LiteLLMProvider(self.user_id)
        response = await llm.complete(
            self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            temperature=0.5,
            max_tokens=3000,
        )
        cv_text = response.choices[0].message.content or ""
        ud = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
        usage = AgentUsage(
            prompt_tokens=getattr(ud, "prompt_tokens", 0),
            completion_tokens=getattr(ud, "completion_tokens", 0),
            total_tokens=getattr(ud, "total_tokens", 0),
            model=getattr(response, "model", "unknown"),
        )

        # Assemble structured content — education/skills/systems are hardcoded from DB
        structured = {
            "_structured_cv_v2": True,
            "cv_text": cv_text,
            "education": education_list,
            "competencies": skills_data.get("competencies", []),
            "systems": skills_data.get("systems", []),
            "languages": languages_list,
            "language": language,
        }
        return AgentResult(content=_json.dumps(structured, ensure_ascii=False), usage=usage)

    async def run(self, input_data: dict) -> AgentResult:
        raw_text = input_data.get("raw_text", "")
        if not raw_text.strip():
            return AgentResult(
                content="{}",
                metadata={"parsed_data": {}, "gaps": [], "error": "Ingen tekst at analysere"},
            )

        messages = [
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyser dette CV:\n\n{raw_text[:30000]}"},
        ]

        llm = LiteLLMProvider(self.user_id)
        start = time.time()
        response = await llm.complete(
            self.name,
            messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096,
        )
        latency_ms = int((time.time() - start) * 1000)

        raw_json = response.choices[0].message.content or "{}"
        parsed = self._safe_parse(raw_json)

        resolved_provider, resolved_model = await llm._resolve_model(self.name)
        usage = AgentUsage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            model=resolved_model,
            provider=resolved_provider,
            latency_ms=latency_ms,
        )
        await self.log_usage(usage, operation="cv_parse", used_user_key=llm.used_user_key)

        return AgentResult(
            content=raw_json,
            usage=usage,
            metadata={"parsed_data": parsed, "gaps": parsed.get("gaps", [])},
        )

    async def extract_facts(
        self,
        user_message: str,
        ai_response: str,
        open_gaps: list[str],
    ) -> dict:
        """Ekstraher strukturerede facts efter én udveksling i discovery-interview."""
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Åbne gaps: {', '.join(open_gaps)}\n\n"
                    f"AI spurgte: {ai_response}\n\n"
                    f"Kandidaten svarede: {user_message}"
                ),
            },
        ]

        llm = LiteLLMProvider(self.user_id)
        response = await llm.complete(
            self.name,
            messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1024,
        )

        return self._safe_parse(response.choices[0].message.content or "{}")

    @staticmethod
    def _safe_parse(raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {}

    def _generic_context_from_title(self, title: str, company: str) -> str:
        """Generic context sentence based on job title keywords."""
        _CONTEXTS: list[tuple[str, str]] = [
            ("facility",        f"Central FM-ressource med ansvar for drift og leverandørstyring hos {company}."),
            ("procurement",     f"Indkøbs- og kontraktstyring på tværs af leverandørrelationer hos {company}."),
            ("controller",      f"Controlling, rapportering og økonomianalyse hos {company}."),
            ("business partner",f"Faglig sparringspartner for ledelsen på tværs af funktioner hos {company}."),
            ("esg",             f"ESG-rapportering og bæredygtighedsdata hos {company}."),
            ("leder",           f"Faglig ledelse og koordinering af processer hos {company}."),
            ("koordinator",     f"Koordinering og procesudvikling på tværs af organisationen hos {company}."),
            ("assistent",       f"Administrative og driftsrelaterede opgaver hos {company}."),
            ("elev",            f"Elevuddannelse med rotation på tværs af afdelinger hos {company}."),
            ("portier",         f"Selvstændigt ansvar for fuld driftsstyring i nattimerne hos {company}."),
            ("tjener",          f"Service og gæstehåndtering hos {company}."),
        ]
        title_l = (title or "").lower()
        for keyword, context in _CONTEXTS:
            if keyword in title_l:
                return context
        return f"Bred rolle med ansvar for kerneopgaver inden for området hos {company}."

    def _build_context_line(self, job: dict, snapshot: dict) -> str:
        """Build 1-2 sentence context description for a position. Never returns empty string."""
        desc = (job.get("description") or "").strip()
        if len(desc) > 30:
            # Truncate to roughly 2 sentences
            sentences = re.split(r"(?<=[.!?])\s+", desc)
            return " ".join(sentences[:2])[:220]

        parts: list[str] = []
        if job.get("team_size"):
            parts.append(f"{job['team_size']} medarbejdere")
        if job.get("budget"):
            parts.append(f"budget på {job['budget']}")
        if job.get("locations"):
            parts.append(f"{job['locations']} lokationer")
        if parts:
            return f"Rollen omfattede ansvar for {', '.join(parts)}."

        return self._generic_context_from_title(
            job.get("title") or "", job.get("company") or ""
        )

    async def _build_experience_section(self, snapshot: dict, job_posting: dict) -> list[dict]:
        """
        Build structured experience entries with header, context line, and bullets.
        Returns list of position dicts for pipeline use when constructing candidate_summary.
        """
        positions = snapshot.get("experience") or []
        result: list[dict] = []
        for job in positions:
            start = (job.get("period_start") or "")[:4]
            end = "nu" if job.get("is_current") else (job.get("period_end") or "")[:4]
            header = f"{job.get('title', '')} – {job.get('company', '')} | {start} – {end}".strip(" –")
            context = self._build_context_line(job, snapshot)
            bullets = [a for a in (job.get("achievements") or []) if a]
            if not bullets and job.get("description") and len(job["description"]) > 20:
                bullets = [job["description"][:150]]
            result.append({
                "type": "position",
                "header": header,
                "context": context,
                "bullets": bullets,
            })
        return result

    def _build_structured_education(self, snapshot: dict) -> list[dict]:
        """
        Build structured education list from snapshot.
        Returns list of {degree, institution, years} dicts.
        Used by generate() — result is hardcoded in PDF, never goes through LLM.
        """
        result: list[dict] = []

        # Source 1: cv_educations table (highest priority)
        for e in (snapshot.get("education") or []):
            degree = (e.get("degree") or "").strip()
            institution = (e.get("institution") or "").strip()
            start = (e.get("period_start") or "")[:4]
            end = (e.get("period_end") or "")[:4]
            years = f"{start}–{end}" if start and end else (start or end or "")
            if degree or institution:
                result.append({"degree": degree, "institution": institution, "years": years})

        # Source 2: certifications appear under education in left column
        for c in (snapshot.get("certifications") or []):
            name = (c.get("name") or "").strip()
            issuer = (c.get("issuer") or "").strip()
            year = (c.get("issued_at") or "")[:4]
            if not name:
                continue
            result.append({"degree": name, "institution": issuer, "years": year})

        return result

    async def _build_education_section(self, cv_text: str, snapshot: dict) -> str:
        """Legacy text builder — kept for backward compat. Use _build_structured_education() instead."""
        items = self._build_structured_education(snapshot)
        if not items:
            return "UDDANNELSE:\n  - Uddannelsesoplysninger ikke registreret"
        lines = []
        for e in items:
            entry = f"{e['degree']} – {e['institution']}" if e.get("degree") and e.get("institution") else (e.get("degree") or e.get("institution") or "")
            if e.get("years"):
                entry += f" | {e['years']}"
            if entry.strip(" –|"):
                lines.append(entry)
        return "UDDANNELSE:\n" + "\n".join(f"  - {line}" for line in lines)

    def _infer_skills_from_experience(self, recent_jobs: list) -> list[str]:
        """Infer generic skills from job titles and descriptions."""
        _TITLE_SKILL_MAP: list[tuple[re.Pattern, list[str]]] = [
            (re.compile(r"project|projekt", re.I), ["Projektledelse", "Planlægning", "Interessenthåndtering"]),
            (re.compile(r"finance|finans|økonomi|controller|regnskab", re.I), ["Budgettering", "Finansiel analyse", "Excel"]),
            (re.compile(r"\bhr\b|human resources|personale", re.I), ["Rekruttering", "Arbejdsret", "HR-processer"]),
            (re.compile(r"marketing|kommunikation|content", re.I), ["Kampagnestyring", "Content marketing", "SEO"]),
            (re.compile(r"supply chain|indkøb|procurement|logistik", re.I), ["Indkøbsforhandling", "Leverandørstyring", "Logistik"]),
            (re.compile(r"\bit\b|developer|software|\bdata\b|\btech\b", re.I), ["Analytisk tænkning", "Problemløsning", "Teknisk forståelse"]),
            (re.compile(r"esg|sustainability|bæredygtighed|klima", re.I), ["ESG-rapportering", "Bæredygtighedsstrategi", "CO2-beregning"]),
            (re.compile(r"salg|sales|business.dev|bd\b", re.I), ["Salgsforhandling", "CRM", "Kundeudvikling"]),
            (re.compile(r"leder|manager|direktør|chef|head of", re.I), ["Ledelse", "Strategisk planlægning", "Teamudvikling"]),
        ]
        inferred: set[str] = set()
        for job in recent_jobs:
            combined = f"{job.get('title', '')} {job.get('description', '')}"
            for pattern, skills in _TITLE_SKILL_MAP:
                if pattern.search(combined):
                    inferred.update(skills)
        return list(inferred)

    def _rank_skills_by_relevance(self, skills: list[str], job_keywords: list[str]) -> list[str]:
        """Sort skills by overlap with job description keywords."""
        if not job_keywords:
            return skills
        kw_set = {k.lower() for k in job_keywords}

        def score(skill: str) -> int:
            return sum(1 for word in skill.lower().split() if word in kw_set)

        return sorted(skills, key=score, reverse=True)

    _SYSTEM_KW = {
        "sap", "servicenow", "excel", "power bi", "sharepoint", "erp", "crm",
        "jira", "oracle", "dynamics", "workday", "fm butler", "cmms", "python",
        "sql", "powerpoint", "power query", "microsoft", "m365", "google",
    }

    def _build_structured_skills(self, snapshot: dict, job: dict) -> dict:
        """
        Build structured skills + systems from snapshot.
        Returns {"competencies": [...], "systems": [...]}.
        Used by generate() — result is hardcoded in PDF, never goes through LLM.
        Always returns minimum 8 competencies.
        """
        # Source 1: confirmed skills (non-language, non-technical)
        skills_raw: list[str] = [
            s.get("name", "").strip()
            for s in (snapshot.get("skills") or [])
            if s.get("name") and s.get("category") not in ("language",)
        ]

        # Source 2: systems from cv_systems table
        systems_raw: list[str] = [
            s.get("name", "").strip()
            for s in (snapshot.get("systems") or [])
            if s.get("name")
        ]
        for s in (snapshot.get("skills") or []):
            if s.get("category") == "technical" and s.get("name"):
                nm = s["name"].strip()
                if nm not in systems_raw:
                    systems_raw.append(nm)

        # Source 3: infer from experience titles as fallback
        inferred = self._infer_skills_from_experience(snapshot.get("experience") or [])

        seen_lower: set[str] = set()
        competencies: list[str] = []
        systems: list[str] = []

        for s in skills_raw:
            sl = s.lower()
            if sl not in seen_lower:
                seen_lower.add(sl)
                if any(kw in sl for kw in self._SYSTEM_KW):
                    systems.append(s)
                else:
                    competencies.append(s)

        for s in systems_raw:
            sl = s.lower()
            if sl not in seen_lower:
                seen_lower.add(sl)
                systems.append(s)

        for s in inferred:
            sl = s.lower()
            if sl not in seen_lower:
                seen_lower.add(sl)
                competencies.append(s)

        job_text = " ".join([
            job.get("title", ""),
            job.get("description", ""),
            " ".join(job.get("requirements", [])),
        ])
        job_keywords = re.findall(r"\b\w{4,}\b", job_text.lower())
        competencies = self._rank_skills_by_relevance(competencies, job_keywords)
        systems      = self._rank_skills_by_relevance(systems, job_keywords)

        if len(competencies) < 8:
            fallback_da = [
                "Procesoptimering", "Stakeholder Management", "Projektkoordinering",
                "Rapportering", "Dataanalyse", "Advanced Excel",
                "Tværorganisatorisk samarbejde", "Struktureret arbejdsmetode",
            ]
            for fb in fallback_da:
                if len(competencies) >= 8:
                    break
                if fb.lower() not in seen_lower:
                    competencies.append(fb)
                    seen_lower.add(fb.lower())

        return {"competencies": competencies[:15], "systems": systems[:10]}

    async def _build_skills_section(self, cv_text: str, snapshot: dict, job: dict) -> str:
        """Legacy text builder — kept for backward compat. Use _build_structured_skills() instead."""
        data = self._build_structured_skills(snapshot, job)
        lines: list[str] = []
        if data["competencies"]:
            lines.append("KOMPETENCER: " + ", ".join(data["competencies"]))
        if data["systems"]:
            lines.append("SYSTEMER: " + ", ".join(data["systems"]))
        return "\n".join(lines) if lines else "KOMPETENCER: Kompetencer opdateres løbende"
