from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

SYSTEM = """Du er en ekspert i dansk ansættelses- og arbejdsret.
Du analyserer ansættelseskontrakter og identificerer rettigheder, risici og usædvanlige vilkår.
Svar altid på dansk. Vær konkret og praktisk.

VIGTIGT: Din analyse er vejledende og udgør ikke juridisk rådgivning.
Anfør altid: "Dette er vejledende analyse og ikke juridisk rådgivning."
Rådfør altid med en advokat eller fagforening ved vigtige beslutninger."""


class ContractAnalysisAgent(BaseAgent):
    name = "contract_analysis_agent"

    async def run(self, input_data: dict) -> AgentResult:
        contract_text = input_data.get("contract_text", "")
        file_name = input_data.get("file_name", "kontrakt")

        user_msg = f"""Analyser denne ansættelseskontrakt grundigt:

KONTRAKT ({file_name}):
{contract_text[:8000]}

Giv en komplet analyse med disse afsnit:

## Resumé
Kort overblik over ansættelsesforholdet (3-5 sætninger).

## Løn og pension
- Grundløn, pension, bonus og personalegoder
- Er disse markedskonforme?

## Arbejdstid og overarbejde
- Normal arbejdstid, overarbejdsregler, kompensation

## Opsigelsesvilkår
- Varsler for begge parter, evt. fratrædelsesgodtgørelse

## Klausuler (vigtige!)
- Konkurrenceklausul: Hvad er forbudt og i hvor lang tid?
- Kundeklausul: Hvilke kunder er afskåret?
- Konsekvenser ved brud

## Ferie og fri
- Ferierettigheder, særlige fridage, barsel

## Usædvanlige vilkår
Vilkår der afviger væsentligt fra normal praksis.

## Potentielle risici
Vilkår der kan skade medarbejderen — beskriv konkret.

## Forbedringspunkter
Hvad bør medarbejderen forsøge at forhandle eller præcisere?

## Anbefalede spørgsmål til arbejdsgiveren
3-5 konkrete spørgsmål inden kontrakten underskrives.

---
Dette er vejledende analyse og ikke juridisk rådgivning."""

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.2,
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
