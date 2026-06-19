"""
5 CV PDF templates using fpdf2.
Each function accepts a cv_data dict and returns PDF bytes.

cv_data keys:
  profile      → {display_name, ...}
  master_cv    → {target_title, summary, ...}
  experiences  → [{title, company, period_start, period_end, is_current, description, achievements}, ...]
  skills       → [{name, category, level}, ...]
  educations   → [{degree, institution, period_start, period_end}, ...]
  certifications → [{name, issuer, issued_at}, ...]
"""
from __future__ import annotations

import textwrap
from datetime import datetime


def _s(text: str) -> str:
    """Latin-1 safe sanitiser for fpdf Helvetica/Times.
    æ/ø/å/Æ/Ø/Å er i Latin-1 — konverter dem ALDRIG til ae/oe/aa."""
    if not text:
        return ""
    return (
        str(text)
        .replace("—", "-").replace("–", "-").replace("•", "-")
        .replace("'", "'").replace("'", "'")
        .replace(""", '"').replace(""", '"')
        .encode("latin-1", errors="replace").decode("latin-1")
    )


def _period(exp: dict) -> str:
    start = (exp.get("period_start") or "")[:7]
    end = "Nu" if exp.get("is_current") else (exp.get("period_end") or "")[:7]
    return f"{start} – {end}" if start else ""


def _today() -> str:
    return datetime.now().strftime("%d/%m/%Y")


# ── 1. ATS Professional ──────────────────────────────────────────────────────

def cv_pdf_ats(cv_data: dict) -> bytes:
    """Clean B&W single-column – maximum ATS parser compatibility."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_margins(20, 22, 20)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    _prof = cv_data.get("profile") or {}
    name = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    # Name
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 9, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if title:
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5, "  |  ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    def section(label: str) -> None:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 5, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(2)

    def body_wrap(text: str, width: int = 110) -> None:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        for wl in textwrap.wrap(text, width) or [""]:
            pdf.cell(0, 4.8, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if summary:
        section("Professional Summary")
        body_wrap(summary)

    exps = cv_data.get("experiences") or []
    if exps:
        section("Experience")
        for exp in exps:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, _s(f"{exp.get('title','')} | {exp.get('company','')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            period = _s(_period(exp))
            if period:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(60, 60, 60)
                pdf.cell(0, 4, period, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)
            if exp.get("description"):
                body_wrap(exp["description"])
            for ach in (exp.get("achievements") or [])[:4]:
                body_wrap(f"- {ach}")
            pdf.ln(2)

    skills = cv_data.get("skills") or []
    if skills:
        section("Skills")
        names = [_s(s.get("name", "")) for s in skills if s.get("name")]
        body_wrap("  |  ".join(names))

    edus = cv_data.get("educations") or []
    if edus:
        section("Education")
        for edu in edus:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, _s(f"{edu.get('degree','')} – {edu.get('institution','')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            ps = (edu.get("period_start") or "")[:7]
            pe = (edu.get("period_end") or "")[:7]
            if ps:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(60, 60, 60)
                pdf.cell(0, 4, _s(f"{ps} – {pe}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)
            pdf.ln(1.5)

    certs = cv_data.get("certifications") or []
    if certs:
        section("Certifications")
        for cert in certs:
            issued = (cert.get("issued_at") or "")[:7]
            line = f"- {cert.get('name','')} – {cert.get('issuer','')}"
            if issued:
                line += f" ({issued})"
            body_wrap(line)

    # Footer
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-13)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, _today(), align="C")

    return bytes(pdf.output())


# ── 2. Modern Professional ───────────────────────────────────────────────────

def cv_pdf_modern(cv_data: dict) -> bytes:
    """Navy sidebar (35%) + white main column, blue accents."""
    from fpdf import FPDF

    SB_X = 0          # sidebar left edge (full-bleed)
    SB_W = 68         # sidebar width mm
    MAIN_X = 72       # main column left
    MAIN_W = 123      # main column width (210 - 72 - 15)
    TOP_Y = 15
    MARGIN_V = 14

    # Navy, accent blue, white
    NAV = (15, 40, 80)
    ACC = (59, 130, 246)
    WHT = (255, 255, 255)
    DRK = (15, 23, 42)
    GRY = (100, 116, 139)

    pdf = FPDF()
    pdf.set_margins(0, 0, 0)
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    # Full-page sidebar background
    pdf.set_fill_color(*NAV)
    pdf.rect(SB_X, 0, SB_W, 297, "F")

    _prof = cv_data.get("profile") or {}
    name = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title_str = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    # ── Sidebar ──
    y = TOP_Y

    def sb_cell(text: str, font: str, size: float, color: tuple, h: float = 5.5) -> None:
        nonlocal y
        pdf.set_font("Helvetica", font, size)
        pdf.set_text_color(*color)
        pdf.set_xy(MARGIN_V, y)
        pdf.multi_cell(SB_W - MARGIN_V * 2, h, _s(text))
        y = pdf.get_y()

    def sb_section(label: str) -> None:
        nonlocal y
        y += 4
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*ACC)
        pdf.set_xy(MARGIN_V, y)
        pdf.cell(SB_W - MARGIN_V * 2, 5, label.upper())
        y += 5
        pdf.set_draw_color(*ACC)
        pdf.set_line_width(0.3)
        pdf.line(MARGIN_V, y, SB_W - MARGIN_V, y)
        y += 2.5

    sb_cell(name, "B", 14, WHT, 7)
    y += 1
    if title_str:
        sb_cell(title_str, "", 9, ACC, 5)
    y += 3

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        sb_section("Contact")
        for c in contact_parts:
            sb_cell(c, "", 8, WHT, 4.5)

    skills = cv_data.get("skills") or []
    if skills:
        sb_section("Skills")
        for sk in skills[:12]:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*WHT)
            pdf.set_xy(MARGIN_V, y)
            pdf.cell(SB_W - MARGIN_V * 2, 5, _s(f"• {sk.get('name','')}"))
            y += 5

    edus = cv_data.get("educations") or []
    if edus:
        sb_section("Education")
        for edu in edus:
            sb_cell(f"{edu.get('degree','')}", "B", 8, WHT, 5)
            sb_cell(edu.get("institution", ""), "", 7.5, (180, 200, 230), 4.5)
            ps = (edu.get("period_start") or "")[:7]
            pe = (edu.get("period_end") or "")[:7]
            if ps:
                sb_cell(f"{ps} – {pe}", "", 7, (150, 170, 210), 4)

    certs = cv_data.get("certifications") or []
    if certs:
        sb_section("Certifications")
        for cert in certs:
            sb_cell(cert.get("name", ""), "", 8, WHT, 4.5)
            if cert.get("issuer"):
                sb_cell(cert["issuer"], "", 7, (180, 200, 230), 4)

    # ── Main column ──
    def section_main(label: str, my: list) -> None:
        my[0] += 4
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ACC)
        pdf.set_xy(MAIN_X, my[0])
        pdf.cell(MAIN_W, 6, label.upper())
        my[0] += 6
        pdf.set_draw_color(*ACC)
        pdf.set_line_width(0.4)
        pdf.line(MAIN_X, my[0], MAIN_X + MAIN_W, my[0])
        my[0] += 3
        pdf.set_text_color(*DRK)

    def main_wrap(text: str, my: list, indent: int = 0) -> None:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*DRK)
        w = MAIN_W - indent
        for wl in textwrap.wrap(_s(text), int(w * 1.5)) or [""]:
            pdf.set_xy(MAIN_X + indent, my[0])
            pdf.cell(w, 4.8, _s(wl))
            my[0] += 4.8

    my = [TOP_Y]

    # Page overflow helper
    def check_overflow(my: list, needed: float = 20) -> None:
        if my[0] + needed > 277:
            pdf.add_page()
            pdf.set_fill_color(*NAV)
            pdf.rect(SB_X, 0, SB_W, 297, "F")
            my[0] = TOP_Y

    if summary:
        section_main("Profile", my)
        main_wrap(summary, my)

    exps = cv_data.get("experiences") or []
    if exps:
        section_main("Experience", my)
        for exp in exps:
            check_overflow(my, 25)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DRK)
            pdf.set_xy(MAIN_X, my[0])
            pdf.cell(MAIN_W, 5, _s(f"{exp.get('title','')}"))
            my[0] += 5
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(*GRY)
            pdf.set_xy(MAIN_X, my[0])
            co = _s(exp.get("company", ""))
            period = _s(_period(exp))
            pdf.cell(MAIN_W / 2, 4.5, co)
            pdf.set_xy(MAIN_X + MAIN_W / 2, my[0])
            pdf.cell(MAIN_W / 2, 4.5, period, align="R")
            my[0] += 4.5
            pdf.set_text_color(*DRK)
            if exp.get("description"):
                main_wrap(exp["description"], my)
            for ach in (exp.get("achievements") or [])[:3]:
                main_wrap(f"• {ach}", my, indent=3)
            my[0] += 2

    # Footer
    pdf.set_y(-12)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRY)
    pdf.set_x(MAIN_X)
    pdf.cell(MAIN_W, 5, _today(), align="R")

    return bytes(pdf.output())


# ── 3. Executive ─────────────────────────────────────────────────────────────

def cv_pdf_executive(cv_data: dict) -> bytes:
    """Wide margins, Times headings, gold accent lines — premium leadership look."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    GOLD = (160, 100, 30)
    DARK = (10, 15, 35)
    GREY = (90, 100, 120)

    pdf = FPDF()
    pdf.set_margins(28, 26, 28)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=24)

    _prof = cv_data.get("profile") or {}
    name = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title_str = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    # Name
    pdf.set_font("Times", "B", 24)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 12, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    if title_str:
        pdf.set_font("Times", "I", 12)
        pdf.set_text_color(*GREY)
        pdf.cell(0, 6, title_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        pdf.set_font("Times", "", 9)
        pdf.set_text_color(*GREY)
        pdf.cell(0, 5, "  ·  ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    # Gold double rule
    pdf.ln(3)
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.8)
    pdf.line(28, pdf.get_y(), 182, pdf.get_y())
    pdf.ln(0.8)
    pdf.set_line_width(0.2)
    pdf.line(28, pdf.get_y(), 182, pdf.get_y())
    pdf.ln(5)

    def section(label: str) -> None:
        pdf.ln(4)
        pdf.set_font("Times", "B", 11)
        pdf.set_text_color(*GOLD)
        pdf.cell(0, 6, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(*GOLD)
        pdf.set_line_width(0.3)
        pdf.line(28, pdf.get_y(), 182, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(*DARK)

    def body_wrap(text: str, width: int = 95) -> None:
        pdf.set_font("Times", "", 10)
        pdf.set_text_color(*DARK)
        for wl in textwrap.wrap(text, width) or [""]:
            pdf.cell(0, 5.5, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if summary:
        section("Executive Summary")
        body_wrap(summary)

    exps = cv_data.get("experiences") or []
    if exps:
        section("Professional Experience")
        for exp in exps:
            pdf.set_font("Times", "B", 10.5)
            pdf.set_text_color(*DARK)
            pdf.cell(0, 6, _s(f"{exp.get('title','')}  ·  {exp.get('company','')}"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            period = _s(_period(exp))
            if period:
                pdf.set_font("Times", "I", 9.5)
                pdf.set_text_color(*GREY)
                pdf.cell(0, 5, period, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(*DARK)
            if exp.get("description"):
                body_wrap(exp["description"])
            for ach in (exp.get("achievements") or [])[:4]:
                body_wrap(f"–  {ach}")
            pdf.ln(3)

    skills = cv_data.get("skills") or []
    if skills:
        section("Core Competencies")
        names = [_s(s.get("name", "")) for s in skills if s.get("name")]
        # 3-column skill grid
        cols = [names[i::3] for i in range(3)]
        col_w = (182 - 28) / 3
        start_y = pdf.get_y()
        for ci, col in enumerate(cols):
            pdf.set_xy(28 + ci * col_w, start_y)
            for sk in col:
                pdf.set_font("Times", "", 10)
                pdf.cell(col_w, 5.5, _s(f"• {sk}"))
                pdf.set_xy(28 + ci * col_w, pdf.get_y() + 5.5)
        end_y = max(start_y + len(c) * 5.5 for c in cols if c)
        pdf.set_y(end_y)

    edus = cv_data.get("educations") or []
    if edus:
        section("Education")
        for edu in edus:
            pdf.set_font("Times", "B", 10.5)
            pdf.set_text_color(*DARK)
            pdf.cell(0, 6, _s(f"{edu.get('degree','')}  ·  {edu.get('institution','')}"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            ps = (edu.get("period_start") or "")[:7]
            pe = (edu.get("period_end") or "")[:7]
            if ps:
                pdf.set_font("Times", "I", 9.5)
                pdf.set_text_color(*GREY)
                pdf.cell(0, 5, _s(f"{ps} – {pe}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(*DARK)
            pdf.ln(1.5)

    certs = cv_data.get("certifications") or []
    if certs:
        section("Certifications")
        for cert in certs:
            issued = (cert.get("issued_at") or "")[:7]
            line = f"–  {cert.get('name','')}  |  {cert.get('issuer','')}"
            if issued:
                line += f"  ({issued})"
            body_wrap(line)

    # Double gold footer rule
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-20)
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.2)
    pdf.line(28, pdf.get_y(), 182, pdf.get_y())
    pdf.ln(0.6)
    pdf.set_line_width(0.8)
    pdf.line(28, pdf.get_y(), 182, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Times", "I", 8)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, _today(), align="C")

    return bytes(pdf.output())


# ── 4. Minimal Nordic ────────────────────────────────────────────────────────

def cv_pdf_nordic(cv_data: dict) -> bytes:
    """Generous whitespace, light gray tones, minimalist Scandinavian design."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    DARK = (25, 35, 50)
    MED = (80, 95, 115)
    LGT = (180, 195, 210)

    pdf = FPDF()
    pdf.set_margins(26, 28, 26)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=26)

    _prof = cv_data.get("profile") or {}
    name = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title_str = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    # Name — light weight, large
    pdf.set_font("Helvetica", "", 22)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 11, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if title_str:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*MED)
        pdf.cell(0, 6, title_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LGT)
        pdf.cell(0, 5, "   ·   ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(3)
    pdf.set_draw_color(*LGT)
    pdf.set_line_width(0.2)
    pdf.line(26, pdf.get_y(), 184, pdf.get_y())
    pdf.ln(6)

    def section(label: str) -> None:
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MED)
        pdf.cell(0, 5, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(*LGT)
        pdf.set_line_width(0.2)
        pdf.line(26, pdf.get_y(), 184, pdf.get_y())
        pdf.ln(4)
        pdf.set_text_color(*DARK)

    def body_wrap(text: str, size: float = 9.5, width: int = 105) -> None:
        pdf.set_font("Helvetica", "", size)
        pdf.set_text_color(*DARK)
        for wl in textwrap.wrap(text, width) or [""]:
            pdf.cell(0, 5.5, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if summary:
        section("Summary")
        body_wrap(summary, 9.5)

    exps = cv_data.get("experiences") or []
    if exps:
        section("Experience")
        for exp in exps:
            period = _s(_period(exp))
            # Period in left margin
            if period:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*MED)
                pdf.cell(38, 5.5, period, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*DARK)
            role_x = 26 + 40
            pdf.set_x(role_x)
            pdf.cell(0, 5.5, _s(f"{exp.get('title','')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(role_x)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MED)
            pdf.cell(0, 5, _s(exp.get("company", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*DARK)
            if exp.get("description"):
                pdf.set_x(role_x)
                pdf.set_font("Helvetica", "", 9)
                for wl in textwrap.wrap(_s(exp["description"]), 80) or [""]:
                    pdf.set_x(role_x)
                    pdf.cell(0, 4.8, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            for ach in (exp.get("achievements") or [])[:3]:
                pdf.set_x(role_x)
                pdf.set_font("Helvetica", "", 8.5)
                pdf.cell(0, 4.5, _s(f"— {ach}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(3)

    skills = cv_data.get("skills") or []
    if skills:
        section("Skills")
        names = [_s(s.get("name", "")) for s in skills if s.get("name")]
        body_wrap("   ·   ".join(names), 9, 110)

    edus = cv_data.get("educations") or []
    if edus:
        section("Education")
        for edu in edus:
            ps = (edu.get("period_start") or "")[:7]
            pe = (edu.get("period_end") or "")[:7]
            if ps:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*MED)
                pdf.cell(38, 5.5, _s(f"{ps} – {pe}"), new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.set_x(26 + 40)
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*DARK)
            pdf.cell(0, 5.5, _s(edu.get("degree", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(26 + 40)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MED)
            pdf.cell(0, 5, _s(edu.get("institution", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1.5)

    certs = cv_data.get("certifications") or []
    if certs:
        section("Certifications")
        for cert in certs:
            issued = (cert.get("issued_at") or "")[:7]
            line = f"{cert.get('name','')}  ·  {cert.get('issuer','')}"
            if issued:
                line += f"  ·  {issued}"
            body_wrap(line)

    # Minimal footer
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-13)
    pdf.set_draw_color(*LGT)
    pdf.set_line_width(0.2)
    pdf.line(26, pdf.get_y(), 184, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*LGT)
    pdf.cell(0, 4, _today(), align="C")

    return bytes(pdf.output())


# ── 5. Creative Professional ─────────────────────────────────────────────────

def cv_pdf_creative(cv_data: dict) -> bytes:
    """Teal header band, modern layout, professional not garish."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    TEAL = (13, 148, 136)
    TEAL_D = (10, 100, 90)
    DARK = (15, 23, 42)
    GRY = (100, 116, 139)
    WHT = (255, 255, 255)
    TEAL_L = (204, 240, 237)

    pdf = FPDF()
    pdf.set_margins(0, 0, 0)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    _prof = cv_data.get("profile") or {}
    name = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title_str = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    # Header band
    HEADER_H = 38
    pdf.set_fill_color(*TEAL)
    pdf.rect(0, 0, 210, HEADER_H, "F")

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*WHT)
    pdf.set_xy(18, 10)
    pdf.cell(174, 10, name)

    if title_str:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(200, 240, 235)
        pdf.set_xy(18, 22)
        pdf.cell(174, 8, title_str)

    # Thin accent strip
    pdf.set_fill_color(*TEAL_D)
    pdf.rect(0, HEADER_H, 210, 2.5, "F")

    # Body starts below header
    pdf.set_margins(18, 0, 18)
    pdf.set_y(HEADER_H + 8)

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRY)
        pdf.cell(0, 5, "  ·  ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    def section(label: str) -> None:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*TEAL)
        pdf.cell(0, 5, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(*TEAL)
        pdf.set_line_width(0.4)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.ln(2.5)
        pdf.set_text_color(*DARK)

    def body_wrap(text: str, width: int = 105, indent: int = 0) -> None:
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*DARK)
        for wl in textwrap.wrap(text, width) or [""]:
            if indent:
                pdf.cell(indent)
            pdf.cell(0, 5, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if summary:
        section("Profile")
        body_wrap(summary)

    exps = cv_data.get("experiences") or []
    if exps:
        section("Experience")
        for exp in exps:
            # Teal left accent bar
            ey = pdf.get_y()
            pdf.set_fill_color(*TEAL_L)
            pdf.rect(18, ey - 0.5, 2, 10, "F")

            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*DARK)
            pdf.set_xy(22, ey)
            pdf.cell(0, 5, _s(exp.get("title", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.set_xy(22, pdf.get_y())
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*GRY)
            period = _s(_period(exp))
            co = _s(exp.get("company", ""))
            pdf.cell(80, 4.5, co)
            pdf.cell(0, 4.5, period, align="R")
            pdf.ln(4.5)
            pdf.set_text_color(*DARK)

            if exp.get("description"):
                pdf.set_x(22)
                for wl in textwrap.wrap(_s(exp["description"]), 100) or [""]:
                    pdf.set_x(22)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.cell(0, 4.8, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            for ach in (exp.get("achievements") or [])[:3]:
                pdf.set_x(22)
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(*TEAL)
                pdf.cell(4, 4.5, "›")
                pdf.set_text_color(*DARK)
                pdf.cell(0, 4.5, _s(ach), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

    skills = cv_data.get("skills") or []
    if skills:
        section("Skills")
        names = [_s(s.get("name", "")) for s in skills if s.get("name")]
        # Pill-style skill tags (simulated with cells)
        x, sy = 18, pdf.get_y()
        for sk in names:
            tw = len(sk) * 2.2 + 8
            if x + tw > 188:
                x = 18
                sy += 7
            pdf.set_fill_color(*TEAL_L)
            pdf.set_text_color(*TEAL_D)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_xy(x, sy)
            pdf.cell(tw, 6, _s(sk), align="C", fill=True)
            x += tw + 3
        pdf.set_y(sy + 10)

    edus = cv_data.get("educations") or []
    if edus:
        section("Education")
        for edu in edus:
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*DARK)
            pdf.cell(0, 5.5, _s(f"{edu.get('degree','')} — {edu.get('institution','')}"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            ps = (edu.get("period_start") or "")[:7]
            pe = (edu.get("period_end") or "")[:7]
            if ps:
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(*GRY)
                pdf.cell(0, 4.5, _s(f"{ps} – {pe}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1.5)

    certs = cv_data.get("certifications") or []
    if certs:
        section("Certifications")
        for cert in certs:
            issued = (cert.get("issued_at") or "")[:7]
            line = f"{cert.get('name','')}  –  {cert.get('issuer','')}"
            if issued:
                line += f"  ({issued})"
            body_wrap(line)

    # Footer
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-12)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRY)
    pdf.cell(0, 5, _today(), align="C")

    return bytes(pdf.output())


# ── Router ────────────────────────────────────────────────────────────────────

CV_PDF_TEMPLATES: dict[str, object] = {
    "ats_professional":   cv_pdf_ats,
    "modern_professional": cv_pdf_modern,
    "executive":          cv_pdf_executive,
    "minimal_nordic":     cv_pdf_nordic,
    "creative_professional": cv_pdf_creative,
}


def render_cv_pdf(cv_data: dict, template: str = "ats_professional") -> bytes:
    fn = CV_PDF_TEMPLATES.get(template, cv_pdf_ats)
    return fn(cv_data)  # type: ignore[operator]
