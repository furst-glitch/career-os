"""
DesignerAgent — oversætter valgt template til konkrete stil-instruktioner.

Producerer en template-specifik stilguide der bruges af ReviewBoardAgent
og ApplicationAgent til at formatere det endelige dokument.

Input:
  template:         str  ('ats_professional' | 'modern_professional' | 'executive' |
                          'minimal_nordic' | 'creative_professional' |
                          'corporate' | 'modern' | 'technical' | 'graduate')
  doc_type:         str  ('cv' | 'cover_letter')
  language:         str  ('da' | 'en')
  critic_feedback:  str  (top-5 forbedringer fra CriticAgent — valgfri)

Output: AgentResult.content = præcis stilguide til næste agent i pipeline
"""
from app.agents.base import AgentResult, AgentUsage, BaseAgent
from app.providers.litellm_provider import LiteLLMProvider

# ── Template stil-profiler ────────────────────────────────────────────────────

_CV_STYLES_DA: dict[str, str] = {
    "ats_professional": (
        "TEMPLATE: ATS Professional\n"
        "Prioritér ATS-kompatibilitet over alt andet:\n"
        "- Standard sektionsnavne: Profil, Erhvervserfaring, Kompetencer, Uddannelse, Certifikater\n"
        "- Inkludér præcise nøgleord fra jobopslaget i teksten\n"
        "- Bulletpoints med målbare resultater (%, DKK, antal medarbejdere)\n"
        "- Ingen tabeller, spalter eller kreativ formatering\n"
        "- Enkel kronologisk rækkefølge\n"
        "- Maks 600 ord total"
    ),
    "modern_professional": (
        "TEMPLATE: Modern Professional\n"
        "Professionel og engagerende — balancér ATS med personlighed:\n"
        "- Stærk profiltekst der fortæller karrierefortællingen\n"
        "- Achievement-bullets med kvantificerede resultater\n"
        "- Kompetencer grupperet efter kategori\n"
        "- Naturlig tone der indbyder til interview\n"
        "- Undgå klichéer og tomme fraser"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "Autoritet og strategisk perspektiv i hvert ord:\n"
        "- Åbn med en stærk executive summary (4-5 linjer, P&L/lederskab/transformation)\n"
        "- Resultater i DKK/EUR, teamstørrelser, markedsandele, EBITDA\n"
        "- Fremhæv bestyrelseserfaring, M&A, strategiske skift\n"
        "- Formel, selvsikker og præcis tone\n"
        "- Kun lederrollernes budget/personaleansvar — udelad administrative detaljer"
    ),
    "minimal_nordic": (
        "TEMPLATE: Minimal Nordic\n"
        "Skandinavisk minimalisme — hvert ord tæller:\n"
        "- Maks 4 bulletpoints per stilling\n"
        "- Korteste mulige beskrivelser der stadig er præcise\n"
        "- Ingen adjektiver uden konkret indhold\n"
        "- Fakta og tal frem for poetiske beskrivelser\n"
        "- Hvidt rum er en feature, ikke en fejl\n"
        "- Maks 400 ord total"
    ),
    "creative_professional": (
        "TEMPLATE: Creative Professional\n"
        "Personlig stemme og differentieret udtryk:\n"
        "- Åbn med en profiltekst der viser personlighed og passion\n"
        "- Narrativt flow der forbinder erfaringerne\n"
        "- Brug aktive og levende verber\n"
        "- Vis unikke projekter og kreative løsninger\n"
        "- Stadig professionel men tydeligt individuelt præg"
    ),
}

_APP_STYLES_DA: dict[str, str] = {
    "corporate": (
        "TEMPLATE: Corporate\n"
        "Formel, struktureret og poleret ansøgning:\n"
        "- Klassisk struktur: åbning → kompetencematch → kulturfit → afslutning\n"
        "- Respektfuldt og professionelt tonefald\n"
        "- Undgå slang og alt for personlige referencer\n"
        "- Tydeligt hierarki af argumenter\n"
        "- Afslut med klar call-to-action og 'Med venlig hilsen'"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "Autoritet og strategisk vision fra første linje:\n"
        "- Åbn med et impact statement om din strategiske bidrag\n"
        "- Vis P&L-ansvar, transformation og resultater i DKK\n"
        "- Strategisk tænkning og ledelsesbeslutninger i centrum\n"
        "- Kortfattet og konfident — ingen unødvendige forklaringer\n"
        "- 3 afsnit maks: impact, strategi, call-to-action"
    ),
    "modern": (
        "TEMPLATE: Modern\n"
        "Moderne og engagerende — undgå klichéer:\n"
        "- Fang med en stærk, uventet åbning\n"
        "- Menneskelig og direkte tone\n"
        "- Specifikke eksempler frem for generelle påstande\n"
        "- Vis nysgerrighed og interesse for virksomheden\n"
        "- Let og flydende læsning"
    ),
    "technical": (
        "TEMPLATE: Technical\n"
        "Teknisk præcision og dybde:\n"
        "- Nævn specifikke teknologier, frameworks, metodologier ved navn\n"
        "- Konkrete projekter med teknisk kontekst og resultater\n"
        "- Vis problemforståelse og løsningsarkitektur\n"
        "- Undgå generelle 'team player'-sætninger\n"
        "- Fremhæv open source, certifikater, teknisk specialisering"
    ),
    "graduate": (
        "TEMPLATE: Graduate\n"
        "Entusiasme og potentiale for entry-level:\n"
        "- Fremhæv uddannelse, specialeprojekt, relevante kurser\n"
        "- Transferable skills fra studiejob, frivilligarbejde, projekter\n"
        "- Vis læringsiveren og motivationen for branchen\n"
        "- Konkrete opnåelser fra studietiden med tal\n"
        "- Afslut med stærk fremadrettet sætning om hvad du vil bidrage med"
    ),
}

_CV_STYLES_EN: dict[str, str] = {
    "ats_professional": (
        "TEMPLATE: ATS Professional\n"
        "Maximize ATS compatibility above all:\n"
        "- Standard section names: Profile, Work Experience, Skills, Education, Certifications\n"
        "- Include exact keywords from the job posting throughout\n"
        "- Bullet points with measurable results (%, numbers, team size)\n"
        "- No tables, columns, or creative formatting\n"
        "- Simple reverse-chronological order\n"
        "- Max 600 words total"
    ),
    "modern_professional": (
        "TEMPLATE: Modern Professional\n"
        "Professional and engaging — balance ATS with personality:\n"
        "- Strong profile summary telling the career story\n"
        "- Achievement bullets with quantified results\n"
        "- Skills grouped by category\n"
        "- Natural tone that invites interview\n"
        "- Avoid clichés and empty phrases"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "Authority and strategic perspective in every word:\n"
        "- Open with strong executive summary (4-5 lines, P&L/leadership/transformation)\n"
        "- Results in USD/EUR, team sizes, market share, EBITDA\n"
        "- Highlight board experience, M&A, strategic pivots\n"
        "- Formal, confident, and precise tone\n"
        "- Leadership roles with budget/headcount — omit administrative details"
    ),
    "minimal_nordic": (
        "TEMPLATE: Minimal Nordic\n"
        "Scandinavian minimalism — every word counts:\n"
        "- Max 4 bullets per position\n"
        "- Shortest possible descriptions that remain precise\n"
        "- No adjectives without concrete content\n"
        "- Facts and numbers over poetic descriptions\n"
        "- Max 400 words total"
    ),
    "creative_professional": (
        "TEMPLATE: Creative Professional\n"
        "Personal voice and differentiated expression:\n"
        "- Open with a profile that shows personality and passion\n"
        "- Narrative flow connecting experiences\n"
        "- Active and vivid verbs\n"
        "- Show unique projects and creative solutions\n"
        "- Professional but with clear individual character"
    ),
}

_APP_STYLES_EN: dict[str, str] = {
    "corporate": (
        "TEMPLATE: Corporate\n"
        "Formal, structured and polished application:\n"
        "- Classic structure: opening → skill match → cultural fit → closing\n"
        "- Respectful and professional tone\n"
        "- Clear hierarchy of arguments\n"
        "- Close with clear call-to-action and 'Yours sincerely'"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "Authority and strategic vision from line one:\n"
        "- Open with an impact statement about strategic contribution\n"
        "- Show P&L responsibility, transformation, and results in $\n"
        "- Strategic thinking and leadership decisions front and center\n"
        "- Concise and confident — no unnecessary explanations\n"
        "- Max 3 paragraphs: impact, strategy, call-to-action"
    ),
    "modern": (
        "TEMPLATE: Modern\n"
        "Modern and engaging — avoid clichés:\n"
        "- Hook with a strong, unexpected opening\n"
        "- Human and direct tone\n"
        "- Specific examples over general claims\n"
        "- Show genuine curiosity about the company\n"
        "- Light and flowing to read"
    ),
    "technical": (
        "TEMPLATE: Technical\n"
        "Technical precision and depth:\n"
        "- Name specific technologies, frameworks, methodologies\n"
        "- Concrete projects with technical context and results\n"
        "- Show problem understanding and solution architecture\n"
        "- Avoid generic 'team player' sentences\n"
        "- Highlight open source, certifications, technical specialization"
    ),
    "graduate": (
        "TEMPLATE: Graduate\n"
        "Enthusiasm and potential for entry-level:\n"
        "- Highlight education, thesis, relevant coursework\n"
        "- Transferable skills from part-time work, volunteering, projects\n"
        "- Show eagerness to learn and motivation for the industry\n"
        "- Concrete achievements from studies with numbers\n"
        "- Close with forward-looking statement about what you'll contribute"
    ),
}


def _get_style_guide(template: str, doc_type: str, language: str) -> str:
    if language == "da":
        if doc_type == "cv":
            return _CV_STYLES_DA.get(template, _CV_STYLES_DA["ats_professional"])
        return _APP_STYLES_DA.get(template, _APP_STYLES_DA["corporate"])
    if doc_type == "cv":
        return _CV_STYLES_EN.get(template, _CV_STYLES_EN["ats_professional"])
    return _APP_STYLES_EN.get(template, _APP_STYLES_EN["corporate"])


class DesignerAgent(BaseAgent):
    name = "designer_agent"

    async def run(self, input_data: dict) -> AgentResult:
        """
        Producerer template-specifik stilguide og tilpasser dokumentstrukturen.

        input_data:
          template:        str  (template-navn)
          doc_type:        str  ('cv' | 'cover_letter')
          language:        str  ('da' | 'en')
          critic_feedback: str  (top-5 forbedringer fra CriticAgent)
          draft:           str  (nuværende udkast — valgfrit, til kontekst)
        """
        template = input_data.get("template", "ats_professional")
        doc_type = input_data.get("doc_type", "cv")
        language = input_data.get("language", "da")
        critic_feedback = input_data.get("critic_feedback", "")
        draft = input_data.get("draft", "")[:1000]

        style_guide = _get_style_guide(template, doc_type, language)
        da = language == "da"
        doc_label = ("CV" if doc_type == "cv" else "ansøgning") if da else ("CV" if doc_type == "cv" else "application")

        if da:
            system = (
                "Du er en dokumentdesigner og præsentationsekspert. "
                f"Du har modtaget en template-stilguide og skal producere PRÆCISE skriveinstruktioner "
                f"der sikrer {doc_label}en lever op til templatens krav. "
                "Instruktionerne bruges af den næste agent til at skrive det endelige dokument.\n\n"
                "Format:\n"
                "STRUKTUR: [Hvilke sektioner/afsnit i hvilken rækkefølge]\n"
                "TONE: [Præcis sproglig stil — eksempler på fraser der ER ok vs. IKKE ok]\n"
                "FORMAT: [Bulletpoints vs. prosa, sætningslængde, ordbrug]\n"
                "PRIORITETER: [Hvad der ALTID skal fremgå, hvad der kan udelades]\n"
                "FEJL DER SKAL RETTES: [Baseret på feedback nedenfor]\n\n"
                "Vær konkret og handlingsorienteret. Maks 200 ord."
            )
            user_msg = f"{style_guide}\n\nFeedback der skal inkorporeres:\n{critic_feedback}"
            if draft:
                user_msg += f"\n\nNuværende udkast (uddrag til kontekst):\n{draft}"
        else:
            system = (
                "You are a document designer and presentation expert. "
                f"You have received a template style guide and must produce PRECISE writing instructions "
                f"ensuring the {doc_label} meets the template's requirements. "
                "These instructions are used by the next agent to write the final document.\n\n"
                "Format:\n"
                "STRUCTURE: [Which sections/paragraphs in which order]\n"
                "TONE: [Precise language style — examples of phrases that ARE ok vs. NOT ok]\n"
                "FORMAT: [Bullets vs. prose, sentence length, word choice]\n"
                "PRIORITIES: [What MUST always appear, what can be omitted]\n"
                "ERRORS TO FIX: [Based on feedback below]\n\n"
                "Be concrete and action-oriented. Max 200 words."
            )
            user_msg = f"{style_guide}\n\nFeedback to incorporate:\n{critic_feedback}"
            if draft:
                user_msg += f"\n\nCurrent draft (excerpt for context):\n{draft}"

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
        return AgentResult(content=content, usage=usage, metadata={"template": template, "style_guide": style_guide})
