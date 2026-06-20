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
    # ── Nye AI-genererede CV templates ───────────────────────────────────────────
    "nordic_executive": (
        "TEMPLATE: Nordic Executive (to-kolonne med mørk sidebar)\n"
        "EGNET TIL: FM, indkøb, drift, ESG, projektledelse, seniorroller\n"
        "KRITISK STRUKTUR — dette er et TO-KOLONNE LAYOUT:\n"
        "  VENSTRE SIDEBAR modtager KUN sektioner med disse navne (brug præcis disse navne):\n"
        "    ## Kompetencer   — liste af nøglekompetencer som bullets\n"
        "    ## Uddannelse    — grader og institutioner\n"
        "    ## Sprog         — sprogkompetencer\n"
        "    ## Certifikater  — relevante certifikater\n"
        "  HØJRE KOLONNE modtager:\n"
        "    ## Profil        — 3-4 linjer karrierefortælling\n"
        "    ## Erhvervserfaring — omvendt kronologisk\n"
        "SEKTIONSRÆKKEFØLGE I TEKSTEN:\n"
        "1. ## Profil\n"
        "2. ## Erhvervserfaring\n"
        "3. ## Kompetencer\n"
        "4. ## Uddannelse\n"
        "5. ## Sprog (kun hvis relevant)\n"
        "Brug PRÆCIS disse sektionsnavne — variationer som 'Kernekompetencer' bruges ikke.\n"
        "Maks 450 ord total. Maks 5 bullets per stilling. Maks 8 bullets i Kompetencer."
    ),
    "clean_professional": (
        "TEMPLATE: Clean Professional (en-kolonne, konservativt)\n"
        "EGNET TIL: finans, jura, offentlig sektor, rådgivning\n"
        "Rene sektioner, ATS-optimal:\n"
        "- Sektioner: ## Profil, ## Erhvervserfaring, ## Kompetencer, ## Uddannelse\n"
        "- Achievement-bullets med DKK/%-resultater\n"
        "- Formel og præcis tone\n"
        "- Maks 550 ord total"
    ),
    "modern_nordic": (
        "TEMPLATE: Modern Nordic (en-kolonne, mørk header)\n"
        "EGNET TIL: tech, marketing, FM, konsulenter\n"
        "Moderne og engagerende:\n"
        "- Sektioner: ## Profil, ## Erhvervserfaring, ## Kompetencer, ## Uddannelse\n"
        "- Stærk åbnende profiltekst\n"
        "- Aktive verber og konkrete resultater\n"
        "- Maks 500 ord total"
    ),
    "minimal_nordic": (
        "TEMPLATE: Minimal Nordic (en-kolonne, minimalistisk)\n"
        "EGNET TIL: senior roller, consulting, tech\n"
        "Skandinavisk minimalisme — hvert ord tæller:\n"
        "- Sektioner: ## Profil, ## Erhvervserfaring, ## Kompetencer, ## Uddannelse\n"
        "- Maks 4 bulletpoints per stilling\n"
        "- Ingen adjektiver uden konkret indhold\n"
        "- Fakta og tal frem for beskrivelser\n"
        "- Maks 350 ord total"
    ),
    "bold_impact": (
        "TEMPLATE: Bold Impact (en-kolonne, stor mørk header)\n"
        "EGNET TIL: salg, BD, marketing, startups\n"
        "Resultater og impact i fokus:\n"
        "- Sektioner: ## Profil, ## Erhvervserfaring, ## Kompetencer, ## Uddannelse\n"
        "- Åbn med kraftfuld profiltekst der kommunikerer impact\n"
        "- Bullets startende med stærkt handlingsverbum + konkret tal\n"
        "- Selvsikker og direkte tone\n"
        "- Maks 500 ord total"
    ),
    # ── Legacy templates (structured CV data) ────────────────────────────────────
    "ats_professional": (
        "TEMPLATE: ATS Professional\n"
        "EGNET TIL: offentlig sektor, finans, jura, konservative brancher\n"
        "Prioritér ATS-kompatibilitet over alt andet:\n"
        "- Standard sektionsnavne: Profil, Erhvervserfaring, Kompetencer, Uddannelse\n"
        "- Inkludér præcise nøgleord fra jobopslaget i teksten\n"
        "- Bulletpoints med målbare resultater (%, DKK, antal medarbejdere)\n"
        "- Ingen tabeller, spalter eller kreativ formatering\n"
        "- Maks 600 ord total"
    ),
    "modern_professional": (
        "TEMPLATE: Modern Professional\n"
        "EGNET TIL: FM, indkøb, drift, ESG-roller\n"
        "Professionel og engagerende:\n"
        "- Stærk profiltekst der fortæller karrierefortællingen\n"
        "- Achievement-bullets med kvantificerede resultater\n"
        "- Kompetencer grupperet efter kategori\n"
        "- Maks 500 ord total"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "EGNET TIL: C-suite nærliggende roller, senior strategiske stillinger\n"
        "Autoritet og strategisk perspektiv:\n"
        "- Åbn med executive summary (4-5 linjer)\n"
        "- Resultater i DKK/EUR, teamstørrelser, EBITDA\n"
        "- Formel og selvsikker tone\n"
        "- Maks 550 ord total"
    ),
    "minimal_nordic_legacy": (
        "TEMPLATE: Minimal Nordic\n"
        "Skandinavisk minimalisme — maks 4 bullets per stilling — maks 400 ord"
    ),
    "creative_professional": (
        "TEMPLATE: Creative Professional\n"
        "EGNET TIL: marketing, kommunikation, kreative roller\n"
        "Personlig stemme og differentieret udtryk — maks 500 ord"
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
    # ── New AI-generated CV templates ────────────────────────────────────────────
    "nordic_executive": (
        "TEMPLATE: Nordic Executive (two-column with dark sidebar)\n"
        "BEST FOR: FM, procurement, operations, ESG, project management, senior roles\n"
        "CRITICAL STRUCTURE — this is a TWO-COLUMN LAYOUT:\n"
        "  LEFT SIDEBAR receives ONLY sections with these exact names:\n"
        "    ## Skills        — bullet list of key competencies\n"
        "    ## Education     — degrees and institutions\n"
        "    ## Languages     — language proficiencies\n"
        "    ## Certifications — relevant certificates\n"
        "  RIGHT COLUMN receives:\n"
        "    ## Profile       — 3-4 lines career narrative\n"
        "    ## Work Experience — reverse chronological\n"
        "SECTION ORDER IN TEXT:\n"
        "1. ## Profile\n"
        "2. ## Work Experience\n"
        "3. ## Skills\n"
        "4. ## Education\n"
        "5. ## Languages (only if relevant)\n"
        "Use EXACTLY these section names.\n"
        "Max 450 words total. Max 5 bullets per position. Max 8 bullets in Skills."
    ),
    "clean_professional": (
        "TEMPLATE: Clean Professional (single column, conservative)\n"
        "BEST FOR: finance, legal, public sector, consulting\n"
        "- Sections: ## Profile, ## Work Experience, ## Skills, ## Education\n"
        "- Achievement bullets with verified numbers\n"
        "- Formal and precise tone\n"
        "- Max 550 words total"
    ),
    "modern_nordic": (
        "TEMPLATE: Modern Nordic (single column, dark header)\n"
        "BEST FOR: tech, marketing, FM, consultants\n"
        "- Sections: ## Profile, ## Work Experience, ## Skills, ## Education\n"
        "- Strong opening profile text\n"
        "- Active verbs and concrete results\n"
        "- Max 500 words total"
    ),
    "minimal_nordic": (
        "TEMPLATE: Minimal Nordic (single column, minimalist)\n"
        "BEST FOR: senior roles, consulting, tech\n"
        "- Sections: ## Profile, ## Work Experience, ## Skills, ## Education\n"
        "- Max 4 bullets per position\n"
        "- Facts and numbers only — no adjectives without content\n"
        "- Max 350 words total"
    ),
    "bold_impact": (
        "TEMPLATE: Bold Impact (single column, large dark header)\n"
        "BEST FOR: sales, BD, marketing, startups\n"
        "- Sections: ## Profile, ## Work Experience, ## Skills, ## Education\n"
        "- Open with powerful impact-focused profile\n"
        "- Bullets starting with strong action verb + concrete number\n"
        "- Max 500 words total"
    ),
    # ── Legacy templates ──────────────────────────────────────────────────────────
    "ats_professional": (
        "TEMPLATE: ATS Professional\n"
        "BEST FOR: public sector, finance, legal, conservative industries\n"
        "Maximize ATS compatibility above all:\n"
        "- Standard section names: Profile, Work Experience, Skills, Education\n"
        "- Include exact keywords from the job posting throughout\n"
        "- Bullet points with measurable verified results\n"
        "- No tables, columns, or creative formatting\n"
        "- Max 600 words total"
    ),
    "modern_professional": (
        "TEMPLATE: Modern Professional\n"
        "BEST FOR: FM, procurement, operations, ESG roles\n"
        "- Strong profile summary telling the career story\n"
        "- Achievement bullets with quantified results\n"
        "- Max 500 words total"
    ),
    "executive": (
        "TEMPLATE: Executive\n"
        "BEST FOR: C-suite adjacent, senior strategic roles\n"
        "- Open with strong executive summary (4-5 lines)\n"
        "- Results in amounts, team sizes, EBITDA\n"
        "- Formal, confident, precise tone\n"
        "- Max 550 words total"
    ),
    "minimal_nordic_legacy": (
        "TEMPLATE: Minimal Nordic — max 4 bullets per position — max 400 words"
    ),
    "creative_professional": (
        "TEMPLATE: Creative Professional\n"
        "BEST FOR: marketing, communications, creative roles\n"
        "- Personal voice and narrative flow — max 500 words"
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
                "KONTAKTINFO-DUPLIKERING:\n"
                "Templatene nordic_executive, modern_nordic, bold_impact og clean_professional "
                "viser kontaktinfo automatisk i headeren og/eller sidebaren. "
                "Instruér IKKE skribenten om at bruge en separat ## Kontakt-sektion i CV-teksten — "
                "det skaber duplikering.\n\n"
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
                "CONTACT DEDUPLICATION:\n"
                "The templates nordic_executive, modern_nordic, bold_impact and clean_professional "
                "display contact info automatically in the header and/or sidebar. "
                "Do NOT instruct the writer to use a separate ## Contact section in the CV text — "
                "this creates duplication.\n\n"
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
