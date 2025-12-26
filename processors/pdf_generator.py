# processors/pdf_generator.py
"""
PDF generation from Markdown with professional styling.
Converts finalized JD Markdown to enterprise-grade PDF output.
CRITICAL: NO HARDCODED CONTENT - Pure format preservation.
"""
from markdown import markdown
from weasyprint import HTML, CSS
from typing import Optional
import os
from utils.logger import setup_logger

logger = setup_logger(__name__)


class PDFGenerator:
    """
    Generates styled PDF documents from Markdown content.
    Applies professional formatting suitable for enterprise JDs.
    ZERO hardcoded content - pure passthrough with styling only.
    """
    
    # Professional CSS styling for JD PDFs
    PDF_STYLES = """
    @page {
        size: A4;
        margin: 2cm;
    }
    
    body {
        font-family: 'Helvetica', 'Arial', sans-serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #2c3e50;
    }
    
    h1 {
        font-size: 24pt;
        font-weight: bold;
        color: #1a1a1a;
        margin-top: 0;
        margin-bottom: 0.5em;
        border-bottom: 3px solid #3498db;
        padding-bottom: 0.3em;
    }
    
    h2 {
        font-size: 16pt;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
        border-bottom: 1px solid #bdc3c7;
        padding-bottom: 0.2em;
    }
    
    h3 {
        font-size: 13pt;
        font-weight: bold;
        color: #34495e;
        margin-top: 1em;
        margin-bottom: 0.5em;
    }
    
    p {
        margin-bottom: 0.8em;
        text-align: justify;
    }
    
    ul, ol {
        margin-left: 1.5em;
        margin-bottom: 1em;
    }
    
    li {
        margin-bottom: 0.3em;
    }
    
    strong {
        font-weight: bold;
        color: #1a1a1a;
    }
    
    em {
        font-style: italic;
        color: #7f8c8d;
    }
    
    code {
        background-color: #ecf0f1;
        padding: 0.1em 0.3em;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
        font-size: 10pt;
    }
    
    table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 1em;
    }
    
    th, td {
        border: 1px solid #bdc3c7;
        padding: 0.5em;
        text-align: left;
    }
    
    th {
        background-color: #ecf0f1;
        font-weight: bold;
    }
    """
    
    @staticmethod
    def markdown_to_pdf(
        markdown_content: str,
        output_path: str,
        custom_css: Optional[str] = None
    ) -> str:
        """
        Convert Markdown content to styled PDF.
        CRITICAL: NO metadata injection, pure content passthrough.
        
        Args:
            markdown_content: Markdown-formatted JD content
            output_path: Path to save PDF file
            custom_css: Optional custom CSS (for visual profile preservation)
        
        Returns:
            Path to generated PDF file
        
        Raises:
            Exception: If PDF generation fails
        """
        try:
            logger.info(f"Generating PDF from Markdown ({len(markdown_content)} chars)")
            
            # Convert Markdown to HTML
            html_content = markdown(markdown_content, extensions=['extra', 'nl2br'])
            
            # Build complete HTML document (NO metadata injection)
            html_document = PDFGenerator._build_html_document(html_content)
            
            # Use custom CSS if provided, otherwise use default
            css_to_use = custom_css if custom_css else PDFGenerator.PDF_STYLES
            
            # Generate PDF
            HTML(string=html_document).write_pdf(
                output_path,
                stylesheets=[CSS(string=css_to_use)]
            )
            
            logger.info(f"PDF generated successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise Exception(f"Failed to generate PDF: {str(e)}")
    
    @staticmethod
    def _build_html_document(html_body: str) -> str:
        """
        Build complete HTML document.
        CRITICAL FIX: ZERO hardcoded content. Pure passthrough.
        
        Args:
            html_body: Converted HTML from Markdown
        
        Returns:
            Complete HTML document string (content-only, no metadata)
        """
        # CRITICAL: NO headers, NO footers, NO metadata
        # Pure content passthrough with HTML wrapper only
        html_document = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Job Description</title>
</head>
<body>
{html_body}
</body>
</html>"""
        
        return html_document
    
    @staticmethod
    def get_pdf_bytes(
        markdown_content: str,
        custom_css: Optional[str] = None
    ) -> bytes:
        """
        Generate PDF as bytes (for API responses).
        CRITICAL: NO metadata injection.
        
        Args:
            markdown_content: Markdown-formatted content
            custom_css: Optional custom CSS string
        
        Returns:
            PDF file as bytes
        """
        try:
            html_content = markdown(markdown_content, extensions=['extra', 'nl2br'])
            html_document = PDFGenerator._build_html_document(html_content)
            
            # Use custom CSS if provided
            css_to_use = custom_css if custom_css else PDFGenerator.PDF_STYLES
            
            pdf_bytes = HTML(string=html_document).write_pdf(
                stylesheets=[CSS(string=css_to_use)]
            )
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"PDF bytes generation failed: {e}")
            raise Exception(f"Failed to generate PDF bytes: {str(e)}")
    
    @staticmethod
    def markdown_to_pdf_with_visual_profile(
        markdown_content: str,
        output_path: str,
        visual_profile: dict
    ) -> str:
        """
        Generate PDF using extracted visual profile for format preservation.
        
        Args:
            markdown_content: Markdown content
            output_path: Output PDF path
            visual_profile: Visual profile dict from extraction
        
        Returns:
            Path to generated PDF
        """
        try:
            from processors.dynamic_css_generator import DynamicCSSGenerator
            from processors.visual_profile_extractor import VisualProfile
            
            # Reconstruct VisualProfile object from dict
            profile_obj = VisualProfile()
            profile_obj.fonts = visual_profile.get("fonts", {})
            profile_obj.colors = visual_profile.get("colors", {})
            profile_obj.heading_styles = visual_profile.get("heading_styles", [])
            profile_obj.paragraph_style = visual_profile.get("paragraph_style", {})
            profile_obj.list_style = visual_profile.get("list_style", {})
            profile_obj.table_style = visual_profile.get("table_style", {})
            profile_obj.page_layout = visual_profile.get("page_layout", {})
            profile_obj.spacing = visual_profile.get("spacing", {})
            
            # Generate custom CSS from profile
            custom_css = DynamicCSSGenerator.generate_css(profile_obj)
            
            logger.info("Using visual profile for PDF generation")
            return PDFGenerator.markdown_to_pdf(
                markdown_content,
                output_path,
                custom_css=custom_css
            )
            
        except Exception as e:
            logger.warning(f"Visual profile CSS generation failed: {e}. Using default styles.")
            # Fallback to default styles
            return PDFGenerator.markdown_to_pdf(markdown_content, output_path)
    
    @staticmethod
    def get_pdf_bytes_with_visual_profile(
        markdown_content: str,
        visual_profile: dict
    ) -> bytes:
        """
        Generate PDF bytes using visual profile.
        
        Args:
            markdown_content: Markdown content
            visual_profile: Visual profile dict
        
        Returns:
            PDF as bytes
        """
        try:
            from processors.dynamic_css_generator import DynamicCSSGenerator
            from processors.visual_profile_extractor import VisualProfile
            
            # Reconstruct VisualProfile object
            profile_obj = VisualProfile()
            profile_obj.fonts = visual_profile.get("fonts", {})
            profile_obj.colors = visual_profile.get("colors", {})
            profile_obj.heading_styles = visual_profile.get("heading_styles", [])
            profile_obj.paragraph_style = visual_profile.get("paragraph_style", {})
            profile_obj.page_layout = visual_profile.get("page_layout", {})
            profile_obj.spacing = visual_profile.get("spacing", {})
            
            # Generate custom CSS
            custom_css = DynamicCSSGenerator.generate_css(profile_obj)
            
            logger.info("Using visual profile for PDF bytes generation")
            return PDFGenerator.get_pdf_bytes(markdown_content, custom_css=custom_css)
            
        except Exception as e:
            logger.warning(f"Visual profile CSS generation failed: {e}. Using default styles.")
            return PDFGenerator.get_pdf_bytes(markdown_content)