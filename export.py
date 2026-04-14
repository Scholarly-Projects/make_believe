#!/usr/bin/env python3
"""
export.py — University of Idaho ETD-Compliant Thesis Exporter
==============================================================
Generates a print-ready PDF from a CollectionBuilder-style Jekyll project.

Document order
--------------
PRELIMINARY  (lowercase roman numerals, top-right, followed by period)
  Title Page       — no page number
  Abstract         — i.
  Acknowledgments  — ii.
  List of Figures  — iii.
  Table of Contents— iv.

MAIN CONTENT  (arabic numerals, top-right, followed by period)
  Chapter 1–N      — 1. 2. 3. …
  Literature Cited — continues
  Technical Notes  — continues

Formatting rules (UI Graduate School Thesis Handbook)
  Margins : left 1.25", right/top/bottom 1.0"
  Font    : Times-Roman/Bold, 11 pt body, 14 pt headings, 9 pt captions
  Leading : 1.5× (16.5 pt body), single-spaced captions & bibliography
  Color   : black text only
  Images  : compressed to JPEG 72 % quality, max 2 400 px, ≤ 60 MB target

Usage
-----
  python export.py [project_dir] [output.pdf]
  python export.py /path/to/make_believe thesis_export.pdf

Dependencies
------------
  pip install reportlab pyyaml markdown pillow
"""

import os
import re
import sys
import csv
import tempfile
import yaml
import markdown
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Optional dependencies ─────────────────────────────────────────────────────

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: Pillow not installed — image compression disabled.\n"
          "         Run: pip install pillow")

try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.lib.colors import black
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame,
        Paragraph, Spacer, PageBreak,
        Image, KeepTogether, Flowable,
        Table, TableStyle,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Error: ReportLab not installed.\n"
          "       Run: pip install reportlab")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def to_roman(n: int) -> str:
    """Return lowercase roman numeral for positive integer n."""
    vals  = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms  = ['m', 'cm', 'd', 'cd', 'c', 'xc', 'l', 'xl', 'x', 'ix', 'v', 'iv', 'i']
    out   = ''
    for v, s in zip(vals, syms):
        while n >= v:
            out += s
            n   -= v
    return out


class SectionMarker(Flowable):
    """
    Zero-height, zero-width flowable that records the PDF page number the
    moment it is rendered. Used to build the TOC and header numbering after
    pass 1.
    """
    def __init__(self, key: str, registry: Dict[str, int]):
        super().__init__()
        self.key      = key
        self.registry = registry
        self.width    = 0
        self.height   = 0

    def wrap(self, avail_w: float, avail_h: float):
        return 0, 0

    def draw(self):
        # canv._pageNumber is the absolute page counter during rendering
        self.registry[self.key] = self.canv._pageNumber


# ─────────────────────────────────────────────────────────────────────────────
# ThesisExporter
# ─────────────────────────────────────────────────────────────────────────────

class ThesisExporter:

    # ── Geometry ──────────────────────────────────────────────────────────────
    MARGIN_LEFT   = 1.25 * inch
    MARGIN_RIGHT  = 1.00 * inch
    MARGIN_TOP    = 1.00 * inch
    MARGIN_BOTTOM = 1.00 * inch
    PAGE_WIDTH, PAGE_HEIGHT = LETTER
    USABLE_WIDTH  = PAGE_WIDTH - (MARGIN_LEFT + MARGIN_RIGHT)
    USABLE_HEIGHT = PAGE_HEIGHT - (MARGIN_TOP  + MARGIN_BOTTOM)
    MAX_IMG_HEIGHT = 4.5 * inch   # ≈ 50 % of usable height — keeps caption together

    # ── Image compression settings ────────────────────────────────────────────
    IMG_MAX_PX    = 2400    # longest edge in pixels before downscaling
    IMG_QUALITY   = 72      # JPEG quality (lower = smaller file)

    def __init__(self, base_path: str, output_path: Optional[str] = None):
        self.base_path   = Path(base_path).resolve()
        self.output_path = (Path(output_path) if output_path
                            else self.base_path / "thesis_export.pdf")

        # Data
        self.config          : Dict            = {}
        self.essays          : List[Dict]      = []
        self.metadata_lookup : Dict[str, Dict] = {}
        self.ordered_figures : List[Dict]      = []
        self.citations       : List[Dict]      = []

        # Fonts
        self.font_body = 'Times-Roman'
        self.font_bold = 'Times-Bold'

        # State (reset between passes)
        self.story           : List[Any]       = []
        self.processed_images: set             = set()
        self.figure_count    : int             = 0

        # Populated by pass 1
        self.section_starts  : Dict[str, int]  = {}

        # Temp files for compressed images (cleaned up after build)
        self._temp_files     : List[str]       = []

        # Cached styles
        self.styles          = None

    # ─────────────────────────────────────────────────────────────────────────
    # Data loading
    # ─────────────────────────────────────────────────────────────────────────

    def load_data(self):
        """Load _config.yml, CSV metadata/citations, and essay markdown files."""

        # Config
        cfg_path = self.base_path / "_config.yml"
        with open(cfg_path, 'r', encoding='utf-8') as fh:
            raw_cfg = unicodedata.normalize('NFC', fh.read())
            self.config = yaml.safe_load(raw_cfg)

        # Figure metadata (order from CSV = figure appearance order in text)
        meta_name    = self.config.get('metadata', 'make_believe')
        metadata_path = self.base_path / "_data" / f"{meta_name}.csv"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as fh:
                raw_meta = unicodedata.normalize('NFC', fh.read())
                self.ordered_figures = list(csv.DictReader(raw_meta.splitlines()))
            for row in self.ordered_figures:
                self.metadata_lookup[row['objectid']] = row
        else:
            print(f"Warning: metadata CSV not found at {metadata_path}")

        # Citations (order from CSV = Literature Cited order)
        citation_path = self.base_path / "_data" / "citation.csv"
        if citation_path.exists():
            with open(citation_path, 'r', encoding='utf-8') as fh:
                raw_cite = unicodedata.normalize('NFC', fh.read())
                self.citations = list(csv.DictReader(raw_cite.splitlines()))
        else:
            print(f"Warning: citation.csv not found at {citation_path}")

        # Essays — load in filesystem order, then sort by front-matter 'order'
        essay_dir = self.base_path / "_essay"
        for essay_file in sorted(essay_dir.glob("*.md")):
            with open(essay_file, 'r', encoding='utf-8') as fh:
                raw = unicodedata.normalize('NFC', fh.read())
            parts = raw.split('---', 2)
            fm    = yaml.safe_load(parts[1]) if len(parts) > 1 else {}
            body  = parts[2].strip()         if len(parts) > 2 else raw.strip()
            self.essays.append({
                'title'  : fm.get('title',  essay_file.stem),
                'order'  : fm.get('order',  99),
                'content': body,
            })
        self.essays.sort(key=lambda e: e['order'])

    def _load_page_md(self, filename: str) -> str:
        """Return the body text of a pages/ markdown file (front matter stripped)."""
        path = self.base_path / "pages" / filename
        if not path.exists():
            return ""
        with open(path, 'r', encoding='utf-8') as fh:
            raw = unicodedata.normalize('NFC', fh.read())
        parts = raw.split('---', 2)
        return (parts[2].strip() if len(parts) > 2 else raw.strip())

    # ─────────────────────────────────────────────────────────────────────────
    # Styles & Fonts
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_fonts(self):
        """Attempt to register TrueType fonts for full UTF-8 character support."""
        try:
            # Place times.ttf and timesbd.ttf in the same directory as the script
            # or provide an absolute path to system fonts.
            pdfmetrics.registerFont(TTFont('TimesNewRoman-TTF', 'times.ttf'))
            pdfmetrics.registerFont(TTFont('TimesNewRoman-TTF-Bold', 'timesbd.ttf'))
            self.font_body = 'TimesNewRoman-TTF'
            self.font_bold = 'TimesNewRoman-TTF-Bold'
            print("  Loaded TrueType fonts for extended character support.")
        except Exception:
            print("  Note: TrueType fonts (times.ttf) not found. Standard ReportLab fonts will be used.")
            self.font_body = 'Times-Roman'
            self.font_bold = 'Times-Bold'

    def _setup_styles(self):
        self.styles = getSampleStyleSheet()

        def add(name: str, **kw):
            if name not in self.styles:
                self.styles.add(ParagraphStyle(name=name, **kw))

        # Body — 11 pt, 1.5 leading, justified, first-line 0.5" indent
        add('ThesisBody',
            fontName=self.font_body, fontSize=11, leading=16.5,
            alignment=TA_JUSTIFY, firstLineIndent=0.5 * inch, textColor=black)

        # Heading — 14 pt bold, centred; caller provides ALL-CAPS text
        add('ThesisHeading',
            fontName=self.font_bold, fontSize=14, leading=21,
            alignment=TA_CENTER, spaceBefore=12, spaceAfter=18,
            keepWithNext=True, textColor=black)

        # Caption — 9 pt, centred, single-spaced
        add('ThesisCaption',
            fontName=self.font_body, fontSize=9, leading=11,
            alignment=TA_CENTER, spaceBefore=4, spaceAfter=10, textColor=black)

        # Bibliography / literature cited — hanging indent, single-spaced
        add('ThesisBib',
            fontName=self.font_body, fontSize=11, leading=16.5,
            alignment=TA_JUSTIFY,
            firstLineIndent=-(0.3 * inch), leftIndent=0.3 * inch,
            spaceBefore=0, spaceAfter=6, textColor=black)

        # Centred body (degree statement lines, "by", date, etc.)
        add('ThesisCentered',
            fontName=self.font_body, fontSize=11, leading=16.5,
            alignment=TA_CENTER, textColor=black)

        # Approval block (left-aligned body size)
        add('ThesisApproval',
            fontName=self.font_body, fontSize=11, leading=16.5,
            alignment=TA_LEFT, textColor=black)

        # TOC entries
        add('ThesisTOC',
            fontName=self.font_body, fontSize=11, leading=16.5,
            alignment=TA_LEFT, firstLineIndent=0, textColor=black)

        # LOF entries (indented)
        add('ThesisLOF',
            fontName=self.font_body, fontSize=11, leading=16.5,
            alignment=TA_LEFT, firstLineIndent=0,
            leftIndent=0.35 * inch, textColor=black)

    # ─────────────────────────────────────────────────────────────────────────
    # Page header (called by ReportLab on every page)
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_header(self, canvas, doc):
        """
        Draws the page number top-right, followed by a period.
          page 1         : no number  (title page)
          pages 2 …      : i. ii. iii. … until first chapter
          first chapter+ : 1. 2. 3. …
        """
        page      = doc.page
        main_start = self.section_starts.get('ch1')

        if page == 1:
            return

        if main_start is None or page < main_start:
            label = to_roman(page - 1) + "."   # page 2 → i., page 3 → ii. …
        else:
            label = str(page - main_start + 1) + "."

        canvas.saveState()
        canvas.setFont(self.font_body, 11)
        canvas.drawRightString(
            self.PAGE_WIDTH  - self.MARGIN_RIGHT,
            self.PAGE_HEIGHT - 0.75 * inch,
            label,
        )
        canvas.restoreState()

    # ─────────────────────────────────────────────────────────────────────────
    # Image handling
    # ─────────────────────────────────────────────────────────────────────────

    def _find_image(self, obj_id: str) -> Optional[Path]:
        """Locate an image file for obj_id; tries jpg, jpeg, png, gif, tif."""
        objects_dir = self.base_path / "objects"
        for ext in ('.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.webp'):
            p = objects_dir / f"{obj_id}{ext}"
            if p.exists():
                return p
        return None

    def _compress_image(self, img_path: Path) -> str:
        """
        Compress and optionally downscale an image using Pillow.
        Returns path to a temporary JPEG (or original path if Pillow unavailable).
        GIFs and other non-JPEG formats are also converted to JPEG here.
        """
        if not PIL_AVAILABLE:
            return str(img_path)
        try:
            with PILImage.open(img_path) as im:
                # Normalise mode → RGB
                if im.mode == 'P':
                    im = im.convert('RGBA')
                if im.mode in ('RGBA', 'LA'):
                    bg = PILImage.new('RGB', im.size, (255, 255, 255))
                    bg.paste(im, mask=im.split()[-1])
                    im = bg
                elif im.mode != 'RGB':
                    im = im.convert('RGB')

                # Downscale very large images
                w, h = im.size
                if max(w, h) > self.IMG_MAX_PX:
                    scale = self.IMG_MAX_PX / max(w, h)
                    im = im.resize(
                        (int(w * scale), int(h * scale)),
                        PILImage.LANCZOS,
                    )

                tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                im.save(tmp.name, 'JPEG',
                        quality=self.IMG_QUALITY,
                        optimize=True,
                        progressive=True)
                self._temp_files.append(tmp.name)
                return tmp.name

        except Exception as exc:
            print(f"  Warning: could not compress {img_path.name}: {exc}")
            return str(img_path)

    def _make_figure(self, obj_id: str) -> Optional[List[Any]]:
        """
        Build [Image, Caption] flowables for one figure.
        Returns None if the object is unknown, already rendered, or file missing.
        """
        if obj_id not in self.metadata_lookup:
            return None
        if obj_id in self.processed_images:
            return None
        raw_path = self._find_image(obj_id)
        if raw_path is None:
            print(f"  Warning: image file not found for {obj_id}")
            return None

        self.figure_count += 1
        meta     = self.metadata_lookup[obj_id]
        img_file = self._compress_image(raw_path)

        img           = Image(img_file)
        orig_w, orig_h = img.wrap(0, 0)
        scale          = self.USABLE_WIDTH / float(orig_w)
        if orig_h * scale > self.MAX_IMG_HEIGHT:
            scale = self.MAX_IMG_HEIGHT / float(orig_h)
        img.drawWidth  = orig_w * scale
        img.drawHeight = orig_h * scale

        # FIX: Removed the redundant 'title' variable prefix [cite: 168]
        img_cite = meta.get('image_citation', '')
        caption  = f"Figure {self.figure_count}. {img_cite}".strip(". ")
        caption  = caption + "."

        self.processed_images.add(obj_id)
        return [img, Paragraph(caption, self.styles['ThesisCaption'])]

    # ─────────────────────────────────────────────────────────────────────────
    # Markdown processing
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_for_reportlab(html_fragment: str) -> str:
        """
        Sanitize an HTML fragment for ReportLab's Paragraph parser.
        - <br>, <br/>, <br /> → space   (bare void tags crash the parser)
        - ^123 → <super>123</super>     (markdown-style footnote markers)
        - <a href="...">text</a> → text  (links are not rendered, keep text only)
        - Collapse extra whitespace
        """
        # Footnote markers  ^163 → superscript
        clean = re.sub(r'\^(\d+)', r'<super>\1</super>', html_fragment)
        # Strip href links but keep visible text
        clean = re.sub(r'<a\b[^>]*>(.*?)</a>', r'\1', clean, flags=re.IGNORECASE | re.DOTALL)
        # <br />, <br/>, <br> → space
        clean = re.sub(r'<br\s*/?>', ' ', clean, flags=re.IGNORECASE)
        # Collapse excess whitespace
        clean = re.sub(r'  +', ' ', clean).strip()
        return clean

    def _md_to_paragraphs(self, text: str, style) -> List[Any]:
        """Convert a plain markdown string to a list of Paragraph flowables."""
        if not text:
            return []
        # Do NOT use nl2br — it injects <br> tags that crash ReportLab's parser
        md   = markdown.Markdown()
        html = md.convert(text)
        out  = []
        for p_text in re.findall(r'<p>(.*?)</p>', html, flags=re.DOTALL):
            p_text = self._sanitize_for_reportlab(p_text)
            if p_text:
                out.append(Paragraph(p_text, style))
        return out

    def _process_essay_md(self, text: str) -> List[Any]:
        """
        Parse essay markdown that may contain CollectionBuilder trigger tags:
        {% include trigger.html id="make_believe_001" action:start %}
        Paragraphs are rendered as ThesisBody; triggers become figures.
        """
        flowables = []
        # Split on any {% ... %} block
        parts = re.split(r'(\{%.*?%\})', text, flags=re.DOTALL)
        for part in parts:
            part = part.strip()
            if not part:
                continue

            if part.startswith('{%'):
                id_match = re.search(r"id:\s*['\"]?([a-zA-Z0-9_-]+)['\"]?", part)
                if id_match:
                    fig = self._make_figure(id_match.group(1))
                    if fig:
                        flowables.append(KeepTogether(fig))
                continue

            # Strip any stray liquid tags left in prose
            clean = re.sub(r'\{%.*?%\}', '', part, flags=re.DOTALL).strip()
            flowables.extend(
                self._md_to_paragraphs(clean, self.styles['ThesisBody'])
            )

        return flowables

    # ─────────────────────────────────────────────────────────────────────────
    # TOC helper
    # ─────────────────────────────────────────────────────────────────────────

    def _page_label(self, key: str, pass_num: int) -> str:
        """
        Return the formatted page label for a given section key.
        Pass 1 returns '…' (section_starts not yet known).
        Pass 2 converts absolute page → roman or arabic label.
        """
        if pass_num < 2 or key not in self.section_starts:
            return "…"
        raw        = self.section_starts[key]
        main_start = self.section_starts.get('ch1', 9999)
        if raw < main_start:
            return to_roman(raw - 1) + "."   # preliminary → roman
        else:
            return str(raw - main_start + 1) + "."

    def _toc_row(self, label: str, pg: str) -> Table:
        """
        One TOC row: label on the left, page number right-aligned.
        Uses a two-column Table so the page number is always flush-right.
        """
        NUM_COL = 0.55 * inch
        t = Table(
            data    = [[label, pg]],
            colWidths = [self.USABLE_WIDTH - NUM_COL, NUM_COL],
            hAlign  = 'LEFT',
        )
        t.setStyle(TableStyle([
            ('FONT',           (0, 0), (-1, -1), self.font_body, 11),
            ('LEADING',        (0, 0), (-1, -1), 16.5),
            ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
            ('ALIGN',          (1, 0), (1,  -1), 'RIGHT'),
            ('TOPPADDING',     (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING',  (0, 0), (-1, -1), 1),
            ('LEFTPADDING',    (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',   (0, 0), (-1, -1), 0),
        ]))
        return t

    # ─────────────────────────────────────────────────────────────────────────
    # Document sections
    # ─────────────────────────────────────────────────────────────────────────

    def _build_title_page(self):
        s = self.story
        cs = self.styles['ThesisCentered']

        s.append(Spacer(1, 0.5 * inch))
        s.append(Paragraph(self.config.get('title', '').upper(),
                            self.styles['ThesisHeading']))
        tagline = self.config.get('tagline', '')
        if tagline:
            s.append(Paragraph(tagline, self.styles['ThesisHeading']))

        s.append(Spacer(1, 0.75 * inch))
        for line in (
            "A Thesis",
            "Presented in Partial Fulfillment of the Requirements for the",
            "Degree of Master of Arts",
            "with a",
            "Major in History",
            "in the",
            "College of Graduate Studies",
            "University of Idaho",
        ):
            s.append(Paragraph(line, cs))

        s.append(Spacer(1, 0.5 * inch))
        s.append(Paragraph("by", cs))
        s.append(Paragraph(self.config.get('author', '').upper(),
                            self.styles['ThesisHeading']))

        s.append(Spacer(1, 0.75 * inch))
        ap = self.styles['ThesisApproval']
        s.append(KeepTogether([
            Paragraph("Approved by:", ap),
            Spacer(1, 6),
            Paragraph("Major Professor:\u2003________________________", ap),
            Paragraph("Committee Members:\u2003________________________", ap),
            Paragraph("Department Administrator:\u2003________________________", ap),
        ]))

        s.append(Spacer(1, 0.5 * inch))
        s.append(Paragraph("December 2026", cs))
        s.append(PageBreak())

    def _build_acknowledgments(self):
        self.story.append(SectionMarker('acknowledgments', self.section_starts))
        self.story.append(Paragraph("ACKNOWLEDGMENTS", self.styles['ThesisHeading']))
        body = self._load_page_md("acknowledgements.md")
        if body:
            self.story.extend(
                self._md_to_paragraphs(body, self.styles['ThesisBody'])
            )
        else:
            self.story.append(
                Paragraph("[Acknowledgments text here.]", self.styles['ThesisBody'])
            )
        self.story.append(PageBreak())

    def _build_abstract(self):
        self.story.append(SectionMarker('abstract', self.section_starts))
        self.story.append(Paragraph("ABSTRACT", self.styles['ThesisHeading']))
        for para in (
            "This work contends that Spokane, Washington's origins represent overlapping "
            "colonialism, where settler ambitions were supplanted by predatory Dutch financial "
            "interests between 1889 and 1923. Capital originating from the Dutch merchant class, "
            "fueled by the 1870s Cape Era diamond boom, flowed into American railway bonds to "
            "establish a foreign-controlled financial market. Consequently, the city's aggressive "
            "display of both exclusionary and aspirational iconography was less an act of civic pride than a cultural "
            "assertion of American identity that obscured its relationship with foreign capital.",

            "While imitation of cultures was common for European American settlers in the Pacific "
            "Northwest during this period, Spokane's booster-driven \u201cInland Empire\u201d "
            "marketing strategies uniquely relied on a pervasive, public display of cultural and "
            "class-based mimicry and affectation. The city's rapid Dutch-financed reconstruction "
            "following the 1889 fire created an artificially inflated metropolis amidst otherwise "
            "sparse agricultural hubs, generating dissonance between the built environment and "
            "pioneer identities that was mediated by civic rituals and commercial pageantry.",

            "Situating Spokane within evolving ideologies of U.S. expansion, this paper highlights "
            "the contradiction between America's professed aversion to foreign entanglement and its "
            "imperial practices. Drawing on contemporaneous Dutch-language media and interviews with "
            "foreign financiers, the work introduces an international perspective largely absent from "
            "existing American historiography. The paper draws on a wide range of archival visual "
            "materials that document pioneer iconography and expressions of ethnic anxiety with a "
            "level of transparency largely absent from written accounts. To support this visually "
            "driven approach, the thesis is presented as a custom digital exhibit, enabling readers "
            "to place these materials in direct dialogue with the historic media, correspondence, "
            "and literature that form the foundation of the research.",
        ):
            self.story.append(Paragraph(para, self.styles['ThesisBody']))
        self.story.append(PageBreak())

    def _build_list_of_figures(self):
        """
        List every figure in the order it appears in the metadata CSV —
        which matches the order figures appear in the text.
        Text wraps correctly because cells contain Paragraph objects.
        """
        self.story.append(SectionMarker('lof', self.section_starts))
        self.story.append(Paragraph("LIST OF FIGURES", self.styles['ThesisHeading']))

        LABEL_W = 0.95 * inch   # "Figure NN." label column
        # Body style with no first-line indent for LOF entries
        lof_body = ParagraphStyle(
            'LOFBody', parent=self.styles['ThesisBody'],
            firstLineIndent=0, alignment=TA_LEFT,
        )

        for i, row in enumerate(self.ordered_figures, 1):
            # FIX: Removed the redundant 'title' variable prefix [cite: 203]
            img_cite = row.get('image_citation', '')
            full_title = img_cite.strip(". ") + "."

            t = Table(
                data      = [[
                    Paragraph(f"Figure {i}.", lof_body),
                    Paragraph(full_title,      lof_body),
                ]],
                colWidths = [LABEL_W, self.USABLE_WIDTH - LABEL_W],
                hAlign  = 'LEFT',
            )
            t.setStyle(TableStyle([
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING',    (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ('LEFTPADDING',   (0, 0), (-1, -1), 0),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
            ]))
            self.story.append(t)

        self.story.append(PageBreak())

    def _build_toc(self, pass_num: int):
        self.story.append(SectionMarker('toc', self.section_starts))
        self.story.append(Paragraph("TABLE OF CONTENTS", self.styles['ThesisHeading']))

        def row(label, key):
            self.story.append(self._toc_row(label, self._page_label(key, pass_num)))

        # Preliminary sections (in document order)
        row("ABSTRACT",           'abstract')
        row("ACKNOWLEDGMENTS",    'acknowledgments')
        row("LIST OF FIGURES",    'lof')
        row("TABLE OF CONTENTS",  'toc')

        self.story.append(Spacer(1, 6))

        # Chapters
        for i, essay in enumerate(self.essays, 1):
            row(f"CHAPTER {i}: {essay['title'].upper()}", f'ch{i}')

        self.story.append(Spacer(1, 6))

        # Back matter
        row("LITERATURE CITED", 'lit_cited')
        row("TECHNICAL NOTES",  'tech_notes')

        self.story.append(PageBreak())

    def _build_chapters(self):
        for i, essay in enumerate(self.essays, 1):
            self.story.append(SectionMarker(f'ch{i}', self.section_starts))
            self.story.append(
                Paragraph(f"CHAPTER {i}: {essay['title'].upper()}",
                          self.styles['ThesisHeading'])
            )
            self.story.extend(self._process_essay_md(essay['content']))
            self.story.append(PageBreak())

    def _build_lit_cited(self):
        """
        Render citations in the row order of citation.csv
        (i.e., the order they appear in the text, not alphabetically).
        """
        self.story.append(SectionMarker('lit_cited', self.section_starts))
        self.story.append(Paragraph("LITERATURE CITED", self.styles['ThesisHeading']))

        for i, cite in enumerate(self.citations, 1):
            text = (cite.get('text') or cite.get('citation') or
                    cite.get('full_citation') or '').strip()
            if text:
                self.story.append(
                    KeepTogether(
                        Paragraph(f"{i}.\u2003{text}", self.styles['ThesisBib'])
                    )
                )

        self.story.append(PageBreak())

    def _build_tech_notes(self):
        self.story.append(SectionMarker('tech_notes', self.section_starts))
        self.story.append(Paragraph("TECHNICAL NOTES", self.styles['ThesisHeading']))

        # ── Subheading style (smaller than chapter heading, left-aligned) ──
        sub_style = ParagraphStyle(
            'TechSubhead', parent=self.styles['ThesisHeading'],
            fontSize=12, leading=18, alignment=TA_LEFT,
            spaceBefore=14, spaceAfter=10,
        )
        # ── Bullet style — indented, no first-line indent ──────────────────
        bullet_style = ParagraphStyle(
            'TechBullet', parent=self.styles['ThesisBody'],
            firstLineIndent=0, leftIndent=0.4 * inch,
            spaceBefore=2, spaceAfter=2,
        )

        # Opening paragraph
        self.story.append(Paragraph(
            "To support the visual resource-oriented nature of this project, I wanted to develop "
            "a digital exhibit template that would allow readers the ability to allow these images "
            "to be in dialogue with the research to underpin the historical argument of the thesis. "
            "The resulting essay template, named Textemporal, is an iteration of my colleague "
            "Devin Becker\u2019s CB Essay and follows CollectionBuilder\u2019s static web hosting "
            "approach. The template was specifically designed to support scholarly work, providing "
            "the reader with just enough information to help them move through the research material "
            "while keeping the reading interface minimal and lightweight.",
            self.styles['ThesisBody'],
        ))

        # Subheading
        self.story.append(Paragraph("Template Features", sub_style))

        # Bullet list
        bullets = [
            "Reading interface is designed to set off a series of citation and image triggers, "
            "which are activated as the reader progresses through the text.",
            "\"Sticky\" media configuration where images remain static as the text scrolls "
            "through vertically, intended for a more concentrated, unified reading experience.",
            "Sidebar which generates a text citation following the reader\u2019s progress through "
            "the material, providing only the most relevant information without cluttering "
            "the interface.",
            "Programmatic manipulation of how images display, where the author of the template "
            "can enter zoom and coordinate data in the essay markdown templates to control how "
            "readers view the media as they scroll through the text.",
            "Citations and images are informed by CSV data, allowing for automatic generation "
            "and editing of Image Credit and Bibliography pages.",
            "\u201cInfinite Scroll\u201d function, which allows readers to seamlessly scroll "
            "from one chapter to another in the essay section of the site, so they can remain "
            "focused on the text, rather than hunting in menu drop-downs to progress. Images and "
            "citations are triggered identically moving both forward and backwards in the text "
            "like an audio recording, which is where the temporal in Textemporal comes from.",
            "Scroll state preservation, to ensure that the reader is returned to where they left "
            "off in the chapter, if they engage with the associated item-level images or "
            "text citations.",
            "Light / Dark mode toggle for essay portions of the site.",
            "Mobile configuration, which displays images and their associated citations in full.",
            "Minimal, horizontally-oriented site design.",
            "Dual navigation tracks: readers can quickly use arrow keys to cycle through "
            "site-level pages (home, browse, map, etc.), or drop down to the item-level pages "
            "to cycle through that material.",
            "Retains CollectionBuilder\u2019s database-oriented approach allowing readers to "
            "dive deeper into the media that complements the essay material and make further "
            "research connections by visualizing those items chronologically, geographically, "
            "or thematically.",
        ]

        for item in bullets:
            self.story.append(
                Paragraph(f"\u2022\u2002{item}", bullet_style)
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Assembly and build
    # ─────────────────────────────────────────────────────────────────────────

    def _assemble(self, pass_num: int):
        """Assemble self.story for a given pass number."""
        self.story            = []
        self.processed_images = set()
        self.figure_count     = 0

        self._build_title_page()
        self._build_abstract()           # i.
        self._build_acknowledgments()    # ii.
        self._build_list_of_figures()    # iii.
        self._build_toc(pass_num)        # iv.
        self._build_chapters()
        self._build_lit_cited()
        self._build_tech_notes()

    def _make_doc(self, path: str) -> BaseDocTemplate:
        """Construct a BaseDocTemplate with correct frame and page template."""
        doc = BaseDocTemplate(
            path,
            pagesize    = LETTER,
            compress    = 1,         # zlib-compress all PDF content streams
            leftMargin  = self.MARGIN_LEFT,
            rightMargin = self.MARGIN_RIGHT,
            topMargin   = self.MARGIN_TOP,
            bottomMargin= self.MARGIN_BOTTOM,
        )
        frame = Frame(
            self.MARGIN_LEFT,
            self.MARGIN_BOTTOM,
            self.USABLE_WIDTH,
            self.USABLE_HEIGHT,
            id='normal',
        )
        doc.addPageTemplates([
            PageTemplate(id='thesis', frames=frame, onPage=self._draw_header)
        ])
        return doc

    def build(self):
        if not REPORTLAB_AVAILABLE:
            print("Cannot build: ReportLab not installed.")
            return

        self.load_data()
        self._setup_fonts()
        self._setup_styles()

        # ── Pass 1: render to /dev/null to record section page numbers ─────
        print("Pass 1: calculating page layout …")
        tmp_path = str(self.output_path) + "._pass1.tmp"
        self._assemble(pass_num=1)
        self._make_doc(tmp_path).build(self.story)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        print(f"  Section starts: { {k: v for k, v in sorted(self.section_starts.items())} }")

        # ── Pass 2: render final PDF with correct page numbers and TOC ─────
        print("Pass 2: building final PDF …")
        self._assemble(pass_num=2)
        self._make_doc(str(self.output_path)).build(self.story)

        # Cleanup compressed image temps
        for tmp in self._temp_files:
            try:
                os.remove(tmp)
            except OSError:
                pass

        # Report file size
        size_mb = os.path.getsize(self.output_path) / (1024 ** 2)
        print(f"Exported: {self.output_path}  ({size_mb:.1f} MB)")
        if size_mb > 60:
            print(
                f"\nWarning: PDF is {size_mb:.1f} MB — exceeds the 60 MB target.\n"
                "  Try lowering IMG_QUALITY (currently "
                f"{self.IMG_QUALITY}) or IMG_MAX_PX ({self.IMG_MAX_PX}).\n"
                "  Example: exporter.IMG_QUALITY = 60; exporter.IMG_MAX_PX = 1800"
            )

# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    out_file = sys.argv[2] if len(sys.argv) > 2 else None
    ThesisExporter(base_dir, out_file).build()