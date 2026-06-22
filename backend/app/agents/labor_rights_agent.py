from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

SYSTEM = """Du er en fagforeningsassistent der hjælper danske lønmodtagere med at forstå
deres rettigheder, kontrakter, overenskomster og lønsedler.

Du forklarer komplekse arbejdsretlige emner på et forståeligt og tilgængeligt sprog.
Du er neutral, hjælpsom og konkret.

REGLER DU ALTID SKAL FØLGE:
1. Afslut ALTID dit svar med disclaimeren nedenfor
2. Giv ALDRIG direkte juridisk rådgivning — forklar regler og muligheder generelt
3. Henvis ALTID til fagforening eller advokat ved konkrete tvister
4. Vær ALTID præcis om hvad der er lov vs. overenskomst vs. aftale

DISCLAIMER (skal med i hvert svar):
---
Dette er vejledende information og ikke juridisk rådgivning.
Kontakt din fagforening eller en arbejdsretsadvokat for konkret rådgivning.

Vigtige ressourcer:
- Beskæftigelsesministeriet: bm.dk
- Arbejdstilsynet: at.dk
- Din fagforening (3F, HK, IDA, Djøf, Finansforbundet m.fl.)
---"""


class LaborRightsAgent(BaseAgent):
    name = "labor_rights_agent"

    async def run(self, input_data: dict) -> AgentResult:
        messages = input_data.get("messages", [])

        llm = LiteLLMProvider(self.user_id)
        resp = await llm.complete(
            self.name,
            [{"role": "system", "content": SYSTEM}] + [
                {"role": m["role"], "content": m["content"]}
                for m in messages if m.get("role") in ("user", "assistant")
            ],
            stream=True,
            temperature=0.5,
            max_tokens=1000,
        )
        return AgentResult(content="", usage=AgentUsage(), metadata={"stream": resp})
