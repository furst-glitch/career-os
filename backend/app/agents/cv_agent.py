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

        input_data:
          job_title, job_company, job_description, job_requirements
          candidate_summary, language, writing_style, focus_areas
        """
        language = input_data.get("language", "da")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:3000]
        requirements = input_data.get("job_requirements", [])
        candidate_summary = input_data.get("candidate_summary", "")
        req_text = "\n".join(f"- {r}" for r in requirements[:15]) if requirements else "Ikke angivet"

        if language == "da":
            system = (
                f"Du er en ekspert CV-skribent. Skriv et stærkt, jobspecifikt CV til stillingen "
                f"{job_title} hos {job_company}.\n\n"
                "PRÆCISIONSTJEK (gennemfør mentalt inden du skriver):\n"
                "1. Har kandidaten formel personaleledelse (direkte rapporteringer) — eller kun faglig/projektledelse?\n"
                "   Skriv ALDRIG 'ledelse' uden at specificere typen.\n"
                "2. Er kandidaten systemejer/ansvarlig — eller power user/implementerer?\n"
                "3. Er alle DKK-beløb, procenter og headcount bekræftet i profilen?\n"
                "4. Er kandidaten enebidragsyder eller del af et team?\n\n"
                "PRÆCISIONSREGLER — TO FEJLTYPER (begge skader kandidaten):\n"
                "Type A — Overstatement (aldrig tilladt):\n"
                "- 'drev implementeringen' ≠ 'var IT-ansvarlig'\n"
                "- 'leverede data til audit' ≠ 'deltog i auditgruppe'\n"
                "- 'bidragede til X' ≠ 'var ansvarlig for X'\n"
                "- 'har arbejdet med X' ≠ 'er ekspert i X'\n"
                "- Opfind ALDRIG eksempler, beløb, datoer eller resultater\n"
                "Type B — Understatement (også en fejl):\n"
                "- Bekræftede kompetencer SKAL med — at udelade data fra profilen er en fejl\n"
                "- Erfaringer og uddannelse i profilen SKAL inkluderes\n"
                "- Brug hæmmet sprog for afledt data ('sandsynligvis', 'formentlig') men inkludér det\n"
                "Bekræftet data: inkludér altid. Afledt data: hæmmet sprog. Opfundet: aldrig.\n\n"
                "LEDERSKABSSPROG:\n"
                "- Formel personaleledelse: skriv 'personaleleder med X direkte rapporteringer'\n"
                "- Faglig ledelse: skriv 'faglig leder / rådgiver for X'\n"
                "- Projektledelse: skriv 'projektleder for X'\n"
                "Skriv ALDRIG bare 'ledelse' uden type.\n\n"
                "KVANTIFICERINGSREGLER:\n"
                "Brug KUN tal kandidaten har bekræftet. Brug 'ca.' eller '+' ved approksimationer.\n"
                "Foretruk: DKK-beløb, antal medarbejdere, antal lokationer, % besparelser, antal år.\n"
                "Rund ALDRIG op. Opfind ALDRIG metrics.\n\n"
                "FULDSTÆNDIGHEDSMANDAT:\n"
                "CV'et skal føles komplet og detaljeret — aldrig minimalt.\n"
                "Primær/nuværende rolle: minimum 12-15 bullets\n"
                "Sekundære roller (seneste 2-3 relevante): minimum 4-6 bullets\n"
                "Ældre roller: minimum 1-2 bullets — aldrig udelad\n\n"
                "OBLIGATORISKE SEKTIONER — MASTER CV 2.0 (9 sektioner, altid alle til stede):\n\n"
                "STRUKTUR (brug præcis disse sektionsnavne med ## foran, i denne rækkefølge):\n\n"
                "## Professionel profil\n"
                "4-5 sætninger der præcist matcher kandidaten til netop dette job. "
                "Inkludér IKKE målvirksomhedens navn — profilteksten skal være portabel. "
                "Nævn kernekompetencer, årstal erfaring, og hvad kandidaten bringer som unik værdi.\n\n"
                "## Erhvervserfaring\n"
                "Omvendt kronologisk. Inkludér ALLE stillinger — afkort aldrig karrierehistorik.\n"
                "For HVER stilling SKAL alle tre elementer være til stede i denne rækkefølge:\n\n"
                "ELEMENT 1 — OVERSKRIFT (altid):\n"
                "  [Stillingsbetegnelse] – [Virksomhed] | [Startår] – [Slutår eller nu]\n"
                "  Eksempel: 'Business Partner – SWECO Danmark | 2018 – nu'\n\n"
                "ELEMENT 2 — KONTEKSTLINJE (altid, 1-2 sætninger — IKKE et bullet):\n"
                "  Hvad rollen indebar på et overordnet niveau, INDEN bullets læses.\n"
                "  Inkludér scope-indikatorer hvis kendte: antal lokationer, medarbejdere, budget, teamstørrelse.\n"
                "  Nutid for nuværende stilling, datid for tidligere.\n"
                "  Gode eksempler:\n"
                "  'Central FM-ressource på tværs af 20+ lokationer og ~2.000 medarbejdere med driftsbudgetter på 120+ mio. kr.'\n"
                "  'Faglig leder med ansvar for driftsøkonomien i lovreguleret forsyningsmiljø under fusion af to organisationer.'\n"
                "  'Administrativt og kundevendt arbejde i kommunal forsyningsvirksomhed.'\n"
                "  Dårlige eksempler (for vage):\n"
                "  'Arbejdede med procurement og FM.' / 'Varetog administrative opgaver.'\n"
                "  Spring ALDRIG Element 2 over — skriv minimum én sætning baseret på tilgængelige data.\n\n"
                "ELEMENT 3 — BULLETS:\n"
                "  Primær/nuværende rolle: 12-15 bullets\n"
                "  Sekundære roller: 4-6 bullets\n"
                "  Ældre roller: 1-2 bullets\n"
                "  Konkrete resultater, ansvar og bidrag. Minimum én hel sætning per bullet.\n"
                "  Mix af: hvad du gjorde + hvad det resulterede i.\n"
                "  Aktivt sprog: 'styrede', 'opbyggede', 'drev', 'designede'\n"
                "  IKKE passivt: 'understøttede', 'bidragede til at understøtte'\n\n"
                "Skriv ALDRIG bullets uden en kontekstlinje over dem.\n\n"
                "## Udvalgte resultater\n"
                "Hent fra PRÆSTATIONER-sektionen i kandidatprofilen. "
                "Vælg de 5-8 stærkeste og mest jobspecifikke kvantificerede resultater. "
                "Format: '- [Resultat med metric]'. Inkludér DKK-besparelser, % forbedringer, headcount, tidsbesparelser. "
                "Udelad IKKE denne sektion hvis PRÆSTATIONER findes i profilen.\n\n"
                "## Kompetencer\n"
                "Hent KUN fra KOMPETENCER-sektionen i kandidatprofilen (ikke fra erfaringstekster). "
                "Inkludér faglige domænekompetencer. Minimum 10 punkter. "
                "Format: kommasepareret liste eller bullets. "
                "Fremhæv dem der matcher dette job.\n\n"
                "## Systemer\n"
                "Hent KUN fra SYSTEMER-sektionen i kandidatprofilen (ikke fra erfaringstekster). "
                "List alle IT-systemer, platforme og teknologier kandidaten behersker. "
                "Angiv gerne kategori: ERP / CAFM / Office / BI / Dev. "
                "Udelad ALDRIG systemer der er bekræftet i profilen.\n\n"
                "## Uddannelse\n"
                "[Uddannelse] – [Institution] | [ÅÅÅÅ] – [ÅÅÅÅ]\n"
                "Denne sektion SKAL ALTID med. Hent fra UDDANNELSE-sektionen i profilen. "
                "Ingen uddannelse fundet: skriv '[Uddannelse ikke angivet]' — udelad aldrig sektionen.\n\n"
                "## Certifikater\n"
                "Hent fra CERTIFIKATER-sektionen i kandidatprofilen. "
                "Inkludér AMU-kurser, lederuddannelser, faglige certifikater, frivillige uddannelser og licensforløb. "
                "Format: '- [Certifikat/kursus] – [Udbyder] | [År]'. "
                "Udelad ALDRIG certifikater der er bekræftet i profilen.\n\n"
                "## Sprog\n"
                "Hent fra SPROG-sektionen i kandidatprofilen. "
                "Angiv alle sprog med niveau (modersmål, flydende, arbejdsniveau).\n\n"
                "FULDSTÆNDIGHEDSREGLER (obligatoriske — alle otte):\n"
                "1. FULD KARRIEREHISTORIK: Inkludér ALLE stillinger fra profilen — afkort aldrig.\n"
                "   Ældre stillinger: 1-2 bullets er nok, men stillingen SKAL med.\n"
                "2. UDDANNELSE ALTID: Hent fra UDDANNELSE i snapshot. Skriv aldrig 'ikke angivet'\n"
                "   hvis uddannelse findes nogen steder i systemet.\n"
                "3. RESULTATER SEPARAT: Kvantificerede præstationer hører i 'Udvalgte resultater' —\n"
                "   ikke kun som bullets i erfaringsteksten.\n"
                "4. SYSTEMER SEPARAT: Systemer og IT-platforme hører i 'Systemer' —\n"
                "   ikke kun gemt i bullets under erfaringer.\n"
                "5. AKTIVT SPROG:\n"
                "   FORKERT: 'understøttede styring af partnerskaber'\n"
                "   RIGTIGT:  'styrede strategiske partnerskaber'\n"
                "   FORKERT: 'bidragede til besparelser'\n"
                "   RIGTIGT:  'reducerede omkostninger med 5+ mio. kr.'\n"
                "   Brug altid det stærkeste aktive verbum der kan verificeres.\n"
                "6. INGEN DUBLETTER: Kompetencer og systemer må ikke gentages ordret i erfaringsbullets.\n"
                "7. KONTAKT ÉN GANG: Navn og kontaktinfo vises kun i headeren — ingen KONTAKT-sektion i teksten.\n"
                "8. LINKEDIN-URL: Vis altid renset URL uden https://www. præfiks.\n\n"
                "REGLER:\n"
                "- Brug KUN de eksakte datoer fra kandidatprofilen. Opfind ALDRIG datoer.\n"
                "- Nuværende arbejdsgiver: startår SKAL komme fra profilen — tjek snapshot.\n"
                "- Hvis startår er ukendt: brug 'ca. [estimeret år]'. Skriv ALDRIG '[årstal ukendt]'.\n"
                "- Hvis slutår er nu: skriv 'nu' (dansk) eller 'present' (engelsk).\n"
                "- Tilpas til kandidatens erfaringsbredde — afkort ALDRIG karrierehistorik.\n"
                "- Fremhæv erfaringer og kompetencer der matcher dette specifikke job.\n"
                "- ESG: hvis kandidaten har ESG-erfaring, specificér Scope-kategori og præcis rolle.\n"
                "- Skriv med korrekte danske bogstaver: æ, ø, å, Æ, Ø, Å.\n"
                "- CO2 skrives altid som 'CO2' — aldrig CO₂ eller andet.\n"
                "- Brug IKKE **, *, eller andre markdown-symboler — kun ## til sektionshoveder og - til bullets.\n"
                "- Brug ALDRIG '---' som tekstseparator.\n"
                "- Skriv INGEN overskrift/navn øverst — det tilføjes automatisk fra profilen."
            )
            user_msg = (
                f"Jobkrav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"Kandidatprofil (brug KUN disse datoer og fakta — opfind intet):\n{candidate_summary}"
            )
        else:
            system = (
                f"You are an expert CV writer. Write a strong, job-specific CV for the "
                f"{job_title} position at {job_company}.\n\n"
                "PRECISION CHECK (perform mentally before writing):\n"
                "1. Does the candidate have formal people management (direct reports) — or only functional/project leadership?\n"
                "   NEVER write 'management' without specifying the type.\n"
                "2. Was the candidate system owner/responsible — or power user/implementer?\n"
                "3. Are all amounts, percentages and headcount confirmed in the profile?\n"
                "4. Is the candidate a sole contributor or part of a team?\n\n"
                "PRECISION RULES — TWO ERROR TYPES (both harm the candidate):\n"
                "Type A — Overstatement (never allowed):\n"
                "- 'drove the implementation' ≠ 'was IT responsible'\n"
                "- 'provided data for audits' ≠ 'participated in audit group'\n"
                "- 'contributed to X' ≠ 'was responsible for X'\n"
                "- 'has worked with X' ≠ 'is an expert in X'\n"
                "- NEVER invent examples, amounts, dates or results\n"
                "Type B — Understatement (also an error):\n"
                "- Confirmed competencies MUST be included — omitting profile data is an error\n"
                "- Experience and education in the profile MUST be included\n"
                "- Use hedged language for inferred data ('likely', 'presumably') but include it\n"
                "Confirmed data: always include. Inferred data: hedge language. Invented: never.\n\n"
                "LEADERSHIP LANGUAGE:\n"
                "- Formal people management: write 'people manager with X direct reports'\n"
                "- Functional leadership: write 'functional lead / advisor for X'\n"
                "- Project leadership: write 'project lead for X'\n"
                "NEVER write just 'management' without specifying the type.\n\n"
                "QUANTIFICATION RULES:\n"
                "Only use numbers the candidate has confirmed. Use 'approx.' or '+' for approximations.\n"
                "Prefer: monetary amounts, headcount, number of locations, % savings, years.\n"
                "NEVER round up. NEVER invent metrics.\n\n"
                "COMPLETENESS MANDATE:\n"
                "The CV must feel complete and detailed, not minimal.\n"
                "Primary/current role: minimum 12-15 bullets\n"
                "Secondary roles (recent 2-3 relevant): minimum 4-6 bullets\n"
                "Older roles: minimum 1-2 bullets — never omit\n\n"
                "MANDATORY SECTIONS — MASTER CV 2.0 (9 sections, all always present):\n\n"
                "STRUCTURE (use exactly these section names with ## prefix, in this order):\n\n"
                "## Professional Profile\n"
                "4-5 sentences precisely matching the candidate to this specific job. "
                "Do NOT include the target company name — the profile text must be portable. "
                "Mention core competencies, years of experience, and unique value brought.\n\n"
                "## Work Experience\n"
                "Reverse chronological. Include ALL roles — never truncate career history.\n"
                "For EACH role ALL THREE elements MUST be present in this order:\n\n"
                "ELEMENT 1 — JOB HEADER (always):\n"
                "  [Job Title] – [Company] | [Start year] – [End year or Present]\n"
                "  Example: 'Business Partner – SWECO Denmark | 2018 – Present'\n\n"
                "ELEMENT 2 — CONTEXT LINE (always, 1-2 sentences — NOT a bullet):\n"
                "  What the role involved at a high level, BEFORE the reader sees the bullets.\n"
                "  Include scope indicators where known: locations, headcount, budget, team size.\n"
                "  Present tense for current role, past tense for previous.\n"
                "  Good examples:\n"
                "  'Central FM resource across 20+ locations and ~2,000 employees with operating budgets of 120+ million DKK.'\n"
                "  'Functional lead responsible for operational economics in a regulated utility environment during merger.'\n"
                "  'Administrative and customer-facing work in a municipal utility company.'\n"
                "  Bad examples (too vague):\n"
                "  'Worked with procurement and FM.' / 'Handled administrative tasks.'\n"
                "  NEVER skip Element 2 — always write at least one sentence based on available data.\n\n"
                "ELEMENT 3 — BULLETS:\n"
                "  Primary/current role: 12-15 bullets\n"
                "  Secondary roles: 4-6 bullets\n"
                "  Older roles: 1-2 bullets\n"
                "  Specific achievements, responsibilities and contributions. One complete sentence each.\n"
                "  Mix of: what you did + what it resulted in.\n"
                "  Active language: 'managed', 'built', 'drove', 'designed'\n"
                "  NOT passive: 'supported', 'contributed to supporting'\n\n"
                "NEVER output bullets without a context line above them.\n\n"
                "## Selected Achievements\n"
                "Pull from the ACHIEVEMENTS section of the candidate profile. "
                "Select the 5-8 strongest and most job-relevant quantified results. "
                "Format: '- [Achievement with metric]'. Include DKK savings, % improvements, headcount, time savings. "
                "Do NOT omit this section if ACHIEVEMENTS exist in the profile.\n\n"
                "## Skills\n"
                "Pull ONLY from the SKILLS section of the candidate profile (not from experience text). "
                "Include professional domain competencies. Minimum 10 items. "
                "Format: comma-separated list or bullets. "
                "Highlight those matching this job.\n\n"
                "## Systems\n"
                "Pull ONLY from the SYSTEMS section of the candidate profile (not from experience text). "
                "List all IT systems, platforms and technologies the candidate masters. "
                "Include category where relevant: ERP / CAFM / Office / BI / Dev. "
                "NEVER omit systems confirmed in the profile.\n\n"
                "## Education\n"
                "[Degree] – [Institution] | [YYYY] – [YYYY]\n"
                "This section MUST always be included. Pull from the EDUCATION section in profile. "
                "No education found: write '[Education not provided]' — never omit this section.\n\n"
                "## Certifications\n"
                "Pull from the CERTIFICATIONS section of the candidate profile. "
                "Include AMU courses, leadership training, professional certifications, volunteer training and licences. "
                "Format: '- [Certificate/course] – [Provider] | [Year]'. "
                "NEVER omit certifications confirmed in the profile.\n\n"
                "## Languages\n"
                "Pull from the LANGUAGES section of the candidate profile. "
                "List all languages with level (native, fluent, working level).\n\n"
                "COMPLETENESS RULES (mandatory — all eight):\n"
                "1. FULL CAREER HISTORY: Include ALL positions from the profile — never truncate.\n"
                "   Older roles: 1-2 bullets suffice, but the role MUST appear.\n"
                "2. EDUCATION ALWAYS: Pull from EDUCATION in snapshot. Never write 'not provided'\n"
                "   if education exists anywhere in the system.\n"
                "3. ACHIEVEMENTS SEPARATE: Quantified results belong in 'Selected Achievements' —\n"
                "   not only as bullets within experience text.\n"
                "4. SYSTEMS SEPARATE: Systems and IT platforms belong in 'Systems' —\n"
                "   not only buried in experience bullets.\n"
                "5. ACTIVE LANGUAGE:\n"
                "   WRONG: 'supported management of partnerships'\n"
                "   RIGHT:  'managed strategic partnerships'\n"
                "   WRONG: 'contributed to savings'\n"
                "   RIGHT:  'reduced costs by 5+ million DKK'\n"
                "   Always use the strongest active verb that can be verified.\n"
                "6. NO DUPLICATES: Skills and systems must not be repeated verbatim in experience bullets.\n"
                "7. CONTACT ONCE: Name and contact appear in the header only — no Contact section in body text.\n"
                "8. LINKEDIN URL: Always display cleaned URL without https://www. prefix.\n\n"
                "RULES:\n"
                "- Use ONLY the exact dates from the candidate profile. NEVER invent dates.\n"
                "- Current employer start year MUST come from profile — check snapshot.\n"
                "- If start year unknown: use 'approx. [estimated year]'. NEVER write '[year unknown]'.\n"
                "- If end year is current: write 'present'.\n"
                "- Adapt to the candidate's career breadth — NEVER truncate career history.\n"
                "- Highlight experience and skills matching this specific job.\n"
                "- ESG: if candidate has ESG experience, specify Scope category and exact role.\n"
                "- Do NOT use **, *, or other markdown symbols — only ## for section headers and - for bullets.\n"
                "- NEVER output '---' as a text separator.\n"
                "- Do NOT write a name/header at the top — it is added automatically from the profile."
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
            max_tokens=3500,
        )
        content = response.choices[0].message.content or ""
        ud = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
        usage = AgentUsage(
            prompt_tokens=getattr(ud, "prompt_tokens", 0),
            completion_tokens=getattr(ud, "completion_tokens", 0),
            total_tokens=getattr(ud, "total_tokens", 0),
            model=getattr(response, "model", "unknown"),
        )
        return AgentResult(content=content, usage=usage)

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

    async def _build_education_section(self, cv_text: str, snapshot: dict) -> str:
        """Build education string from snapshot (priority) or cv_text fallback."""
        edu = snapshot.get("education") or []
        if edu:
            parts = []
            for e in edu:
                degree = e.get("degree") or ""
                institution = e.get("institution") or ""
                start = (e.get("period_start") or "")[:4]
                end = (e.get("period_end") or "")[:4]
                period = f"{start}-{end}" if start and end else (start or end or "")
                entry = f"{degree} - {institution}" if degree and institution else (degree or institution)
                if period:
                    entry += f" | {period}"
                if entry.strip(" -|"):
                    parts.append(entry)
            if parts:
                return "UDDANNELSE:\n" + "\n".join(f"  - {p}" for p in parts)

        edu_match = re.search(
            r"(?:uddannelse|education|bachelor|master|kandidat|diplom|cand\.|hd |hd\.|mba|ph\.?d)"
            r"[^\n]*(?:\n[ \t]*[^\n#\-]{10,100}){0,3}",
            cv_text,
            re.IGNORECASE,
        )
        if edu_match:
            return f"UDDANNELSE (fra CV-tekst):\n  {edu_match.group(0)[:250].strip()}"

        return "UDDANNELSE: [Ikke oplyst]"

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

    async def _build_skills_section(self, cv_text: str, snapshot: dict, job: dict) -> str:
        """Build ranked skills list from snapshot + inferred from experience."""
        skills: list[str] = [
            s.get("name", "").strip()
            for s in (snapshot.get("skills") or [])
            if s.get("name")
        ]
        inferred = self._infer_skills_from_experience(snapshot.get("experience") or [])
        seen_lower = {s.lower() for s in skills}
        for s in inferred:
            if s.lower() not in seen_lower:
                skills.append(s)
                seen_lower.add(s.lower())

        job_text = " ".join([
            job.get("title", ""),
            job.get("description", ""),
            " ".join(job.get("requirements", [])),
        ])
        job_keywords = re.findall(r"\b\w{4,}\b", job_text.lower())
        ranked = self._rank_skills_by_relevance(skills, job_keywords)
        if not ranked:
            return ""
        return "KOMPETENCER: " + ", ".join(ranked[:15])
