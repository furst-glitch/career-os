from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

SYSTEM = """Du er en ekspert i dansk arbejdstidslovgivning, hviletidsregler og overenskomstbestemmelser.
Du analyserer vagtplaner og timesedler for overtrædelser og mulige tillæg.
Svar altid på dansk. Vær konkret og struktureret.

Kend de vigtigste regler:
- Arbejdstidsloven: max 48 timer/uge i gennemsnit over 4 måneder
- Hviletid: min 11 timers sammenhængende hvile pr. 24 timer
- Ugentlig fridag: min 24 timer + 11 timers hviletid = 35 timer sammenhængende
- Overarbejdstillæg varierer efter overenskomst (typisk 50% de første 3 timer, 100% derefter)

VIGTIGT: Anfør altid: "Dette er vejledende analyse og ikke juridisk rådgivning." """


class WorktimeCheckAgent(BaseAgent):
    name = "worktime_check_agent"

    async def run(self, input_data: dict) -> AgentResult:
        schedule_text = input_data.get("schedule_text", "")
        agreement_text = input_data.get("agreement_text", "")

        ctx = f"VAGTPLAN/TIMESEDDEL:\n{schedule_text[:5000]}"
        if agreement_text:
            ctx += f"\n\nOVEERENSKOMST:\n{agreement_text[:3000]}"

        user_msg = f"""Analyser denne arbejdstidsdata:

{ctx}

Giv en komplet analyse:

## Overblik
Identificer: periode, medarbejder, arbejdsgiver, type af tjeneste.

## Ugentlig arbejdstid
Beregn faktisk ugentlig arbejdstid og sammenlign med lovlig grænse (48 timer/uge i snit).

## Hviletid
Er der overholdt min. 11 timers hvile mellem vagter?
List alle perioder med potentiel underskridelse.

## Ugentlig fridag
Er der min. 35 timers sammenhængende frihed (24+11) i løbet af uge?

## Overarbejde
Identificer konkrete overarbejdstimer.
Hvilke tillæg har medarbejderen sandsynligvis ret til?

## Weekend- og helligdagstillæg
Er der arbejde på weekender/helligdage der udløser tillæg?

## Skifteholdsregler
Gælder der særlige skifteholdsregler? Hvilke tillæg udløses?

## Potentielle overtrædelser ⚠️
List konkrete datoer/perioder hvor reglerne muligvis er brudt.

## Mulige manglende tillæg
Estimér overtrædelsernes omfang i timer og potentielle tillæg.

## Anbefalinger
Hvad bør medarbejderen gøre videre?

---
Dette er vejledende analyse og ikke juridisk rådgivning."""

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.2,
            max_tokens=1600,
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
