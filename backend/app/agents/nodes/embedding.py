import logging
from app.agents.state import FoundryState
from app.services.embedding_service import embed_chunks

logger = logging.getLogger(__name__)

async def embedding_node(state: FoundryState) -> dict:
    """Chunk and embed document text."""
    logger.info(f"embedding_node for job {state['job_id']}")
    
    raw_text = state.get("raw_text", "")
    document_id = state.get("document_id")
    facility_id = state.get("facility_id")
    doc_type = state.get("doc_type", "unknown")
    
    if not raw_text or not document_id:
        return {"error": "Missing text or document_id for embedding", "status": "error"}

    try:
        records = await embed_chunks(
            text=raw_text,
            document_id=document_id,
            doc_type=doc_type,
            facility_id=facility_id
        )
        
        return {
            "current_stage": "complete",
            "status": "complete"
        }
        
    except Exception as e:
        logger.error(f"Error in embedding_node: {e}")
        return {"error": str(e), "status": "error"}
