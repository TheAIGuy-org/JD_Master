# workflow/section_processor.py
"""
Granular section processing orchestrator.
Handles individual section generation, validation, and approval.
"""
from typing import Optional
from core.models import JDState, SectionBlock, SectionStatus
from core.state_manager import StateManager
from llm.groq_client import GroqClient
from llm.prompts import PromptTemplates
from utils.logger import setup_logger
import time

logger = setup_logger(__name__)


class SectionProcessor:
    """
    Handles granular section-by-section processing.
    Each section goes through: Generate → Validate → Approve independently.
    """
    
    def __init__(self):
        """Initialize with LLM client"""
        self.llm = GroqClient()
        self.prompts = PromptTemplates()
    
    def get_next_pending_section(self, state: JDState) -> Optional[SectionBlock]:
        """
        Get the next section that needs processing.
        
        Args:
            state: Current workflow state
        
        Returns:
            Next pending section or None if all processed
        """
        for section in state["sections"]:
            # Skip brand static sections (passthrough)
            if section["semantic_tag"] == "BRAND_STATIC":
                continue
            
            # Find first non-approved section
            if section["status"] != SectionStatus.APPROVED:
                return section
        
        return None
    
    def generate_section_draft(
        self,
        state: JDState,
        section_id: str
    ) -> JDState:
        """
        Generate draft for a specific section only.
        
        Args:
            state: Current state
            section_id: ID of section to process
        
        Returns:
            Updated state with draft for this section
        """
        logger.info(f"=== GENERATING DRAFT: Section {section_id} ===")
        
        try:
            # Find target section
            target_section = None
            for section in state["sections"]:
                if section["id"] == section_id:
                    target_section = section
                    break
            
            if not target_section:
                raise ValueError(f"Section {section_id} not found")
            
            # Check if already processed
            if target_section["status"] in [SectionStatus.VALIDATED, SectionStatus.APPROVED]:
                logger.warning(f"Section {section_id} already processed")
                return state
            
            # Get ground truth
            target_profile = state["target_profile"]
            approved_skills = state["approved_skills"]
            domain_context = state["domain_context"]
            
            # Generate draft
            logger.info(f"Generating draft for: {target_section['original_header']}")
            
            prompt = self.prompts.rewrite_section_actor(
                section=target_section,
                target_profile=target_profile,
                approved_skills=approved_skills,
                domain_context=domain_context
            )
            
            draft = self.llm.complete_reasoning(prompt)
            
            # Update state
            new_state = state.copy()
            for section in new_state["sections"]:
                if section["id"] == section_id:
                    section["draft_content"] = draft.strip()
                    section["status"] = SectionStatus.DRAFTED
                    break
            
            logger.info(f"Draft generated successfully: {len(draft)} chars")
            return new_state
            
        except Exception as e:
            logger.error(f"Draft generation failed for section {section_id}: {e}")
            return StateManager.add_processing_error(
                state,
                f"Section {section_id} draft generation failed: {str(e)}"
            )
    
    def validate_section_draft(
        self,
        state: JDState,
        section_id: str
    ) -> JDState:
        """
        Validate draft for a specific section using Critic.
        
        Args:
            state: Current state
            section_id: ID of section to validate
        
        Returns:
            Updated state with validation results
        """
        logger.info(f"=== VALIDATING DRAFT: Section {section_id} ===")
        
        try:
            # Find target section
            target_section = None
            for section in state["sections"]:
                if section["id"] == section_id:
                    target_section = section
                    break
            
            if not target_section:
                raise ValueError(f"Section {section_id} not found")
            
            if target_section["status"] != SectionStatus.DRAFTED:
                logger.warning(f"Section {section_id} not in DRAFTED status")
                return state
            
            # Get validation context
            target_profile = state["target_profile"]
            approved_skills = state["approved_skills"]
            
            # Validate
            logger.info(f"Validating: {target_section['original_header']}")
            
            prompt = self.prompts.validate_section_critic(
                section=target_section,
                draft_content=target_section["draft_content"],
                target_profile=target_profile,
                approved_skills=approved_skills
            )
            
            # Add pacing before validation
            time.sleep(2)
            
            response = self.llm.complete_json(prompt)
            
            is_valid = response.get("is_valid", True)
            violations = response.get("violations", [])
            suggestions = response.get("suggestions", "")
            
            # Update state
            new_state = state.copy()
            for section in new_state["sections"]:
                if section["id"] == section_id:
                    if is_valid:
                        section["status"] = SectionStatus.VALIDATED
                        section["critique_feedback"] = "Validation passed"
                        logger.info(f"Section validated successfully")
                    else:
                        # Auto-refinement attempt
                        logger.info(f"Validation failed, attempting auto-refinement...")
                        
                        critique_message = f"Violations: {', '.join(violations)}. {suggestions}"
                        
                        try:
                            refinement_prompt = self.prompts.refine_section_actor(
                                original_draft=target_section["draft_content"],
                                critique=critique_message,
                                target_profile=target_profile,
                                approved_skills=approved_skills
                            )
                            
                            # Pacing before refinement
                            time.sleep(2)
                            
                            refined_draft = self.llm.complete_reasoning(refinement_prompt)
                            
                            section["draft_content"] = refined_draft.strip()
                            section["status"] = SectionStatus.DRAFTED  # Mark for user review
                            section["critique_feedback"] = f"Auto-refined: {critique_message}"
                            
                            logger.info("Auto-refinement complete - awaiting user review")
                            
                        except Exception as refine_error:
                            logger.error(f"Refinement failed: {refine_error}")
                            section["critique_feedback"] = f"Validation failed: {critique_message}"
                            section["status"] = SectionStatus.DRAFTED
                    
                    break
            
            return new_state
            
        except Exception as e:
            logger.error(f"Validation failed for section {section_id}: {e}")
            return StateManager.add_processing_error(
                state,
                f"Section {section_id} validation failed: {str(e)}"
            )
    
    def approve_section(
        self,
        state: JDState,
        section_id: str,
        final_content: Optional[str] = None
    ) -> JDState:
        """
        Approve a section and finalize its content.
        
        Args:
            state: Current state
            section_id: ID of section to approve
            final_content: Optional user-edited content (if None, uses draft)
        
        Returns:
            Updated state with approved section
        """
        logger.info(f"=== APPROVING SECTION: {section_id} ===")
        
        try:
            new_state = state.copy()
            
            for section in new_state["sections"]:
                if section["id"] == section_id:
                    # Use provided content or fall back to draft
                    section["final_content"] = final_content or section["draft_content"]
                    section["status"] = SectionStatus.APPROVED
                    
                    logger.info(f"Section approved: {section['original_header']}")
                    break
            
            return new_state
            
        except Exception as e:
            logger.error(f"Approval failed for section {section_id}: {e}")
            return StateManager.add_processing_error(
                state,
                f"Section {section_id} approval failed: {str(e)}"
            )
    
    def regenerate_section(
        self,
        state: JDState,
        section_id: str,
        custom_instruction: Optional[str] = None
    ) -> JDState:
        """
        Regenerate section with optional custom instruction.
        
        Args:
            state: Current state
            section_id: ID of section to regenerate
            custom_instruction: Optional user guidance for regeneration
        
        Returns:
            Updated state with new draft
        """
        logger.info(f"=== REGENERATING SECTION: {section_id} ===")
        
        try:
            # Find target section
            target_section = None
            for section in state["sections"]:
                if section["id"] == section_id:
                    target_section = section
                    break
            
            if not target_section:
                raise ValueError(f"Section {section_id} not found")
            
            # Reset status to allow regeneration
            target_section["status"] = SectionStatus.PENDING
            
            # Build enhanced prompt with custom instruction
            target_profile = state["target_profile"]
            approved_skills = state["approved_skills"]
            domain_context = state["domain_context"]
            
            base_prompt = self.prompts.rewrite_section_actor(
                section=target_section,
                target_profile=target_profile,
                approved_skills=approved_skills,
                domain_context=domain_context
            )
            
            # Add custom instruction if provided
            if custom_instruction:
                enhanced_prompt = f"{base_prompt}\n\nADDITIONAL USER GUIDANCE:\n{custom_instruction}\n\nREWRITTEN CONTENT:"
            else:
                enhanced_prompt = base_prompt
            
            # Generate new draft
            logger.info(f"Regenerating with custom instruction: {bool(custom_instruction)}")
            
            draft = self.llm.complete_reasoning(enhanced_prompt)
            
            # Update state
            new_state = state.copy()
            for section in new_state["sections"]:
                if section["id"] == section_id:
                    section["draft_content"] = draft.strip()
                    section["status"] = SectionStatus.DRAFTED
                    if custom_instruction:
                        section["metadata"]["custom_instruction"] = custom_instruction
                    break
            
            logger.info(f"Regeneration complete: {len(draft)} chars")
            return new_state
            
        except Exception as e:
            logger.error(f"Regeneration failed for section {section_id}: {e}")
            return StateManager.add_processing_error(
                state,
                f"Section {section_id} regeneration failed: {str(e)}"
            )
    
    def get_section_progress(self, state: JDState) -> dict:
        """
        Calculate processing progress for all sections.
        
        Args:
            state: Current state
        
        Returns:
            Progress dictionary with counts and percentages
        """
        total_sections = len([
            s for s in state["sections"]
            if s["semantic_tag"] != "BRAND_STATIC"
        ])
        
        approved_count = len([
            s for s in state["sections"]
            if s["status"] == SectionStatus.APPROVED
        ])
        
        drafted_count = len([
            s for s in state["sections"]
            if s["status"] == SectionStatus.DRAFTED
        ])
        
        pending_count = len([
            s for s in state["sections"]
            if s["status"] == SectionStatus.PENDING
        ])
        
        progress_pct = (approved_count / total_sections * 100) if total_sections > 0 else 0
        
        return {
            "total_sections": total_sections,
            "approved": approved_count,
            "drafted": drafted_count,
            "pending": pending_count,
            "progress_percentage": round(progress_pct, 1)
        }