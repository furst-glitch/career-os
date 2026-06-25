from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

SYSTEM = """Du er en ekspert i danske lønsedler, lønberegning og overenskomstret.
Du kontrollerer lønsedler og identificerer potentielle fejl og manglende betalinger.
Svar altid på dansk. Vær konkret og struktureret.

VIGTIGT:
- Anfør altid: "Dette er vejledende analyse og ikke juridisk rådgivning."
- Ved potentielle fejl: anbefal altid at kontakte fagforening eller lønkontor.
- Undgå at konkludere med 100% sikkerhed — vurder altid sandsynlighed."""


class PayslipCheckAgent(BaseAgent):
    name = "payslip_check_agent"

    async def run(self, input_data: dict) -> AgentResult:
        payslip_text = input_data.get("payslip_text", "")
        contract_text = input_data.get("contract_text", "")
        agreement_text = input_data.get("agreement_text", "")

        ctx_parts = [f"LØNSEDDEL:\n{payslip_text[:4000]}"]
        if contract_text:
            ctx_parts.append(f"\nANSÆTTELSESKONTRAKT:\n{contract_text[:3000]}")
        if agreement_text:
            ctx_parts.append(f"\nOVEERENSKOMST:\n{agreement_text[:3000]}")

        user_msg = f"""Kontroller denne lønseddel grundigt:

{''.join(ctx_parts)}

Giv en komplet kontrol:

## Overblik
Identificer: lønperiode, lønart, arbejdsgiver og medarbejder.

## Grundløn
Er grundlønnen i overensstemmelse med kontrakt/overenskomst?
Angiv hvad der er registreret og hvad der burde være.

## Pension
Er pensionsbidraget korrekt (arbejdsgiver + medarbejderbidrag)?
Er beregningsgrundlaget rigtigt?

## Tillæg
Er alle relevante tillæg medtaget?
(SH-betaling, fritvalg, skiftetillæg, overarbejde, ubekvem arbejdstid)

## Fradrag
Er fradrags korrekte? (AM-bidrag, A-skat, evt. fagforening)

## Ferietillæg
Er ferietillæg korrekt beregnet?

## Potentielle fejl ⚠️
Lav en liste over konkrete poster der muligvis mangler eller er forkerte.
For hvert punkt: hvad der er registreret vs. hvad der burde være.

## Mulige manglende betalinger
Estimér om muligt beløb der potentielt mangler (angiv altid som estimat).

## Anbefalinger
Hvad bør medarbejderen gøre videre?

---
Dette er vejledende analyse og ikke juridisk rådgivning.
Kontakt din fagforening eller lønkontor ved mistanke om fejl."""

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.2,
            max_tokens=1800,
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
