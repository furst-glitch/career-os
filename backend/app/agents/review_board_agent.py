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
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        job_description = input_data.get("job_description", "")[:1500]
        language = input_data.get("language", "da")

        if language == "da":
            system = (
                "Du er chefredaktør og producerer den endelige udgave af et CV. "
                "Du modtager et udkast og en prioriteret liste af forbedringer. "
                "Din opgave: omskriv udkastet så det implementerer ALLE forbedringer og bliver markant stærkere. "
                "Bevar kandidatens reelle erfaringer og informationer — tilføj eller opfind IKKE facts. "
                "Output: KUN det forbedrede CV. Ingen kommentarer om hvad du har ændret.\n\n"
                "VIGTIGT: Skriv altid med korrekte danske bogstaver: æ, ø, å, Æ, Ø, Å. Brug IKKE ae, oe, aa.\n"
                "Brug IKKE markdown-formatering (ingen **, *, # eller andre symboler). Skriv ren tekst."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Jobbeskrivelse (uddrag):\n{job_description}\n\n"
                f"CV-udkast:\n{draft}\n\n"
                f"Forbedringer der SKAL implementeres:\n{critic_feedback}"
            )
        else:
            system = (
                "You are editor-in-chief producing the final version of a CV. "
                "You receive a draft and a prioritized list of improvements. "
                "Your task: rewrite the draft to implement ALL improvements and make it markedly stronger. "
                "Preserve the candidate's real experiences and information — do NOT add or invent facts. "
                "Output: ONLY the improved CV. No commentary about what you changed.\n\n"
                "Do NOT use markdown formatting (no **, *, # or other symbols). Write plain text."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Job Description (excerpt):\n{job_description}\n\n"
                f"CV Draft:\n{draft}\n\n"
                f"Improvements to implement:\n{critic_feedback}"
            )

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
        job_title = input_data.get("job_title", "")
        job_company = input_data.get("job_company", "")
        language = input_data.get("language", "da")

        if language == "da":
            system = (
                "Du er kreativ direktør og udformer præcise skriveinstruktioner. "
                "Baseret på jobanalysen og de vigtigste krav: producér en konkret skrivebrief "
                "som en ansøgningsskriver KAN FØLGE for at skrive den perfekte ansøgning.\n\n"
                "Format:\n"
                "ÅBNING: [Præcist hvad første afsnit skal sige og hvilken tone]\n"
                "KERNEPUNKTER: [3 specifikke argumenter der SKAL fremgå med eksempler]\n"
                "AFSLUTNING: [Hvad afslutningen skal indeholde og call-to-action]\n"
                "NØGLEORD: [Specifikke ord der SKAL stå i teksten]\n"
                "UNDGÅ: [Klichéer og fraser der svækker ansøgningen]\n\n"
                "Maks 200 ord. Vær konkret og direkte — ingen generelle råd."
            )
            user_msg = (
                f"Stilling: {job_title} hos {job_company}\n\n"
                f"Jobanalyse:\n{job_analysis}\n\n"
                f"Vigtigste krav til ansøgningen:\n{must_haves}"
            )
        else:
            system = (
                "You are a creative director producing precise writing instructions. "
                "Based on the job analysis and key requirements: produce a concrete writing brief "
                "that a letter writer CAN FOLLOW to write the perfect application.\n\n"
                "Format:\n"
                "OPENING: [Exactly what the first paragraph should say and tone]\n"
                "CORE POINTS: [3 specific arguments that MUST appear with examples]\n"
                "CLOSING: [What the closing should contain and call-to-action]\n"
                "KEYWORDS: [Specific words that MUST appear in the text]\n"
                "AVOID: [Clichés and phrases that weaken the application]\n\n"
                "Max 200 words. Be concrete and direct — no generic advice."
            )
            user_msg = (
                f"Position: {job_title} at {job_company}\n\n"
                f"Job Analysis:\n{job_analysis}\n\n"
                f"Key requirements for the application:\n{must_haves}"
            )

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
