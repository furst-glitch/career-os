"""
Hiring Manager Agent — vurderer professionel relevans, resultater og teknisk match.
"""
from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider


class HiringManagerAgent(BaseAgent):
    name = "hiring_manager_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          draft, job_title, job_company, job_description, job_requirements,
          language ('da'|'en'), doc_type
        """
        draft = input_data.get("draft", "")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:2000]
        requirements = input_data.get("job_requirements", [])
        language = input_data.get("language", "da")
        doc_type = input_data.get("doc_type", "cover_letter")
        req_text = "\n".join(f"- {r}" for r in requirements[:15]) if requirements else "Ikke angivet"

        if language == "da":
            system = (
                "Du er hiring manager for denne stilling og screener kandidater.\n\n"
                "MATCHKLASSIFICERING — vurder hvert krav som:\n"
                "- STÆRKT_MATCH: Direkte erfaring, konkret eksempel tilgængeligt\n"
                "- DELVIST_MATCH: Relateret erfaring, kræver omhyggelig indramning\n"
                "- ÆRLIG_GAP: Mangler men kan læres — adressér åbent\n"
                "- SHOWSTOPPER_GAP: Mangler og kritisk — flag til menneskelig vurdering\n\n"
                "BROBYGNINGSSPROG for DELVIST_MATCH:\n"
                "DÅRLIG: 'Jeg har erfaring med X'\n"
                "GODT:  'Gennem mit arbejde med Y har jeg opbygget stærkt fundament i X'\n\n"
                "ÆRLIG GAP-INDRAMNING:\n"
                "DÅRLIG: Ignorer eller skjul gabet\n"
                "GODT:  'X er ikke mit primære fagområde, men min track record viser at jeg\n"
                "        hurtigt tilegner mig nye domæner og skaber resultater'\n\n"
                "DANSK BRANCHEKONTEKST:\n"
                "FM/Facility: leverandørstyring, driftsøkonomi, SLA/KPI, OPEX/CAPEX\n"
                "ESG: Scope 1/2/3, CSRD, ESRS, GHG Protocol, dobbelt væsentlighed\n"
                "Indkøb: spend-analyse, rammeaftaler, mini-udbud, sourcing\n"
                "Controlling: business cases til CFO, rapporteringsmodeller, forecasting\n\n"
                "NØJAGTIGHEDSREGEL: Flag enhver påstand der overvurderer kandidatens faktiske erfaring.\n\n"
                "Vurder dokumentet: Er kandidatens relevante erfaring tydelig? "
                "Er der konkrete resultater og tal? Matcher kandidaten det vi søger? "
                "Hvad ville få dig til at kalde dem til samtale — eller IKKE? "
                "Maks 4 punkter, ét punkt pr. linje med '-' foran. "
                "Skriv KUN forbedringspunkterne, ingen introduktion."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Krav:\n{req_text}\n\nJobbeskrivelse:\n{job_description}\n\n"
                f"{'CV' if doc_type == 'cv' else 'Ansøgning'}:\n{draft}"
            )
        else:
            system = (
                "You are the hiring manager for this position screening candidates.\n\n"
                "MATCH CLASSIFICATION — assess each requirement as:\n"
                "- STRONG_MATCH: Direct experience, concrete example available\n"
                "- PARTIAL_MATCH: Related experience, needs careful framing\n"
                "- HONEST_GAP: Missing but learnable, address openly\n"
                "- DEALBREAKER_GAP: Missing and critical, flag for human review\n\n"
                "BRIDGE LANGUAGE for PARTIAL_MATCH:\n"
                "BAD:  'I have experience with X'\n"
                "GOOD: 'Through my work with Y, I have built a strong foundation in X'\n\n"
                "HONEST GAP FRAMING:\n"
                "BAD:  Ignore or hide the gap\n"
                "GOOD: 'X is not my primary area, but my track record shows I rapidly\n"
                "       acquire new domains and deliver results'\n\n"
                "INDUSTRY CONTEXT:\n"
                "FM/Facility: vendor management, operational economics, SLA/KPI, OPEX/CAPEX\n"
                "ESG: Scope 1/2/3, CSRD, ESRS, GHG Protocol, double materiality\n"
                "Procurement: spend analysis, framework agreements, mini-tenders, sourcing\n"
                "Controlling: business cases to CFO, reporting models, forecasting\n\n"
                "ACCURACY RULE: Flag any claim overstating the candidate's actual experience.\n\n"
                "Evaluate the document: Is the candidate's relevant experience clear? "
                "Are there concrete results and numbers? Does the candidate match what we need? "
                "What would make you call them for an interview — or NOT? "
                "Max 4 bullet points, one per line starting with '-'. "
                "Output ONLY the improvement points, no introduction."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Requirements:\n{req_text}\n\nJob Description:\n{job_description}\n\n"
                f"{'CV' if doc_type == 'cv' else 'Cover letter'}:\n{draft}"
            )

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.25,
            max_tokens=350,
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
