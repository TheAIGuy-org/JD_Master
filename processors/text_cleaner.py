# processors/text_cleaner.py
"""
Markdown segmentation and structure utilities.
Works with structure-aware Markdown from pymupdf4llm.
"""
import re
from typing import List, Tuple
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MarkdownSegmenter:
    """
    Segments Markdown text into logical sections based on headers.
    Deterministic splitting using Markdown syntax.
    """
    
    @staticmethod
    def segment_by_headers(markdown_text: str) -> List[Tuple[str, str]]:
        """
        Split Markdown text into sections based on headers (# or ##).
        
        Args:
            markdown_text: Markdown-formatted text with headers
        
        Returns:
            List of (header, content) tuples
        """
        logger.debug("Segmenting Markdown by headers")
        
        # Split on H1 (#) or H2 (##) headers
        # Pattern: Line starting with # or ##, followed by text
        lines = markdown_text.split('\n')
        
        sections = []
        current_header = "Introduction"
        current_content = []
        
        for line in lines:
            # Check if line is a header (# or ##)
            header_match = re.match(r'^(#{1,2})\s+(.+)$', line.strip())
            
            if header_match:
                # Save previous section
                if current_content:
                    sections.append((
                        current_header,
                        '\n'.join(current_content).strip()
                    ))
                
                # Start new section
                current_header = header_match.group(2).strip()
                current_content = []
            else:
                # Accumulate content
                if line.strip():  # Skip empty lines
                    current_content.append(line)
        
        # Save last section
        if current_content:
            sections.append((
                current_header,
                '\n'.join(current_content).strip()
            ))
        
        # Filter out very short sections (likely artifacts)
        sections = [(h, c) for h, c in sections if len(c) > 20]
        
        logger.info(f"Segmented into {len(sections)} sections")
        return sections
    
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