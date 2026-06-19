"""
Critic Agent — syntetiserer feedback fra ATS, HR og Hiring Manager
til en prioriteret liste af de vigtigste forbedringer.
"""
from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider


class CriticAgent(BaseAgent):
    name = "critic_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          ats_review: str   (feedback fra ATSAgent)
          hr_review: str    (feedback fra HRAgent)
          hm_review: str    (feedback fra HiringManagerAgent)
          language: 'da' | 'en'
          doc_type: 'cover_letter' | 'cv'
        """
        ats_review = input_data.get("ats_review", "")
        hr_review = input_data.get("hr_review", "")
        hm_review = input_data.get("hm_review", "")
        language = input_data.get("language", "da")

        if language == "da":
            system = (
                "Du er en skarp redaktør med ansvar for præcision og sandhed i karrieredokumenter. "
                "Du modtager feedback fra tre eksperter (ATS, HR, Hiring Manager) om et dokument.\n\n"
                "KRITIKPRIORITETER (streng rækkefølge):\n"
                "1. NØJAGTIGHED: Flag enhver påstand der overstater kandidatens faktiske erfaring\n"
                "   - 'drev implementeringen' ≠ 'var IT-ansvarlig'\n"
                "   - 'bidragede til X' ≠ 'var ansvarlig for X'\n"
                "   - 'har arbejdet med X' ≠ 'er ekspert i X'\n"
                "2. SPECIFICITET: Erstat vage påstande med konkrete eksempler\n"
                "3. RELEVANS: Fjern kompetencer der ikke er relevante for DETTE specifikke job\n"
                "4. GAPS: Identificér 1-2 ærlige gaps der bør adresseres i ansøgningen\n"
                "5. ATS: Verificér at jobopslagets nøgleord fremgår naturligt i teksten\n"
                "6. TONE: Selvsikker men ikke arrogant, specifik ikke generisk\n\n"
                "FLAG TIL MENNESKELIG GENNEMGANG hvis:\n"
                "- Nogen metrik eller beløb ikke kan genfindes i kildeprofilden\n"
                "- Lederskabstypen er tvetydig (formel/faglig/projekt)\n"
                "- Et gap sandsynligvis er en showstopper\n\n"
                "Syntetiser til de 5 VIGTIGSTE forbedringer, sorteret efter impact. Eliminer overlap. "
                "Format: '1. [type: forbedring]' til '5. [type: forbedring]'. Kun listen, ingen indledning."
            )
            user_msg = (
                f"ATS-feedback:\n{ats_review}\n\n"
                f"HR-feedback:\n{hr_review}\n\n"
                f"Hiring Manager-feedback:\n{hm_review}"
            )
        else:
            system = (
                "You are a sharp editor responsible for accuracy and truthfulness in career documents. "
                "You receive feedback from three experts (ATS, HR, Hiring Manager) about a document.\n\n"
                "CRITIC PRIORITIES (strict order):\n"
                "1. ACCURACY: Flag any claim overstating the candidate's actual experience\n"
                "   - 'drove the implementation' ≠ 'was IT responsible'\n"
                "   - 'contributed to X' ≠ 'was responsible for X'\n"
                "   - 'has worked with X' ≠ 'is an expert in X'\n"
                "2. SPECIFICITY: Replace vague claims with concrete examples\n"
                "3. RELEVANCE: Remove competencies not relevant to THIS specific job\n"
                "4. GAPS: Identify top 1-2 honest gaps to address in the cover letter\n"
                "5. ATS: Verify job posting keywords appear naturally in the text\n"
                "6. TONE: Confident but not arrogant, specific not generic\n\n"
                "FLAG FOR HUMAN REVIEW if:\n"
                "- Any metric or amount not found in source profile\n"
                "- Leadership type is ambiguous (formal/functional/project)\n"
                "- A gap is likely a dealbreaker\n\n"
                "Synthesize into the 5 MOST IMPORTANT improvements, sorted by impact. Eliminate overlap. "
                "Format: '1. [type: improvement]' through '5. [type: improvement]'. Only the list, no introduction."
            )
            user_msg = (
                f"ATS feedback:\n{ats_review}\n\n"
                f"HR feedback:\n{hr_review}\n\n"
                f"Hiring Manager feedback:\n{hm_review}"
            )

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.2,
            max_tokens=400,
        )
        content = response.choices[0].message.content or ""
        ud = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
        usage = AgentUsage(
            prompt_tokens=getattr(ud, "prompt_tokens", 0),
            completion_tokens=getattr(ud, "completion_tokens", 0),
            total_tokens=getattr(ud, "total_tokens", 0),
            model=getattr(response, "model", "unknown"),
        )
        return AgentResult(content=content, usage=usage)
