"""
FactExtractionAgent — structured JSON fact extraction from employment documents.

Extracts typed facts with confidence levels and provenance from:
  - Ansættelseskontrakter (contracts)
  - Overenskomster (union agreements)
  - Lønsedler (payslips)

Each fact carries: type, value, unit, confidence (high/medium/low),
requires_confirmation flag, source_text (exact quote), and source_page.

This agent is the Gateway-native entry point for the Document Intelligence
pipeline. DocumentIntelligenceService calls extract() directly; run() provides
the BaseAgent interface for pipeline compatibility.

Capability routing (via plan_capabilities, migration 00047 + 00050):
  contract  → contract_analysis
  agreement → agreement_analysis
  payslip   → payslip_extraction
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent

logger = logging.getLogger("app.agents.fact_extraction")

_DOC_TYPES = frozenset({"contract", "agreement", "payslip"})

_CAPABILITY_MAP: dict[str, str] = {
    "contract": "contract_analysis",
    "agreement": "agreement_analysis",
    "payslip": "payslip_extraction",
}

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Du er en præcis faktaekstraktor for danske arbejdslivsdokumenter.

REGLER:
1. Udtræk KUN fakta der er EKSPLICIT nævnt i teksten — gæt eller beregn aldrig.
2. Angiv det PRÆCISE tekstudsnit (source_text) der understøtter faktummet.
   Maksimum 200 tegn — citér det mest relevante udsnit.
3. Confidence:
   - high:   Fakta er eksplicit og utvetydig (konkrete tal, datoer, specifikke vilkår).
   - medium: Fakta er klart angivet men kræver enkel kontekstuel forståelse.
   - low:    Fakta er tvetydig, modstridende, indirekte, eller kræver fortolkning.
4. requires_confirmation=true ALTID når confidence=low.
5. source_page: sidetal i dokumentet (0 hvis ukendt).
6. Returner ALTID valid JSON. Ingen markdown. Ingen forklaring udenfor JSON.
7. Udelad fakta der ikke er nævnt i teksten — returner aldrig null-værdier.

OUTPUT FORMAT (ingen anden tekst):
{
  "facts": [
    {
      "fact_type": "snake_case_navn",
      "value": "den udtrukne værdi",
      "unit": "DKK|months|pct|hours|days|text|YYYY-MM|YYYY-MM-DD|per_hour",
      "confidence": "high|medium|low",
      "requires_confirmation": false,
      "source_text": "eksakt citat fra dokumentet maks 200 tegn",
      "source_page": 1
    }
  ],
  "document_summary": "Én sætning om dokumentet.",
  "extraction_quality": "high|medium|low"
}
"""

_CONTRACT_FACTS = """\
UDTRÆK disse faktaer (udelad dem der ikke fremgår af teksten):
- monthly_salary: Månedlig grundløn
- pension_pct_total: Samlet pensionsprocent
- pension_pct_employee: Medarbejderens pensionsandel
- pension_pct_employer: Arbejdsgiverens pensionsandel
- notice_period_employee_months: Opsigelsesvarsel fra medarbejderens side (måneder)
- notice_period_employer_months: Opsigelsesvarsel fra arbejdsgiverens side (måneder)
- vacation_days: Feriedage pr. år
- trial_period_months: Prøvetid (måneder; 0 = ingen prøvetid)
- non_compete_months: Konkurrenceklausul varighed (måneder; 0 = ingen klausul)
- confidentiality_clause: Fortrolighedsklausul (ja/nej)
- bonus_structure: Bonus eller variabel løn (kort beskrivelse)
- working_hours_per_week: Ugentlig arbejdstid (timer)
- employer_name: Arbejdsgiver (firmanavn)
- job_title: Stillingsbetegnelse
- contract_start_date: Ansættelsesstartdato
"""

_AGREEMENT_FACTS = """\
UDTRÆK disse faktaer (udelad dem der ikke fremgår af teksten):
- minimum_wage: Minimumssats (angiv unit som DKK, per_hour, eller monthly)
- overtime_rate_pct: Overtidsbetaling som procent af normalløn
- union_name: Fagforbundets navn
- employer_organization: Arbejdsgiverorganisationens navn
- agreement_name: Overenskomstens fulde navn
- pension_pct_total: Samlet pensionsprocent
- pension_pct_employee: Medarbejderens andel
- pension_pct_employer: Arbejdsgiverens andel
- vacation_days: Feriedage pr. år
- working_hours_per_week: Normal ugentlig arbejdstid (timer)
- seniority_pay_rules: Anciennitetsregler (kort beskrivelse)
"""

_PAYSLIP_FACTS = """\
UDTRÆK disse faktaer (udelad dem der ikke fremgår af teksten):
- gross_salary: Bruttoløn (DKK)
- net_salary: Nettoløn (DKK)
- pension_contribution_employee: Eget pensionsbidrag (DKK)
- pension_contribution_employer: Arbejdsgiverens pensionsbidrag (DKK)
- tax_amount: Indeholdt skat (DKK)
- am_bidrag: AM-bidrag (DKK)
- period_month_year: Lønperiode (YYYY-MM)
- employer_name: Arbejdsgiver (firmanavn)
"""

_FACT_SPECS: dict[str, str] = {
    "contract": _CONTRACT_FACTS,
    "agreement": _AGREEMENT_FACTS,
    "payslip": _PAYSLIP_FACTS,
}

_VALID_CONFIDENCE = frozenset({"high", "medium", "low"})
_VALID_QUALITY = frozenset({"high", "medium", "low"})
_SOURCE_TEXT_MAX = 200


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class ExtractedFact:
    fact_type: str
    value: str
    unit: str
    confidence: str          # high | medium | low
    requires_confirmation: bool
    source_text: str         # exact quote, max _SOURCE_TEXT_MAX chars
    source_page: int         # 0 = unknown


@dataclass
class ExtractionResult:
    facts: list[ExtractedFact] = field(default_factory=list)
    document_summary: str = ""
    extraction_quality: str = "low"
    raw_response: str = ""
    error: str | None = None


# ── Agent ─────────────────────────────────────────────────────────────────────


class FactExtractionAgent(BaseAgent):
    """
    Extracts structured facts from employment documents via the AI Gateway.

    Call extract(text, doc_type) directly from DocumentIntelligenceService.
    run() provides BaseAgent compatibility.
    """

    name = "fact_extraction_agent"
    capability = "contract_analysis"
    capabilities = {
        "contract": "contract_analysis",
        "agreement": "agreement_analysis",
        "payslip": "payslip_extraction",
    }

    async def run(self, input_data: dict) -> AgentResult:
        doc_type = input_data.get("doc_type", "contract")
        text = input_data.get("text", "")
        result = await self.extract(text, doc_type)
        return AgentResult(
            content=result.raw_response or (result.error or ""),
            metadata={
                "facts_count": len(result.facts),
                "extraction_quality": result.extraction_quality,
                "error": result.error,
            },
        )

    async def extract(self, text: str, doc_type: str) -> ExtractionResult:
        """
        Extract structured facts from document text.

        Returns ExtractionResult — always safe to call; errors are embedded
        in result.error and never raised.
        """
        if doc_type not in _DOC_TYPES:
            return ExtractionResult(error=f"unsupported_doc_type:{doc_type}")

        fact_spec = _FACT_SPECS[doc_type]
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT + "\n" + fact_spec},
            {"role": "user", "content": f"Dokument til analyse:\n\n{text[:12000]}"},
        ]
        capability = self.capabilities[doc_type]

        try:
            response = await self._call_gateway(
                capability,
                messages,
                temperature=0.1,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            raw = response.content or "{}"
        except Exception as exc:
            logger.error("fact_extraction_gateway_error doc_type=%s error=%s", doc_type, exc)
            return ExtractionResult(error=f"gateway_error:{exc}")

        return self._parse_response(raw)

    @staticmethod
    def _parse_response(raw: str) -> ExtractionResult:
        """Parse raw JSON into ExtractionResult. Never raises."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("fact_extraction_json_parse_error error=%s", exc)
            return ExtractionResult(raw_response=raw, error="json_parse_error")

        facts: list[ExtractedFact] = []
        for item in data.get("facts", []):
            try:
                raw_confidence = item.get("confidence", "low")
                confidence = raw_confidence if raw_confidence in _VALID_CONFIDENCE else "low"
                facts.append(ExtractedFact(
                    fact_type=str(item.get("fact_type", "")).strip(),
                    value=str(item.get("value", "")).strip(),
                    unit=str(item.get("unit", "")).strip(),
                    confidence=confidence,
                    requires_confirmation=bool(item.get("requires_confirmation", confidence == "low")),
                    source_text=str(item.get("source_text", "")).strip()[:_SOURCE_TEXT_MAX],
                    source_page=max(0, int(item.get("source_page") or 0)),
                ))
            except (TypeError, ValueError) as exc:
                logger.debug("fact_item_parse_skip item=%s error=%s", item, exc)

        raw_quality = data.get("extraction_quality", "low")
        quality = raw_quality if raw_quality in _VALID_QUALITY else "low"

        return ExtractionResult(
            facts=facts,
            document_summary=str(data.get("document_summary", "")).strip()[:300],
            extraction_quality=quality,
            raw_response=raw,
        )
