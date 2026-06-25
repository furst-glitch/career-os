from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

SYSTEM = """Du er en ekspert i det danske arbejdsmarked og lønanalyse.
Du giver præcise, vejledende løndata baseret på jobtitel, branche og erfaring.
Brug altid DKK. Svar på dansk.

VIGTIGT: Dine estimater er baseret på din viden om det danske arbejdsmarked og er vejledende."""


class SalaryCheckAgent(BaseAgent):
    name = "salary_check_agent"

    async def run(self, input_data: dict) -> AgentResult:
        title = input_data.get("title", "")
        industry = input_data.get("industry", "")
        location = input_data.get("location", "")
        company = input_data.get("company", "")
        experience_years = input_data.get("experience_years", "")
        education = input_data.get("education", "")
        management = input_data.get("management_responsibility", False)
        budget = input_data.get("budget_responsibility", "")
        team_size = input_data.get("team_size", "")
        current_salary = input_data.get("current_salary", "")
        pension = input_data.get("pension", "")
        bonus = input_data.get("bonus", "")
        benefits = input_data.get("benefits", "")

        user_msg = f"""Analyser lønniveauet for denne stilling:

STILLINGSPROFIL:
- Jobtitel: {title}
- Branche: {industry}
- Lokation: {location}
- Virksomhed: {company or '(ikke angivet)'}
- Erfaring: {experience_years} år
- Uddannelse: {education}
- Ledelsesansvar: {'Ja' if management else 'Nej'}
- Budgetansvar: {budget or '(ikke angivet)'}
- Teamstørrelse: {team_size or '(ikke angivet)'}

NUVÆRENDE KOMPENSATION:
- Grundløn: {current_salary or '(ikke angivet)'}
- Pension: {pension or '(ikke angivet)'}
- Bonus: {bonus or '(ikke angivet)'}
- Personalegoder: {benefits or '(ikke angivet)'}

Giv en komplet lønanalyse med disse afsnit:

## Markedsløn (vejledende — DKK/måned brutto)
Angiv nedre kvartil, median og øvre kvartil som månedlig grundløn.
Specificér om tal er ekskl. pension og bonus.

## Samlet kompensationspakke
Beregn total kompensation inkl. pension og bonus.
Sammenlign med markedet.

## Lønniveau-score
Vurder om nuværende løn er under/på/over markedsniveauet.
Angiv forskellen i DKK og procent.
Giv en score fra 1-10 (10 = toppen af markedet).

## Faktorer der påvirker lønnen
Hvilke elementer løfter eller sænker markedsværdien i dette tilfælde?

## Anbefalinger
Konkrete handlinger for at forbedre lønsituationen."""

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.3,
            max_tokens=1400,
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
