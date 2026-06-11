import logging
from app.agents.state import FoundryState
from app.services.graph_service import resolve_entity_id

logger = logging.getLogger(__name__)

async def entity_resolution_node(state: FoundryState) -> dict:
    """Resolve extracted entities into deterministic IDs."""
    logger.info(f"entity_resolution_node for job {state['job_id']}")
    
    extracted_entities = state.get("extracted_entities", [])
    facility_id = state.get("facility_id", "nexus-01")
    
    resolved_entities = []
    
    for entity in extracted_entities:
        name = entity.get("name", "")
        e_type = entity.get("type", "Unknown")
        
        if name:
            # Add deterministic ID
            entity_id = resolve_entity_id(e_type, name, facility_id)
            entity["id"] = entity_id
            resolved_entities.append(entity)
            
    return {
        "extracted_entities": resolved_entities,
        "current_stage": "graph_write"
    }
