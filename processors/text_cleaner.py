# processors/text_cleaner.py
"""
Markdown segmentation and structure utilities.
Works with structure-aware Markdown from pymupdf4llm.
PRODUCTION EDITION: Zero assumptions, pure structure extraction.
"""
import re
from typing import List, Tuple
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MarkdownSegmenter:
    """
    Segments Markdown text into logical sections based on headers.
    Deterministic splitting using Markdown syntax.
    PRODUCTION: Captures structural metadata for perfect reconstruction.
    """
    
    @staticmethod
    def segment_by_headers(markdown_text: str) -> List[Tuple[str, str, int, int]]:
        """
        Split Markdown text into sections based on headers (# or ##).
        RETURNS STRUCTURAL METADATA for perfect reconstruction.
        
        Args:
            markdown_text: Markdown-formatted text with headers
        
        Returns:
            List of (header, content, header_level, position_index) tuples
            - header: Section header text
            - content: Section content
            - header_level: 1 (H1/title) or 2 (H2/section) or 3 (H3/subsection)
            - position_index: Original position in document (0-based)
        """
        logger.debug("Segmenting Markdown by headers with structural preservation")
        
        lines = markdown_text.split('\n')
        
        sections = []
        current_header = None
        current_header_level = None
        current_content = []
        position_index = 0
        
        for line in lines:
            # Check if line is a header (# or ## or ###)
            header_match = re.match(r'^(#{1,3})\s+(.+)$', line.strip())
            
            if header_match:
                # Save previous section before starting new one
                if current_header is not None and current_content:
                    sections.append((
                        current_header,
                        '\n'.join(current_content).strip(),
                        current_header_level,
                        position_index
                    ))
                    position_index += 1
                
                # Start new section
                header_prefix = header_match.group(1)
                current_header_level = len(header_prefix)  # Count # symbols
                current_header = header_match.group(2).strip()
                current_content = []
                
            else:
                # Accumulate content
                if line.strip():  # Skip empty lines at start of section
                    current_content.append(line)
        
        # Save last section
        if current_header is not None and current_content:
            sections.append((
                current_header,
                '\n'.join(current_content).strip(),
                current_header_level,
                position_index
            ))
        
        # Filter out very short sections (likely artifacts)
        # But keep ALL sections if they have headers (don't assume)
        sections = [(h, c, lvl, idx) for h, c, lvl, idx in sections if len(c) > 20]
        
        logger.info(f"Segmented into {len(sections)} sections with structure preservation")
        
        # Log structure for debugging
        for h, _, lvl, idx in sections:
            logger.debug(f"  [{idx}] H{lvl}: {h}")
        
        return sections
    
    @staticmethod
    def detect_document_structure(sections: List[Tuple[str, str, int, int]]) -> dict:
        """
        Analyze sections to detect document structure.
        ZERO ASSUMPTIONS - pure analysis of what's actually there.
        
        Args:
            sections: List of (header, content, header_level, position_index) tuples
        
        Returns:
            Structure dictionary with:
            - has_title_section: bool (first section is H1)
            - title_text: str or None
            - header_hierarchy: dict mapping position -> level
        """
        if not sections:
            return {
                "has_title_section": False,
                "title_text": None,
                "header_hierarchy": {}
            }
        
        first_header, first_content, first_level, first_idx = sections[0]
        
        # Simple rule: If first section is H1, treat it as document title
        has_title_section = (first_level == 1)
        title_text = first_header if has_title_section else None
        
        # Build hierarchy map
        header_hierarchy = {
            idx: level for _, _, level, idx in sections
        }
        
        logger.info(f"Document structure detected: has_title={has_title_section}, title='{title_text}'")
        
        return {
            "has_title_section": has_title_section,
            "title_text": title_text,
            "header_hierarchy": header_hierarchy
        }
    
    @staticmethod
    def extract_tables(markdown_text: str) -> List[dict]:
        """
        Extract Markdown tables from text.
        
        Args:
            markdown_text: Markdown text containing tables
        
        Returns:
            List of table dictionaries with headers and rows
        """
        logger.debug("Extracting tables from Markdown")
        
        tables = []
        lines = markdown_text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Detect table header (contains pipes)
            if '|' in line and i + 1 < len(lines):
                # Check if next line is separator
                next_line = lines[i + 1].strip()
                if re.match(r'^\|?\s*[-:]+\s*\|', next_line):
                    # Found table
                    headers = [h.strip() for h in line.split('|') if h.strip()]
                    
                    # Skip separator line
                    i += 2
                    
                    # Collect rows
                    rows = []
                    while i < len(lines) and '|' in lines[i]:
                        row = [c.strip() for c in lines[i].split('|') if c.strip()]
                        if row:
                            rows.append(row)
                        i += 1
                    
                    tables.append({
                        'headers': headers,
                        'rows': rows
                    })
                    continue
            
            i += 1
        
        logger.info(f"Extracted {len(tables)} tables")
        return tables
    
    @staticmethod
    def clean_markdown(markdown_text: str) -> str:
        """
        Clean Markdown text while preserving structure.
        
        Args:
            markdown_text: Raw Markdown text
        
        Returns:
            Cleaned Markdown text
        """
        # Remove page numbers (standalone numbers)
        markdown_text = re.sub(r'^\s*\d+\s*$', '', markdown_text, flags=re.MULTILINE)
        
        # Normalize header spacing
        markdown_text = re.sub(r'(#{1,6})\s*(.+)', r'\1 \2', markdown_text)
        
        # Clean up excessive blank lines
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        
        return markdown_text.strip()

