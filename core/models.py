# core/models.py
"""
Core data models defining the state and structure.
These are the atoms of our system - immutable contracts.
PRODUCTION EDITION: Zero hardcoded assumptions.
"""
from typing import TypedDict, List, Dict, Optional, Any
from enum import Enum
import uuid


class SectionStatus(str, Enum):
    """Section processing status"""
    PENDING = "PENDING"
    DRAFTED = "DRAFTED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    FAILED = "FAILED"


class SemanticTag(str, Enum):
    """Semantic classification of JD sections"""
    WORK_SCOPE = "WORK_SCOPE"
    PREREQUISITES = "PREREQUISITES"
    SKILL_LIST = "SKILL_LIST"
    BRAND_STATIC = "BRAND_STATIC"
    COMPENSATION = "COMPENSATION"
    UNKNOWN = "UNKNOWN"


class SkillFilters(TypedDict):
    """Skill filtering configuration"""
    exclude_categories: List[str]


class SeniorityProfile(TypedDict):
    """
    Strongly-typed seniority profile structure.
    Provides type safety for target_profile field in JDState.
    """
    label: str
    reasoning_focus: str
    autonomy_level: str
    risk_avoidance: str
    vocabulary_shifts: Dict[str, str]
    skill_filters: SkillFilters


class SectionBlock(TypedDict):
    """
    Atomic unit representing one logical section of the JD.
    Each block moves through the workflow independently.
    NOW WITH STRUCTURAL METADATA for perfect reconstruction.
    """
    id: str
    original_header: str
    original_content: str
    semantic_tag: str
    draft_content: str
    final_content: str
    status: str
    critique_feedback: Optional[str]
    metadata: Dict
    
    # NEW: Structural preservation fields
    header_level: int  # 1 = H1 (title), 2 = H2 (section), 3 = H3 (subsection)
    position_index: int  # Original position in document (0-based)


class DocumentStructure(TypedDict):
    """
    NEW: Captures the original document's structural DNA.
    This is the blueprint for perfect reconstruction.
    """
    has_title_section: bool  # Does first section act as document title?
    title_text: Optional[str]  # Extracted title if exists
    section_order: List[str]  # Ordered list of section IDs
    header_hierarchy: Dict[str, int]  # section_id -> header_level mapping


class CompensationData(TypedDict):
    """Structured compensation information"""
    salary_range: Optional[str]
    benefits: List[str]
    equity: Optional[str]


class JDState(TypedDict):
    """
    The spine of the entire workflow.
    Passed from node to node, accumulating transformations.
    """
    # Phase 1: Inputs
    raw_text: str
    target_profile: SeniorityProfile
    target_profile_key: str
    
    # Metadata for internal processing (e.g. file paths)
    metadata: Dict[str, Any]
    
    # Phase 1: Structure
    sections: List[SectionBlock]
    
    # NEW: Document Structure Memory
    document_structure: DocumentStructure
    
    # Phase 1: Ground Truth (Locked after Gate 1)
    approved_skills: List[str]
    domain_context: str
    job_title: str
    
    # Visual Profile (for format preservation)
    visual_profile: Optional[Dict]
    
    # Phase 1: Additional extracted data
    compensation_data: Optional[CompensationData]
    experience_level: Optional[str]
    
    # Phase 2: Processing Metadata
    processing_errors: List[str]
    validation_warnings: List[str]
    
    # Phase 3: Output
    final_jd_markdown: str
    
    # Workflow Control
    phase: str
    gate_1_approved: bool
    gate_2_approved: bool


def create_section_block(
    header: str,
    content: str,
    semantic_tag: str = SemanticTag.UNKNOWN,
    header_level: int = 2,
    position_index: int = 0
) -> SectionBlock:
    """
    Factory function to create a new section block with defaults.
    Ensures consistent initialization.
    NOW WITH STRUCTURAL METADATA.
    """
    return SectionBlock(
        id=str(uuid.uuid4()),
        original_header=header,
        original_content=content,
        semantic_tag=semantic_tag,
        draft_content="",
        final_content="",
        status=SectionStatus.PENDING,
        critique_feedback=None,
        metadata={},
        header_level=header_level,
        position_index=position_index
    )


def create_initial_state(target_profile_key: str) -> JDState:
    """
    Initialize empty state for a new workflow run.
    """
    return JDState(
        raw_text="",
        target_profile={},  # type: ignore
        target_profile_key=target_profile_key,
        metadata={},
        sections=[],
        document_structure=DocumentStructure(
            has_title_section=False,
            title_text=None,
            section_order=[],
            header_hierarchy={}
        ),
        approved_skills=[],
        domain_context="",
        job_title="",
        visual_profile=None,
        compensation_data=None,
        experience_level=None,
        processing_errors=[],
        validation_warnings=[],
        final_jd_markdown="",
        phase="INIT",
        gate_1_approved=False,
        gate_2_approved=False,
    )