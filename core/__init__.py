# core/__init__.py
"""
Core module containing data models and state management.
"""
from .models import (
    JDState,
    SectionBlock,
    SectionStatus,
    SemanticTag,
    CompensationData,
    create_section_block,
    create_initial_state
)
from .state_manager import StateManager

__all__ = [
    "JDState",
    "SectionBlock",
    "SectionStatus",
    "SemanticTag",
    "CompensationData",
    "create_section_block",
    "create_initial_state",
    "StateManager"
]