# workflow/nodes.py
"""
LangGraph workflow nodes implementing each processing step.
Each node is a pure function: state_in -> state_out.
NOW WITH VISUAL PROFILE EXTRACTION IN INGEST NODE.
"""
import json
import time
from typing import Dict
from core.models import (
    JDState, SectionBlock, SectionStatus, SemanticTag,
    create_section_block
)
from core.state_manager import StateManager
from processors.pdf_processor import PDFProcessor
from processors.text_cleaner import MarkdownSegmenter
from llm.groq_client import GroqClient
from llm.prompts import PromptTemplates
from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class WorkflowNodes:
    """
    Container for all workflow node functions.
    Each method represents one step in the LangGraph workflow.
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
        NOW ALSO EXTRACTS VISUAL PROFILE FOR FORMAT PRESERVATION.
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
            
            # CRITICAL CHANGE: Extract BOTH content AND visual profile
            raw_text, visual_profile = PDFProcessor.extract_with_visual_profile(pdf_path)
            
            new_state = state.copy()
            new_state["raw_text"] = raw_text
            
            # NEW: Store visual profile as serializable dict
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
        """
        logger.info("=== NODE: Segment Sections ===")
        
        try:
            raw_text = state["raw_text"]
            if not raw_text:
                raise ValueError("No raw text available for segmentation")
            
            sections = []
            
            # STRATEGY 1: Deterministic Markdown Splitting (Preferred)
            if "## " in raw_text or "# " in raw_text:
                logger.info("Using Structure-First Markdown Segmentation")
                md_sections = MarkdownSegmenter.segment_by_headers(raw_text)
                
                for header, content in md_sections:
                    # Classify the section using the robust logic
                    semantic_tag = self._infer_semantic_tag(header, content)
                    sections.append(create_section_block(header, content, semantic_tag))
                    
            # STRATEGY 2: LLM Fallback (If no headers found)
            else:
                logger.info("No Markdown headers found. Falling back to LLM segmentation.")
                prompt = self.prompts.segment_sections(raw_text)
                response = self.llm.complete_json(prompt)
                
                if response.get("parsing_failed", False):
                    # Final Fallback: Treat as one giant section
                    logger.warning("LLM segmentation failed. Treating as single section.")
                    sections.append(create_section_block(
                        "Job Description", 
                        raw_text, 
                        SemanticTag.WORK_SCOPE
                    ))
                else:
                    section_list = response if isinstance(response, list) else response.get("sections", [])
                    for section_data in section_list:
                        sections.append(create_section_block(
                            header=section_data.get("header", "Untitled"),
                            content=section_data.get("content", ""),
                            semantic_tag=section_data.get("semantic_tag", SemanticTag.UNKNOWN)
                        ))
            
            new_state = state.copy()
            new_state["sections"] = sections
            new_state = StateManager.set_phase(new_state, "SEGMENTED")
            
            logger.info(f"Segmented into {len(sections)} sections")
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
            
            skills = response.get("skills", [])
            domain = response.get("domain", "General")
            
            # Safety: Ensure we have at least generic skills
            if not skills:
                skills = ["Communication", "Problem Solving"]
                
            new_state = state.copy()
            new_state["approved_skills"] = skills
            new_state["domain_context"] = domain
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
    # PHASE 3: ASSEMBLY
    # ============================================================
    
    def assemble_output(self, state: JDState) -> JDState:
        """
        Node 7: Assemble final document.
        """
        logger.info("=== NODE: Assemble Output ===")
        try:
            sections = state["sections"]
            domain_context = state["domain_context"]
            
            final_sections = []
            for section in sections:
                content = section.get("final_content") or section.get("draft_content") or section["original_content"]
                final_sections.append({
                    "original_header": section["original_header"],
                    "final_content": content
                })
            
            # Simple assembly
            markdown_parts = []
            markdown_parts.append(f"# Job Description\n")
            markdown_parts.append(f"*Domain: {domain_context}*\n")
            
            for section in final_sections:
                markdown_parts.append(f"\n## {section['original_header']}\n")
                markdown_parts.append(f"{section['final_content']}\n")
            
            final_markdown = "\n".join(markdown_parts)
            
            new_state = state.copy()
            new_state["final_jd_markdown"] = final_markdown
            new_state = StateManager.set_phase(new_state, "COMPLETE")
            
            logger.info(f"Assembly complete: {len(final_markdown)} chars")
            return new_state
            
        except Exception as e:
            logger.error(f"Assembly failed: {e}")
            return StateManager.add_processing_error(state, f"Document assembly failed: {str(e)}")

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
            
            # Using complete_fast (8b model) for speed/cost
            tag = self.llm.complete_fast(prompt, max_tokens=10).strip().upper()
            
            for valid_tag in SemanticTag:
                if valid_tag.value in tag:
                    return valid_tag.value
                    
        except Exception as e:
            logger.warning(f"LLM Classification failed: {e}")

        # 2. HEURISTIC FALLBACK
        # Explicitly handle "Competencies", "Soft Skills", "Introduction" as WORK_SCOPE
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
            # Default to WORK_SCOPE to ensure visibility
            return SemanticTag.WORK_SCOPE