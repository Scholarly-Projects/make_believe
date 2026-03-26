#!/usr/bin/env python3
"""
export.py - UI ETD Compliant Exporter
Fixes: Title page overflow, Page number formatting (e.g., 2.), 
       and strict consistency in headings.
"""

import os
import sys
import re
import csv
import yaml
import markdown
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame, Paragraph, 
        Spacer, PageBreak, Image, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.lib.colors import black
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

class ThesisExporter:
    # U of Idaho Margins
    MARGIN_LEFT = 1.25 * inch
    MARGIN_RIGHT = 1.0 * inch
    MARGIN_TOP = 1.0 * inch
    MARGIN_BOTTOM = 1.0 * inch
    PAGE_WIDTH, PAGE_HEIGHT = LETTER
    USABLE_WIDTH = PAGE_WIDTH - (MARGIN_LEFT + MARGIN_RIGHT)
    MAX_IMG_HEIGHT = 4.5 * inch # Slightly under 50% for safety

    def __init__(self, base_path: str, output_path: Optional[str] = None):
        self.base_path = Path(base_path).resolve()
        self.output_path = Path(output_path) if output_path else self.base_path / "thesis_export.pdf"
        self.config = {}
        self.essays = []
        self.metadata_lookup = {}
        self.ordered_figures = []
        self.citations = []
        self.story = []
        self.styles = None
        self.processed_images = set()
        self.figure_count = 0

    def load_data(self):
        # Load _config.yml
        with open(self.base_path / "_config.yml", 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # Load Metadata and Figures
        metadata_path = self.base_path / "_data" / f"{self.config.get('metadata', 'make_believe')}.csv"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                self.ordered_figures = list(csv.DictReader(f))
                for row in self.ordered_figures:
                    self.metadata_lookup[row['objectid']] = row

        # Load Citations
        citation_path = self.base_path / "_data" / "citation.csv"
        if citation_path.exists():
            with open(citation_path, 'r', encoding='utf-8') as f:
                self.citations = list(csv.DictReader(f))

        # Load Essays
        essay_dir = self.base_path / "_essay"
        for essay_file in sorted(essay_dir.glob("*.md")):
            with open(essay_file, 'r', encoding='utf-8') as f:
                content = f.read()
                parts = content.split('---', 2)
                fm = yaml.safe_load(parts[1]) if len(parts) > 1 else {}
                body = parts[2].strip() if len(parts) > 2 else content
                self.essays.append({'title': fm.get('title', essay_file.stem), 'order': fm.get('order', 99), 'content': body})
        self.essays.sort(key=lambda x: x['order'])

    def _setup_styles(self):
        self.styles = getSampleStyleSheet()
        # 11pt Body, 1.5 spacing (16.5 leading)
        self.styles.add(ParagraphStyle(
            name='ThesisBody', fontName='Times-Roman', fontSize=11, leading=16.5,
            alignment=TA_JUSTIFY, firstLineIndent=0.5 * inch, textColor=black
        ))
        # 14pt Heading, All Caps, Bold, Centered
        self.styles.add(ParagraphStyle(
            name='ThesisHeading', fontName='Times-Bold', fontSize=14, leading=18,
            alignment=TA_CENTER, spaceBefore=12, spaceAfter=18, keepWithNext=True, textColor=black
        ))
        # 9pt Captions
        self.styles.add(ParagraphStyle(
            name='ThesisCaption', fontName='Times-Roman', fontSize=9, leading=11,
            alignment=TA_CENTER, spaceBefore=6, spaceAfter=12, textColor=black
        ))

    def _draw_header(self, canvas, doc):
        """Upper right page numbers with period."""
        if doc.page > 1:
            page_text = f"{doc.page}."
            canvas.saveState()
            canvas.setFont('Times-Roman', 11)
            canvas.drawRightString(self.PAGE_WIDTH - self.MARGIN_RIGHT, self.PAGE_HEIGHT - 0.75 * inch, page_text)
            canvas.restoreState()

    def _create_title_page(self):
        """Constructs title page to match template without spilling over."""
        # Title Section
        self.story.append(Spacer(1, 0.5 * inch))
        self.story.append(Paragraph(self.config.get('title', '').upper(), self.styles['ThesisHeading']))
        # Changed: Use ThesisHeading (centered) for subtitle
        self.story.append(Paragraph(self.config.get('tagline', ''), self.styles['ThesisHeading']))
        
        # Degree Statement
        self.story.append(Spacer(1, 0.75 * inch))
        degree_style = ParagraphStyle('Degree', parent=self.styles['ThesisCaption'], alignment=TA_CENTER, fontSize=11)
        lines = [
            "A Thesis", "Presented in Partial Fulfillment of the Requirements for the",
            "Degree of Master of Arts", "with a", "Major in History", "in the",
            "College of Graduate Studies", "University of Idaho"
        ]
        for line in lines:
            self.story.append(Paragraph(line, degree_style))
        
        # Author
        self.story.append(Spacer(1, 0.5 * inch))
        self.story.append(Paragraph("by", degree_style))
        self.story.append(Paragraph(self.config.get('author', '').upper(), self.styles['ThesisHeading']))
        
        # Approval Block (Compact)
        self.story.append(Spacer(1, 0.75 * inch))
        app_style = ParagraphStyle('Approve', parent=self.styles['ThesisCaption'], alignment=TA_LEFT, fontSize=10, leading=14)
        self.story.append(KeepTogether([
            Paragraph("Approved by:", app_style),
            Paragraph("Major Professor: ________________________", app_style),
            Paragraph("Committee Members: ________________________", app_style),
            Paragraph("Department Administrator: ________________________", app_style)
        ]))
        
        # Date
        self.story.append(Spacer(1, 0.5 * inch))
        self.story.append(Paragraph("December 2026", degree_style))
        self.story.append(PageBreak())

    def _process_markdown(self, text: str) -> List[Any]:
        flowables = []
        parts = re.split(r'(\{%\s*trigger.*?action:\s*start.*?%\})', text, flags=re.DOTALL)
        for part in parts:
            if part.startswith('{%'):
                id_match = re.search(r'id:\s*([a-zA-Z0-9_-]+)', part)
                if id_match:
                    obj_id = id_match.group(1)
                    if obj_id in self.metadata_lookup and obj_id not in self.processed_images:
                        self.figure_count += 1
                        meta = self.metadata_lookup[obj_id]
                        # Image logic
                        img_path = self.base_path / "objects" / f"{obj_id}.jpg"
                        if img_path.exists():
                            img = Image(str(img_path))
                            orig_w, orig_h = img.wrap(0, 0)
                            scale = self.USABLE_WIDTH / float(orig_w)
                            if (orig_h * scale) > self.MAX_IMG_HEIGHT:
                                scale = self.MAX_IMG_HEIGHT / float(orig_h)
                            img.drawWidth, img.drawHeight = orig_w * scale, orig_h * scale
                            caption = f"Figure {self.figure_count}: \"{meta.get('image_citation', '')}\""
                            flowables.append(KeepTogether([img, Paragraph(caption, self.styles['ThesisCaption'])]))
                            self.processed_images.add(obj_id)
                continue
            
            md = markdown.Markdown()
            html = md.convert(re.sub(r'\{%.*?%\}', '', part))
            for p_text in re.findall(r'<p>(.*?)</p>', html, flags=re.DOTALL):
                if p_text.strip():
                    flowables.append(Paragraph(p_text, self.styles['ThesisBody']))
        return flowables

    def build(self):
        if not REPORTLAB_AVAILABLE: return
        self.load_data()
        self._setup_styles()
        doc = BaseDocTemplate(str(self.output_path), pagesize=LETTER)
        frame = Frame(self.MARGIN_LEFT, self.MARGIN_BOTTOM, self.USABLE_WIDTH, 
                      self.PAGE_HEIGHT - (self.MARGIN_TOP + self.MARGIN_BOTTOM), id='normal')
        doc.addPageTemplates([PageTemplate(id='UI', frames=frame, onPage=self._draw_header)])

        self._create_title_page()
        for i, essay in enumerate(self.essays, 1):
            self.story.append(Paragraph(f"CHAPTER {i}: {essay['title'].upper()}", self.styles['ThesisHeading']))
            self.story.extend(self._process_markdown(essay['content']))
            self.story.append(PageBreak())

        self.story.append(Paragraph("LITERATURE CITED", self.styles['ThesisHeading']))
        bib_style = ParagraphStyle('Bib', parent=self.styles['ThesisBody'], firstLineIndent=-0.3*inch, leftIndent=0.3*inch)
        for i, cite in enumerate(self.citations, 1):
            self.story.append(KeepTogether(Paragraph(f"{i}. {cite.get('text', '')}", bib_style)))

        doc.build(self.story)
        print(f"Exported: {self.output_path}")

if __name__ == "__main__":
    ThesisExporter(".").build()
