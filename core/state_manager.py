# core/state_manager.py
"""
State management utilities for safe state manipulation.
Provides helper functions to update state immutably.
"""
from typing import List, Dict
from copy import deepcopy
from .models import JDState, SectionBlock, SectionStatus


class StateManager:
    """
    Centralized state manipulation logic.
    All state updates go through this class to maintain consistency.
    """
    
    @staticmethod
    def update_section_status(
        state: JDState,
        section_id: str,
        new_status: str
    ) -> JDState:
        """Update status of a specific section"""
        new_state = deepcopy(state)
        for section in new_state["sections"]:
            if section["id"] == section_id:
                section["status"] = new_status
                break
        return new_state
    
    @staticmethod
    def update_section_draft(
        state: JDState,
        section_id: str,
        draft_content: str
    ) -> JDState:
        """Update draft content of a specific section"""
        new_state = deepcopy(state)
        for section in new_state["sections"]:
            if section["id"] == section_id:
                section["draft_content"] = draft_content
                section["status"] = SectionStatus.DRAFTED
                break
        return new_state
    
    @staticmethod
    def add_processing_error(
        state: JDState,
        error_message: str
    ) -> JDState:
        """Add error to processing errors list"""
        new_state = deepcopy(state)
        new_state["processing_errors"].append(error_message)
        return new_state
    
    @staticmethod
    def add_validation_warning(
        state: JDState,
        warning_message: str
    ) -> JDState:
        """Add warning to validation warnings list"""
        new_state = deepcopy(state)
        new_state["validation_warnings"].append(warning_message)
        return new_state
    
    @staticmethod
    def set_phase(state: JDState, phase: str) -> JDState:
        """Update workflow phase"""
        new_state = deepcopy(state)
        new_state["phase"] = phase
        return new_state
    
    @staticmethod
    def approve_gate_1(
        state: JDState,
        approved_skills: List[str],
        domain_context: str
    ) -> JDState:
        """Lock ground truth after Gate 1 approval"""
        new_state = deepcopy(state)
        new_state["approved_skills"] = approved_skills
        new_state["domain_context"] = domain_context
        new_state["gate_1_approved"] = True
        return new_state
    
    @staticmethod
    def approve_gate_2(state: JDState) -> JDState:
        """Mark Gate 2 as approved"""
        new_state = deepcopy(state)
        new_state["gate_2_approved"] = True
        return new_state
    
    @staticmethod
    def get_sections_by_status(
        state: JDState,
        status: str
    ) -> List[SectionBlock]:
        """Filter sections by status"""
        return [s for s in state["sections"] if s["status"] == status]
    
    @staticmethod
    def get_sections_by_tag(
        state: JDState,
        semantic_tag: str
    ) -> List[SectionBlock]:
        """Filter sections by semantic tag"""
        return [s for s in state["sections"] if s["semantic_tag"] == semantic_tag]
