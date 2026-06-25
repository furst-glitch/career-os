from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

SYSTEM = """Du er en ekspert i danske overenskomster og fagforeningsrettigheder.
Du analyserer overenskomster og forklarer rettigheder på et forståeligt sprog.
Svar altid på dansk. Vær konkret og praktisk.

VIGTIGT: Din analyse er vejledende og udgør ikke juridisk rådgivning.
Anfør altid: "Dette er vejledende analyse og ikke juridisk rådgivning."

Kend de vigtigste overenskomster:
- DI/HK, DI/3F, Finansforbundet, Dansk Erhverv/HK
- Industriens Funktionæroverenskomst, IDA, Dansk Metal
- AC-overenskomsten, Kommunernes Landsforening
- Djøf-overenskomsten"""


class AgreementAnalysisAgent(BaseAgent):
    name = "agreement_analysis_agent"

    async def run(self, input_data: dict) -> AgentResult:
        contract_text = input_data.get("contract_text", "")
        agreement_text = input_data.get("agreement_text", "")
        mode = input_data.get("mode", "identify")  # 'identify' or 'analyze'
        file_name = input_data.get("file_name", "dokument")

        if mode == "identify":
            user_msg = f"""Analyser denne ansættelseskontrakt og identificer den relevante overenskomst:

KONTRAKT ({file_name}):
{contract_text[:6000]}

Giv:

## Overenskomstidentifikation
Hvilken overenskomst dækker sandsynligvis dette ansættelsesforhold?
- Overenskomstens navn
- Arbejdsgiverorganisation
- Fagforening
- Branche

## Confidence-score
Angiv din sikkerhed som procent (0-100%) og begrund dit svar.
Angiv hvilke elementer i kontrakten der peger på denne overenskomst.

## Vigtige rettigheder under denne overenskomst
Beskriv de mest centrale rettigheder:
- Løntrin og regulering
- Pension
- Arbejdstid og overarbejde
- Ferie og fri
- Opsigelse

## Anbefalinger
Hvad bør medarbejderen kende til under denne overenskomst?
Hvad bør de kontakte fagforeningen om?

---
Dette er vejledende analyse og ikke juridisk rådgivning."""
        else:
            doc_ctx = f"\nOVEERENSKOMST:\n{agreement_text[:6000]}" if agreement_text else ""
            user_msg = f"""Analyser denne overenskomst grundigt:

DOKUMENT ({file_name}):
{contract_text[:6000]}{doc_ctx}

Giv en komplet analyse:

## Executive Summary
Overenskomstens navn, parter og anvendelsesområde (3-5 sætninger).

## Løntrin og anciennitet
Lønskala, anciennitetsregler, hvornår stiger lønnen automatisk?

## Lønregulering
Hvornår og hvordan reguleres lønnen? (overenskomstfornyelse, procenttillæg)

## Pension
Pensionssatser og regler.

## Tillæg
Hvilke tillæg har medarbejderen ret til?
(skiftetillæg, weekend, overarbejde, ubekvemt, etc.)

## Arbejdstid
Normal ugentlig arbejdstid, fleksibilitet, overtidsregler.

## Ferie og fri
Ferieret, særlige fridage, feriepenge, SH-betaling.

## Opsigelse
Varsler afhængigt af anciennitet og årsag.

## Potentielle tillæg der overses
Tillæg som mange medarbejdere ikke er klar over de har ret til.

## Vigtige forhold at kende
3-5 praktiske pointer der er særligt vigtige for medarbejderen.

---
Dette er vejledende analyse og ikke juridisk rådgivning."""

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.3,
            max_tokens=2200,
        )
        content = resp.choices[0].message.content or ""
        usage = AgentUsage(
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            model=getattr(resp, "model", "unknown"),
            provider=getattr(resp, "_hidden_params", {}).get("custom_llm_provider", "unknown"),
        )
        await self.log_usage(usage, operation=self.name, used_user_key=llm.used_user_key)
        return AgentResult(content=content, usage=usage)
