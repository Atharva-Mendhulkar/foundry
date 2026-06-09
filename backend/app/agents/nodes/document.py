import logging
import os
from app.agents.state import FoundryState
from app.services.ocr_service import needs_ocr, extract_text_pymupdf, extract_text_tesseract
from app.db.postgres import AsyncSessionLocal
from sqlalchemy import text

logger = logging.getLogger(__name__)

async def document_processing_node(state: FoundryState) -> dict:
    """Process document file to extract raw text."""
    logger.info(f"document_processing_node for job {state['job_id']}")
    
    document_id = state['document_id']
    
    # Fetch file path from db
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT storage_path FROM documents WHERE id = :id"),
            {"id": document_id}
        )
        row = result.first()
        if not row:
            return {"error": f"Document {document_id} not found", "status": "error"}
            
        file_path = row[0]
        
    if not os.path.exists(file_path):
        return {"error": f"File not found on disk: {file_path}", "status": "error"}

    try:
        # Check if OCR is needed
        if needs_ocr(file_path):
            logger.info("Using Tesseract OCR")
            raw_text = extract_text_tesseract(file_path)
        else:
            logger.info("Using PyMuPDF text extraction")
            raw_text = extract_text_pymupdf(file_path)
            
        if not raw_text.strip():
            return {"error": "No text extracted from document", "status": "error"}
            
        return {
            "raw_text": raw_text,
            "current_stage": "extract_entities"
        }
    except Exception as e:
        logger.error(f"Error in document_processing_node: {e}")
        return {"error": str(e), "status": "error"}
