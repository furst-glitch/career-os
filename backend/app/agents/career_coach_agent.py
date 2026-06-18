"""
Career Coach Agent — analyserer karrierevej og giver strategiske anbefalinger.
"""
from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, AgentUsage
from app.providers.litellm_provider import LiteLLMProvider, NoProviderKeyError


class CareerCoachAgent(BaseAgent):
    name = "career_coach_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          snapshot_text: str
          question: str | None
          analysis_type: 'full' | 'skills_gap' | 'career_path' | 'next_steps'
          language: 'da' | 'en'
          target_role: str | None
        """
        snapshot_text = input_data.get("snapshot_text", "")
        question = input_data.get("question", "")
        analysis_type = input_data.get("analysis_type", "full")
        language = input_data.get("language", "da")
        target_role = input_data.get("target_role", "")

        if language == "da":
            system = (
                "Du er en erfaren karriere-coach med speciale i tech og ledelse. "
                "Svar altid på dansk. "
                "Du har adgang til kandidatens komplette karriereprofil. "
                "Vær konkret, handlingsorienteret og specifik — undgå generiske råd. "
                "Brug bullet points og klare sektioner. "
                "Dine anbefalinger skal baseres på kandidatens faktiske baggrund."
            )
        else:
            system = (
                "You are an experienced career coach specializing in tech and leadership. "
                "Always respond in English. "
                "You have access to the candidate's complete career profile. "
                "Be concrete, action-oriented and specific — avoid generic advice. "
                "Use bullet points and clear sections. "
                "Base your recommendations on the candidate's actual background."
            )

        type_prompts: dict[str, str] = {
            "full": (
                "Generer en komplet karrierecoaching-analyse med:\n"
                "## Styrker\nTop 3 konkurrencefordele baseret på profilen.\n\n"
                "## Udviklingsområder\nDe 3 vigtigste gaps at lukke.\n\n"
                "## Karrierevej\nRealistiske næste roller (6-18 måneder).\n\n"
                "## Kompetencegap\nSpecifikke skills der mangler til målet.\n\n"
                "## Handlingsplan\n5 konkrete tiltag de næste 90 dage.\n\n"
                "## Anbefalede certifikater\n2-3 certifikater med begrundelse."
            ) if language == "da" else (
                "Generate a complete career coaching analysis with:\n"
                "## Strengths\nTop 3 competitive advantages.\n\n"
                "## Development Areas\nThe 3 most important gaps.\n\n"
                "## Career Path\nRealistic next roles (6-18 months).\n\n"
                "## Skills Gap\nSpecific skills missing for the target.\n\n"
                "## Action Plan\n5 concrete actions over the next 90 days.\n\n"
                "## Recommended Certifications\n2-3 certifications with rationale."
            ),
            "skills_gap": (
                f"Analysér kompetencegap{f' mod rollen: {target_role}' if target_role else ''}. "
                "List 5 vigtigste manglende kompetencer, prioriteret efter impact. "
                "For hver: hvad mangler, hvordan læres det, tidsestimat."
            ) if language == "da" else (
                f"Analyze skills gap{f' for role: {target_role}' if target_role else ''}. "
                "List 5 most important missing skills by impact. "
                "For each: what is missing, how to learn it, time estimate."
            ),
            "career_path": (
                f"Skitsér karriereveje{f' mod: {target_role}' if target_role else ''}. "
                "Giv 3 mulige veje: optimistisk, realistisk, konservativ. "
                "For hver: tidslinje, nødvendige skridt, sandsynlighed."
            ) if language == "da" else (
                f"Outline career paths{f' toward: {target_role}' if target_role else ''}. "
                "Provide 3 paths: optimistic, realistic, conservative. "
                "For each: timeline, steps, likelihood."
            ),
            "next_steps": (
                "Giv de 5 mest impactfulde ting kandidaten kan gøre NU (næste 30 dage). "
                "Vær ekstremt konkret — specifikke kurser, handlinger, ressourcer."
            ) if language == "da" else (
                "Give the 5 most impactful actions the candidate can take NOW (next 30 days). "
                "Be extremely concrete — specific courses, actions, resources."
            ),
        }

        type_instruction = type_prompts.get(analysis_type, type_prompts["full"])

        prefix = "Kandidatprofil" if language == "da" else "Candidate Profile"
        user_msg = f"{prefix}:\n{snapshot_text}\n\n{type_instruction}"
        if question:
            q_label = "Kandidatens spørgsmål" if language == "da" else "Candidate's question"
            user_msg += f"\n\n{q_label}: {question}"
        if target_role and analysis_type == "full":
            r_label = "Målrolle" if language == "da" else "Target role"
            user_msg += f"\n\n{r_label}: {target_role}"

        provider = LiteLLMProvider(self.user_id)
        try:
            response = await provider.complete(
                agent_name=self.name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                stream=False,
                temperature=0.6,
                max_tokens=1200,
            )
        except NoProviderKeyError as exc:
            raise exc

        content = response.choices[0].message.content or ""
        usage_data = response.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()

        usage = AgentUsage(
            prompt_tokens=getattr(usage_data, "prompt_tokens", 0),
            completion_tokens=getattr(usage_data, "completion_tokens", 0),
            total_tokens=getattr(usage_data, "total_tokens", 0),
            model=getattr(response, "model", "unknown"),
            provider=getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown"),
        )

        return AgentResult(
            content=content,
            usage=usage,
            metadata={"analysis_type": analysis_type, "language": language},
        )
