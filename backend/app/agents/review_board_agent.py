"""
ReviewBoardAgent — "Den endelige dommer" i generationspipelinen.

Modes:
  mode="rewrite":  Omskriver et CV-udkast baseret på CriticAgent-feedback.
                   Input: draft, critic_feedback, job_title, job_company,
                          job_description, language
                   Output: forbedret, endeligt CV

  mode="brief":    Producerer en konkret skrivebrief til ApplicationAgent
                   (bruges i ansøgningspipelinen).
                   Input: job_analysis, must_haves, job_title, job_company, language
                   Output: præcise skriveinstruktioner
"""
from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider


class ReviewBoardAgent(BaseAgent):
    name = "review_board_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data:
          mode: "rewrite" | "brief"
          language: "da" | "en"
          + mode-specifikke felter (se modul-docstring)
        """
        mode = input_data.get("mode", "rewrite")
        if mode == "brief":
            return await self._run_brief(input_data)
        return await self._run_rewrite(input_data)

    async def _run_rewrite(self, input_data: dict) -> AgentResult:
        draft = input_data.get("draft", "")
        critic_feedback = input_data.get("critic_feedback", "")
        design_guide = input_data.get("design_guide", "")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:1500]
        language = input_data.get("language", "da")

        if language == "da":
            system = (
                "Du er chefredaktør og producerer den endelige udgave af et CV.\n\n"
                "NØJAGTIGHEDSTJEK (gennemfør inden du omskriver):\n"
                "1. Flag enhver påstand der overstater kandidatens faktiske erfaring\n"
                "2. Verificér at alle tal, DKK-beløb og procenter stammer fra kilden\n"
                "3. Tjek at lederskabstype er specificeret (formel/faglig/projekt) — aldrig bare 'ledelse'\n"
                "4. Reducer eller fjern claims der ikke kan verificeres i udkastet\n\n"
                "HÅRDE BEGRÆNSNINGER:\n"
                "- 'drev implementeringen' ≠ 'var IT-ansvarlig' — brug det ringeste niveau\n"
                "- 'bidragede til X' ≠ 'var ansvarlig for X'\n"
                "- Opfind ALDRIG eksempler, beløb, datoer eller resultater\n\n"
                "Du modtager et udkast, en prioriteret liste af forbedringer og en template-stilguide. "
                "Din opgave: omskriv udkastet så det implementerer ALLE forbedringer og følger stilguiden præcist. "
                "Bevar kandidatens reelle erfaringer og informationer — tilføj eller opfind IKKE facts. "
                "Output: KUN det forbedrede CV. Ingen kommentarer om hvad du har ændret.\n\n"
                "Skriv med korrekte danske bogstaver: æ, ø, å, Æ, Ø, Å.\n"
                "CO2 altid som 'CO2'. Brug ## til sektionshoveder og - til bullets. Ingen ** eller *."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Jobbeskrivelse (uddrag):\n{job_description}\n\n"
                f"CV-udkast:\n{draft}\n\n"
                f"Forbedringer der SKAL implementeres:\n{critic_feedback}"
            )
            if design_guide:
                user_msg += f"\n\nTemplate-stilguide (følg disse instruktioner):\n{design_guide}"
        else:
            system = (
                "You are editor-in-chief producing the final version of a CV.\n\n"
                "ACCURACY CHECK (perform before rewriting):\n"
                "1. Flag any claim overstating the candidate's actual experience\n"
                "2. Verify all numbers, amounts and percentages come from the source\n"
                "3. Check leadership type is specified (formal/functional/project) — never just 'management'\n"
                "4. Downgrade or remove claims that cannot be verified in the draft\n\n"
                "HARD CONSTRAINTS:\n"
                "- 'drove the implementation' ≠ 'was IT responsible' — use the lower claim\n"
                "- 'contributed to X' ≠ 'was responsible for X'\n"
                "- NEVER invent examples, amounts, dates or results\n\n"
                "You receive a draft, a prioritized list of improvements, and a template style guide. "
                "Your task: rewrite the draft to implement ALL improvements and follow the style guide precisely. "
                "Preserve the candidate's real experiences and information — do NOT add or invent facts. "
                "Output: ONLY the improved CV. No commentary about what you changed.\n\n"
                "Use ## for section headers and - for bullets. No **, * or # elsewhere."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Job Description (excerpt):\n{job_description}\n\n"
                f"CV Draft:\n{draft}\n\n"
                f"Improvements to implement:\n{critic_feedback}"
            )
            if design_guide:
                user_msg += f"\n\nTemplate style guide (follow these instructions):\n{design_guide}"

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.4,
            max_tokens=1400,
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

    async def _run_brief(self, input_data: dict) -> AgentResult:
        job_analysis = input_data.get("job_analysis", "")
        must_haves = input_data.get("must_haves", "")
        design_guide = input_data.get("design_guide", "")
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        language = input_data.get("language", "da")

        if language == "da":
            system = (
                "Du er kreativ direktør og udformer præcise skriveinstruktioner.\n\n"
                "NØJAGTIGHEDSKRAV TIL BRIEFEN:\n"
                "- Inkludér KUN claims der kan verificeres i kandidatprofilen\n"
                "- Specificér lederskabstype (formel/faglig/projekt) — aldrig bare 'ledelse'\n"
                "- Flag gaps ærligt frem for at skjule dem\n"
                "- Brug 'ca.' eller '+' ved approksimationer\n\n"
                "Baseret på jobanalysen og de vigtigste krav: producér en konkret skrivebrief "
                "som en ansøgningsskriver KAN FØLGE for at skrive den perfekte ansøgning.\n\n"
                "Ansøgningen skal have 4 afsnit:\n"
                "ÅBNING: [Afsnit 1 — hvad der præcist skal siges om HVORFOR DENNE ROLLE]\n"
                "KERNEPUNKT: [Afsnit 2 — kandidatens stærkeste verificerede match med konkret eksempel]\n"
                "SEKUNDÆR VINKEL ELLER GAP: [Afsnit 3 — anden vinkel ELLER ærlig gap-håndtering]\n"
                "FREMAD: [Afsnit 4 — selvsikker afslutning med virksomhedsnavnet]\n"
                "NØGLEORD: [Specifikke ord fra jobopslaget der SKAL stå i teksten]\n"
                "UNDGÅ: ['Jeg brænder for', 'Jeg er struktureret', 'Det vil jeg meget gerne' og lignende]\n\n"
                "Maks 200 ord. Vær konkret og direkte — ingen generelle råd."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Jobanalyse:\n{job_analysis}\n\n"
                f"Vigtigste krav til ansøgningen:\n{must_haves}"
            )
            if design_guide:
                user_msg += f"\n\nTemplate-stilguide (inkorporér i briefen):\n{design_guide}"
        else:
            system = (
                "You are a creative director producing precise writing instructions.\n\n"
                "ACCURACY REQUIREMENTS FOR THE BRIEF:\n"
                "- Include ONLY claims verifiable in the candidate profile\n"
                "- Specify leadership type (formal/functional/project) — never just 'management'\n"
                "- Address gaps honestly rather than hiding them\n"
                "- Use 'approx.' or '+' for approximations\n\n"
                "Based on the job analysis and key requirements: produce a concrete writing brief "
                "that a letter writer CAN FOLLOW to write the perfect application.\n\n"
                "The application must have 4 paragraphs:\n"
                "OPENING: [Paragraph 1 — exactly what to say about WHY THIS ROLE]\n"
                "CORE POINT: [Paragraph 2 — strongest verified match with concrete example]\n"
                "SECONDARY ANGLE OR GAP: [Paragraph 3 — another angle OR honest gap handling]\n"
                "FORWARD: [Paragraph 4 — confident close naming the company]\n"
                "KEYWORDS: [Specific words from the job posting that MUST appear in the text]\n"
                "AVOID: ['passionate about', 'I am structured', 'I would very much like to' and similar]\n\n"
                "Max 200 words. Be concrete and direct — no generic advice."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Job Analysis:\n{job_analysis}\n\n"
                f"Key requirements for the application:\n{must_haves}"
            )
            if design_guide:
                user_msg += f"\n\nTemplate style guide (incorporate into the brief):\n{design_guide}"

        provider = LiteLLMProvider(self.user_id)
        response = await provider.complete(
            agent_name=self.name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            stream=False,
            temperature=0.3,
            max_tokens=380,
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
