# processors/dynamic_css_generator.py
"""
Dynamic CSS Generation Module
Creates custom stylesheets matching the original PDF's visual profile.
"""
from typing import Dict
from processors.visual_profile_extractor import VisualProfile
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DynamicCSSGenerator:
    """
    Generates CSS stylesheets dynamically based on VisualProfile.
    Maps extracted visual characteristics to WeasyPrint-compatible CSS.
    """
    
    @staticmethod
    def generate_css(profile: VisualProfile) -> str:
        """
        Generate complete CSS stylesheet from visual profile.
        
        Args:
            profile: VisualProfile object with extracted styling
        
        Returns:
            CSS string for WeasyPrint rendering
        """
        logger.info("Generating dynamic CSS from visual profile")
        
        # Extract profile data
        page_layout = profile.page_layout
        paragraph_style = profile.paragraph_style
        heading_styles = profile.heading_styles
        spacing = profile.spacing
        
        # Build CSS sections
        css_parts = []
        
        # 1. Page Layout
        css_parts.append(DynamicCSSGenerator._generate_page_css(page_layout))
        
        # 2. Body/Paragraph Styles
        css_parts.append(DynamicCSSGenerator._generate_body_css(paragraph_style, spacing))
        
        # 3. Heading Styles (H1, H2, H3)
        for heading in heading_styles:
            css_parts.append(DynamicCSSGenerator._generate_heading_css(heading, spacing))
        
        # 4. List Styles
        css_parts.append(DynamicCSSGenerator._generate_list_css(paragraph_style))
        
        # 5. Table Styles
        css_parts.append(DynamicCSSGenerator._generate_table_css(paragraph_style))
        
        # 6. Utility Classes
        css_parts.append(DynamicCSSGenerator._generate_utility_css())
        
        complete_css = "\n\n".join(css_parts)
        
        logger.info(f"Generated CSS: {len(complete_css)} chars")
        return complete_css
    
    @staticmethod
    def _generate_page_css(layout: Dict) -> str:
        """Generate @page CSS rules"""
        width_cm = layout.get("width", 595) / 28.35  # Convert points to cm
        height_cm = layout.get("height", 842) / 28.35
        
        margin_left_cm = layout.get("margin_left", 72) / 28.35
        margin_right_cm = layout.get("margin_right", 72) / 28.35
        margin_top_cm = layout.get("margin_top", 72) / 28.35
        margin_bottom_cm = layout.get("margin_bottom", 72) / 28.35
        
        return f"""
@page {{
    size: {width_cm:.1f}cm {height_cm:.1f}cm;
    margin-top: {margin_top_cm:.1f}cm;
    margin-bottom: {margin_bottom_cm:.1f}cm;
    margin-left: {margin_left_cm:.1f}cm;
    margin-right: {margin_right_cm:.1f}cm;
}}
"""
    
    @staticmethod
    def _generate_body_css(paragraph_style: Dict, spacing: Dict) -> str:
        """Generate body and paragraph CSS"""
        font_name = paragraph_style.get("font", "Helvetica")
        font_size = paragraph_style.get("size", 11)
        line_height = spacing.get("line_height", 1.5)
        alignment = paragraph_style.get("alignment", "justify")
        
        # Map PDF fonts to web-safe fonts
        web_font = DynamicCSSGenerator._map_to_web_font(font_name)
        
        return f"""
body {{
    font-family: {web_font};
    font-size: {font_size}pt;
    line-height: {line_height};
    color: #2c3e50;
    text-align: {alignment};
}}

p {{
    margin-bottom: {spacing.get('paragraph_spacing', '0.8em')};
    text-align: {alignment};
}}
"""
    
    @staticmethod
    def _generate_heading_css(heading: Dict, spacing: Dict) -> str:
        """Generate CSS for a specific heading level"""
        level = heading.get("level", 1)
        font_name = heading.get("font", "Helvetica")
        font_size = heading.get("size", 24)
        font_weight = heading.get("weight", "bold")
        color = heading.get("color", "#1a1a1a")
        
        web_font = DynamicCSSGenerator._map_to_web_font(font_name)
        
        # Determine border style (H1 gets border, others don't)
        border_style = "border-bottom: 3px solid #3498db;" if level == 1 else "border-bottom: 1px solid #bdc3c7;" if level == 2 else ""
        padding_bottom = "0.3em" if level <= 2 else "0"
        
        return f"""
h{level} {{
    font-family: {web_font};
    font-size: {font_size}pt;
    font-weight: {font_weight};
    color: {color};
    margin-top: {spacing.get('heading_spacing_before', '1.5em')};
    margin-bottom: {spacing.get('heading_spacing_after', '0.5em')};
    {border_style}
    padding-bottom: {padding_bottom};
}}
"""
    
    @staticmethod
    def _generate_list_css(paragraph_style: Dict) -> str:
        """Generate list styling"""
        font_size = paragraph_style.get("size", 11)
        
        return f"""
ul, ol {{
    margin-left: 1.5em;
    margin-bottom: 1em;
}}

li {{
    margin-bottom: 0.3em;
}}
"""
    
    @staticmethod
    def _generate_table_css(paragraph_style: Dict) -> str:
        """Generate table styling"""
        return """
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
    def _generate_utility_css() -> str:
        """Generate utility classes"""
        return """
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

.metadata {
    color: #7f8c8d;
    font-size: 9pt;
    font-style: italic;
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
    def _map_to_web_font(pdf_font: str) -> str:
        """
        Map PDF font names to web-safe font families.
        
        Args:
            pdf_font: Font name from PDF (e.g., "Arial-BoldMT")
        
        Returns:
            CSS font-family string
        """
        pdf_font_lower = pdf_font.lower()
        
        # Common mappings
        if "arial" in pdf_font_lower:
            return "'Arial', sans-serif"
        elif "helvetica" in pdf_font_lower or "helv" in pdf_font_lower:
            return "'Helvetica', 'Arial', sans-serif"
        elif "times" in pdf_font_lower:
            return "'Times New Roman', 'Times', serif"
        elif "courier" in pdf_font_lower:
            return "'Courier New', 'Courier', monospace"
        elif "georgia" in pdf_font_lower:
            return "'Georgia', serif"
        elif "verdana" in pdf_font_lower:
            return "'Verdana', sans-serif"
        elif "calibri" in pdf_font_lower:
            return "'Calibri', 'Arial', sans-serif"
        elif "cambria" in pdf_font_lower:
            return "'Cambria', 'Georgia', serif"
        elif "comic" in pdf_font_lower:
            return "'Comic Sans MS', cursive"
        elif "impact" in pdf_font_lower:
            return "'Impact', sans-serif"
        else:
            # Default fallback
            return "'Helvetica', 'Arial', sans-serif"