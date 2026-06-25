"""
JobDiscoveryAgent — AI-baseret berigelse af job-søgeresultater.

Bruges til at:
- Udtrække strukturerede krav fra jobbeskrivelser
- Normalisere job-type og remote-type
- Prioritere resultater ud fra karrierematch

Kører kun hvis bruger har en API-nøgle konfigureret; ellers passes results igennem uændret.
"""
from __future__ import annotations

import json
import logging

from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider, NoProviderKeyError

logger = logging.getLogger(__name__)

_SYSTEM = """Du er en karriereassistent der analyserer jobopslag.
Givet et liste af job-søgeresultater og en kandidatprofil, returnér en JSON-liste med berigede jobs.

For hvert job:
- Udtræk requirements (maks 8 korte tekster) fra beskrivelsen
- Normaliser job_type: full_time / part_time / contract / freelance / internship
- Normaliser remote_type: remote / hybrid / onsite
- Beregn en kort "ai_summary" på dansk (maks 80 tegn) der opsummerer jobbet

Svar KUN med valid JSON array. Ingen forklaring.
"""


class JobDiscoveryAgent(BaseAgent):
    name = "job_discovery_agent"

    async def run(self, input_data: dict) -> AgentResult:
        results: list[dict] = input_data.get("results", [])
        snapshot_text: str = input_data.get("snapshot_text", "")

        if not results:
            return AgentResult(content="[]", metadata={"enriched": 0})

        # Enrich top 15 — bruger fuld beskrivelse når tilgængelig
        to_enrich = results[:15]

        jobs_json = json.dumps(
            [
                {
                    "title": r["title"],
                    "company": r["company"],
                    # full_description foretrækkes (scraped); fallback til teaser
                    "description": (r.get("full_description") or r.get("description") or "")[:1500],
                }
                for r in to_enrich
            ],
            ensure_ascii=False,
        )

        prompt = (
            f"Kandidatprofil:\n{snapshot_text[:600]}\n\n"
            f"Jobs:\n{jobs_json}"
        )

        try:
            provider = LiteLLMProvider(self.user_id)
            response = await provider.complete(
                agent_name=self.name,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            enriched_list = json.loads(raw)

            # Merge AI enrichments back
            for i, enrichment in enumerate(enriched_list):
                if i < len(results):
                    if enrichment.get("requirements"):
                        results[i]["requirements"] = enrichment["requirements"]
                    if enrichment.get("job_type"):
                        results[i]["job_type"] = enrichment["job_type"]
                    if enrichment.get("remote_type"):
                        results[i]["remote_type"] = enrichment["remote_type"]
                    if enrichment.get("ai_summary"):
                        results[i]["ai_summary"] = enrichment["ai_summary"]

            ud = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
            usage = AgentUsage(
                prompt_tokens=getattr(ud, "prompt_tokens", 0),
                completion_tokens=getattr(ud, "completion_tokens", 0),
                total_tokens=getattr(ud, "total_tokens", 0),
                model=getattr(response, "model", "unknown"),
                provider=getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown"),
            )
            await self.log_usage(usage, operation=self.name, used_user_key=provider.used_user_key)

        except NoProviderKeyError:
            pass  # No key — pass results through without AI enrichment
        except Exception as exc:
            logger.warning("JobDiscoveryAgent enrichment failed: %s", exc)

        return AgentResult(
            content=json.dumps(results, ensure_ascii=False),
            metadata={"enriched": len(to_enrich)},
        )
