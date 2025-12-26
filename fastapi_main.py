# fastapi_main.py
"""
FastAPI backend for JD Rewriter system.
Updated for SEQUENTIAL SECTION PROCESSING and FORMAT-PRESERVING PDF GENERATION.
PRODUCTION: Zero hardcoded assumptions, pure structure preservation.
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager
import uuid
import os
import tempfile
from datetime import datetime
from threading import Lock

from main import JDRewriterOrchestrator
from core.models import JDState, SectionBlock, SectionStatus
from workflow.section_processor import SectionProcessor
from processors.pdf_generator import PDFGenerator
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Global instances
orchestrator = JDRewriterOrchestrator()
section_processor = SectionProcessor()

# In-memory state storage with thread safety
session_store: Dict[str, JDState] = {}
session_lock = Lock()

# ============================================================
# LIFESPAN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JD Rewriter API starting up")
    logger.info(f"Loaded {len(orchestrator.seniority_profiles)} seniority profiles")
    yield
    logger.info("JD Rewriter API shutting down")
    with session_lock:
        session_store.clear()

app = FastAPI(
    title="JD Rewriter API", 
    version="3.0.0",
    description="Production-grade JD rewriting with zero hardcoded assumptions",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# MODELS
# ============================================================
class SessionCreate(BaseModel):
    target_profile_key: str

class Gate1Approval(BaseModel):
    approved_skills: List[str]
    domain_context: str

class SectionAction(BaseModel):
    section_id: str
    custom_instruction: Optional[str] = None
    content: Optional[str] = None

# ============================================================
# HELPERS
# ============================================================
def get_session(session_id: str) -> JDState:
    """Thread-safe session retrieval."""
    with session_lock:
        if session_id not in session_store:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_store[session_id]

def update_session(session_id: str, state: JDState) -> None:
    """Thread-safe session update."""
    with session_lock:
        session_store[session_id] = state

def serialize_section(section: SectionBlock) -> Dict[str, Any]:
    """Serialize section with structural metadata."""
    return {
        "id": section["id"],
        "original_header": section["original_header"],
        "original_content": section["original_content"],
        "semantic_tag": section["semantic_tag"],
        "draft_content": section.get("draft_content", ""),
        "final_content": section.get("final_content", ""),
        "status": section["status"],
        "critique_feedback": section.get("critique_feedback"),
        "metadata": section.get("metadata", {}),
        # NEW: Include structural metadata for debugging
        "header_level": section.get("header_level", 2),
        "position_index": section.get("position_index", 0)
    }

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """Health check and API info."""
    return {
        "service": "JD Rewriter API",
        "version": "3.0.0",
        "status": "operational",
        "architecture": "zero-hardcoded-assumptions"
    }

@app.get("/profiles")
async def list_profiles():
    """Get available seniority profiles."""
    return [
        {"key": k, **v} 
        for k, v in orchestrator.seniority_profiles.items()
    ]

@app.post("/sessions")
async def create_session(request: SessionCreate):
    """Create a new processing session."""
    # Validate profile key
    if request.target_profile_key not in orchestrator.seniority_profiles:
        raise HTTPException(
            400, 
            f"Invalid profile key: {request.target_profile_key}"
        )
    
    session_id = str(uuid.uuid4())
    from core.models import create_initial_state
    
    initial_state = create_initial_state(request.target_profile_key)
    initial_state["target_profile"] = orchestrator.get_profile_info(request.target_profile_key)
    
    update_session(session_id, initial_state)
    
    logger.info(f"Created session: {session_id}")
    return {"session_id": session_id}

@app.post("/sessions/{session_id}/phase1")
async def execute_phase_1(session_id: str, file: UploadFile = File(...)):
    """
    Execute Phase 1: Ingest PDF and extract structure.
    CRITICAL: Captures document structure and visual profile.
    """
    state = get_session(session_id)
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are supported")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    
    try:
        logger.info(f"Phase 1 starting for session: {session_id}")
        
        result_state = orchestrator.execute_phase_1(tmp_path, state["target_profile_key"])
        update_session(session_id, result_state)
        
        # Get document structure info
        doc_structure = result_state.get("document_structure", {})
        
        return {
            "status": "Phase 1 Complete",
            "extracted_skills": result_state["approved_skills"],
            "domain_context": result_state["domain_context"],
            "job_title": result_state.get("job_title", ""),
            "sections_count": len(result_state["sections"]),
            "has_visual_profile": "visual_profile" in result_state,
            # NEW: Document structure metadata
            "document_structure": {
                "has_title_section": doc_structure.get("has_title_section", False),
                "title_text": doc_structure.get("title_text"),
                "sections_count": len(result_state["sections"])
            }
        }
        
    except Exception as e:
        logger.error(f"Phase 1 failed: {e}")
        raise HTTPException(500, f"Phase 1 execution failed: {str(e)}")
        
    finally:
        if os.path.exists(tmp_path): 
            os.unlink(tmp_path)

@app.post("/sessions/{session_id}/gate1")
async def approve_gate_1(session_id: str, data: Gate1Approval):
    """Approve Gate 1 with skills and domain."""
    state = get_session(session_id)
    
    logger.info(f"Gate 1 approval for session: {session_id}")
    
    result_state = orchestrator.approve_gate_1(state, data.approved_skills, data.domain_context)
    update_session(session_id, result_state)
    
    return {"status": "Gate 1 Approved"}

@app.post("/sessions/{session_id}/phase2/init")
async def init_phase_2(session_id: str):
    """
    Initialize Phase 2: Route sections but DO NOT generate drafts yet.
    This prepares the 'Wizard' view.
    """
    state = get_session(session_id)
    
    if not state.get("gate_1_approved"):
        raise HTTPException(400, "Gate 1 must be approved before Phase 2")
    
    logger.info(f"Initializing Phase 2 for session: {session_id}")
    
    result_state = orchestrator.execute_phase_2(state)
    update_session(session_id, result_state)
    
    return {
        "sections": [serialize_section(s) for s in result_state["sections"]]
    }

# --- GRANULAR SECTION ENDPOINTS ---

@app.post("/sessions/{session_id}/sections/{section_id}/generate")
async def generate_section(session_id: str, section_id: str):
    """Generate draft for ONE section."""
    state = get_session(session_id)
    
    logger.info(f"Generating section {section_id}")
    
    # 1. Generate
    state = section_processor.generate_section_draft(state, section_id)
    # 2. Auto-Validate (Self-Correction Loop)
    state = section_processor.validate_section_draft(state, section_id)
    
    update_session(session_id, state)
    
    # Return the updated section
    updated_section = next(s for s in state["sections"] if s["id"] == section_id)
    return serialize_section(updated_section)

@app.post("/sessions/{session_id}/sections/{section_id}/regenerate")
async def regenerate_section(session_id: str, payload: SectionAction):
    """Regenerate with custom instruction."""
    state = get_session(session_id)
    
    logger.info(f"Regenerating section {payload.section_id}")
    
    state = section_processor.regenerate_section(
        state, payload.section_id, payload.custom_instruction
    )
    # Re-validate after regeneration
    state = section_processor.validate_section_draft(state, payload.section_id)
    
    update_session(session_id, state)
    updated_section = next(s for s in state["sections"] if s["id"] == payload.section_id)
    return serialize_section(updated_section)

@app.post("/sessions/{session_id}/sections/{section_id}/approve")
async def approve_section(session_id: str, payload: SectionAction):
    """Approve a section with final content."""
    state = get_session(session_id)
    
    logger.info(f"Approving section {payload.section_id}")
    
    state = section_processor.approve_section(state, payload.section_id, payload.content)
    update_session(session_id, state)
    
    # Check progress
    progress = section_processor.get_section_progress(state)
    return {
        "status": "Approved", 
        "progress": progress,
        "is_complete": progress["approved"] == progress["total_sections"]
    }

@app.get("/sessions/{session_id}/progress")
async def get_progress(session_id: str):
    """Get current processing progress."""
    state = get_session(session_id)
    progress = section_processor.get_section_progress(state)
    
    return {
        "session_id": session_id,
        "phase": state.get("phase"),
        **progress
    }

@app.post("/sessions/{session_id}/gate2")
async def approve_gate_2(session_id: str):
    """Finalize Phase 2."""
    state = get_session(session_id)
    
    # Validate all sections are approved
    unapproved = [
        s for s in state["sections"]
        if s["status"] != SectionStatus.APPROVED and 
           s.get("metadata", {}).get("requires_rewrite", False)
    ]
    
    if unapproved:
        raise HTTPException(
            400, 
            f"{len(unapproved)} sections still pending approval"
        )
    
    logger.info(f"Gate 2 approval for session: {session_id}")
    
    result_state = orchestrator.approve_gate_2(state)
    update_session(session_id, result_state)
    
    return {"status": "Gate 2 Approved"}

@app.post("/sessions/{session_id}/phase3")
async def execute_phase_3(session_id: str):
    """
    Assemble final document using document structure memory.
    CRITICAL: Zero hardcoded assumptions, pure structure preservation.
    """
    state = get_session(session_id)
    
    if not state.get("gate_2_approved"):
        raise HTTPException(400, "Gate 2 must be approved before Phase 3")
    
    logger.info(f"Executing Phase 3 for session: {session_id}")
    
    try:
        result_state = orchestrator.execute_phase_3(state)
        update_session(session_id, result_state)
        
        return {
            "status": "Phase 3 Complete",
            "final_markdown": result_state["final_jd_markdown"],
            "job_title": result_state.get("job_title", ""),
            "document_structure_preserved": True
        }
        
    except Exception as e:
        logger.error(f"Phase 3 failed: {e}")
        raise HTTPException(500, f"Phase 3 execution failed: {str(e)}")

@app.get("/sessions/{session_id}/download/markdown")
async def download_markdown(session_id: str):
    """Download final markdown file."""
    state = get_session(session_id)
    
    if not state.get("final_jd_markdown"):
        raise HTTPException(400, "Document not finalized. Complete Phase 3 first.")
    
    return Response(
        content=state["final_jd_markdown"].encode('utf-8'),
        media_type="text/markdown",
        headers={
            "Content-Disposition": "attachment; filename=evolved_jd.md"
        }
    )

@app.get("/sessions/{session_id}/download/pdf")
async def download_pdf(session_id: str):
    """
    Download final PDF with format preservation.
    CRITICAL: Uses visual profile if available - ZERO hardcoded content.
    """
    state = get_session(session_id)
    
    if not state.get("final_jd_markdown"):
        raise HTTPException(400, "Document not finalized. Complete Phase 3 first.")
    
    try:
        visual_profile = state.get("visual_profile")
        
        if visual_profile:
            logger.info("Generating PDF with visual profile (format preservation)")
            pdf_bytes = PDFGenerator.get_pdf_bytes_with_visual_profile(
                state["final_jd_markdown"],
                visual_profile
            )
        else:
            logger.info("Generating PDF with default styles (no visual profile)")
            pdf_bytes = PDFGenerator.get_pdf_bytes(state["final_jd_markdown"])
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=evolved_jd.pdf"
            }
        )
        
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(500, f"PDF generation failed: {str(e)}")

@app.get("/sessions/{session_id}/state")
async def get_state_info(session_id: str):
    """Get current session state (for debugging)."""
    state = get_session(session_id)
    
    doc_structure = state.get("document_structure", {})
    
    return {
        "session_id": session_id,
        "phase": state.get("phase"),
        "gate_1_approved": state.get("gate_1_approved", False),
        "gate_2_approved": state.get("gate_2_approved", False),
        "sections_count": len(state.get("sections", [])),
        "has_visual_profile": "visual_profile" in state,
        "job_title": state.get("job_title", ""),
        "domain_context": state.get("domain_context", ""),
        "document_structure": {
            "has_title_section": doc_structure.get("has_title_section", False),
            "title_text": doc_structure.get("title_text"),
            "section_count": len(doc_structure.get("section_order", []))
        }
    }

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and free resources."""
    with session_lock:
        if session_id in session_store:
            del session_store[session_id]
            logger.info(f"Deleted session: {session_id}")
            return {"status": "Session deleted"}
        else:
            raise HTTPException(404, "Session not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_main:app", host="0.0.0.0", port=8000, reload=True)