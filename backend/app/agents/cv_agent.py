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
  "experience_additions": [
    { "company": string, "new_achievements": string[], "new_technologies": string[] }
  ],
  "gaps_resolved": string[]
}

Regler:
- Inkludér KUN eksplicit nævnte facts fra dette svar
- Brug tomme arrays for sektioner uden nye facts
- gaps_resolved: beskrivelser af gaps der nu er tilstrækkeligt besvaret
- Returner KUN valid JSON"""


class CVAgent(BaseAgent):
    name = "cv_agent"

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
