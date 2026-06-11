import logging
from app.agents.state import FoundryState

logger = logging.getLogger(__name__)

def supervisor_node(state: FoundryState) -> dict:
    """Determine the next step based on input type."""
    input_type = state.get("input_type", "")
    
    logger.info(f"supervisor_node for job {state['job_id']}, input_type: {input_type}")
    
    if input_type == "document":
        return {"current_stage": "process_document"}
    elif input_type == "query":
        return {"current_stage": "process_query"}
    elif input_type == "voice":
        return {"current_stage": "process_voice"} # Handled in Phase 4
    elif input_type == "shift":
        return {"current_stage": "process_shift"} # Handled in Phase 5
    else:
        return {"error": f"Unknown input type: {input_type}", "status": "error"}

def route_from_supervisor(state: FoundryState) -> str:
    """Router function to determine the next node based on state."""
    stage = state.get("current_stage")
    if stage == "process_document":
        return "document_processing_node"
    elif stage == "process_query":
        return "retrieval_node"
    # Additional routing for other phases can be added here
    return "end"

def check_error(state: FoundryState) -> str:
    """Check if the state contains an error and route accordingly."""
    if state.get("error") or state.get("status") == "error":
        return "error_end"
    
    stage = state.get("current_stage")
    if stage == "extract_entities":
        return "entity_extraction_node"
    elif stage == "embed_document":
        return "embedding_node"
    elif stage == "retrieval_complete":
        return "end"
    elif stage == "complete":
        return "end"
        
    return "end"
