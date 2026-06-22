from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

INTERVIEW_SYSTEM = """Du er en erfaren lønforhandlingscoach med dyb indsigt i det danske arbejdsmarked.
Du interviewer kandidaten for at forberede dem til en lønsamtale.

Din opgave:
1. Identificer kandidatens stærkeste resultater og præstationer
2. Afdæk nye ansvarsområder og kompetencer siden sidst ansatte eller lønstigning
3. Find konkrete tal og besparelser kandidaten kan fremhæve
4. Forstå kandidatens lønmål og minimumsmål

Stil ét spørgsmål ad gangen. Vær coachende og konstruktiv. Maks 5 spørgsmål.
Svar altid på dansk."""

PACKAGE_SYSTEM = """Du er ekspert i lønforhandling og skriver lønsamtalepakker til det danske marked.
Svar altid på dansk. Vær konkret, præcis og actionable."""


class SalaryPrepAgent(BaseAgent):
    name = "salary_prep_agent"

    async def run_interview(self, input_data: dict) -> AgentResult:
        """Chat-trin i lønsamtale-forberedelse (stateless SSE)."""
        snapshot_text = input_data.get("snapshot_text", "")
        messages = input_data.get("messages", [])
        current_salary = input_data.get("current_salary", "")
        target_salary = input_data.get("target_salary", "")

        salary_ctx = ""
        if current_salary:
            salary_ctx += f"\nNUVÆRENDE LØN: {current_salary}"
        if target_salary:
            salary_ctx += f"\nMÅLLØN: {target_salary}"

        system = (
            f"{INTERVIEW_SYSTEM}\n\nKANDIDATENS PROFIL:\n{snapshot_text[:3000]}{salary_ctx}"
        )

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": system}] + [
                {"role": m["role"], "content": m["content"]}
                for m in messages if m.get("role") in ("user", "assistant")
            ],
            stream=True,
            temperature=0.6,
            max_tokens=400,
        )
        return AgentResult(content="", usage=AgentUsage(), metadata={"stream": resp})

    async def run(self, input_data: dict) -> AgentResult:
        """Generer komplet lønsamtalepakke baseret på samtalehistorik."""
        snapshot_text = input_data.get("snapshot_text", "")
        conversation = input_data.get("conversation", "")
        current_salary = input_data.get("current_salary", "")
        target_salary = input_data.get("target_salary", "")
        min_salary = input_data.get("min_salary", "")
        market_salary = input_data.get("market_salary", "")

        salary_ctx = f"""
NUVÆRENDE LØN: {current_salary or '(ikke angivet)'}
MÅLLØN: {target_salary or '(ikke angivet)'}
MINIMUMSMÅL: {min_salary or '(ikke angivet)'}
MARKEDSLØN (estimat): {market_salary or '(ikke angivet)'}"""

        user_msg = f"""Generer en komplet lønsamtalepakke baseret på:

KARRIEREPROFIL:
{snapshot_text[:3000]}

LØNMÅL:
{salary_ctx}

FORBEREDELSESSAMTALE (kandidatens svar):
{conversation[:3000]}

Generér lønsamtalepakken med PRÆCIS disse afsnit:

# LØNSAMTALEPAKKE

## 1. Executive Summary
- Nuværende løn: [beløb]
- Markedsløn (estimat): [beløb]
- Målløn: [beløb]
- Minimumsmål: [beløb]
- Forhandlingsstyrke: [kort vurdering]

## 2. Stærkeste argumenter
Lav en nummereret liste af de 5 stærkeste argumenter for lønstigning.
Hvert argument skal være specifikt og baseret på kandidatens profil og svar.

## 3. Resultatoversigt
Liste over konkrete resultater, besparelser, projekter og præstationer.
Brug tal og procenter hvor muligt.

## 4. Potentielle chef-indvendinger og forslag til svar
For hvert typisk modargument: hvad siger chefen, hvad svarer kandidaten.

## 5. Konkrete formuleringer
Eksempel-sætninger kandidaten kan bruge under samtalen.
Inkluder: åbningssætning, argumentation, reaktion på nej.

## 6. Forhandlingsstrategi
Trin-for-trin strategi for selve forhandlingen.
Hvornår fremfører man hvad? Hvad gør man hvis man får nej?"""

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": PACKAGE_SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.5,
            max_tokens=2800,
        )
        content = resp.choices[0].message.content or ""
        usage = AgentUsage(
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
        )
        return AgentResult(content=content, usage=usage)

    async def generate_a4(self, input_data: dict) -> AgentResult:
        """Genererer en kompakt A4-side til lønsamtalen."""
        package_text = input_data.get("package_text", "")
        current_salary = input_data.get("current_salary", "")
        target_salary = input_data.get("target_salary", "")
        min_salary = input_data.get("min_salary", "")

        user_msg = f"""Baseret på denne lønsamtalepakke:

{package_text[:3000]}

Generer en KOMPAKT A4-SIDE der passer på én side:

# LØNSAMTALE — MÅL OG ARGUMENTER

**Nuværende løn:** {current_salary or '___'}
**Målløn:** {target_salary or '___'}
**Minimumsmål:** {min_salary or '___'}

## Mine 3 stærkeste argumenter
[Liste de 3 allerstærkeste argumenter — max 2 linjer pr. argument]

## Nøgleresultater
[Max 5 konkrete resultater med tal]

## Hvis chefen siger nej
[2-3 konkrete modargumenter og alternative løsninger]

## Mine formuleringer
**Åbning:** [en konkret sætning]
**Hovedargument:** [en konkret sætning]
**Reaktion på nej:** [en konkret sætning]

Hold teksten kort — siden må MAX fylde en A4-side."""

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": PACKAGE_SYSTEM}, {"role": "user", "content": user_msg}],
            temperature=0.4,
            max_tokens=800,
        )
        content = resp.choices[0].message.content or ""
        usage = AgentUsage(
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
        )
        return AgentResult(content=content, usage=usage)
