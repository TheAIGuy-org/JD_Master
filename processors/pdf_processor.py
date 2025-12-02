# processors/pdf_processor.py
"""
PDF extraction and processing module with Markdown structure preservation.
Uses pymupdf4llm for structure-aware extraction.
NOW WITH VISUAL PROFILE EXTRACTION.
"""
import pymupdf4llm
import re
from typing import Optional, Tuple
from utils.logger import setup_logger
from utils.validators import Validator, ValidationError
from processors.visual_profile_extractor import VisualProfileExtractor, VisualProfile

logger = setup_logger(__name__)


class PDFProcessor:
    """
    Handles PDF file processing with Markdown structure extraction.
    Preserves headers, lists, and formatting for accurate segmentation.
    NOW EXTRACTS VISUAL PROFILE FOR FORMAT PRESERVATION.
    """
    
    @staticmethod
    def extract_markdown(file_path: str) -> str:
        """
        Extract PDF content as Markdown with structure preservation.
        
        Args:
            file_path: Path to PDF file
        
        Returns:
            Markdown-formatted text with headers and structure
        
        Raises:
            ValidationError: If file is invalid
            Exception: If extraction fails
        """
        try:
            Validator.validate_pdf_path(file_path)
        except ValidationError as e:
            logger.error(f"PDF validation failed: {e}")
            raise
        
        try:
            logger.info(f"Extracting Markdown from PDF: {file_path}")
            
            # Use pymupdf4llm for structure-aware extraction
            md_text = pymupdf4llm.to_markdown(file_path)
            
            if not md_text.strip():
                raise Exception("No content extracted from PDF")
            
            # Clean artifacts
            cleaned_text = PDFProcessor._clean_extraction_artifacts(md_text)
            
            logger.info(f"Successfully extracted {len(cleaned_text)} chars as Markdown")
            return cleaned_text
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise Exception(f"Failed to extract Markdown from PDF: {str(e)}")
    
    @staticmethod
    def extract_with_visual_profile(file_path: str) -> Tuple[str, VisualProfile]:
        """
        Extract BOTH content (Markdown) AND visual profile (formatting).
        This is the new primary method for format-preserving extraction.
        
        Args:
            file_path: Path to PDF file
        
        Returns:
            Tuple of (markdown_text, visual_profile)
        
        Raises:
            ValidationError: If file is invalid
            Exception: If extraction fails
        """
        logger.info(f"Extracting content + visual profile from: {file_path}")
        
        try:
            Validator.validate_pdf_path(file_path)
        except ValidationError as e:
            logger.error(f"PDF validation failed: {e}")
            raise
        
        try:
            # Extract content (existing method)
            markdown_text = PDFProcessor.extract_markdown(file_path)
            
            # Extract visual profile (NEW)
            visual_profile = VisualProfileExtractor.extract_profile(file_path)
            
            logger.info("Successfully extracted content + visual profile")
            return markdown_text, visual_profile
            
        except Exception as e:
            logger.error(f"Extraction with visual profile failed: {e}")
            raise Exception(f"Failed to extract with visual profile: {str(e)}")
    
    @staticmethod
    def _clean_extraction_artifacts(text: str) -> str:
        """
        Clean common PDF extraction artifacts.
        
        Args:
            text: Raw extracted Markdown
        
        Returns:
            Cleaned text
        """
        # Fix double-character artifact (e.g., "SSEENNIIOORR" -> "SENIOR")
        # Pattern: Matches repeated characters (same char appears twice consecutively)
        def fix_double_chars(match):
            return match.group(1)
        
        # Only deduplicate UPPERCASE letters (typical PDF header artifacts)
        # This prevents breaking valid words like "meeting", "access", "skill"
        text = re.sub(r'([A-Z])\1', fix_double_chars, text)
        
        # Remove excessive blank lines (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Clean up table artifacts
        text = re.sub(r'\|?\s*-+\s*\|', '', text)  # Remove separator lines
        
        # Normalize whitespace in headers
        text = re.sub(r'#+\s+', lambda m: m.group(0).strip() + ' ', text)
        
        return text.strip()