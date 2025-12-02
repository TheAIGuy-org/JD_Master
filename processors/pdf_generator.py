# processors/pdf_generator.py
"""
PDF generation from Markdown with professional styling.
Converts finalized JD Markdown to enterprise-grade PDF output.
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
    
    .metadata {
        color: #7f8c8d;
        font-size: 9pt;
        font-style: italic;
        margin-bottom: 2em;
    }
    
    .header-logo {
        text-align: center;
        margin-bottom: 2em;
    }
    
    .footer {
        margin-top: 3em;
        padding-top: 1em;
        border-top: 1px solid #bdc3c7;
        text-align: center;
        font-size: 9pt;
        color: #95a5a6;
    }
    """
    
    @staticmethod
    def markdown_to_pdf(
        markdown_content: str,
        output_path: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Convert Markdown content to styled PDF.
        
        Args:
            markdown_content: Markdown-formatted JD content
            output_path: Path to save PDF file
            metadata: Optional metadata (domain, date, version)
        
        Returns:
            Path to generated PDF file
        
        Raises:
            Exception: If PDF generation fails
        """
        try:
            logger.info(f"Generating PDF from Markdown ({len(markdown_content)} chars)")
            
            # Convert Markdown to HTML
            html_content = markdown(markdown_content, extensions=['extra', 'nl2br'])
            
            # Build complete HTML document
            html_document = PDFGenerator._build_html_document(
                html_content,
                metadata
            )
            
            # Generate PDF
            HTML(string=html_document).write_pdf(
                output_path,
                stylesheets=[CSS(string=PDFGenerator.PDF_STYLES)]
            )
            
            logger.info(f"PDF generated successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise Exception(f"Failed to generate PDF: {str(e)}")
    
    @staticmethod
    def _build_html_document(
        html_body: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Build complete HTML document with metadata and styling.
        
        Args:
            html_body: Converted HTML from Markdown
            metadata: Optional metadata dict
        
        Returns:
            Complete HTML document string
        """
        metadata = metadata or {}
        
        # Extract metadata
        domain = metadata.get('domain', 'General')
        date = metadata.get('date', '')
        version = metadata.get('version', '1.0')
        
        # Build metadata section
        metadata_html = f"""
        <div class="metadata">
            Domain: {domain} | Generated: {date} | Version: {version}
        </div>
        """
        
        # Build footer
        footer_html = """
        <div class="footer">
            Generated by JD Rewriter - AI-Powered Semantic Evolution Engine
        </div>
        """
        
        # Assemble complete document
        html_document = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Job Description</title>
        </head>
        <body>
            {metadata_html}
            {html_body}
            {footer_html}
        </body>
        </html>
        """
        
        return html_document
    
    @staticmethod
    def get_pdf_bytes(
        markdown_content: str,
        metadata: Optional[dict] = None,
        visual_profile_dict: Optional[dict] = None  
    ) -> bytes:
        """
        Generate PDF bytes with dynamic styling.
        """
        try:
            html_content = markdown(markdown_content, extensions=['extra', 'nl2br'])
            html_document = PDFGenerator._build_html_document(html_content, metadata)
            
            # DYNAMIC CSS LOGIC
            if visual_profile_dict:
                # Rehydrate the profile object
                profile = VisualProfile()
                profile.fonts = visual_profile_dict.get("fonts", {})
                profile.colors = visual_profile_dict.get("colors", {})
                profile.heading_styles = visual_profile_dict.get("heading_styles", [])
                profile.paragraph_style = visual_profile_dict.get("paragraph_style", {})
                profile.page_layout = visual_profile_dict.get("page_layout", {})
                profile.spacing = visual_profile_dict.get("spacing", {})
                
                # Generate custom CSS
                css_string = DynamicCSSGenerator.generate_css(profile)
            else:
                # Fallback to default
                css_string = PDFGenerator.PDF_STYLES
            
            return HTML(string=html_document).write_pdf(
                stylesheets=[CSS(string=css_string)]
            )
            
        except Exception as e:
            logger.error(f"PDF bytes generation failed: {e}")
            raise Exception(f"Failed to generate PDF bytes: {str(e)}")