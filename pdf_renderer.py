"""Renders the tailored resume text into an ATS-friendly PDF.

ATS-safe design rules applied here:
  - Single column, top-to-bottom reading order — no text boxes, tables,
    columns, images, or graphics.
  - Real embedded text (selectable/extractable), standard Arial font.
  - Standard section headers on their own line.
  - Simple round bullets; no decorative symbols.
  - Generous margins; no content in header/footer zones.

Visual structure recovered from the plain text:
  - Role lines ("Employer | Title | 01/2022 - 07/2023") render bold with
    the date range right-aligned on the same line.
  - Project titles ("Name | Spring 2024") render bold with the season/date
    right-aligned.
  - Education lines ("Degree | University | May 2025 (4.00 CGPA)") render
    as two rows: bold degree + right-aligned date, then university +
    right-aligned GPA.
  - Skill category lines ("Programming: Python, ...") render with a bold
    category prefix.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from fpdf import FPDF

FONT_DIR = Path("C:/Windows/Fonts")
FONT_REGULAR = FONT_DIR / "arial.ttf"
FONT_BOLD = FONT_DIR / "arialbd.ttf"
FONT_ITALIC = FONT_DIR / "ariali.ttf"

PAGE_MARGIN = 14  # mm
BODY_SIZE = 10
LINE_H = 4.8
BULLET_PREFIXES = ("* ", "- ", "• ", "*\t", "-\t")

SEASON_OR_MONTH = (
    r"(?:Spring|Summer|Fall|Winter|Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
DATE_TOKEN = rf"(?:\d{{1,2}}/\d{{4}}|{SEASON_OR_MONTH}\.?\s+\d{{4}})"
DATE_RANGE_RE = re.compile(
    rf"[|,;\s]*({DATE_TOKEN}(?:\s*[–—-]\s*(?:{DATE_TOKEN}|Present))?)\s*$"
)
GPA_RE = re.compile(
    r"\(?\s*(\d\.\d{1,2}(?:\s*/\s*\d{1,2}(?:\.\d+)?)?\s*C?GPA)\s*\)?", re.I
)
CATEGORY_RE = re.compile(r"^([A-Za-z][A-Za-z&,/.\- ]{2,45}):\s+(.+)$")
DEGREE_RE = re.compile(
    r"Master|Bachelor|B\.?\s*Tech|M\.?\s*Tech|M\.?S\.?|B\.?S\.?|Ph\.?D", re.I
)


def _is_section_header(line: str) -> bool:
    """A section header is a short all-caps line like 'PROFESSIONAL EXPERIENCE'."""
    stripped = line.strip()
    if not (2 < len(stripped) < 60):
        return False
    letters = [c for c in stripped if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _split_dated_line(line: str) -> Optional[Tuple[str, str]]:
    """Split a line ending in a date/range into (left_text, dates)."""
    m = DATE_RANGE_RE.search(line)
    if not m or m.start() == 0:
        return None
    left = line[: m.start()].rstrip(" |,;\t")
    return (left, m.group(1).strip()) if left else None


def _parse_education(line: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse an education line into (degree, university, date, gpa)."""
    work = line
    gpa = ""
    m = GPA_RE.search(work)
    if m:
        gpa = m.group(1)
        work = work[: m.start()] + work[m.end():]
    work = work.rstrip(" |,()")
    date = ""
    dm = DATE_RANGE_RE.search(work)
    if dm and dm.start() > 0:
        date = dm.group(1).strip()
        work = work[: dm.start()]
    parts = [p.strip(" ,") for p in work.split("|") if p.strip(" ,|")]
    if not parts:
        return None
    degree = parts[0]
    university = " | ".join(parts[1:]) if len(parts) > 1 else ""
    return degree, university, date, gpa


class ResumePDF(FPDF):
    def __init__(self) -> None:
        super().__init__(format="Letter", unit="mm")
        self.set_margins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        self.set_auto_page_break(auto=True, margin=PAGE_MARGIN)
        self.add_font("Body", "", str(FONT_REGULAR))
        self.add_font("Body", "B", str(FONT_BOLD))
        self.add_font("Body", "I", str(FONT_ITALIC))

    @property
    def content_width(self) -> float:
        return self.w - 2 * PAGE_MARGIN

    def para(self, text: str, style: str = "", size: float = BODY_SIZE,
             align: str = "L", h: float = LINE_H, indent: float = 0) -> None:
        self.set_font("Body", style, size)
        self.set_x(PAGE_MARGIN + indent)
        self.multi_cell(self.content_width - indent, h, text, align=align)

    def two_col(self, left: str, right: str, lstyle: str = "",
                rstyle: str = "", lsize: float = BODY_SIZE,
                rsize: float = 9.8, h: float = 5.2) -> None:
        """Left text with right-aligned text on the same line."""
        self.set_font("Body", lstyle, lsize)
        left_w = self.get_string_width(left)
        self.set_font("Body", rstyle, rsize)
        right_w = self.get_string_width(right) + 2
        if right and left_w + right_w <= self.content_width:
            self.set_font("Body", lstyle, lsize)
            self.cell(self.content_width - right_w, h, left)
            self.set_font("Body", rstyle, rsize)
            self.cell(right_w, h, right, align="R",
                      new_x="LMARGIN", new_y="NEXT")
        else:
            text = f"{left}  |  {right}" if right else left
            self.para(text, style=lstyle, size=lsize, h=h)

    def section_header(self, text: str, first: bool) -> None:
        self.ln(1.5 if first else 2.5)
        self.para(text, style="B", size=11.5, h=5.5)
        y = self.get_y() + 0.4
        self.set_line_width(0.3)
        self.line(PAGE_MARGIN, y, self.w - PAGE_MARGIN, y)
        self.ln(1.6)

    def category_line(self, category: str, rest: str) -> None:
        self.set_font("Body", "B", BODY_SIZE)
        self.set_x(PAGE_MARGIN)
        self.write(LINE_H, f"{category}: ")
        self.set_font("Body", "", BODY_SIZE)
        self.write(LINE_H, rest)
        self.ln(LINE_H)

    def bullet(self, text: str) -> None:
        self.set_font("Body", "", BODY_SIZE)
        self.set_x(PAGE_MARGIN + 4)
        self.multi_cell(self.content_width - 4, LINE_H, f"• {text}", align="J")


def render_pdf(resume_text: str, output_path: Path) -> Path:
    """Render plain resume text to an ATS-friendly single-column PDF."""
    pdf = ResumePDF()
    pdf.add_page()
    lines: List[str] = resume_text.splitlines()

    # Name (first non-empty line) then contact block until the first blank.
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines):
        pdf.para(lines[idx].strip(), style="B", size=15.5, align="C", h=7)
        idx += 1
    while idx < len(lines) and lines[idx].strip():
        pdf.para(lines[idx].strip(), size=9.3, align="C", h=4.6)
        idx += 1

    current_section = ""
    first_section = True
    for raw in lines[idx:]:
        stripped = raw.strip()
        if not stripped:
            continue

        if _is_section_header(stripped):
            pdf.section_header(stripped, first_section)
            first_section = False
            current_section = stripped.upper()
            continue

        if any(stripped.startswith(p) for p in BULLET_PREFIXES) or (
            stripped.startswith("*") and len(stripped) > 1
        ):
            pdf.bullet(stripped.lstrip("*-• \t"))
            continue

        if "EDUCATION" in current_section:
            edu = _parse_education(stripped)
            if edu:
                degree, university, date, gpa = edu
                pdf.ln(0.8)
                pdf.two_col(degree, date, lstyle="B", rstyle="I", h=5.0)
                if university or gpa:
                    pdf.two_col(university, gpa, lsize=9.6, rsize=9.6, h=4.8)
                continue

        if "SKILL" not in current_section:
            dated = _split_dated_line(stripped)
            if dated:
                pdf.ln(1.2)
                pdf.two_col(dated[0], dated[1], lstyle="B", rstyle="I",
                            lsize=10.3)
                continue

        cat = CATEGORY_RE.match(stripped)
        if cat and ("SKILL" in current_section or "|" not in stripped):
            pdf.category_line(cat.group(1), cat.group(2))
            continue

        pdf.para(stripped, align="J")

    try:
        pdf.output(str(output_path))
        return output_path
    except PermissionError:
        # The target is locked (usually open in a PDF viewer). Fall back to
        # a numbered name instead of crashing the whole pipeline.
        for n in range(2, 20):
            alt = output_path.with_stem(f"{output_path.stem}_{n}")
            try:
                pdf.output(str(alt))
                print(
                    f"[pdf] {output_path.name} is locked (close your PDF "
                    f"viewer). Saved as {alt.name} instead."
                )
                return alt
            except PermissionError:
                continue
        raise


if __name__ == "__main__":
    source = Path(__file__).parent / "tailored_resume.md"
    target = Path(__file__).parent / "tailored_resume.pdf"
    result = render_pdf(source.read_text(encoding="utf-8"), target)
    print(f"Rendered {result}")
