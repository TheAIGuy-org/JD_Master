# fastapi_main.py
"""
FastAPI backend for JD Rewriter system.
Updated for SEQUENTIAL SECTION PROCESSING and PDF GENERATION.
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

from main import JDRewriterOrchestrator
from core.models import JDState, SectionBlock, SectionStatus
from workflow.section_processor import SectionProcessor
from processors.pdf_generator import PDFGenerator
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Global instances
orchestrator = JDRewriterOrchestrator()
section_processor = SectionProcessor()

# In-memory state storage
session_store: Dict[str, JDState] = {}

# ============================================================
# LIFESPAN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JD Rewriter API starting up")
    yield
    logger.info("JD Rewriter API shutting down")
    session_store.clear()

app = FastAPI(title="JD Rewriter API", version="2.0.0", lifespan=lifespan)

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
    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_store[session_id]

def serialize_section(section: SectionBlock) -> Dict[str, Any]:
    return {
        "id": section["id"],
        "original_header": section["original_header"],
        "original_content": section["original_content"],
        "semantic_tag": section["semantic_tag"],
        "draft_content": section.get("draft_content", ""),
        "final_content": section.get("final_content", ""),
        "status": section["status"],
        "critique_feedback": section.get("critique_feedback"),
        "metadata": section.get("metadata", {})
    }

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/profiles")
async def list_profiles():
    return [
        {"key": k, **v} 
        for k, v in orchestrator.seniority_profiles.items()
    ]

@app.post("/sessions")
async def create_session(request: SessionCreate):
    session_id = str(uuid.uuid4())
    # Import locally to avoid circular dep issues during init
    from core.models import create_initial_state
    
    initial_state = create_initial_state(request.target_profile_key)
    initial_state["target_profile"] = orchestrator.get_profile_info(request.target_profile_key)
    session_store[session_id] = initial_state
    
    return {"session_id": session_id}

@app.post("/sessions/{session_id}/phase1")
async def execute_phase_1(session_id: str, file: UploadFile = File(...)):
    state = get_session(session_id)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    
    try:
        result_state = orchestrator.execute_phase_1(tmp_path, state["target_profile_key"])
        session_store[session_id] = result_state
        return {
            "extracted_skills": result_state["approved_skills"],
            "domain_context": result_state["domain_context"]
        }
    finally:
        if os.path.exists(tmp_path): os.unlink(tmp_path)

@app.post("/sessions/{session_id}/gate1")
async def approve_gate_1(session_id: str, data: Gate1Approval):
    state = get_session(session_id)
    result_state = orchestrator.approve_gate_1(state, data.approved_skills, data.domain_context)
    session_store[session_id] = result_state
    return {"status": "Gate 1 Approved"}

@app.post("/sessions/{session_id}/phase2/init")
async def init_phase_2(session_id: str):
    """
    Initialize Phase 2: Route sections but DO NOT generate drafts yet.
    This prepares the 'Wizard' view.
    """
    state = get_session(session_id)
    # This runs the Graph which now ONLY does routing (marking sections as pending)
    result_state = orchestrator.execute_phase_2(state)
    session_store[session_id] = result_state
    
    return {
        "sections": [serialize_section(s) for s in result_state["sections"]]
    }

# --- GRANULAR SECTION ENDPOINTS ---

@app.post("/sessions/{session_id}/sections/{section_id}/generate")
async def generate_section(session_id: str, section_id: str):
    """Generate draft for ONE section."""
    state = get_session(session_id)
    
    # 1. Generate
    state = section_processor.generate_section_draft(state, section_id)
    # 2. Auto-Validate (Self-Correction Loop)
    state = section_processor.validate_section_draft(state, section_id)
    
    session_store[session_id] = state
    
    # Return the updated section
    updated_section = next(s for s in state["sections"] if s["id"] == section_id)
    return serialize_section(updated_section)

@app.post("/sessions/{session_id}/sections/{section_id}/regenerate")
async def regenerate_section(session_id: str, payload: SectionAction):
    """Regenerate with custom instruction."""
    state = get_session(session_id)
    state = section_processor.regenerate_section(
        state, payload.section_id, payload.custom_instruction
    )
    # Re-validate after regeneration
    state = section_processor.validate_section_draft(state, payload.section_id)
    
    session_store[session_id] = state
    updated_section = next(s for s in state["sections"] if s["id"] == payload.section_id)
    return serialize_section(updated_section)

@app.post("/sessions/{session_id}/sections/{section_id}/approve")
async def approve_section(session_id: str, payload: SectionAction):
    """Approve a section with final content."""
    state = get_session(session_id)
    state = section_processor.approve_section(state, payload.section_id, payload.content)
    session_store[session_id] = state
    
    # Check progress
    progress = section_processor.get_section_progress(state)
    return {
        "status": "Approved", 
        "progress": progress,
        "is_complete": progress["approved"] == progress["total_sections"]
    }

@app.post("/sessions/{session_id}/gate2")
async def approve_gate_2(session_id: str):
    """Finalize Phase 2."""
    state = get_session(session_id)
    result_state = orchestrator.approve_gate_2(state)
    session_store[session_id] = result_state
    return {"status": "Gate 2 Approved"}

@app.post("/sessions/{session_id}/phase3")
async def execute_phase_3(session_id: str):
    """Assemble final document and generate PDF."""
    state = get_session(session_id)
    result_state = orchestrator.execute_phase_3(state)
    
    # Generate PDF
    # In a real app, you might save this to S3/Disk. For now, generate on fly.
    try:
        pdf_bytes = PDFGenerator.get_pdf_bytes(
            result_state["final_jd_markdown"],
            metadata={
                "domain": result_state["domain_context"],
                "version": "2.0",
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        )
        # Store PDF path or bytes in state if needed, or just return success
        # Here we just ensure Markdown is ready.
    except Exception as e:
        logger.error(f"PDF generation pre-check failed: {e}")
        # Don't fail the request, user can still download Markdown
    
    session_store[session_id] = result_state
    
    return {
        "final_markdown": result_state["final_jd_markdown"]
    }

@app.get("/sessions/{session_id}/download/pdf")
async def download_pdf(session_id: str):
    state = get_session(session_id)
    if not state.get("final_jd_markdown"):
        raise HTTPException(400, "Document not finalized")
        
    pdf_bytes = PDFGenerator.get_pdf_bytes(
        state["final_jd_markdown"],
        metadata={"domain": state["domain_context"]},
        visual_profile_dict=state.get("visual_profile")  
    )
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=evolved_jd.pdf"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_main:app", host="0.0.0.0", port=8000, reload=True)