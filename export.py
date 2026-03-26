#!/usr/bin/env python3
"""
export_thesis.py - Export CollectionBuilder Jekyll Thesis to PDF

This script converts a CollectionBuilder-based digital thesis into a 
University of Idaho ETD-compliant PDF document.

Requirements:
    pip install reportlab pyyaml markdown python-dateutil

Usage:
    python export_thesis.py [--output OUTPUT_PATH] [--debug]

Author: Andrew Weymouth
Project: Make, Believe - MA History Thesis, University of Idaho
"""

import os
import sys
import re
import csv
import yaml
import markdown
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('thesis_export.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether,
        Table, TableStyle, Image, ListFlowable, ListItem
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.pdfgen import canvas
    from reportlab.lib.fonts import addMapping
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not available. Install with: pip install reportlab")


class ThesisExporter:
    """
    Export CollectionBuilder Jekyll thesis to University of Idaho ETD-compliant PDF.
    
    Formatting Standards (per U of Idaho COGS):
    - Paper size: 8.5" x 11"
    - Margins: 1.25" left, 1" right, 1" top, 1" bottom
    - Font: Times New Roman, 11pt main text, 14pt chapter titles
    - Line spacing: 1.5
    - Page numbers: Roman numerals (ii, iii, iv...) for preliminary pages,
                   Arabic (1, 2, 3...) starting with Chapter 1
    - Title page: No page number
    """
    
    # University of Idaho formatting constants
    PAPER_WIDTH = 8.5 * inch
    PAPER_HEIGHT = 11 * inch
    MARGIN_LEFT = 1.25 * inch
    MARGIN_RIGHT = 1 * inch
    MARGIN_TOP = 1 * inch
    MARGIN_BOTTOM = 1 * inch
    
    FONT_MAIN = "Times-Roman"
    FONT_BOLD = "Times-Bold"
    FONT_ITALIC = "Times-BoldItalic"
    FONT_SIZE_MAIN = 11
    FONT_SIZE_TITLE = 14
    FONT_SIZE_CAPTION = 9
    
    LINE_SPACING = 1.5
    
    def __init__(self, base_path: str, output_path: Optional[str] = None):
        """
        Initialize the thesis exporter.
        
        Args:
            base_path: Path to the CollectionBuilder repository root
            output_path: Optional path for output PDF (default: thesis_export.pdf)
        """
        self.base_path = Path(base_path).resolve()
        self.output_path = Path(output_path) if output_path else self.base_path / "thesis_export.pdf"
        
        # Data storage
        self.config: Dict[str, Any] = {}
        self.essays: List[Dict[str, Any]] = []
        self.metadata: List[Dict[str, Any]] = []
        self.citations: List[Dict[str, Any]] = []
        self.figures: List[Dict[str, Any]] = []
        self.tables: List[Dict[str, Any]] = []
        
        # Page content storage
        self.acknowledgements_content: str = ""
        self.technical_content: str = ""
        
        # PDF elements
        self.story: List[Any] = []
        self.styles = None
        
        # Page tracking
        self.roman_page_count = 0
        self.arabic_page_count = 0
        self.current_section = "preliminary"
        
        logger.info(f"Initialized ThesisExporter for path: {self.base_path}")
        logger.info(f"Output will be saved to: {self.output_path}")
    
    def load_config(self) -> bool:
        """Load _config.yml file."""
        config_path = self.base_path / "_config.yml"
        if not config_path.exists():
            logger.error(f"Config file not found: {config_path}")
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_path}")
            logger.info(f"  Title: {self.config.get('title', 'N/A')}")
            logger.info(f"  Author: {self.config.get('author', 'N/A')}")
            logger.info(f"  Metadata: {self.config.get('metadata', 'N/A')}")
            return True
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return False
    
    def load_essays(self) -> bool:
        """Load all essay markdown files from _essay/ directory."""
        essay_dir = self.base_path / "_essay"
        if not essay_dir.exists():
            logger.error(f"Essay directory not found: {essay_dir}")
            return False
        
        essay_files = sorted(essay_dir.glob("*.md"))
        logger.info(f"Found {len(essay_files)} essay files")
        
        for essay_file in essay_files:
            try:
                with open(essay_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse YAML front matter
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        front_matter = yaml.safe_load(parts[1])
                        body = parts[2].strip()
                    else:
                        front_matter = {}
                        body = content
                else:
                    front_matter = {}
                    body = content
                
                essay_data = {
                    'file': essay_file.name,
                    'path': essay_file,
                    'title': front_matter.get('title', essay_file.stem.replace('-', ' ').title()),
                    'chapter': front_matter.get('chapter', front_matter.get('title', '')),
                    'order': front_matter.get('order', 999),
                    'layout': front_matter.get('layout', 'essay-right'),
                    'content': body,
                    'front_matter': front_matter
                }
                self.essays.append(essay_data)
                logger.debug(f"  Loaded: {essay_data['title']} (order: {essay_data['order']})")
                
            except Exception as e:
                logger.error(f"Error loading essay {essay_file}: {e}")
        
        # Sort by order
        self.essays.sort(key=lambda x: x['order'])
        logger.info(f"Loaded {len(self.essays)} essays, sorted by order")
        return True
    
    def load_metadata_csv(self) -> bool:
        """Load collection metadata from _data/ CSV file."""
        metadata_name = self.config.get('metadata', 'make_believe')
        metadata_path = self.base_path / "_data" / f"{metadata_name}.csv"
        
        if not metadata_path.exists():
            logger.warning(f"Metadata CSV not found: {metadata_path}")
            return False
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.metadata = list(reader)
            logger.info(f"Loaded {len(self.metadata)} metadata records from {metadata_path}")
            
            # Extract figures from metadata (items with image_citation)
            self._extract_figures_from_metadata()
            return True
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            return False
    
    def load_citations(self) -> bool:
        """Load citations from _data/citation.csv - same logic as bibliography.html."""
        citation_path = self.base_path / "_data" / "citation.csv"
        
        if not citation_path.exists():
            logger.warning(f"Citation CSV not found: {citation_path}")
            return False
        
        try:
            with open(citation_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                all_citations = list(reader)
            
            # Sort by "text" and deduplicate (same logic as bibliography.html)
            # This ensures duplicate citation texts are adjacent and we skip duplicates
            all_citations.sort(key=lambda x: x.get('text', ''))
            
            last_text = ""
            unique_citations = []
            for item in all_citations:
                if item.get('text', '') != last_text:
                    last_text = item.get('text', '')
                    unique_citations.append(item)
            
            self.citations = unique_citations
            logger.info(f"Loaded {len(self.citations)} unique citations (from {len(all_citations)} total)")
            return True
        except Exception as e:
            logger.error(f"Error loading citations: {e}")
            return False
    
    def load_acknowledgements(self) -> bool:
        """Load acknowledgements content from pages/acknowledgements.md."""
        ack_path = self.base_path / "pages" / "acknowledgements.md"
        
        if not ack_path.exists():
            logger.warning(f"Acknowledgements page not found: {ack_path}")
            return False
        
        try:
            with open(ack_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse YAML front matter and extract body
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    self.acknowledgements_content = parts[2].strip()
                else:
                    self.acknowledgements_content = content
            else:
                self.acknowledgements_content = content
            
            # Remove markdown heading
            self.acknowledgements_content = re.sub(r'^##\s*Acknowledgements\s*\n', '', 
                                                    self.acknowledgements_content, 
                                                    flags=re.MULTILINE)
            
            logger.info(f"Loaded acknowledgements from {ack_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading acknowledgements: {e}")
            return False
    
    def load_technical_notes(self) -> bool:
        """Load technical notes content from pages/technical.md."""
        tech_path = self.base_path / "pages" / "technical.md"
        
        if not tech_path.exists():
            logger.warning(f"Technical notes page not found: {tech_path}")
            return False
        
        try:
            with open(tech_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse YAML front matter and extract body
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    self.technical_content = parts[2].strip()
                else:
                    self.technical_content = content
            else:
                self.technical_content = content
            
            # Remove markdown heading
            self.technical_content = re.sub(r'^##\s*Technical Notes\s*\n', '', 
                                             self.technical_content, 
                                             flags=re.MULTILINE)
            
            logger.info(f"Loaded technical notes from {tech_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading technical notes: {e}")
            return False
    
    def _extract_figures_from_metadata(self):
        """
        Extract figures from metadata CSV - same logic as image.html layout.
        Only items with non-empty image_citation values are included.
        """
        for item in self.metadata:
            image_citation = item.get('image_citation', '')
            if image_citation and image_citation.strip():
                figure_entry = {
                    'objectid': item.get('objectid', 'unknown'),
                    'title': item.get('title', 'Untitled'),
                    'image_citation': image_citation,
                    'image_thumb': item.get('image_thumb', ''),
                    'image_small': item.get('image_small', ''),
                    'image_alt_text': item.get('image_alt_text', item.get('title', '')),
                    'page': 0,  # Will be set during PDF generation
                    'type': 'figure'
                }
                self.figures.append(figure_entry)
        
        # Sort by image_citation alphabetically (same as image.html)
        self.figures.sort(key=lambda x: x['image_citation'])
        
        logger.info(f"Extracted {len(self.figures)} figures with image_citation from metadata")
    
    def _setup_styles(self):
    """Create paragraph styles for the document."""
    self.styles = getSampleStyleSheet()
    
    # Main text style (1.5 line spacing, 11pt Times New Roman)
    self.styles.add(ParagraphStyle(
        name='ThesisBodyText',
        parent=self.styles['Normal'],
        fontName=self.FONT_MAIN,
        fontSize=self.FONT_SIZE_MAIN,
        leading=self.FONT_SIZE_MAIN * self.LINE_SPACING,
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        spaceBefore=0,
        leftIndent=0,
        rightIndent=0,
        firstLineIndent=0
    ), replace=True)
    
    # Chapter title style (14pt, bold)
    self.styles.add(ParagraphStyle(
        name='ThesisChapterTitle',
        parent=self.styles['Heading1'],
        fontName=self.FONT_BOLD,
        fontSize=self.FONT_SIZE_TITLE,
        leading=self.FONT_SIZE_TITLE * self.LINE_SPACING,
        alignment=TA_LEFT,
        spaceAfter=18,
        spaceBefore=24,
        keepWithNext=True
    ), replace=True)
    
    # Section heading style (12pt, bold)
    self.styles.add(ParagraphStyle(
        name='ThesisSectionHeading',
        parent=self.styles['Heading2'],
        fontName=self.FONT_BOLD,
        fontSize=12,
        leading=12 * self.LINE_SPACING,
        alignment=TA_LEFT,
        spaceAfter=12,
        spaceBefore=18,
        keepWithNext=True
    ), replace=True)
    
    # Subsection heading style (11pt, bold italic)
    self.styles.add(ParagraphStyle(
        name='ThesisSubsectionHeading',
        parent=self.styles['Heading3'],
        fontName=self.FONT_ITALIC,
        fontSize=self.FONT_SIZE_MAIN,
        leading=self.FONT_SIZE_MAIN * self.LINE_SPACING,
        alignment=TA_LEFT,
        spaceAfter=12,
        spaceBefore=12,
        keepWithNext=True
    ), replace=True)
    
    # Abstract text style
    self.styles.add(ParagraphStyle(
        name='ThesisAbstractText',
        parent=self.styles['Normal'],
        fontName=self.FONT_MAIN,
        fontSize=self.FONT_SIZE_MAIN,
        leading=self.FONT_SIZE_MAIN * self.LINE_SPACING,
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        firstLineIndent=0
    ), replace=True)
    
    # Caption style (9pt)
    self.styles.add(ParagraphStyle(
        name='ThesisCaption',
        parent=self.styles['Normal'],
        fontName=self.FONT_MAIN,
        fontSize=self.FONT_SIZE_CAPTION,
        leading=self.FONT_SIZE_CAPTION * self.LINE_SPACING,
        alignment=TA_LEFT,
        spaceAfter=6,
        spaceBefore=6,
        italic=True
    ), replace=True)
    
    # TOC entry style
    self.styles.add(ParagraphStyle(
        name='ThesisTOCEntry',
        parent=self.styles['Normal'],
        fontName=self.FONT_MAIN,
        fontSize=self.FONT_SIZE_MAIN,
        leading=self.FONT_SIZE_MAIN * self.LINE_SPACING,
        alignment=TA_LEFT,
        spaceAfter=6
    ), replace=True)
    
    # Title page style (centered)
    self.styles.add(ParagraphStyle(
        name='ThesisTitlePage',
        parent=self.styles['Normal'],
        fontName=self.FONT_BOLD,
        fontSize=16,
        leading=16 * self.LINE_SPACING,
        alignment=TA_CENTER,
        spaceAfter=24,
        spaceBefore=24
    ), replace=True)
    
    # Bibliography entry style (hanging indent)
    self.styles.add(ParagraphStyle(
        name='ThesisBibliographyEntry',
        parent=self.styles['Normal'],
        fontName=self.FONT_MAIN,
        fontSize=self.FONT_SIZE_MAIN,
        leading=self.FONT_SIZE_MAIN * self.LINE_SPACING,
        leftIndent=36,
        firstLineIndent=-36,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    ), replace=True)
    
    # Figure citation style (hanging indent)
    self.styles.add(ParagraphStyle(
        name='ThesisFigureCitation',
        parent=self.styles['Normal'],
        fontName=self.FONT_MAIN,
        fontSize=self.FONT_SIZE_MAIN,
        leading=self.FONT_SIZE_MAIN * self.LINE_SPACING,
        leftIndent=36,
        firstLineIndent=-36,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    ), replace=True)
    
    logger.info("Paragraph styles configured")
    
    def _clean_markdown(self, md_content: str) -> str:
        """
        Clean markdown content for PDF conversion.
        Remove Jekyll/CollectionBuilder specific tags and convert to plain text.
        """
        # Remove {% trigger %} tags
        md_content = re.sub(r'\{%\s*trigger[^%]*%\}', '', md_content)
        
        # Remove {% include %} tags
        md_content = re.sub(r'\{%\s*include[^%]*%\}', '', md_content)
        
        # Remove liquid variables {{ }}
        md_content = re.sub(r'\{\{[^}]*\}\}', '', md_content)
        
        # Remove HTML style tags
        md_content = re.sub(r'<style[^>]*>.*?</style>', '', md_content, flags=re.DOTALL)
        
        # Convert footnote markers ^1, ^2, etc. to superscript
        md_content = re.sub(r'\^(\d+)', r'<sup>\1</sup>', md_content)
        
        # Convert markdown links to plain text (keep link text)
        md_content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', md_content)
        
        # Convert markdown images to captions
        md_content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'<em>Figure: \1</em>', md_content)
        
        # Convert bold and italic
        md_content = re.sub(r'\*\*\*([^*]+)\*\*\*', r'<b><i>\1</i></b>', md_content)
        md_content = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', md_content)
        md_content = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', md_content)
        
        # Convert headers to paragraph breaks with emphasis
        md_content = re.sub(r'^###\s+(.+)$', r'<br/><b>\1</b><br/>', md_content, flags=re.MULTILINE)
        md_content = re.sub(r'^##\s+(.+)$', r'<br/><b>\1</b><br/>', md_content, flags=re.MULTILINE)
        md_content = re.sub(r'^#\s+(.+)$', r'<br/><b>\1</b><br/>', md_content, flags=re.MULTILINE)
        
        # Convert horizontal rules to page breaks (marked for later processing)
        md_content = re.sub(r'^---\s*$', '<PAGEBREAK/>', md_content, flags=re.MULTILINE)
        
        # Convert list items
        md_content = re.sub(r'^[\-\*]\s+(.+)$', r'• \1<br/>', md_content, flags=re.MULTILINE)
        
        # Convert line breaks
        md_content = md_content.replace('\n\n', '</p><p>')
        md_content = md_content.replace('\n', '<br/>')
        
        # Remove empty paragraph tags
        md_content = re.sub(r'<p>\s*</p>', '', md_content)
        
        # Wrap in paragraph tags if not already
        if md_content.strip() and not md_content.strip().startswith('<p>'):
            md_content = f'<p>{md_content}</p>'
        
        return md_content
    
    def _to_roman(self, num: int) -> str:
        """Convert integer to lowercase Roman numeral."""
        val = [10, 9, 5, 4, 1]
        syms = ['x', 'ix', 'v', 'iv', 'i']
        roman_num = ''
        i = 0
        while num > 0:
            for _ in range(num // val[i]):
                roman_num += syms[i]
                num -= val[i]
            i += 1
        return roman_num
    
    def _create_title_page(self):
        """Create the title page (no page number)."""
        logger.info("Creating title page")
        
        title = self.config.get('title', 'Thesis')
        author = self.config.get('author', 'Unknown Author')
        tagline = self.config.get('tagline', '')
        
        self.story.append(Spacer(1, 3 * inch))
        self.story.append(Paragraph(f"<b><font size=18>{title}</font></b>", self.styles['TitlePage']))
        
        if tagline:
            self.story.append(Spacer(1, 0.5 * inch))
            self.story.append(Paragraph(f"<i>{tagline}</i>", self.styles['BodyText']))
        
        self.story.append(Spacer(1, 1 * inch))
        self.story.append(Paragraph(f"by {author}", self.styles['BodyText']))
        
        self.story.append(Spacer(1, 1.5 * inch))
        self.story.append(Paragraph(
            "A thesis submitted in partial fulfillment of the requirements "
            "for the degree of", 
            self.styles['BodyText']
        ))
        self.story.append(Paragraph("Master of Arts in History", self.styles['BodyText']))
        
        self.story.append(Spacer(1, 0.5 * inch))
        self.story.append(Paragraph("University of Idaho", self.styles['BodyText']))
        self.story.append(Paragraph("College of Graduate Studies", self.styles['BodyText']))
        
        grad_month = "May"
        grad_year = datetime.now().year
        if datetime.now().month > 5:
            grad_month = "August"
        if datetime.now().month > 8:
            grad_month = "December"
            grad_year += 1
        
        self.story.append(Spacer(1, 0.5 * inch))
        self.story.append(Paragraph(f"{grad_month} {grad_year}", self.styles['BodyText']))
        
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_abstract_page(self):
        """Create abstract page (page ii)."""
        logger.info("Creating abstract page")
        
        self.story.append(Paragraph("<b>ABSTRACT</b>", self.styles['SectionHeading']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        abstract_text = self.config.get('abstract', '')
        
        if not abstract_text:
            # Use default abstract from home-essay.html layout
            abstract_text = """
            <p>This work contends that Spokane, Washington's origins represent overlapping colonialism, 
            where settler ambitions were supplanted by predatory Dutch financial interests between 1889 
            and 1923. Capital originating from the Dutch merchant class, fueled by the 1870s Cape Era 
            diamond boom, flowed into American railway bonds to establish a foreign-controlled financial 
            market. Consequently, the city's aggressive display of frontier iconography was less an act 
            of civic pride than a cultural assertion of American identity that obscured its relationship 
            with foreign capital.</p>
            
            <p>While imitation of cultures was common for European American settlers in the Pacific 
            Northwest during this period, Spokane's booster-driven "Inland Empire" marketing strategies 
            uniquely relied on a pervasive, public display of cultural and class-based mimicry and 
            affectation. The city's rapid Dutch-financed reconstruction following the 1889 fire created 
            an artificially inflated metropolis amidst otherwise sparse agricultural hubs, generating 
            dissonance between the built environment and pioneer identities that was mediated by civic 
            rituals and commercial pageantry.</p>
            
            <p>Situating Spokane within evolving ideologies of U.S. expansion, this paper highlights 
            the contradiction between America's professed aversion to foreign entanglement and its 
            imperial practices. Drawing on contemporaneous Dutch-language media and interviews with 
            foreign financiers, the work introduces an international perspective largely absent from 
            existing American historiography. The paper draws on a wide range of archival visual 
            materials that document pioneer iconography and expressions of ethnic anxiety with a level 
            of transparency largely absent from written accounts. To support this visually driven 
            approach, the thesis is presented as a custom digital exhibit, enabling readers to place 
            these materials in direct dialogue with the historic media, correspondence, and literature 
            that form the foundation of the research.</p>
            """
        
        md = markdown.Markdown()
        abstract_html = md.convert(abstract_text)
        abstract_clean = self._clean_markdown(abstract_html)
        
        for para in abstract_clean.split('</p><p>'):
            if para.strip():
                para = para.replace('<p>', '').replace('</p>', '')
                para = re.sub(r'<[^>]+>', '', para)
                if len(para) > 5:
                    self.story.append(Paragraph(para, self.styles['AbstractText']))
        
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_acknowledgments_page(self):
        """Create acknowledgments page from pages/acknowledgements.md (page iii)."""
        logger.info("Creating acknowledgments page from pages/acknowledgements.md")
        
        self.story.append(Paragraph("<b>ACKNOWLEDGMENTS</b>", self.styles['SectionHeading']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        if self.acknowledgements_content:
            md = markdown.Markdown()
            html_content = md.convert(self.acknowledgements_content)
            clean_content = self._clean_markdown(html_content)
            
            for para in clean_content.split('</p><p>'):
                if para.strip():
                    para = para.replace('<p>', '').replace('</p>', '')
                    para = re.sub(r'<[^>]+>', '', para)
                    if len(para) > 5:
                        self.story.append(Paragraph(para, self.styles['BodyText']))
        else:
            self.story.append(Paragraph(
                "<i>Acknowledgments content not found. Please ensure pages/acknowledgements.md exists.</i>", 
                self.styles['BodyText']
            ))
        
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_dedication_page(self):
        """Create dedication page (page iv)."""
        logger.info("Creating dedication page")
        
        self.story.append(Spacer(1, 4 * inch))
        
        dedication = """
        <p align="center">For all those whose stories remain untold<br/>
        and whose contributions have been forgotten.</p>
        """
        
        self.story.append(Paragraph(dedication, self.styles['BodyText']))
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_list_of_tables(self):
        """Create list of tables page."""
        if not self.tables:
            logger.info("No tables found, skipping list of tables")
            return
        
        logger.info(f"Creating list of tables ({len(self.tables)} entries)")
        
        self.story.append(Paragraph("<b>LIST OF TABLES</b>", self.styles['SectionHeading']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        for i, table in enumerate(self.tables, 1):
            table_num = f"Table {i}"
            caption = table.get('caption', table.get('title', 'Untitled'))[:100]
            page_ref = str(i + 10)
            
            line = f"{table_num}. {caption} <font name='Times-Roman'>{'.' * 50}</font> {page_ref}"
            self.story.append(Paragraph(line, self.styles['TOCEntry']))
        
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_list_of_figures(self):
        """
        Create list of figures page from metadata CSV.
        Same logic as image.html layout - only items with image_citation values.
        """
        if not self.figures:
            logger.info("No figures with image_citation found, skipping list of figures")
            return
        
        logger.info(f"Creating list of figures ({len(self.figures)} entries)")
        
        self.story.append(Paragraph("<b>LIST OF FIGURES</b>", self.styles['SectionHeading']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        for i, figure in enumerate(self.figures, 1):
            fig_num = f"Figure {i}"
            # Use image_citation field (same as image.html layout)
            caption = figure.get('image_citation', figure.get('title', 'Untitled'))[:150]
            # Clean any markdown from caption
            caption = re.sub(r'[\*\_`]', '', caption)
            page_ref = str(i + 10)
            
            line = f"{fig_num}. {caption} <font name='Times-Roman'>{'.' * 50}</font> {page_ref}"
            self.story.append(Paragraph(line, self.styles['TOCEntry']))
        
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_ai_statement(self):
        """Create AI use statement page (required per U of Idaho)."""
        logger.info("Creating AI statement page")
        
        self.story.append(Paragraph(
            "<b>STATEMENT ON THE USE OF ARTIFICIAL INTELLIGENCE</b>", 
            self.styles['SectionHeading']
        ))
        self.story.append(Spacer(1, 0.5 * inch))
        
        ai_statement = """
        <p>I hereby disclose the use of Artificial Intelligence tools in the preparation of this 
        thesis. AI-assisted tools were utilized for the following purposes:</p>
        
        <p>• Code generation and debugging for the digital exhibit platform (CollectionBuilder)</p>
        <p>• Text editing and grammar checking</p>
        <p>• Research assistance and source discovery</p>
        
        <p>All substantive analysis, argumentation, research conclusions, and scholarly interpretation 
        presented in this work are my own. AI tools were not used to generate original research content, 
        analysis, or conclusions. All sources consulted, including AI-generated suggestions, have been 
        independently verified and properly cited where applicable.</p>
        
        <p>This statement is made in accordance with University of Idaho College of Graduate Studies 
        requirements for Electronic Thesis and Dissertation (ETD) submission.</p>
        """
        
        for para in ai_statement.split('</p><p>'):
            if para.strip():
                para = para.replace('<p>', '').replace('</p>', '')
                para = re.sub(r'<[^>]+>', '', para)
                if len(para) > 5:
                    self.story.append(Paragraph(para, self.styles['BodyText']))
        
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_contribution_statement(self):
        """Create statement of contribution page."""
        logger.info("Creating contribution statement page")
        
        self.story.append(Paragraph("<b>STATEMENT OF CONTRIBUTION</b>", self.styles['SectionHeading']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        author = self.config.get('author', 'Andrew Weymouth')
        title = self.config.get('title', 'Make, Believe')
        tagline = self.config.get('tagline', '')
        
        contribution = f"""
        <p>I, {author}, affirm that this thesis titled "{title}: {tagline}" is my own original work. 
        All research, analysis, writing, and digital exhibit development were conducted by me under 
        the supervision of my major professor and thesis committee.</p>
        
        <p>All sources, including archival materials, published works, and digital resources, have 
        been properly cited in accordance with the Chicago Manual of Style (17th edition). Any 
        collaborative work or assistance received has been acknowledged in the Acknowledgments 
        section of this document.</p>
        
        <p>This thesis is submitted in partial fulfillment of the requirements for the Master of 
        Arts in History degree at the University of Idaho.</p>
        """
        
        for para in contribution.split('</p><p>'):
            if para.strip():
                para = para.replace('<p>', '').replace('</p>', '')
                para = re.sub(r'<[^>]+>', '', para)
                if len(para) > 5:
                    self.story.append(Paragraph(para, self.styles['BodyText']))
        
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_toc_page(self):
        """Create table of contents page."""
        logger.info("Creating table of contents")
        
        self.story.append(Paragraph("<b>TABLE OF CONTENTS</b>", self.styles['SectionHeading']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        toc_entries = [
            ("Abstract", "ii"),
            ("Acknowledgments", "iii"),
            ("Dedication", "iv"),
        ]
        
        if self.figures:
            toc_entries.append(("List of Figures", "v"))
        if self.tables:
            toc_entries.append(("List of Tables", "vi"))
        
        toc_entries.extend([
            ("Statement on the Use of Artificial Intelligence", "vii"),
            ("Statement of Contribution", "viii"),
        ])
        
        chapter_num = 1
        for essay in self.essays:
            toc_entries.append((f"Chapter {chapter_num}: {essay['title']}", chapter_num))
            chapter_num += 1
        
        toc_entries.extend([
            ("Literature Cited", chapter_num + 1),
            ("List of Image Citations", chapter_num + 2),
            ("Technical Notes", chapter_num + 3),
            ("Appendices", chapter_num + 4),
        ])
        
        for title, page in toc_entries:
            line = f"{title} <font name='Times-Roman'>{'.' * 50}</font> {page}"
            self.story.append(Paragraph(line, self.styles['TOCEntry']))
        
        self.story.append(PageBreak())
        self.roman_page_count += 1
    
    def _create_chapters(self):
        """Create all chapter content pages."""
        logger.info(f"Creating {len(self.essays)} chapters")
        
        chapter_num = 1
        for essay in self.essays:
            self.story.append(Paragraph(
                f"<b>CHAPTER {chapter_num}</b>", 
                self.styles['ChapterTitle']
            ))
            self.story.append(Paragraph(
                f"<b>{essay['title']}</b>", 
                self.styles['ChapterTitle']
            ))
            self.story.append(Spacer(1, 0.5 * inch))
            
            md = markdown.Markdown(extensions=['extra', 'codehilite'])
            html_content = md.convert(essay['content'])
            clean_content = self._clean_markdown(html_content)
            
            paragraphs = clean_content.split('<PAGEBREAK/>')
            for i, para_block in enumerate(paragraphs):
                for para in para_block.split('</p><p>'):
                    if para.strip():
                        para = para.replace('<p>', '').replace('</p>', '')
                        para = re.sub(r'<[^>]+>', '', para)
                        if len(para) > 5:
                            self.story.append(Paragraph(para, self.styles['BodyText']))
                
                if i < len(paragraphs) - 1:
                    self.story.append(PageBreak())
            
            self.story.append(PageBreak())
            self.arabic_page_count += 1
            chapter_num += 1
    
    def _create_bibliography(self):
        """
        Create bibliography/literature cited section.
        Same logic as bibliography.html layout - sorted by "text", deduplicated.
        """
        logger.info("Creating bibliography from _data/citation.csv")
        
        self.story.append(Paragraph("<b>LITERATURE CITED</b>", self.styles['ChapterTitle']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        if self.citations:
            for citation in self.citations:
                citation_text = citation.get('text', citation.get('citation', 'Unknown'))
                # Clean any markdown from citation text
                citation_text = re.sub(r'[\*\_`]', '', citation_text)
                if len(citation_text) > 10:
                    self.story.append(Paragraph(citation_text, self.styles['BibliographyEntry']))
        else:
            self.story.append(Paragraph(
                "<i>No citations found. Please ensure _data/citation.csv exists with citation data.</i>", 
                self.styles['BodyText']
            ))
        
        self.story.append(PageBreak())
        self.arabic_page_count += 1
    
    def _create_image_citations(self):
        """
        Create list of image citations section.
        Same logic as image.html layout - items with image_citation from metadata CSV.
        """
        if not self.figures:
            logger.info("No figures with image_citation, skipping image citations section")
            return
        
        logger.info(f"Creating image citations section ({len(self.figures)} entries)")
        
        self.story.append(Paragraph("<b>LIST OF IMAGE CITATIONS</b>", self.styles['ChapterTitle']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        for i, figure in enumerate(self.figures, 1):
            # Use image_citation field (same as image.html layout)
            citation_text = figure.get('image_citation', figure.get('title', 'Untitled'))
            # Clean any markdown from citation text
            citation_text = re.sub(r'[\*\_`]', '', citation_text)
            if len(citation_text) > 10:
                self.story.append(Paragraph(citation_text, self.styles['FigureCitation']))
        
        self.story.append(PageBreak())
        self.arabic_page_count += 1
    
    def _create_technical_notes(self):
        """
        Create technical notes section from pages/technical.md.
        """
        logger.info("Creating technical notes from pages/technical.md")
        
        self.story.append(Paragraph("<b>TECHNICAL NOTES</b>", self.styles['ChapterTitle']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        if self.technical_content:
            md = markdown.Markdown(extensions=['extra'])
            html_content = md.convert(self.technical_content)
            clean_content = self._clean_markdown(html_content)
            
            paragraphs = clean_content.split('</p><p>')
            for para in paragraphs:
                if para.strip():
                    para = para.replace('<p>', '').replace('</p>', '')
                    para = re.sub(r'<[^>]+>', '', para)
                    if len(para) > 5:
                        self.story.append(Paragraph(para, self.styles['BodyText']))
        else:
            self.story.append(Paragraph(
                "<i>Technical notes content not found. Please ensure pages/technical.md exists.</i>", 
                self.styles['BodyText']
            ))
        
        self.story.append(PageBreak())
        self.arabic_page_count += 1
    
    def _create_appendices(self):
        """Create appendices section."""
        logger.info("Creating appendices")
        
        self.story.append(Paragraph("<b>APPENDICES</b>", self.styles['ChapterTitle']))
        self.story.append(Spacer(1, 0.5 * inch))
        
        self.story.append(Paragraph("<b>Appendix A: Document Checklists</b>", self.styles['SectionHeading']))
        self.story.append(Spacer(1, 0.25 * inch))
        
        checklist = """
        <p><b>Formatting Checklist:</b></p>
        <p>☐ Margins: 1.25" left, 1" right, 1" top, 1" bottom</p>
        <p>☐ Font: Times New Roman, 11pt main text, 14pt chapter titles</p>
        <p>☐ Line spacing: 1.5 throughout</p>
        <p>☐ Page numbers: Roman numerals for preliminary pages, Arabic for chapters</p>
        <p>☐ Title page: No page number</p>
        <p>☐ All required sections present and in correct order</p>
        """
        
        for para in checklist.split('</p><p>'):
            if para.strip():
                para = para.replace('<p>', '').replace('</p>', '')
                para = re.sub(r'<[^>]+>', '', para)
                if len(para) > 5:
                    self.story.append(Paragraph(para, self.styles['BodyText']))
        
        self.story.append(Spacer(1, 0.5 * inch))
        
        self.story.append(Paragraph("<b>Appendix B: Examples and Tips</b>", self.styles['SectionHeading']))
        self.story.append(Spacer(1, 0.25 * inch))
        
        tips = """
        <p><b>Using Headings and Subheadings:</b></p>
        <p>Organize your document using consistent heading levels. Chapter titles should be the 
        largest, followed by section headings, then subsections. Maintain consistent formatting 
        throughout.</p>
        
        <p><b>Figure and Table Captions:</b></p>
        <p>All figures and tables should have descriptive captions. Number them sequentially by 
        chapter (Figure 1.1, Figure 1.2, Figure 2.1, etc.) or continuously throughout the document.</p>
        
        <p><b>References:</b></p>
        <p>Follow your discipline's citation style consistently. Remove all active hyperlinks from 
        the final PDF submission.</p>
        """
        
        for para in tips.split('</p><p>'):
            if para.strip():
                para = para.replace('<p>', '').replace('</p>', '')
                para = re.sub(r'<[^>]+>', '', para)
                if len(para) > 5:
                    self.story.append(Paragraph(para, self.styles['BodyText']))
        
        self.arabic_page_count += 1
    
    def build_pdf(self) -> bool:
        """Build the complete PDF document."""
        if not REPORTLAB_AVAILABLE:
            logger.error("ReportLab is not available. Cannot build PDF.")
            logger.error("Install with: pip install reportlab")
            return False
        
        logger.info("Building PDF document")
        
        self._setup_styles()
        
        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=LETTER,
            leftMargin=self.MARGIN_LEFT,
            rightMargin=self.MARGIN_RIGHT,
            topMargin=self.MARGIN_TOP,
            bottomMargin=self.MARGIN_BOTTOM,
            title=self.config.get('title', 'Thesis'),
            author=self.config.get('author', 'Unknown')
        )
        
        self.current_section = "preliminary"
        self._create_title_page()
        self._create_abstract_page()
        self._create_acknowledgments_page()
        self._create_dedication_page()
        self._create_list_of_tables()
        self._create_list_of_figures()
        self._create_ai_statement()
        self._create_contribution_statement()
        self._create_toc_page()
        
        self.current_section = "main"
        self._create_chapters()
        self._create_bibliography()
        self._create_image_citations()
        self._create_technical_notes()
        self._create_appendices()
        
        try:
            doc.build(self.story)
            logger.info(f"PDF successfully created: {self.output_path}")
            logger.info(f"  Total preliminary pages (Roman): {self.roman_page_count}")
            logger.info(f"  Total content pages (Arabic): {self.arabic_page_count}")
            return True
        except Exception as e:
            logger.error(f"Error building PDF: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def run(self) -> bool:
        """Run the complete export process."""
        logger.info("=" * 60)
        logger.info("Starting Thesis Export Process")
        logger.info("=" * 60)
        
        if not self.load_config():
            return False
        
        if not self.load_essays():
            return False
        
        self.load_metadata_csv()
        self.load_citations()
        self.load_acknowledgements()
        self.load_technical_notes()
        
        success = self.build_pdf()
        
        logger.info("=" * 60)
        if success:
            logger.info("Thesis Export Completed Successfully")
        else:
            logger.error("Thesis Export Failed")
        logger.info("=" * 60)
        
        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Export CollectionBuilder Jekyll thesis to PDF',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python export_thesis.py
    python export_thesis.py --output my_thesis.pdf
    python export_thesis.py --debug
    
University of Idaho ETD Formatting Standards:
    - Paper: 8.5" x 11"
    - Margins: 1.25" left, 1" right/top/bottom
    - Font: Times New Roman, 11pt (14pt for chapter titles)
    - Line spacing: 1.5
    - Page numbers: Roman (preliminary), Arabic (chapters)
    
Content Sources:
    - Bibliography: _data/citation.csv (same logic as bibliography.html)
    - Image Citations: _data/[metadata].csv image_citation field (same as image.html)
    - Acknowledgments: pages/acknowledgements.md
    - Technical Notes: pages/technical.md
    - Chapters: _essay/*.md
    - Config: _config.yml
        """
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output PDF path (default: thesis_export.pdf)'
    )
    
    parser.add_argument(
        '--path', '-p',
        type=str,
        default='.',
        help='Path to CollectionBuilder repository (default: current directory)'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    exporter = ThesisExporter(args.path, args.output)
    success = exporter.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()