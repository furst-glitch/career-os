"""
CV PDF templates using fpdf2.

Two template systems:
  render_generated_cv_pdf(text, candidate, template) — AI plain-text -> PDF
    Templates: nordic_executive | clean_professional | modern_nordic
               minimal_nordic | bold_impact

  render_cv_pdf(cv_data, template) — structured dict -> PDF (legacy)
    Templates: ats_professional | modern_professional | executive
               minimal_nordic | creative_professional
"""
from __future__ import annotations

import textwrap
from datetime import datetime


def _s(text: str) -> str:
    """Latin-1 safe sanitiser. ae/oe/aa er forkert — brug originale ae/oe/aa."""
    if not text:
        return ""
    return (
        str(text)
        .replace("—", "-").replace("–", "-").replace("•", "-")
        .replace("‘", "'").replace("’", "'")
        .replace("“", '"').replace("”", '"')
        .encode("latin-1", errors="replace").decode("latin-1")
    )


def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _today() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def _period(exp: dict) -> str:
    start = (exp.get("period_start") or "")[:7]
    end = "Nu" if exp.get("is_current") else (exp.get("period_end") or "")[:7]
    return f"{start} - {end}" if start else ""


# ═══════════════════════════════════════════════════════════════
# SHARED PARSER
# ═══════════════════════════════════════════════════════════════

def parse_cv_text(text: str) -> list[dict]:
    blocks: list[dict] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            blocks.append({"type": "SPACING", "mm": 3})
        elif stripped.startswith("## "):
            blocks.append({"type": "SECTION_HEADER", "text": stripped[3:].strip().upper()})
        elif " | " in stripped and not stripped.startswith("-"):
            parts = stripped.split(" | ", 1)
            blocks.append({"type": "JOB_HEADER", "title": parts[0].strip(), "date": parts[1].strip()})
        elif stripped.startswith("- "):
            blocks.append({"type": "BULLET", "text": stripped[2:].strip()})
        else:
            blocks.append({"type": "BODY_TEXT", "text": stripped})
    return blocks


_LEFT_KW = {
    # Danish
    "KOMPETENCER", "UDDANNELSE", "CERTIFIKAT", "CERTIF",
    "SPROG", "REFERENCER", "REFERENCE", "KURSER",
    "FAGLIGE", "TEKNISKE", "NØGLE",
    # English
    "SKILLS", "EDUCATION", "LANGUAGE", "COURSE",
    "CERTIFICATION", "REFERENCE", "QUALIF",
}


def _is_left_section(text: str) -> bool:
    u = text.upper()
    return any(kw in u for kw in _LEFT_KW)


def _route_blocks(blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    left: list[dict] = []
    right: list[dict] = []
    in_left = False
    for b in blocks:
        if b["type"] == "SECTION_HEADER":
            in_left = _is_left_section(b["text"])
        (left if in_left else right).append(b)
    return left, right


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 1: nordic_executive
# Two-column. Dark left sidebar (62mm), white right (148mm).
# Gold accent line. Strictly one A4 page.
# ═══════════════════════════════════════════════════════════════

class NordicExecutiveTemplate:
    # Page geometry (A4 = 210 × 297 mm)
    LW   = 62    # left column total width
    LP   = 7     # left column inner padding
    CW_L = 62 - 7 - 4   # 51 mm usable text width in sidebar
    RX   = 62    # right column starts here
    RP   = 8     # right column left pad
    RX_C = 62 + 8        # 70 mm — right column text start
    CW_R = 210 - 62 - 8 - 6   # 134 mm usable text width in right column

    HDR_H = 18   # header height
    FTR_H = 9    # footer height

    # Content area (same for both columns, enforced 1-page)
    CS = HDR_H + 5        # content_start y = 23
    CE = 297 - FTR_H - 4  # content_end   y = 284

    C_LEFT_BG   = _hex("#1a1a2e")
    C_ACCENT    = _hex("#c8a96e")
    C_LEFT_TXT  = _hex("#c8ccdd")
    C_LEFT_BOLD = _hex("#ffffff")
    C_LEFT_SUB  = _hex("#8899bb")
    C_LEFT_SEC  = _hex("#c8a96e")
    C_R_BODY    = _hex("#333344")
    C_R_TITLE   = _hex("#1a1a2e")
    C_R_SUB     = _hex("#666688")
    C_R_SEC     = _hex("#1a1a2e")

    # Font sizes
    FS_SEC_L  = 6.5   # section header left
    FS_SEC_R  = 7.5   # section header right
    FS_BODY_L = 8     # body text left
    FS_BODY_R = 8.5   # body text right
    FS_TITLE  = 8.5   # job title right

    # Line heights
    LH_L = 4.3
    LH_R = 4.5

    def render(self, blocks: list[dict], candidate: dict) -> bytes:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.set_margins(0, 0, 0)
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()
        self._c = candidate

        # 1. Draw backgrounds first
        self._draw_bg(pdf)
        # 2. Header and footer
        self._draw_header(pdf, candidate)
        self._draw_footer(pdf, candidate)

        # 3. Route blocks
        left_blocks, right_blocks = _route_blocks(blocks)

        # Always add contact section at top of sidebar
        sidebar = self._make_sidebar(candidate, left_blocks)

        # 4. Render both columns (strict 1-page: break instead of add_page)
        self._render_left(pdf, sidebar)
        self._render_right(pdf, right_blocks)

        return bytes(pdf.output())

    def _draw_bg(self, pdf) -> None:
        # Full-height dark left panel
        pdf.set_fill_color(*self.C_LEFT_BG)
        pdf.rect(0, 0, self.LW, 297, "F")

    def _draw_header(self, pdf, c: dict) -> None:
        # Dark header bar spans full width
        pdf.set_fill_color(*self.C_LEFT_BG)
        pdf.rect(self.LW, 0, 210 - self.LW, self.HDR_H, "F")

        # Name in sidebar header
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*self.C_LEFT_BOLD)
        pdf.set_xy(self.LP, 3.5)
        pdf.cell(self.CW_L + 3, 8, _s(c.get("name") or ""))

        # Title + contact in right header area
        rx = self.RX_C
        title = _s(c.get("title") or "")
        if title:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.C_ACCENT)
            pdf.set_xy(rx, 2.5)
            pdf.cell(self.CW_R, 5, title)

        parts = [_s(v) for v in [c.get("email"), c.get("phone"), c.get("location")] if v]
        if parts:
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(*self.C_LEFT_SUB)
            pdf.set_xy(rx, 9.5)
            pdf.cell(self.CW_R, 4, "  \xb7  ".join(parts))

        # Gold separator line
        pdf.set_draw_color(*self.C_ACCENT)
        pdf.set_line_width(0.6)
        pdf.line(0, self.HDR_H, 210, self.HDR_H)

    def _draw_footer(self, pdf, c: dict) -> None:
        fy = 297 - self.FTR_H
        pdf.set_draw_color(*self.C_ACCENT)
        pdf.set_line_width(0.3)
        pdf.line(0, fy, 210, fy)
        # Dark right footer bar
        pdf.set_fill_color(*self.C_LEFT_BG)
        pdf.rect(self.LW, fy, 210 - self.LW, self.FTR_H, "F")

        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*self.C_LEFT_SUB)
        name_t = _s(c.get("name") or "")
        pdf.set_xy(self.LP, fy + 3)
        pdf.cell(self.CW_L, 3.5, name_t)
        right_t = "  \xb7  ".join(_s(v) for v in [c.get("email"), c.get("phone")] if v)
        pdf.set_xy(self.RX_C, fy + 3)
        pdf.cell(self.CW_R, 3.5, right_t, align="R")

    def _make_sidebar(self, c: dict, left_blocks: list[dict]) -> list[dict]:
        """Build the left column: contact section always first, then AI-routed blocks."""
        contact: list[dict] = [{"type": "SECTION_HEADER", "text": "KONTAKT"}]
        for val in [c.get("email"), c.get("phone"), c.get("location")]:
            if val:
                contact.append({"type": "BODY_TEXT", "text": _s(val)})
        li = _s(c.get("linkedin") or "")
        if li:
            contact.append({"type": "BODY_TEXT", "text": li})
        contact.append({"type": "SPACING", "mm": 3})
        return contact + left_blocks

    def _render_left(self, pdf, blocks: list[dict]) -> None:
        x = self.LP
        w = self.CW_L
        y = float(self.CS)
        end_y = float(self.CE)

        for b in blocks:
            bt = b["type"]
            if y >= end_y - 6:
                break

            if bt == "SPACING":
                y = min(y + b.get("mm", 3), end_y)
                continue

            if bt == "SECTION_HEADER":
                # Space before section, then gold label + thin line
                y = min(y + 6, end_y - 12)
                if y >= end_y - 6:
                    break
                pdf.set_font("Helvetica", "B", self.FS_SEC_L)
                pdf.set_text_color(*self.C_LEFT_SEC)
                pdf.set_xy(x, y)
                pdf.cell(w, 4, b["text"])
                y += 4
                pdf.set_draw_color(*self.C_ACCENT)
                pdf.set_line_width(0.3)
                pdf.line(x, y, x + w, y)
                y += 2.5

            elif bt == "BULLET":
                if y + self.LH_L > end_y:
                    break
                pdf.set_font("Helvetica", "", self.FS_BODY_L)
                pdf.set_text_color(*self.C_LEFT_TXT)
                # Calculate expected height before rendering
                txt = "\xb7  " + _s(b["text"])
                pdf.set_xy(x + 2, y)
                pdf.multi_cell(w - 2, self.LH_L, txt)
                y = min(pdf.get_y() + 1, end_y)

            elif bt == "BODY_TEXT":
                if y + self.LH_L > end_y:
                    break
                pdf.set_font("Helvetica", "", self.FS_BODY_L)
                pdf.set_text_color(*self.C_LEFT_TXT)
                pdf.set_xy(x, y)
                pdf.multi_cell(w, self.LH_L, _s(b["text"]))
                y = min(pdf.get_y() + 1.5, end_y)

            elif bt == "JOB_HEADER":
                if y + self.LH_L * 2 > end_y:
                    break
                pdf.set_font("Helvetica", "B", self.FS_BODY_L)
                pdf.set_text_color(*self.C_LEFT_BOLD)
                pdf.set_xy(x, y)
                pdf.multi_cell(w, self.LH_L, _s(b["title"]))
                y = pdf.get_y()
                pdf.set_font("Helvetica", "", self.FS_BODY_L - 0.5)
                pdf.set_text_color(*self.C_LEFT_SUB)
                pdf.set_xy(x, y)
                pdf.multi_cell(w, self.LH_L, _s(b["date"]))
                y = min(pdf.get_y() + 1, end_y)

    def _render_right(self, pdf, blocks: list[dict]) -> None:
        x = self.RX_C
        w = self.CW_R
        y = float(self.CS)
        end_y = float(self.CE)

        for b in blocks:
            bt = b["type"]
            if y >= end_y - 6:
                break   # Hard 1-page limit: clip, never add page

            if bt == "SPACING":
                y = min(y + b.get("mm", 2), end_y)
                continue

            if bt == "SECTION_HEADER":
                y = min(y + 7, end_y - 14)
                if y >= end_y - 6:
                    break
                pdf.set_font("Helvetica", "B", self.FS_SEC_R)
                pdf.set_text_color(*self.C_R_SEC)
                pdf.set_xy(x, y)
                pdf.cell(w, 4.5, b["text"])
                y += 4.5
                pdf.set_draw_color(*self.C_ACCENT)
                pdf.set_line_width(0.4)
                pdf.line(x, y, x + w, y)
                y += 2.5

            elif bt == "JOB_HEADER":
                if y + 5 > end_y:
                    break
                title_p = _s(b["title"])
                date_p  = _s(b["date"])
                # Measure date width so it right-aligns
                pdf.set_font("Helvetica", "", self.FS_BODY_R - 1)
                dw = min(pdf.get_string_width(date_p) + 4, w * 0.45)
                tw = w - dw
                pdf.set_font("Helvetica", "B", self.FS_TITLE)
                pdf.set_text_color(*self.C_R_TITLE)
                pdf.set_xy(x, y)
                pdf.cell(tw, 5, title_p)
                pdf.set_font("Helvetica", "", self.FS_BODY_R - 1)
                pdf.set_text_color(*self.C_R_SUB)
                pdf.cell(dw, 5, date_p, align="R")
                y += 5.5

            elif bt == "BULLET":
                if y + self.LH_R > end_y:
                    break
                pdf.set_font("Helvetica", "", self.FS_BODY_R)
                pdf.set_text_color(*self.C_R_BODY)
                pdf.set_xy(x + 4, y)
                pdf.multi_cell(w - 4, self.LH_R, "\xb7  " + _s(b["text"]))
                y = min(pdf.get_y() + 1, end_y)

            elif bt == "BODY_TEXT":
                if y + self.LH_R > end_y:
                    break
                pdf.set_font("Helvetica", "", self.FS_BODY_R)
                pdf.set_text_color(*self.C_R_BODY)
                pdf.set_xy(x, y)
                pdf.multi_cell(w, self.LH_R, _s(b["text"]))
                y = min(pdf.get_y() + 2, end_y)


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 2: clean_professional
# Single-column, no colored header. Finance / legal / public.
# ═══════════════════════════════════════════════════════════════

class CleanProfessionalTemplate:
    MARGIN = 15
    CW     = 180

    C_ACC  = _hex("#2c5282")
    C_BODY = _hex("#2d3748")
    C_SUB  = _hex("#718096")
    C_NAME = _hex("#1a202c")

    def render(self, blocks: list[dict], candidate: dict) -> bytes:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
        pdf = FPDF()
        pdf.set_margins(self.MARGIN, self.MARGIN, self.MARGIN)
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*self.C_NAME)
        pdf.multi_cell(0, 11, _s(candidate.get("name") or ""), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        title = _s(candidate.get("title") or "")
        if title:
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(*self.C_ACC)
            pdf.multi_cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        contact = "  ·  ".join(_s(v) for v in [candidate.get("email"), candidate.get("phone"), candidate.get("location")] if v)
        if contact:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.C_SUB)
            pdf.multi_cell(0, 5, contact, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(2)
        pdf.set_draw_color(*self.C_ACC)
        pdf.set_line_width(1)
        pdf.line(self.MARGIN, pdf.get_y(), self.MARGIN + self.CW, pdf.get_y())
        pdf.ln(5)

        for b in blocks:
            bt = b["type"]

            if bt == "SPACING":
                pdf.ln(3)
                continue

            if bt == "SECTION_HEADER":
                pdf.ln(8)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*self.C_ACC)
                pdf.multi_cell(0, 5, b["text"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_draw_color(*self.C_ACC)
                pdf.set_line_width(0.5)
                pdf.line(self.MARGIN, pdf.get_y(), self.MARGIN + self.CW, pdf.get_y())
                pdf.ln(2)

            elif bt == "JOB_HEADER":
                title_p = _s(b["title"])
                date_p  = _s(b["date"])
                pdf.set_font("Helvetica", "", 9)
                dw = pdf.get_string_width(date_p) + 6
                tw = max(self.CW // 2, self.CW - dw)
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(*self.C_BODY)
                pdf.set_x(self.MARGIN)
                pdf.cell(tw, 5.5, title_p)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*self.C_SUB)
                pdf.cell(0, 5.5, date_p, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1)

            elif bt == "BULLET":
                pdf.set_x(self.MARGIN + 6)
                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(*self.C_BODY)
                pdf.multi_cell(self.CW - 6, 5, _s(f"-  {b['text']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1.5)

            elif bt == "BODY_TEXT":
                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(*self.C_BODY)
                pdf.multi_cell(0, 5.5, _s(b["text"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(2.5)

        pdf.set_auto_page_break(auto=False)
        pdf.set_y(-12)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*self.C_SUB)
        pdf.cell(0, 5, _today(), align="R")

        return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 3: modern_nordic
# 4mm accent strip + dark header. Tech / consulting / FM.
# ═══════════════════════════════════════════════════════════════

class ModernNordicTemplate:
    HDR_H     = 20
    STRIP_W   = 4
    CONTENT_X = 25
    CW        = 170
    MARGIN_R  = 15

    C_STRIP  = _hex("#1a1a2e")
    C_ACCENT = _hex("#c8a96e")
    C_BODY   = _hex("#374151")
    C_SUB    = _hex("#6b7280")
    C_NAME   = _hex("#111827")
    C_HDR_BG = _hex("#1a1a2e")
    C_WHITE  = (255, 255, 255)

    def render(self, blocks: list[dict], candidate: dict) -> bytes:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
        pdf = FPDF()
        pdf.set_margins(0, 0, self.MARGIN_R)
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        pdf.set_fill_color(*self.C_STRIP)
        pdf.rect(0, 0, self.STRIP_W, 297, "F")

        pdf.set_fill_color(*self.C_HDR_BG)
        pdf.rect(self.STRIP_W, 0, 210 - self.STRIP_W, self.HDR_H, "F")

        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(*self.C_WHITE)
        pdf.set_xy(self.CONTENT_X, 4)
        pdf.cell(self.CW, 8, _s(candidate.get("name") or ""))

        sub_parts = [_s(v) for v in [candidate.get("title"), candidate.get("email"), candidate.get("phone")] if v]
        if sub_parts:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*self.C_ACCENT)
            pdf.set_xy(self.CONTENT_X, 13.5)
            pdf.cell(self.CW, 5, "  ·  ".join(sub_parts))

        pdf.set_y(self.HDR_H + 5)

        for b in blocks:
            bt = b["type"]

            if bt == "SPACING":
                pdf.ln(3)
                continue

            if bt == "SECTION_HEADER":
                pdf.ln(8)
                sy = pdf.get_y()
                pdf.set_fill_color(*self.C_ACCENT)
                pdf.rect(self.CONTENT_X, sy + 0.5, 3, 3, "F")
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(*self.C_ACCENT)
                pdf.set_xy(self.CONTENT_X + 5, sy)
                pdf.cell(self.CW - 5, 5, b["text"])
                pdf.set_y(sy + 5)
                pdf.ln(2)

            elif bt == "JOB_HEADER":
                title_p = _s(b["title"])
                date_p  = _s(b["date"])
                pdf.set_font("Helvetica", "I", 8.5)
                dw = pdf.get_string_width(date_p) + 6
                tw = max(self.CW // 2, self.CW - dw)
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(*self.C_NAME)
                pdf.set_x(self.CONTENT_X)
                pdf.cell(tw, 5.5, title_p)
                pdf.set_font("Helvetica", "I", 8.5)
                pdf.set_text_color(*self.C_SUB)
                pdf.cell(0, 5.5, date_p, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1)

            elif bt == "BULLET":
                pdf.set_x(self.CONTENT_X + 5)
                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(*self.C_BODY)
                pdf.multi_cell(self.CW - 5, 5, _s(f">  {b['text']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1.5)

            elif bt == "BODY_TEXT":
                pdf.set_x(self.CONTENT_X)
                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(*self.C_BODY)
                pdf.multi_cell(self.CW, 5.5, _s(b["text"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(2.5)

        pdf.set_auto_page_break(auto=False)
        pdf.set_y(-11)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*self.C_SUB)
        pdf.set_x(self.CONTENT_X)
        pdf.cell(self.CW, 5, _today(), align="R")

        return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 4: minimal_nordic
# Maximum white space, no color. Senior / executive roles.
# ═══════════════════════════════════════════════════════════════

class MinimalNordicTemplate:
    MARGIN = 25
    CW     = 160

    C_TEXT = _hex("#1a1a1a")
    C_SUB  = _hex("#666666")

    def render(self, blocks: list[dict], candidate: dict) -> bytes:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
        pdf = FPDF()
        pdf.set_margins(self.MARGIN, self.MARGIN, self.MARGIN)
        pdf.set_auto_page_break(auto=True, margin=25)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(*self.C_TEXT)
        pdf.multi_cell(0, 12, _s(candidate.get("name") or ""), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(8)

        title = _s(candidate.get("title") or "")
        if title:
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(*self.C_SUB)
            pdf.multi_cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        contact = "  ·  ".join(_s(v) for v in [candidate.get("email"), candidate.get("phone"), candidate.get("location")] if v)
        if contact:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.C_SUB)
            pdf.multi_cell(0, 5, contact, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(6)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.5)
        pdf.line(self.MARGIN, pdf.get_y(), self.MARGIN + self.CW, pdf.get_y())
        pdf.ln(5)

        bullet_count = 0

        for b in blocks:
            bt = b["type"]

            if bt == "SPACING":
                pdf.ln(4)
                continue

            if bt == "SECTION_HEADER":
                bullet_count = 0
                pdf.ln(10)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(*self.C_TEXT)
                pdf.multi_cell(0, 5, b["text"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1)

            elif bt == "JOB_HEADER":
                bullet_count = 0
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(*self.C_TEXT)
                pdf.multi_cell(0, 5.5, _s(b["title"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*self.C_SUB)
                pdf.multi_cell(0, 5, _s(b["date"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1)

            elif bt == "BULLET":
                if bullet_count < 4:
                    pdf.set_x(self.MARGIN + 4)
                    pdf.set_font("Helvetica", "", 9.5)
                    pdf.set_text_color(*self.C_TEXT)
                    pdf.multi_cell(self.CW - 4, 5.5, "\xb7  " + _s(b["text"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    pdf.ln(2.5)
                    bullet_count += 1

            elif bt == "BODY_TEXT":
                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(*self.C_TEXT)
                pdf.multi_cell(0, 6, _s(b["text"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(3.5)

        pdf.set_auto_page_break(auto=False)
        pdf.set_y(-14)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*self.C_SUB)
        pdf.cell(0, 5, _today(), align="R")

        return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 5: bold_impact
# Dark header, amber accent. Sales / marketing / BD.
# ═══════════════════════════════════════════════════════════════

class BoldImpactTemplate:
    MARGIN = 15
    HDR_H  = 25
    CW     = 180

    C_HDR   = _hex("#111827")
    C_ACC   = _hex("#f59e0b")
    C_ACC_L = _hex("#fef3c7")
    C_BODY  = _hex("#374151")
    C_SUB   = _hex("#6b7280")
    C_WHITE = (255, 255, 255)
    C_CTCT  = _hex("#9ca3af")

    def render(self, blocks: list[dict], candidate: dict) -> bytes:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
        pdf = FPDF()
        pdf.set_margins(self.MARGIN, 0, self.MARGIN)
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        pdf.set_fill_color(*self.C_HDR)
        pdf.rect(0, 0, 210, self.HDR_H, "F")

        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*self.C_WHITE)
        pdf.set_xy(self.MARGIN, 4)
        pdf.cell(self.CW, 9, _s(candidate.get("name") or ""))

        title = _s(candidate.get("title") or "")
        if title:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*self.C_ACC)
            pdf.set_xy(self.MARGIN, 13.5)
            pdf.cell(self.CW, 6, title)

        contact = "  ·  ".join(_s(v) for v in [candidate.get("email"), candidate.get("phone"), candidate.get("location")] if v)
        if contact:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*self.C_CTCT)
            pdf.set_xy(self.MARGIN, 20)
            pdf.cell(self.CW, 4, contact)

        pdf.set_fill_color(*self.C_ACC)
        pdf.rect(0, self.HDR_H, 210, 3, "F")
        pdf.set_y(self.HDR_H + 7)

        for b in blocks:
            bt = b["type"]

            if bt == "SPACING":
                pdf.ln(3)
                continue

            if bt == "SECTION_HEADER":
                pdf.ln(8)
                sy = pdf.get_y()
                rect_h = 7
                pdf.set_fill_color(*self.C_ACC_L)
                pdf.rect(self.MARGIN - 3, sy, self.CW + 6, rect_h, "F")
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*self.C_HDR)
                pdf.set_xy(self.MARGIN, sy + 1)
                pdf.cell(self.CW, 5, b["text"])
                pdf.set_y(sy + rect_h + 1)

            elif bt == "JOB_HEADER":
                title_p = _s(b["title"])
                date_p  = _s(b["date"])
                pdf.set_font("Helvetica", "", 9)
                dw = pdf.get_string_width(date_p) + 6
                tw = max(self.CW // 2, self.CW - dw)
                pdf.set_font("Helvetica", "B", 10.5)
                pdf.set_text_color(*self.C_HDR)
                pdf.set_x(self.MARGIN)
                pdf.cell(tw, 5.5, title_p)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*self.C_SUB)
                pdf.cell(0, 5.5, date_p, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1)

            elif bt == "BULLET":
                pdf.set_x(self.MARGIN + 6)
                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(*self.C_BODY)
                pdf.multi_cell(self.CW - 6, 5, _s(f">  {b['text']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1.5)

            elif bt == "BODY_TEXT":
                pdf.set_x(self.MARGIN)
                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(*self.C_BODY)
                pdf.multi_cell(0, 5.5, _s(b["text"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(2.5)

        pdf.set_auto_page_break(auto=False)
        pdf.set_y(-11)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*self.C_SUB)
        pdf.cell(0, 5, _today(), align="R")

        return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════
# TEMPLATE REGISTRY + ENTRY POINT
# ═══════════════════════════════════════════════════════════════

GENERATED_CV_TEMPLATES: dict[str, type] = {
    "nordic_executive":   NordicExecutiveTemplate,
    "clean_professional": CleanProfessionalTemplate,
    "modern_nordic":      ModernNordicTemplate,
    "minimal_nordic":     MinimalNordicTemplate,
    "bold_impact":        BoldImpactTemplate,
}


def render_generated_cv_pdf(
    text: str,
    candidate: dict,
    template: str = "nordic_executive",
) -> bytes:
    cls = GENERATED_CV_TEMPLATES.get(template, NordicExecutiveTemplate)
    blocks = parse_cv_text(text)
    return cls().render(blocks, candidate)


# ═══════════════════════════════════════════════════════════════
# LEGACY: structured cv_data templates (keep for render_cv_pdf)
# ═══════════════════════════════════════════════════════════════

def cv_pdf_ats(cv_data: dict) -> bytes:
    """Clean B&W single-column – maximum ATS parser compatibility."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_margins(20, 22, 20)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    _prof = cv_data.get("profile") or {}
    name    = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title   = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 9, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if title:
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 5, "  |  ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    def section(label: str) -> None:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(2)

    def body_wrap(text: str, width: int = 110) -> None:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        for wl in textwrap.wrap(text, width) or [""]:
            pdf.multi_cell(0, 4.8, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if summary:
        section("Professional Summary")
        body_wrap(summary)

    exps = cv_data.get("experiences") or []
    if exps:
        section("Experience")
        for exp in exps:
            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(0, 5, _s(f"{exp.get('title','')} | {exp.get('company','')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            p = _s(_period(exp))
            if p:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(60, 60, 60)
                pdf.multi_cell(0, 4, p, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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
            pdf.multi_cell(0, 5, _s(f"{edu.get('degree','')} - {edu.get('institution','')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            ps = (edu.get("period_start") or "")[:7]
            pe = (edu.get("period_end") or "")[:7]
            if ps:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(60, 60, 60)
                pdf.multi_cell(0, 4, _s(f"{ps} - {pe}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)
            pdf.ln(1.5)

    certs = cv_data.get("certifications") or []
    if certs:
        section("Certifications")
        for cert in certs:
            issued = (cert.get("issued_at") or "")[:7]
            line = f"- {cert.get('name','')} - {cert.get('issuer','')}"
            if issued:
                line += f" ({issued})"
            body_wrap(line)

    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-13)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, _today(), align="C")
    return bytes(pdf.output())


def cv_pdf_modern(cv_data: dict) -> bytes:
    """Navy sidebar (35%) + white main column, blue accents."""
    from fpdf import FPDF

    SB_X = 0; SB_W = 68; MAIN_X = 72; MAIN_W = 123; TOP_Y = 15; MV = 14
    NAV = (15, 40, 80); ACC = (59, 130, 246); WHT = (255, 255, 255)
    DRK = (15, 23, 42); GRY = (100, 116, 139)

    pdf = FPDF()
    pdf.set_margins(0, 0, 0)
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)
    pdf.set_fill_color(*NAV)
    pdf.rect(SB_X, 0, SB_W, 297, "F")

    _prof  = cv_data.get("profile") or {}
    name   = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title_str = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary   = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    y = TOP_Y

    def sb_cell(text: str, font: str, size: float, color: tuple, h: float = 5.5) -> None:
        nonlocal y
        pdf.set_font("Helvetica", font, size)
        pdf.set_text_color(*color)
        pdf.set_xy(MV, y)
        pdf.multi_cell(SB_W - MV * 2, h, _s(text))
        y = pdf.get_y()

    def sb_section(label: str) -> None:
        nonlocal y
        y += 4
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*ACC)
        pdf.set_xy(MV, y)
        pdf.cell(SB_W - MV * 2, 5, label.upper())
        y += 5
        pdf.set_draw_color(*ACC)
        pdf.set_line_width(0.3)
        pdf.line(MV, y, SB_W - MV, y)
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
            pdf.set_xy(MV, y)
            pdf.cell(SB_W - MV * 2, 5, _s(f"- {sk.get('name','')}"))
            y += 5

    edus = cv_data.get("educations") or []
    if edus:
        sb_section("Education")
        for edu in edus:
            sb_cell(edu.get("degree", ""), "B", 8, WHT, 5)
            sb_cell(edu.get("institution", ""), "", 7.5, (180, 200, 230), 4.5)
            ps = (edu.get("period_start") or "")[:7]
            pe = (edu.get("period_end") or "")[:7]
            if ps:
                sb_cell(f"{ps} - {pe}", "", 7, (150, 170, 210), 4)

    certs = cv_data.get("certifications") or []
    if certs:
        sb_section("Certifications")
        for cert in certs:
            sb_cell(cert.get("name", ""), "", 8, WHT, 4.5)
            if cert.get("issuer"):
                sb_cell(cert["issuer"], "", 7, (180, 200, 230), 4)

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
            pdf.cell(MAIN_W, 5, _s(exp.get("title", "")))
            my[0] += 5
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(*GRY)
            pdf.set_xy(MAIN_X, my[0])
            co = _s(exp.get("company", ""))
            p  = _s(_period(exp))
            pdf.cell(MAIN_W / 2, 4.5, co)
            pdf.set_xy(MAIN_X + MAIN_W / 2, my[0])
            pdf.cell(MAIN_W / 2, 4.5, p, align="R")
            my[0] += 4.5
            pdf.set_text_color(*DRK)
            if exp.get("description"):
                main_wrap(exp["description"], my)
            for ach in (exp.get("achievements") or [])[:3]:
                main_wrap(f"- {ach}", my, indent=3)
            my[0] += 2

    pdf.set_y(-12)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRY)
    pdf.set_x(MAIN_X)
    pdf.cell(MAIN_W, 5, _today(), align="R")
    return bytes(pdf.output())


def cv_pdf_executive(cv_data: dict) -> bytes:
    """Wide margins, Times headings, gold accent lines."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    GOLD = (160, 100, 30); DARK = (10, 15, 35); GREY = (90, 100, 120)

    pdf = FPDF()
    pdf.set_margins(28, 26, 28)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=24)

    _prof     = cv_data.get("profile") or {}
    name      = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title_str = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary   = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    pdf.set_font("Times", "B", 24)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 12, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    if title_str:
        pdf.set_font("Times", "I", 12)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 6, title_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        pdf.set_font("Times", "", 9)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 5, "  ·  ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

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
        pdf.multi_cell(0, 6, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(*GOLD)
        pdf.set_line_width(0.3)
        pdf.line(28, pdf.get_y(), 182, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(*DARK)

    def body_wrap(text: str, width: int = 95) -> None:
        pdf.set_font("Times", "", 10)
        pdf.set_text_color(*DARK)
        for wl in textwrap.wrap(text, width) or [""]:
            pdf.multi_cell(0, 5.5, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

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
            p = _s(_period(exp))
            if p:
                pdf.set_font("Times", "I", 9.5)
                pdf.set_text_color(*GREY)
                pdf.multi_cell(0, 5, p, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(*DARK)
            if exp.get("description"):
                body_wrap(exp["description"])
            for ach in (exp.get("achievements") or [])[:4]:
                body_wrap(f"-  {ach}")
            pdf.ln(3)

    skills = cv_data.get("skills") or []
    if skills:
        section("Core Competencies")
        names = [_s(s.get("name", "")) for s in skills if s.get("name")]
        cols = [names[i::3] for i in range(3)]
        col_w = (182 - 28) / 3
        start_y = pdf.get_y()
        for ci, col in enumerate(cols):
            pdf.set_xy(28 + ci * col_w, start_y)
            for sk in col:
                pdf.set_font("Times", "", 10)
                pdf.cell(col_w, 5.5, _s(f"- {sk}"))
                pdf.set_xy(28 + ci * col_w, pdf.get_y() + 5.5)
        if any(cols):
            pdf.set_y(max(start_y + len(c) * 5.5 for c in cols if c))

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
                pdf.multi_cell(0, 5, _s(f"{ps} - {pe}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(*DARK)
            pdf.ln(1.5)

    certs = cv_data.get("certifications") or []
    if certs:
        section("Certifications")
        for cert in certs:
            issued = (cert.get("issued_at") or "")[:7]
            line = f"-  {cert.get('name','')}  |  {cert.get('issuer','')}"
            if issued:
                line += f"  ({issued})"
            body_wrap(line)

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


def cv_pdf_nordic(cv_data: dict) -> bytes:
    """Generous whitespace, light gray tones, minimalist Scandinavian design."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    DARK = (25, 35, 50); MED = (80, 95, 115); LGT = (180, 195, 210)

    pdf = FPDF()
    pdf.set_margins(26, 28, 26)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=26)

    _prof     = cv_data.get("profile") or {}
    name      = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title_str = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary   = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    pdf.set_font("Helvetica", "", 22)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 11, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if title_str:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*MED)
        pdf.multi_cell(0, 6, title_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LGT)
        pdf.multi_cell(0, 5, "   ·   ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(3)
    pdf.set_draw_color(*LGT)
    pdf.set_line_width(0.2)
    pdf.line(26, pdf.get_y(), 184, pdf.get_y())
    pdf.ln(6)

    def section(label: str) -> None:
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MED)
        pdf.multi_cell(0, 5, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(*LGT)
        pdf.set_line_width(0.2)
        pdf.line(26, pdf.get_y(), 184, pdf.get_y())
        pdf.ln(4)
        pdf.set_text_color(*DARK)

    def body_wrap(text: str, size: float = 9.5, width: int = 105) -> None:
        pdf.set_font("Helvetica", "", size)
        pdf.set_text_color(*DARK)
        for wl in textwrap.wrap(text, width) or [""]:
            pdf.multi_cell(0, 5.5, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if summary:
        section("Summary")
        body_wrap(summary, 9.5)

    exps = cv_data.get("experiences") or []
    if exps:
        section("Experience")
        for exp in exps:
            p = _s(_period(exp))
            if p:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*MED)
                pdf.cell(38, 5.5, p, new_x="RIGHT", new_y="TOP")
            role_x = 26 + 40
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*DARK)
            pdf.set_x(role_x)
            pdf.multi_cell(0, 5.5, _s(exp.get("title", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(role_x)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MED)
            pdf.multi_cell(0, 5, _s(exp.get("company", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*DARK)
            if exp.get("description"):
                for wl in textwrap.wrap(_s(exp["description"]), 80) or [""]:
                    pdf.set_x(role_x)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.multi_cell(0, 4.8, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            for ach in (exp.get("achievements") or [])[:3]:
                pdf.set_x(role_x)
                pdf.set_font("Helvetica", "", 8.5)
                pdf.multi_cell(0, 4.5, _s(f"- {ach}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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
                pdf.cell(38, 5.5, _s(f"{ps} - {pe}"), new_x="RIGHT", new_y="TOP")
            pdf.set_x(26 + 40)
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 5.5, _s(edu.get("degree", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(26 + 40)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MED)
            pdf.multi_cell(0, 5, _s(edu.get("institution", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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


def cv_pdf_creative(cv_data: dict) -> bytes:
    """Teal header band, modern layout."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    TEAL = (13, 148, 136); TEAL_D = (10, 100, 90); DARK = (15, 23, 42)
    GRY = (100, 116, 139); WHT = (255, 255, 255); TEAL_L = (204, 240, 237)

    pdf = FPDF()
    pdf.set_margins(0, 0, 0)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    _prof     = cv_data.get("profile") or {}
    name      = _s(_prof.get("full_name") or _prof.get("display_name") or "")
    title_str = _s((cv_data.get("master_cv") or {}).get("target_title") or "")
    summary   = _s((cv_data.get("master_cv") or {}).get("summary") or "")

    HEADER_H = 38
    pdf.set_fill_color(*TEAL)
    pdf.rect(0, 0, 210, HEADER_H, "F")

    fs_name = 20
    pdf.set_font("Helvetica", "B", fs_name)
    while pdf.get_string_width(name) > 168 and fs_name > 12:
        fs_name -= 1
        pdf.set_font("Helvetica", "B", fs_name)
    pdf.set_text_color(*WHT)
    pdf.set_xy(18, 10)
    pdf.cell(174, 10, name)

    if title_str:
        fs_sub = 10
        pdf.set_font("Helvetica", "", fs_sub)
        while pdf.get_string_width(title_str) > 168 and fs_sub > 7:
            fs_sub -= 0.5
            pdf.set_font("Helvetica", "", fs_sub)
        pdf.set_text_color(200, 240, 235)
        pdf.set_xy(18, 22)
        pdf.cell(174, 8, title_str)

    pdf.set_fill_color(*TEAL_D)
    pdf.rect(0, HEADER_H, 210, 2.5, "F")
    pdf.set_margins(18, 0, 18)
    pdf.set_y(HEADER_H + 8)

    contact_parts = [_s(v) for v in [_prof.get("email"), _prof.get("phone"), _prof.get("location")] if v]
    if contact_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRY)
        pdf.multi_cell(0, 5, "  ·  ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    def section(label: str) -> None:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*TEAL)
        pdf.multi_cell(0, 5, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(*TEAL)
        pdf.set_line_width(0.4)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.ln(2.5)
        pdf.set_text_color(*DARK)

    def body_wrap(text: str, width: int = 105) -> None:
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*DARK)
        for wl in textwrap.wrap(text, width) or [""]:
            pdf.multi_cell(0, 5, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if summary:
        section("Profile")
        body_wrap(summary)

    exps = cv_data.get("experiences") or []
    if exps:
        section("Experience")
        for exp in exps:
            ey = pdf.get_y()
            pdf.set_fill_color(*TEAL_L)
            pdf.rect(18, ey - 0.5, 2, 10, "F")
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*DARK)
            pdf.set_xy(22, ey)
            pdf.multi_cell(0, 5, _s(exp.get("title", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_xy(22, pdf.get_y())
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*GRY)
            p = _s(_period(exp))
            co = _s(exp.get("company", ""))
            pdf.cell(80, 4.5, co)
            pdf.cell(0, 4.5, p, align="R")
            pdf.ln(4.5)
            pdf.set_text_color(*DARK)
            if exp.get("description"):
                for wl in textwrap.wrap(_s(exp["description"]), 100) or [""]:
                    pdf.set_x(22)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.multi_cell(0, 4.8, _s(wl), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            for ach in (exp.get("achievements") or [])[:3]:
                pdf.set_x(22)
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(*TEAL)
                pdf.cell(4, 4.5, ">")
                pdf.set_text_color(*DARK)
                pdf.multi_cell(0, 4.5, _s(ach), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

    skills = cv_data.get("skills") or []
    if skills:
        section("Skills")
        names = [_s(s.get("name", "")) for s in skills if s.get("name")]
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
            pdf.cell(0, 5.5, _s(f"{edu.get('degree','')} - {edu.get('institution','')}"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            ps = (edu.get("period_start") or "")[:7]
            pe = (edu.get("period_end") or "")[:7]
            if ps:
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(*GRY)
                pdf.multi_cell(0, 4.5, _s(f"{ps} - {pe}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1.5)

    certs = cv_data.get("certifications") or []
    if certs:
        section("Certifications")
        for cert in certs:
            issued = (cert.get("issued_at") or "")[:7]
            line = f"{cert.get('name','')} - {cert.get('issuer','')}"
            if issued:
                line += f"  ({issued})"
            body_wrap(line)

    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-12)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRY)
    pdf.cell(0, 5, _today(), align="C")
    return bytes(pdf.output())


# ── Legacy router ─────────────────────────────────────────────────────────────

CV_PDF_TEMPLATES: dict[str, object] = {
    "ats_professional":      cv_pdf_ats,
    "modern_professional":   cv_pdf_modern,
    "executive":             cv_pdf_executive,
    "minimal_nordic":        cv_pdf_nordic,
    "creative_professional": cv_pdf_creative,
}


def render_cv_pdf(cv_data: dict, template: str = "ats_professional") -> bytes:
    fn = CV_PDF_TEMPLATES.get(template, cv_pdf_ats)
    return fn(cv_data)  # type: ignore[operator]
