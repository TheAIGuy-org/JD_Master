# workflow/graph_builder.py
"""
LangGraph workflow builder and orchestrator.
Defines the state machine with HITL gates.
"""
from typing import Dict, Literal
from langgraph.graph import StateGraph, END
from core.models import JDState, create_initial_state
from workflow.nodes import WorkflowNodes
from utils.logger import setup_logger
import json

logger = setup_logger(__name__)


class JDRewriterGraph:
    """
    Orchestrates the entire JD rewriting workflow using LangGraph.
    Implements 3-phase execution with 2 HITL gates.
    """
    
    def __init__(self):
        """Initialize workflow nodes"""
        self.nodes = WorkflowNodes()
        # No single self.graph - we build ephemeral graphs per phase
    
    def _build_phase_1_graph(self) -> StateGraph:
        """
        Build ephemeral graph for Phase 1 only.
        
        Workflow: ingest -> segment -> extract -> END
        """
        logger.info("Building Phase 1 graph")
        
        workflow = StateGraph(JDState)
        
        # Phase 1 nodes
        workflow.add_node("ingest_pdf", self.nodes.ingest_pdf)
        workflow.add_node("segment_sections", self.nodes.segment_sections)
        workflow.add_node("extract_trinity", self.nodes.extract_trinity)
        
        # Phase 1 flow
        workflow.set_entry_point("ingest_pdf")
        workflow.add_edge("ingest_pdf", "segment_sections")
        workflow.add_edge("segment_sections", "extract_trinity")
        workflow.add_edge("extract_trinity", END)
        
        return workflow.compile()
    
    def _build_phase_2_graph(self) -> StateGraph:
        """
        Build ephemeral graph for Phase 2 only.
        
        Workflow: route -> END
        
        NOTE: Phase 2 ONLY does routing. Actual section generation/validation
        happens via API calls to section_processor.py (section-by-section).
        """
        logger.info("Building Phase 2 graph")
        
        workflow = StateGraph(JDState)
        
        # Phase 2 nodes - ONLY routing
        workflow.add_node("route_sections", self.nodes.route_sections)
        
        # Phase 2 flow - route and stop (sections processed via API)
        workflow.set_entry_point("route_sections")
        workflow.add_edge("route_sections", END)
        
        return workflow.compile()
    
    def _build_phase_3_graph(self) -> StateGraph:
        """
        Build ephemeral graph for Phase 3 only.
        
        Workflow: assemble -> END
        """
        logger.info("Building Phase 3 graph")
        
        workflow = StateGraph(JDState)
        
        # Phase 3 nodes
        workflow.add_node("assemble_output", self.nodes.assemble_output)
        
        # Phase 3 flow
        workflow.set_entry_point("assemble_output")
        workflow.add_edge("assemble_output", END)
        
        return workflow.compile()
    
    
    # ============================================================
    # EXECUTION METHODS
    # ============================================================
    
    def run_phase_1(
        self,
        pdf_path: str,
        target_profile_key: str,
        seniority_profiles: Dict
    ) -> JDState:
        """
        Execute Phase 1: Ingest & Anchor.
        
        Args:
            pdf_path: Path to PDF file
            target_profile_key: Key from seniority_profiles.json
            seniority_profiles: Loaded seniority profiles
        
        Returns:
            State after Phase 1 execution
        """
        logger.info("=" * 60)
        logger.info("EXECUTING PHASE 1: INGEST & ANCHOR")
        logger.info("=" * 60)
        
        # Initialize state
        initial_state = create_initial_state(target_profile_key)
        initial_state["target_profile"] = seniority_profiles[target_profile_key]
        initial_state["metadata"] = {"pdf_path": pdf_path}
        
        # Build ephemeral Phase 1 graph and execute
        phase_1_graph = self._build_phase_1_graph()
        result = phase_1_graph.invoke(initial_state)
        
        logger.info("Phase 1 complete - awaiting Gate 1 approval")
        return result
    
    def run_phase_2(self, state: JDState) -> JDState:
        """
        Execute Phase 2: Reasoning & Drafting.
        
        Args:
            state: State with gate_1_approved=True
        
        Returns:
            State after Phase 2 execution
        """
        logger.info("=" * 60)
        logger.info("EXECUTING PHASE 2: REASONING & DRAFTING")
        logger.info("=" * 60)
        
        if not state.get("gate_1_approved", False):
            logger.error("Cannot run Phase 2: Gate 1 not approved")
            raise ValueError("Gate 1 must be approved before Phase 2")
        
        # Build ephemeral Phase 2 graph and execute with existing state
        phase_2_graph = self._build_phase_2_graph()
        result = phase_2_graph.invoke(state)
        
        logger.info("Phase 2 complete - awaiting Gate 2 approval")
        return result
    
    def run_phase_3(self, state: JDState) -> JDState:
        """
        Execute Phase 3: Assembly.
        
        Args:
            state: State with gate_2_approved=True
        
        Returns:
            Final state with assembled output
        """
        logger.info("=" * 60)
        logger.info("EXECUTING PHASE 3: ASSEMBLY")
        logger.info("=" * 60)
        
        if not state.get("gate_2_approved", False):
            logger.error("Cannot run Phase 3: Gate 2 not approved")
            raise ValueError("Gate 2 must be approved before Phase 3")
        
        # Build ephemeral Phase 3 graph and execute with existing state
        phase_3_graph = self._build_phase_3_graph()
        result = phase_3_graph.invoke(state)
        
        logger.info("Phase 3 complete - workflow finished")
        return result
    
    def get_visualization(self) -> str:
        """
        Get Mermaid diagram of the workflow.
        
        Returns:
            Mermaid diagram string
        """
        mermaid = """
graph TD
    A[Start] --> B[Ingest PDF]
    B --> C[Segment Sections]
    C --> D[Extract Trinity]
    D --> E{Gate 1<br/>Approve Skills?}
    E -->|No| F[Stop]
    E -->|Yes| G[Route Sections]
    G --> H[Section-by-Section Processing<br/>via API calls]
    H --> J{Gate 2<br/>Approve All Sections?}
    J -->|No| K[Stop]
    J -->|Yes| L[Assemble Output]
    L --> M[End]
    
    style E fill:#ff9800
    style J fill:#ff9800
    style F fill:#f44336
    style K fill:#f44336
    style M fill:#4caf50
    style H fill:#2196f3
"""
        return mermaid



