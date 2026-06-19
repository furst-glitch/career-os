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
                "NØJAGTIGHEDSREGLER (HÅRD BEGRÆNSNING — aldrig overskrid):\n"
                "- 'drev implementeringen' ≠ 'var IT-ansvarlig'\n"
                "- 'leverede data til audit' ≠ 'deltog i auditgruppe'\n"
                "- 'bidragede til X' ≠ 'var ansvarlig for X'\n"
                "- 'har arbejdet med X' ≠ 'er ekspert i X'\n"
                "Kan en påstand IKKE verificeres i kandidatprofilen: nedtone sproget eller fjern påstanden.\n"
                "Opfind ALDRIG eksempler, beløb, datoer eller resultater.\n\n"
                "LEDERSKABSSPROG:\n"
                "- Formel personaleledelse: skriv 'personaleleder med X direkte rapporteringer'\n"
                "- Faglig ledelse: skriv 'faglig leder / rådgiver for X'\n"
                "- Projektledelse: skriv 'projektleder for X'\n"
                "Skriv ALDRIG bare 'ledelse' uden type.\n\n"
                "KVANTIFICERINGSREGLER:\n"
                "Brug KUN tal kandidaten har bekræftet. Brug 'ca.' eller '+' ved approksimationer.\n"
                "Foretruk: DKK-beløb, antal medarbejdere, antal lokationer, % besparelser, antal år.\n"
                "Rund ALDRIG op. Opfind ALDRIG metrics.\n\n"
                "STRUKTUR (brug præcis disse sektionsnavne med ## foran):\n"
                "## Profil\n"
                "3-4 linjer der matcher kandidaten præcist til netop dette job.\n\n"
                "## Erhvervserfaring\n"
                "Omvendt kronologisk. For HVER stilling:\n"
                "  [Stillingsbetegnelse] – [Virksomhed] | [ÅÅÅÅ-MM] – [ÅÅÅÅ-MM eller Nu]\n"
                "  - Bullet med konkret resultat og verificeret tal/procent\n"
                "  - Bullet med nøgleopgave (maks 6 bullets per stilling)\n\n"
                "## Kompetencer\n"
                "Kun kompetencer der er direkte relevante for dette job.\n\n"
                "## Uddannelse\n"
                "[Uddannelse] – [Institution] | [ÅÅÅÅ-MM] – [ÅÅÅÅ-MM]\n\n"
                "REGLER:\n"
                "- Brug KUN de eksakte datoer fra kandidatprofilen. Opfind ALDRIG datoer.\n"
                "- Hvis en dato mangler i profilen, skriv [årstal ukendt].\n"
                "- Maks 500 ord total (tilpasset én A4-side).\n"
                "- Fremhæv KUN erfaringer og kompetencer der matcher dette specifikke job.\n"
                "- ESG: hvis kandidaten har ESG-erfaring, specificér Scope-kategori og præcis rolle.\n"
                "- Skriv med korrekte danske bogstaver: æ, ø, å, Æ, Ø, Å.\n"
                "- CO2 skrives altid som 'CO2' — aldrig CO₂ eller andet.\n"
                "- Brug IKKE **, *, eller andre markdown-symboler — kun ## til sektionshoveder og - til bullets.\n"
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
                "ACCURACY RULES (HARD CONSTRAINT — never violate):\n"
                "- 'drove the implementation' ≠ 'was IT responsible'\n"
                "- 'provided data for audits' ≠ 'participated in audit group'\n"
                "- 'contributed to X' ≠ 'was responsible for X'\n"
                "- 'has worked with X' ≠ 'is an expert in X'\n"
                "If a claim CANNOT be verified in the candidate profile: downgrade the language or remove it.\n"
                "NEVER invent examples, amounts, dates or results.\n\n"
                "LEADERSHIP LANGUAGE:\n"
                "- Formal people management: write 'people manager with X direct reports'\n"
                "- Functional leadership: write 'functional lead / advisor for X'\n"
                "- Project leadership: write 'project lead for X'\n"
                "NEVER write just 'management' without specifying the type.\n\n"
                "QUANTIFICATION RULES:\n"
                "Only use numbers the candidate has confirmed. Use 'approx.' or '+' for approximations.\n"
                "Prefer: monetary amounts, headcount, number of locations, % savings, years.\n"
                "NEVER round up. NEVER invent metrics.\n\n"
                "STRUCTURE (use exactly these section names with ## prefix):\n"
                "## Profile\n"
                "3-4 lines precisely matching the candidate to this specific job.\n\n"
                "## Work Experience\n"
                "Reverse chronological. For EACH role:\n"
                "  [Job Title] – [Company] | [YYYY-MM] – [YYYY-MM or Present]\n"
                "  - Bullet with concrete verified result and number/percentage\n"
                "  - Bullet with key responsibility (max 6 bullets per role)\n\n"
                "## Skills\n"
                "Only skills directly relevant to this job.\n\n"
                "## Education\n"
                "[Degree] – [Institution] | [YYYY-MM] – [YYYY-MM]\n\n"
                "RULES:\n"
                "- Use ONLY the exact dates from the candidate profile. NEVER invent dates.\n"
                "- If a date is missing from the profile, write [year unknown].\n"
                "- Max 500 words total (fits one A4 page).\n"
                "- Highlight ONLY experience and skills matching this specific job.\n"
                "- ESG: if candidate has ESG experience, specify Scope category and exact role.\n"
                "- Do NOT use **, *, or other markdown symbols — only ## for section headers and - for bullets.\n"
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
            max_tokens=1200,
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
            {"role": "user", "content": f"Analyser dette CV:\n\n{raw_text[:12000]}"},
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
