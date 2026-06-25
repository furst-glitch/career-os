"""
JobAgent — dybdegående analyse af jobopslag.

Input:  job_title, job_company, job_description, job_requirements, language
Output: struktureret jobanalyse med nøglekrav, kulturelle signaler,
        ATS-nøgleord og hvad der adskiller vinderkandidater.
"""
from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider


class JobAgent(BaseAgent):
    name = "job_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          job_title, job_company, job_description, job_requirements, language
        """
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:3000]
        requirements = input_data.get("job_requirements", [])
        language = input_data.get("language", "da")
        req_text = "\n".join(f"- {r}" for r in requirements[:20]) if requirements else "Ikke angivet"

        if language == "da":
            system = (
                "Du er en ekspert rekrutteringsstrateg. Analysér jobopslaget og producér en præcis jobanalyse.\n\n"
                "DANSKE MARKEDSSIGNALER — flag disse eksplicit hvis de forekommer:\n"
                "- 'Relevant videregående uddannelse' = akademisk grad PÅKRÆVET (hård filter)\n"
                "- 'Cand.merc./HD/cand.oecon.' = specifik akademisk filter\n"
                "- 'Solid ledelseserfaring' = reel personaleledelse med direkte rapporteringer PÅKRÆVET\n"
                "- 'Lede gennem ledere' = senior peoplemanager PÅKRÆVET\n"
                "- 'EU-udbud' = ekspertise i offentlig udbudsjura PÅKRÆVET\n"
                "- 'Big 4' = revisorhus-baggrund PÅKRÆVET\n\n"
                "RØDE FLAG — fremhæv altid:\n"
                "- Rollen kræver direkte rapporteringer hvis kandidaten ikke har dem\n"
                "- Rollen kræver specifik uddannelse kandidaten ikke har\n"
                "- Rollen er vikar/barselsorlov\n"
                "- Lokation er udenfor kandidatens geografi\n"
                "- Løn sandsynligvis under kandidatens mål\n\n"
                "Format (brug disse præcise overskrifter):\n"
                "NØGLEKRAV: [De 5 vigtigste krav — hvad der SKAL matche]\n"
                "HÅRDE FILTRE: [Krav der eliminerer kandidater med det samme — uddannelse, lovgivning, ledelsestype]\n"
                "KULTURELLE SIGNALER: [Virksomhedskultur, arbejdsstil, tone i opslaget]\n"
                "ATS-NØGLEORD: [Præcise ord og sætninger fra opslaget der SKAL fremgå i ansøgningen]\n"
                "VINDERKVALITETER: [Hvad adskiller den ideelle kandidat fra en middelmådig ansøger]\n"
                "RØDE FLAG: [Krav der typisk eliminerer kandidater — vær ærlig og konkret]\n"
                "ANBEFALING: [apply / overvej / spring over — med begrundelse]\n\n"
                "Vær konkret og kortfattet. Maks 300 ord total."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Krav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}"
            )
        else:
            system = (
                "You are an expert recruiting strategist. Analyze the job posting and produce a precise job analysis.\n\n"
                "MARKET SIGNALS — flag these explicitly if present:\n"
                "- 'Relevant degree' = academic qualification REQUIRED (hard filter)\n"
                "- Specific degree (e.g. MBA/CPA/LLB) = academic hard filter\n"
                "- 'Strong leadership experience' = real people management with direct reports REQUIRED\n"
                "- 'Lead through leaders' = senior people manager REQUIRED\n"
                "- Public procurement law = specialist legal knowledge REQUIRED\n"
                "- Big 4 = audit firm background REQUIRED\n\n"
                "RED FLAGS — always surface:\n"
                "- Role requires direct reports if candidate has none\n"
                "- Role requires specific degree candidate does not have\n"
                "- Role is temp/maternity cover\n"
                "- Location is outside candidate's stated geography\n"
                "- Salary likely below candidate's target\n\n"
                "Format (use these exact headings):\n"
                "KEY REQUIREMENTS: [The 5 most important requirements — what MUST match]\n"
                "HARD FILTERS: [Requirements that immediately eliminate candidates — degree, law, leadership type]\n"
                "CULTURAL SIGNALS: [Company culture, work style, tone in the posting]\n"
                "ATS KEYWORDS: [Exact words and phrases from the posting that MUST appear in the application]\n"
                "WINNER QUALITIES: [What separates the ideal candidate from an average applicant]\n"
                "RED FLAGS: [Requirements that typically eliminate candidates — be honest and specific]\n"
                "RECOMMENDATION: [apply / consider / skip — with reason]\n\n"
                "Be concrete and concise. Max 300 words total."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}"
            )

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.2,
            max_tokens=450,
        )
        content = response.choices[0].message.content or ""
        ud = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
        usage = AgentUsage(
            prompt_tokens=getattr(ud, "prompt_tokens", 0),
            completion_tokens=getattr(ud, "completion_tokens", 0),
            total_tokens=getattr(ud, "total_tokens", 0),
            model=getattr(response, "model", "unknown"),
            provider=getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown"),
        )
        await self.log_usage(usage, operation=self.name, used_user_key=provider.used_user_key)
        return AgentResult(content=content, usage=usage)
