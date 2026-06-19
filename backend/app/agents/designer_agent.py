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
        "EGNET TIL: offentlig sektor, finans, jura, konservative brancher\n"
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
        "EGNET TIL: FM, indkøb, drift, ESG-roller\n"
        "Professionel og engagerende — balancér ATS med personlighed:\n"
        "- Stærk profiltekst der fortæller karrierefortællingen\n"
        "- Achievement-bullets med kvantificerede resultater\n"
        "- Kompetencer grupperet efter kategori\n"
        "- Naturlig tone der indbyder til interview\n"
        "- Undgå klichéer og tomme fraser"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "EGNET TIL: C-suite nærliggende roller, senior strategiske stillinger\n"
        "Autoritet og strategisk perspektiv i hvert ord:\n"
        "- Åbn med en stærk executive summary (4-5 linjer, P&L/lederskab/transformation)\n"
        "- Resultater i DKK/EUR, teamstørrelser, markedsandele, EBITDA\n"
        "- Fremhæv bestyrelseserfaring, M&A, strategiske skift\n"
        "- Formel, selvsikker og præcis tone\n"
        "- Kun lederrollernes budget/personaleansvar — udelad administrative detaljer"
    ),
    "minimal_nordic": (
        "TEMPLATE: Minimal Nordic\n"
        "EGNET TIL: tech, consulting, roller der værdsætter kortfattethed\n"
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
        "EGNET TIL: marketing, kommunikation, kreative roller\n"
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
        "EGNET TIL: formelle organisationer, offentlig sektor, advokatfirmaer\n"
        "Formel, struktureret og poleret ansøgning — 4 afsnit:\n"
        "- Afsnit 1 (HVORFOR DENNE ROLLE): Specifik årsag til ansøgning med konkret reference til jobopslaget\n"
        "- Afsnit 2 (STÆRKESTE MATCH): Én kompetence med konkret eksempel og verificeret resultat (DKK/tal)\n"
        "- Afsnit 3 (SEKUNDÆR VÆRDI ELLER GAP): Andet differentierende aspekt eller ærligt gap med bro\n"
        "- Afsnit 4 (FREMAD): 'Jeg ser frem til en dialog om, hvordan jeg kan bidrage til [VIRKSOMHED].'\n"
        "- Respektfuldt og professionelt tonefald\n"
        "- INGEN fed skrift, INGEN bullets, INGEN overskrifter\n"
        "- Afslut med 'Med venlig hilsen' på separat linje\n"
        "- Maks 450 ord total"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "EGNET TIL: senior roller, bestyrelsesnære stillinger\n"
        "Autoritet og strategisk vision fra første linje — 4 afsnit:\n"
        "- Afsnit 1 (STRATEGISK PERSPEKTIV): Impact statement om din strategiske bidrag til netop denne stilling\n"
        "- Afsnit 2 (DOKUMENTEREDE RESULTATER): P&L-ansvar, transformation og verificerede resultater i DKK\n"
        "- Afsnit 3 (KULTURMATCH ELLER GAP): Strategisk tænkning og ledelsesbeslutninger der matcher kulturen\n"
        "- Afsnit 4 (FREMAD): Konfident afslutning med virksomhedsnavnet\n"
        "- INGEN fed skrift, INGEN bullets, INGEN overskrifter\n"
        "- Afslut med 'Med venlig hilsen' på separat linje"
    ),
    "modern": (
        "TEMPLATE: Modern\n"
        "EGNET TIL: vækstvirksomheder, uformelle kulturer, tech\n"
        "Moderne og engagerende — 4 afsnit:\n"
        "- Afsnit 1 (KONKRET HOOK): Specifik, uventet åbning med reference til noget konkret fra jobopslaget\n"
        "- Afsnit 2 (STÆRKESTE MATCH): Menneskelig og direkte med verificeret eksempel og tal\n"
        "- Afsnit 3 (NYSGERRIGHED): Vis interesse for virksomheden specifikt — ikke branchen generelt\n"
        "- Afsnit 4 (FREMAD): Let og direkte afslutning med virksomhedsnavnet\n"
        "- INGEN fed skrift, INGEN bullets, INGEN overskrifter\n"
        "- Afslut med 'Med venlig hilsen' på separat linje\n"
        "- Maks 400 ord total"
    ),
    "technical": (
        "TEMPLATE: Technical\n"
        "EGNET TIL: IT, engineering, dataroller\n"
        "Teknisk præcision og dybde — 4 afsnit:\n"
        "- Afsnit 1 (TEKNISK HOOK): Nævn specifik teknologi/problem fra jobopslaget\n"
        "- Afsnit 2 (TEKNISK MATCH): Konkret projekt med teknisk kontekst, stack og verificeret resultat\n"
        "- Afsnit 3 (BREDDE ELLER GAP): Anden teknisk styrke eller ærlig gap med bro til hurtig tilegnelse\n"
        "- Afsnit 4 (FREMAD): Direkte afslutning med virksomhedsnavnet\n"
        "- INGEN fed skrift, INGEN bullets, INGEN overskrifter\n"
        "- Afslut med 'Med venlig hilsen' på separat linje"
    ),
    "graduate": (
        "TEMPLATE: Graduate\n"
        "EGNET TIL: entry-level, karriereskift\n"
        "Entusiasme og potentiale — 4 afsnit:\n"
        "- Afsnit 1 (MOTIVATION): Specifik årsag til ansøgning med reference til jobopslaget\n"
        "- Afsnit 2 (STÆRKESTE BEVIS): Uddannelse, speciale eller studiejob med verificeret opnåelse og tal\n"
        "- Afsnit 3 (TRANSFERABLE VALUE): Frivilligarbejde eller projekter der viser rollespecifikke evner\n"
        "- Afsnit 4 (FREMAD): 'Jeg ser frem til at bidrage til [VIRKSOMHED].'\n"
        "- INGEN fed skrift, INGEN bullets, INGEN overskrifter\n"
        "- Afslut med 'Med venlig hilsen' på separat linje\n"
        "- Maks 400 ord total"
    ),
}

_CV_STYLES_EN: dict[str, str] = {
    "ats_professional": (
        "TEMPLATE: ATS Professional\n"
        "BEST FOR: public sector, finance, legal, conservative industries\n"
        "Maximize ATS compatibility above all:\n"
        "- Standard section names: Profile, Work Experience, Skills, Education, Certifications\n"
        "- Include exact keywords from the job posting throughout\n"
        "- Bullet points with measurable verified results (%, numbers, team size)\n"
        "- No tables, columns, or creative formatting\n"
        "- Simple reverse-chronological order\n"
        "- Max 600 words total"
    ),
    "modern_professional": (
        "TEMPLATE: Modern Professional\n"
        "BEST FOR: FM, procurement, operations, ESG roles\n"
        "Professional and engaging — balance ATS with personality:\n"
        "- Strong profile summary telling the career story\n"
        "- Achievement bullets with quantified verified results\n"
        "- Skills grouped by category\n"
        "- Natural tone that invites interview\n"
        "- Avoid clichés and empty phrases"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "BEST FOR: C-suite adjacent, senior strategic roles\n"
        "Authority and strategic perspective in every word:\n"
        "- Open with strong executive summary (4-5 lines, P&L/leadership/transformation)\n"
        "- Results in USD/EUR, team sizes, market share, EBITDA\n"
        "- Highlight board experience, M&A, strategic pivots\n"
        "- Formal, confident, and precise tone\n"
        "- Leadership roles with budget/headcount — omit administrative details"
    ),
    "minimal_nordic": (
        "TEMPLATE: Minimal Nordic\n"
        "BEST FOR: tech, consulting, roles valuing brevity\n"
        "Scandinavian minimalism — every word counts:\n"
        "- Max 4 bullets per position\n"
        "- Shortest possible descriptions that remain precise\n"
        "- No adjectives without concrete content\n"
        "- Facts and numbers over poetic descriptions\n"
        "- Max 400 words total"
    ),
    "creative_professional": (
        "TEMPLATE: Creative Professional\n"
        "BEST FOR: marketing, communications, creative roles\n"
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
        "BEST FOR: formal organisations, public sector, law firms\n"
        "Formal, structured and polished application — 4 paragraphs:\n"
        "- Paragraph 1 (WHY THIS ROLE): Specific reason for applying with concrete reference to the job posting\n"
        "- Paragraph 2 (STRONGEST MATCH): One competency with concrete example and verified result\n"
        "- Paragraph 3 (SECONDARY VALUE OR GAP): Another differentiating angle or honest gap with bridge\n"
        "- Paragraph 4 (FORWARD): 'I look forward to discussing how I can contribute to [COMPANY].'\n"
        "- NO bold text, NO bullets, NO headers\n"
        "- Close with 'Yours sincerely' on a separate line\n"
        "- Max 450 words total"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "BEST FOR: senior roles, board-adjacent positions\n"
        "Authority and strategic vision from line one — 4 paragraphs:\n"
        "- Paragraph 1 (STRATEGIC PERSPECTIVE): Impact statement about strategic contribution to this specific role\n"
        "- Paragraph 2 (DOCUMENTED RESULTS): P&L responsibility, transformation and verified results\n"
        "- Paragraph 3 (CULTURE FIT OR GAP): Strategic thinking matching the company's direction\n"
        "- Paragraph 4 (FORWARD): Confident close naming the company specifically\n"
        "- NO bold text, NO bullets, NO headers\n"
        "- Close with 'Yours sincerely' on a separate line"
    ),
    "modern": (
        "TEMPLATE: Modern\n"
        "BEST FOR: growth companies, informal cultures, tech\n"
        "Modern and engaging — 4 paragraphs:\n"
        "- Paragraph 1 (CONCRETE HOOK): Specific, unexpected opening referencing something from the job posting\n"
        "- Paragraph 2 (STRONGEST MATCH): Human and direct with verified example and number\n"
        "- Paragraph 3 (CURIOSITY): Show interest in the company specifically — not the industry generally\n"
        "- Paragraph 4 (FORWARD): Light, direct close naming the company\n"
        "- NO bold text, NO bullets, NO headers\n"
        "- Close with 'Yours sincerely' on a separate line\n"
        "- Max 400 words total"
    ),
    "technical": (
        "TEMPLATE: Technical\n"
        "BEST FOR: IT, engineering, data roles\n"
        "Technical precision and depth — 4 paragraphs:\n"
        "- Paragraph 1 (TECHNICAL HOOK): Reference specific technology/problem from the job posting\n"
        "- Paragraph 2 (TECHNICAL MATCH): Concrete project with technical context, stack, verified result\n"
        "- Paragraph 3 (BREADTH OR GAP): Another technical strength or honest gap with rapid-learning bridge\n"
        "- Paragraph 4 (FORWARD): Direct close naming the company\n"
        "- NO bold text, NO bullets, NO headers\n"
        "- Close with 'Yours sincerely' on a separate line"
    ),
    "graduate": (
        "TEMPLATE: Graduate\n"
        "BEST FOR: entry level, career change\n"
        "Enthusiasm and potential — 4 paragraphs:\n"
        "- Paragraph 1 (MOTIVATION): Specific reason for applying with reference to the job posting\n"
        "- Paragraph 2 (STRONGEST EVIDENCE): Education, thesis or student job with verified achievement\n"
        "- Paragraph 3 (TRANSFERABLE VALUE): Volunteering or projects showing role-specific abilities\n"
        "- Paragraph 4 (FORWARD): 'I look forward to contributing to [COMPANY].'\n"
        "- NO bold text, NO bullets, NO headers\n"
        "- Close with 'Yours sincerely' on a separate line\n"
        "- Max 400 words total"
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
                "DANSKE FORMATERINGSREGLER (gælder alle templates — HÅRD BEGRÆNSNING):\n"
                "- CO2 altid som 'CO2' — aldrig CO₂ eller subscript\n"
                "- Datoer: '19. juni 2026' format\n"
                "- Valuta: 'kr.' eller 'DKK' — aldrig ',-' alene\n"
                "- Specialtegn: altid æ, ø, å — aldrig ae, oe, aa\n"
                "- Ingen markdown i output — kun ## til CV-sektionshoveder og - til bullets\n"
                "- Ingen ** * # formateringssymboler\n\n"
                "CV-FORMATERING:\n"
                "- Fed: kun stillingstitler og nøglemetrics (DKK/%) — ikke andet\n"
                "- Bullets: maks 6 per stilling i CV\n"
                "- Hvert bullet: minimum én hel sætning, ikke fragmenter\n\n"
                "ANSØGNING-FORMATERING:\n"
                "- INGEN fed skrift nogen steder\n"
                "- INGEN bullet points\n"
                "- INGEN overskrifter\n"
                "- Maks 4 afsnit\n"
                "- Afslutning altid: 'Med venlig hilsen' på separat linje\n\n"
                "Format:\n"
                "STRUKTUR: [Hvilke sektioner/afsnit i hvilken rækkefølge]\n"
                "TONE: [Præcis sproglig stil — eksempler på fraser der ER ok vs. IKKE ok]\n"
                "FORMAT: [Bulletpoints vs. prosa, sætningslængde, ordbrug]\n"
                "PRIORITETER: [Hvad der ALTID skal fremgå, hvad der kan udelades]\n"
                "FEJL DER SKAL RETTES: [Baseret på feedback nedenfor]\n\n"
                "Vær konkret og handlingsorienteret. Maks 250 ord."
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
                "FORMATTING RULES (apply to all templates — HARD CONSTRAINT):\n"
                "- CO2 always as plain text 'CO2' — never CO₂ or subscript\n"
                "- No markdown in output — only ## for CV section headers and - for bullets\n"
                "- No ** * # formatting characters\n\n"
                "CV FORMATTING:\n"
                "- Bold: job titles and key metrics (amounts/%) only — nothing else\n"
                "- Bullets: max 6 per position in CV\n"
                "- Each bullet: minimum one complete sentence, not fragments\n\n"
                "COVER LETTER FORMATTING:\n"
                "- NO bold text anywhere\n"
                "- NO bullet points\n"
                "- NO headers\n"
                "- Max 4 paragraphs\n"
                "- Closing always: 'Yours sincerely' on a separate line\n\n"
                "Format:\n"
                "STRUCTURE: [Which sections/paragraphs in which order]\n"
                "TONE: [Precise language style — examples of phrases that ARE ok vs. NOT ok]\n"
                "FORMAT: [Bullets vs. prose, sentence length, word choice]\n"
                "PRIORITIES: [What MUST always appear, what can be omitted]\n"
                "ERRORS TO FIX: [Based on feedback below]\n\n"
                "Be concrete and action-oriented. Max 250 words."
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
