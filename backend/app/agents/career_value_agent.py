from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

SYSTEM = """Du er en ekspert i karriereøkonomi og lønforhandling på det danske arbejdsmarked.
Du analyserer en kandidats samlede markedsværdi baseret på erfaring, kompetencer og resultater.
Svar altid på dansk. Vær konkret, nuanceret og praktisk handlingsorienteret."""


class CareerValueAgent(BaseAgent):
    name = "career_value_agent"

    async def run(self, input_data: dict) -> AgentResult:
        snapshot_text = input_data.get("snapshot_text", "")
        current_salary = input_data.get("current_salary", "")

        salary_ctx = f"\nNUVÆRENDE LØN: {current_salary}" if current_salary else ""

        user_msg = f"""Analyser denne kandidats markedsværdi:

KARRIEREPROFIL:
{snapshot_text[:5000]}{salary_ctx}

Giv en komplet karriereværdianalyse:

## Markedsværdi
Estimér kandidatens markedsværdi som månedlig bruttoløn (DKK).
Angiv et realistisk spænd baseret på profilen.
Begrund estimatet konkret med reference til profilen.

## Karriereværdi-score (1-10)
Giv en score for hvert parameter:
- Erfaringsdybde: X/10
- Kompetencebredde: X/10
- Ledererfaring: X/10
- Specialisering: X/10
- Markedsbehov: X/10
- Samlet score: X/10

## Forhandlingsstyrke
Hvad er kandidatens stærkeste kort i en lønforhandling?
Hvad er de svageste punkter?

## Risiko for underbetaling
Er der tegn på at kandidaten er underbetalt i forhold til markedet?
Hvad indikerer det?

## Forventet løn ved jobskifte
Hvad kan kandidaten realistisk opnå ved jobskifte?
Angiv som: Konservativt / Realistisk / Ambitiøst scenario.

## Top 5 anbefalinger
Konkrete handlinger for at maksimere markedsværdien de næste 12 måneder."""

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.4,
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
