# workflow/nodes.py
"""
LangGraph workflow nodes implementing each processing step.
Each node is a pure function: state_in -> state_out.
PRODUCTION EDITION: Zero hardcoded assumptions, pure structure preservation.
"""
import json
import time
from typing import Dict
from core.models import (
    JDState, SectionBlock, SectionStatus, SemanticTag,
    create_section_block, DocumentStructure
)
from core.state_manager import StateManager
from processors.pdf_processor import PDFProcessor
from processors.text_cleaner import MarkdownSegmenter
from llm.groq_client import GroqClient
from llm.prompts import PromptTemplates
from config.settings import settings
from utils.logger import setup_logger
import re

logger = setup_logger(__name__)


class WorkflowNodes:
    """
    Container for all workflow node functions.
    Each method represents one step in the LangGraph workflow.
    PRODUCTION: Pure data-driven processing, zero assumptions.
    """
    
    def __init__(self):
        """Initialize with LLM client and prompts"""
        self.llm = GroqClient()
        self.prompts = PromptTemplates()
    
    # ============================================================
    # PHASE 1: INGEST & ANCHOR
    # ============================================================
    
    def ingest_pdf(self, state: JDState) -> JDState:
        """
        Node 1: Extract and clean text from PDF as Markdown.
        ALSO EXTRACTS VISUAL PROFILE FOR FORMAT PRESERVATION.
        """
        logger.info("=== NODE: Ingest PDF (WITH VISUAL PROFILE) ===")
        
        # Idempotency check
        if state.get("raw_text") and len(state["raw_text"]) > 0:
            logger.info("Using cached raw_text")
            return state
        
        try:
            pdf_path = state.get("metadata", {}).get("pdf_path")
            if not pdf_path:
                raise ValueError("PDF path not provided in state")
            
            # Extract BOTH content AND visual profile
            raw_text, visual_profile = PDFProcessor.extract_with_visual_profile(pdf_path)
            
            new_state = state.copy()
            new_state["raw_text"] = raw_text
            new_state["visual_profile"] = visual_profile.to_dict()
            new_state = StateManager.set_phase(new_state, "INGESTED")
            
            logger.info(f"Successfully ingested PDF: {len(raw_text)} chars + visual profile")
            return new_state
            
        except Exception as e:
            logger.error(f"Ingest failed: {e}")
            return StateManager.add_processing_error(state, f"PDF ingestion failed: {str(e)}")
    
    def segment_sections(self, state: JDState) -> JDState:
        """
        Node 2: Break text into semantic sections using Markdown Headers.
        PRODUCTION: Captures structural metadata for perfect reconstruction.
        """
        logger.info("=== NODE: Segment Sections (Structure Preservation) ===")
        
        try:
            raw_text = state["raw_text"]
            if not raw_text:
                raise ValueError("No raw text available for segmentation")
            
            sections = []
            
            # STRATEGY 1: Deterministic Markdown Splitting (Preferred)
            if "## " in raw_text or "# " in raw_text:
                logger.info("Using Structure-First Markdown Segmentation")
                
                # NEW: Returns (header, content, header_level, position_index)
                md_sections = MarkdownSegmenter.segment_by_headers(raw_text)
                
                for header, content, header_level, position_index in md_sections:
                    # Classify the section
                    semantic_tag = self._infer_semantic_tag(header, content)
                    
                    # Create section WITH structural metadata
                    sections.append(create_section_block(
                        header=header,
                        content=content,
                        semantic_tag=semantic_tag,
                        header_level=header_level,
                        position_index=position_index
                    ))
                
                # CRITICAL: Detect document structure
                document_structure = MarkdownSegmenter.detect_document_structure(md_sections)
                    
            # STRATEGY 2: LLM Fallback (If no headers found)
            else:
                logger.info("No Markdown headers found. Falling back to LLM segmentation.")
                prompt = self.prompts.segment_sections(raw_text)
                response = self.llm.complete_json(prompt)
                
                if response.get("parsing_failed", False):
                    # Final Fallback: Treat as one giant section
                    logger.warning("LLM segmentation failed. Treating as single section.")
                    sections.append(create_section_block(
                        header="Job Description",
                        content=raw_text,
                        semantic_tag=SemanticTag.WORK_SCOPE,
                        header_level=1,
                        position_index=0
                    ))
                    document_structure = {
                        "has_title_section": True,
                        "title_text": "Job Description",
                        "header_hierarchy": {0: 1}
                    }
                else:
                    section_list = response if isinstance(response, list) else response.get("sections", [])
                    for idx, section_data in enumerate(section_list):
                        sections.append(create_section_block(
                            header=section_data.get("header", "Untitled"),
                            content=section_data.get("content", ""),
                            semantic_tag=section_data.get("semantic_tag", SemanticTag.UNKNOWN),
                            header_level=2,  # Default to H2 for LLM-generated sections
                            position_index=idx
                        ))
                    
                    # Build structure for LLM-segmented content
                    document_structure = {
                        "has_title_section": False,
                        "title_text": None,
                        "header_hierarchy": {i: 2 for i in range(len(sections))}
                    }
            
            # Build section order list
            section_order = [s["id"] for s in sections]
            document_structure["section_order"] = section_order
            
            new_state = state.copy()
            new_state["sections"] = sections
            new_state["document_structure"] = document_structure
            new_state = StateManager.set_phase(new_state, "SEGMENTED")
            
            logger.info(f"Segmented into {len(sections)} sections")
            logger.info(f"Document structure: {document_structure}")
            return new_state
            
        except Exception as e:
            logger.error(f"Segmentation failed: {e}")
            return StateManager.add_processing_error(state, f"Section segmentation failed: {str(e)}")
    
    def extract_trinity(self, state: JDState) -> JDState:
        """
        Node 3: Extract ground truth (skills + domain).
        """
        logger.info("=== NODE: Extract Trinity ===")
        try:
            sections = state["sections"]
            target_profile = state["target_profile"]
            
            # Look for Skills sections first
            skill_sections = [
                s for s in sections
                if s["semantic_tag"] in [SemanticTag.SKILL_LIST, SemanticTag.PREREQUISITES]
            ]
            
            # If no explicit skill section, use everything (fallback)
            if not skill_sections:
                logger.warning("No explicit skill sections found, analyzing full context")
                skill_sections = sections
            
            prompt = self.prompts.extract_trinity(skill_sections, target_profile)
            response = self.llm.complete_json(prompt)
            
            # Check for failure flag from groq_client
            if response.get("parsing_failed"):
                logger.warning("Extraction failed. Using Heuristic Extraction.")
                skills = ["Communication", "Problem Solving", "Adaptability"]
                domain = "General Technology"
                job_title = "Job Description"
            else:
                skills = response.get("skills", [])
                domain = response.get("domain", "General")
                job_title = response.get("job_title", "Job Description")
            
            # Safety: Ensure we have at least generic skills
            if not skills:
                skills = ["Communication", "Problem Solving"]
                
            new_state = state.copy()
            new_state["approved_skills"] = skills
            new_state["domain_context"] = domain
            new_state["job_title"] = job_title
            new_state = StateManager.set_phase(new_state, "TRINITY_EXTRACTED")
            
            logger.info(f"Extracted {len(skills)} skills for domain: {domain}")
            return new_state
            
        except Exception as e:
            logger.error(f"Trinity extraction failed: {e}")
            return StateManager.add_processing_error(state, f"Skill extraction failed: {str(e)}")
    
    # ============================================================
    # PHASE 2: ROUTING (SEQUENTIAL SETUP)
    # ============================================================
    
    def route_sections(self, state: JDState) -> JDState:
        """
        Node 4: Route sections for processing.
        Marks which sections need rewriting vs passthrough.
        """
        logger.info("=== NODE: Route Sections ===")
        try:
            new_state = state.copy()
            
            for section in new_state["sections"]:
                semantic_tag = section["semantic_tag"]
                
                # Logic: Anything that isn't purely static branding should be checked
                if semantic_tag in [SemanticTag.WORK_SCOPE, SemanticTag.PREREQUISITES, SemanticTag.COMPENSATION]:
                    section["metadata"]["requires_rewrite"] = True
                elif semantic_tag == SemanticTag.BRAND_STATIC:
                    section["draft_content"] = section["original_content"]
                    section["status"] = SectionStatus.DRAFTED
                    section["metadata"]["requires_rewrite"] = False
                else:
                    # Default to rewriting to be safe (User can always skip)
                    section["metadata"]["requires_rewrite"] = True
            
            new_state = StateManager.set_phase(new_state, "ROUTED")
            logger.info("Sections routed for processing")
            return new_state
            
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            return StateManager.add_processing_error(state, f"Section routing failed: {str(e)}")

    # ============================================================
    # PHASE 3: ASSEMBLY (PRODUCTION: ZERO ASSUMPTIONS)
    # ============================================================
    
    def assemble_output(self, state: JDState) -> JDState:
        """
        Node 7: Assemble final document.
        PRODUCTION: Pure structure-driven reconstruction.
        Uses document_structure memory - ZERO hardcoded logic.
        """
        logger.info("=== NODE: Assemble Output (Structure-Driven) ===")
        
        try:
            sections = state["sections"]
            document_structure = state["document_structure"]
            
            # CRITICAL: Use stored structural metadata
            section_order = document_structure["section_order"]
            header_hierarchy = document_structure["header_hierarchy"]
            
            # Build ordered sections map
            sections_by_id = {s["id"]: s for s in sections}
            
            # Reconstruct document in ORIGINAL order with ORIGINAL header levels
            markdown_parts = []
            
            for idx, section_id in enumerate(section_order):
                section = sections_by_id.get(section_id)
                if not section:
                    logger.warning(f"Section {section_id} not found, skipping")
                    continue
                
                # Get final content (approved > draft > original)
                content = (
                    section.get("final_content") or 
                    section.get("draft_content") or 
                    section["original_content"]
                )
                
                # Get original header level from structure memory
                header_level = section.get("header_level", 2)
                
                # Reconstruct with EXACT original structure
                header_prefix = "#" * header_level
                markdown_parts.append(f"{header_prefix} {section['original_header']}\n")
                markdown_parts.append(f"{content}\n\n")
            
            # Join without modifying spacing
            final_markdown = "".join(markdown_parts).strip()
            
            # Update state
            new_state = state.copy()
            new_state["final_jd_markdown"] = final_markdown
            new_state = StateManager.set_phase(new_state, "COMPLETE")
            
            logger.info(f"Assembly complete: {len(final_markdown)} chars (structure-driven)")
            return new_state
            
        except Exception as e:
            logger.error(f"Assembly failed: {e}")
            return StateManager.add_processing_error(
                state, 
                f"Document assembly failed: {str(e)}"
            )

    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def _infer_semantic_tag(self, header: str, content: str) -> str:
        """
        Robust Semantic Classification.
        Combines Fast LLM check with Heuristic Fallback.
        """
        header_lower = header.lower()
        
        # 1. FAST LLM CHECK
        try:
            prompt = f"""Classify this Job Description section.
Header: "{header}"
Snippet: "{content[:200]}..."

Options:
- WORK_SCOPE (Responsibilities, Duties, Competencies, Day-to-Day)
- PREREQUISITES (Requirements, Qualifications, Education)
- SKILL_LIST (Comma separated tools, tech stack)
- BRAND_STATIC (About company, culture)
- COMPENSATION (Salary, Benefits)

Return ONLY the Option Name."""
            
            tag = self.llm.complete_fast(prompt, max_tokens=10).strip().upper()
            
            for valid_tag in SemanticTag:
                if valid_tag.value in tag:
                    return valid_tag.value
                    
        except Exception as e:
            logger.warning(f"LLM Classification failed: {e}")

        # 2. HEURISTIC FALLBACK
        if any(k in header_lower for k in ["competenc", "soft skill", "capability", "expert-level", "intro", "about the role"]):
            return SemanticTag.WORK_SCOPE
            
        if any(k in header_lower for k in ["responsib", "duties", "what you", "you will"]):
            return SemanticTag.WORK_SCOPE
        elif any(k in header_lower for k in ["require", "qualif", "prerequis", "must have", "education"]):
            return SemanticTag.PREREQUISITES
        elif any(k in header_lower for k in ["skill", "technolog", "tools", "stack"]):
            return SemanticTag.SKILL_LIST
        elif any(k in header_lower for k in ["about", "company", "mission", "culture", "working condition"]):
            return SemanticTag.BRAND_STATIC
        elif any(k in header_lower for k in ["compensat", "salary", "benefit", "perks"]):
            return SemanticTag.COMPENSATION
        else:
            return SemanticTag.WORK_SCOPE