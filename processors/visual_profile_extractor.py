# processors/visual_profile_extractor.py
"""
Visual Profile Extraction Module
Captures the styling DNA of the original PDF to preserve formatting.
"""
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Tuple
from collections import Counter
from utils.logger import setup_logger

logger = setup_logger(__name__)


class VisualProfile:
    """
    Represents the visual styling characteristics of a PDF document.
    This is the "DNA" we'll use to reconstruct the output PDF.
    """
    
    def __init__(self):
        self.fonts: Dict[str, Dict] = {}  # font_name -> {size, weight, usage_count}
        self.colors: Dict[str, int] = {}  # color_hex -> usage_count
        self.heading_styles: List[Dict] = []  # [{level, font, size, color, spacing}]
        self.paragraph_style: Dict = {}  # {font, size, line_height, alignment}
        self.list_style: Dict = {}  # {bullet_char, indent, spacing}
        self.table_style: Dict = {}  # {border_width, cell_padding, header_bg}
        self.page_layout: Dict = {}  # {margins, columns, page_size}
        self.spacing: Dict = {}  # {line_height, paragraph_spacing, section_spacing}
        
    def to_dict(self) -> Dict:
        """Convert profile to serializable dictionary"""
        return {
            "fonts": self.fonts,
            "colors": self.colors,
            "heading_styles": self.heading_styles,
            "paragraph_style": self.paragraph_style,
            "list_style": self.list_style,
            "table_style": self.table_style,
            "page_layout": self.page_layout,
            "spacing": self.spacing
        }


class VisualProfileExtractor:
    """
    Extracts visual formatting characteristics from PDF documents.
    Uses PyMuPDF to analyze fonts, colors, spacing, and layout.
    """
    
    @staticmethod
    def extract_profile(pdf_path: str) -> VisualProfile:
        """
        Extract complete visual profile from PDF.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            VisualProfile object containing all styling information
        """
        logger.info(f"Extracting visual profile from: {pdf_path}")
        
        profile = VisualProfile()
        
        try:
            doc = fitz.open(pdf_path)
            
            # Extract from all pages (sample first 5 for performance)
            pages_to_analyze = min(5, len(doc))
            
            for page_num in range(pages_to_analyze):
                page = doc[page_num]
                
                # Extract page layout (first page only)
                if page_num == 0:
                    profile.page_layout = VisualProfileExtractor._extract_page_layout(page)
                
                # Extract text blocks with formatting
                blocks = page.get_text("dict")["blocks"]
                
                for block in blocks:
                    if block.get("type") == 0:  # Text block
                        VisualProfileExtractor._analyze_text_block(block, profile)
            
            # Post-process: Identify heading hierarchy
            profile.heading_styles = VisualProfileExtractor._identify_heading_hierarchy(profile)
            
            # Infer paragraph style (most common body text)
            profile.paragraph_style = VisualProfileExtractor._infer_paragraph_style(profile)
            
            # Infer spacing patterns
            profile.spacing = VisualProfileExtractor._infer_spacing(profile)
            
            doc.close()
            
            logger.info(f"Visual profile extracted: {len(profile.fonts)} fonts, {len(profile.heading_styles)} heading levels")
            return profile
            
        except Exception as e:
            logger.error(f"Visual profile extraction failed: {e}")
            # Return default profile as fallback
            return VisualProfileExtractor._create_default_profile()
    
    @staticmethod
    def _extract_page_layout(page: fitz.Page) -> Dict:
        """Extract page dimensions and margins"""
        rect = page.rect
        
        # Estimate margins by analyzing text positioning
        blocks = page.get_text("dict")["blocks"]
        if blocks:
            text_blocks = [b for b in blocks if b.get("type") == 0]
            if text_blocks:
                left_margins = [b["bbox"][0] for b in text_blocks]
                right_margins = [rect.width - b["bbox"][2] for b in text_blocks]
                top_margins = [b["bbox"][1] for b in text_blocks]
                
                margin_left = min(left_margins) if left_margins else 72
                margin_right = min(right_margins) if right_margins else 72
                margin_top = min(top_margins) if top_margins else 72
            else:
                margin_left = margin_right = margin_top = 72
        else:
            margin_left = margin_right = margin_top = 72
        
        return {
            "width": rect.width,
            "height": rect.height,
            "margin_left": margin_left,
            "margin_right": margin_right,
            "margin_top": margin_top,
            "margin_bottom": 72,  # Default
        }
    
    @staticmethod
    def _analyze_text_block(block: Dict, profile: VisualProfile) -> None:
        """Analyze a text block and update profile statistics"""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                # Extract font information
                font_name = span.get("font", "Unknown")
                font_size = span.get("size", 12)
                color = span.get("color", 0)
                
                # Convert color to hex
                color_hex = f"#{color:06x}"
                
                # Update font statistics
                font_key = f"{font_name}_{font_size}"
                if font_key not in profile.fonts:
                    profile.fonts[font_key] = {
                        "name": font_name,
                        "size": font_size,
                        "weight": "bold" if "bold" in font_name.lower() else "normal",
                        "usage_count": 0,
                        "avg_size": font_size
                    }
                profile.fonts[font_key]["usage_count"] += 1
                
                # Update color statistics
                profile.colors[color_hex] = profile.colors.get(color_hex, 0) + 1
    
    @staticmethod
    def _identify_heading_hierarchy(profile: VisualProfile) -> List[Dict]:
        """
        Identify heading levels based on font sizes.
        Strategy: Larger fonts = higher level headings
        """
        # Extract unique font sizes
        font_sizes = {}
        for font_key, font_data in profile.fonts.items():
            size = font_data["size"]
            if size not in font_sizes:
                font_sizes[size] = {
                    "size": size,
                    "fonts": [],
                    "usage_count": 0
                }
            font_sizes[size]["fonts"].append(font_data["name"])
            font_sizes[size]["usage_count"] += font_data["usage_count"]
        
        # Sort by size (largest first)
        sorted_sizes = sorted(font_sizes.items(), key=lambda x: x[1]["size"], reverse=True)
        
        # Map to heading levels (H1, H2, H3, etc.)
        heading_styles = []
        
        for idx, (size, data) in enumerate(sorted_sizes[:6]):  # Max 6 heading levels
            # Determine most common font at this size
            most_common_font = Counter(data["fonts"]).most_common(1)[0][0] if data["fonts"] else "Unknown"
            
            # Determine if it's a heading (heuristic: larger than body text AND used sparingly)
            # Body text is typically the MOST used size
            body_text_size = sorted(font_sizes.items(), key=lambda x: x[1]["usage_count"], reverse=True)[0][1]["size"]
            
            if size > body_text_size or idx < 3:  # Anything larger than body OR top 3 sizes
                heading_styles.append({
                    "level": idx + 1,  # H1, H2, H3...
                    "font": most_common_font,
                    "size": size,
                    "weight": "bold" if "bold" in most_common_font.lower() else "normal",
                    "color": list(profile.colors.keys())[0] if profile.colors else "#000000"
                })
        
        return heading_styles[:3]  # Return top 3 heading levels (H1, H2, H3)
    
    @staticmethod
    def _infer_paragraph_style(profile: VisualProfile) -> Dict:
        """
        Infer body paragraph style (most commonly used font/size).
        """
        if not profile.fonts:
            return {
                "font": "Helvetica",
                "size": 11,
                "line_height": 1.6,
                "alignment": "left"
            }
        
        # Find most used font (body text)
        most_used = max(profile.fonts.items(), key=lambda x: x[1]["usage_count"])
        font_data = most_used[1]
        
        return {
            "font": font_data["name"],
            "size": font_data["size"],
            "line_height": 1.5,  # Standard default
            "alignment": "justify"  # Common for JDs
        }
    
    @staticmethod
    def _infer_spacing(profile: VisualProfile) -> Dict:
        """
        Infer spacing patterns from font sizes.
        """
        body_size = profile.paragraph_style.get("size", 11)
        
        return {
            "line_height": 1.5,
            "paragraph_spacing": f"{body_size * 0.8}pt",
            "section_spacing": f"{body_size * 1.5}pt",
            "heading_spacing_before": f"{body_size * 1.2}pt",
            "heading_spacing_after": f"{body_size * 0.6}pt"
        }
    
    @staticmethod
    def _create_default_profile() -> VisualProfile:
        """
        Create a default profile as fallback.
        """
        profile = VisualProfile()
        
        profile.fonts = {
            "Helvetica_11": {
                "name": "Helvetica",
                "size": 11,
                "weight": "normal",
                "usage_count": 100
            }
        }
        
        profile.colors = {"#000000": 100}
        
        profile.heading_styles = [
            {"level": 1, "font": "Helvetica", "size": 24, "weight": "bold", "color": "#1a1a1a"},
            {"level": 2, "font": "Helvetica", "size": 16, "weight": "bold", "color": "#2c3e50"},
            {"level": 3, "font": "Helvetica", "size": 13, "weight": "bold", "color": "#34495e"}
        ]
        
        profile.paragraph_style = {
            "font": "Helvetica",
            "size": 11,
            "line_height": 1.6,
            "alignment": "justify"
        }
        
        profile.page_layout = {
            "width": 595,  # A4
            "height": 842,
            "margin_left": 72,
            "margin_right": 72,
            "margin_top": 72,
            "margin_bottom": 72
        }
        
        profile.spacing = {
            "line_height": 1.5,
            "paragraph_spacing": "8pt",
            "section_spacing": "16pt",
            "heading_spacing_before": "12pt",
            "heading_spacing_after": "6pt"
        }
        
        return profile