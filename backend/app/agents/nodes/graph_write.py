import logging
from app.agents.state import FoundryState
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)

async def graph_write_node(state: FoundryState) -> dict:
    """Write resolved entities to Neo4j knowledge graph."""
    logger.info(f"graph_write_node for job {state['job_id']}")
    
    extracted_entities = state.get("extracted_entities", [])
    facility_id = state.get("facility_id", "nexus-01")
    
    equipment_nodes = []
    failure_nodes = []
    procedure_nodes = []
    
    for entity in extracted_entities:
        e_type = entity.get("type", "").lower()
        if e_type == "equipment":
            equipment_nodes.append(entity)
        elif e_type == "failure":
            failure_nodes.append(entity)
        elif e_type == "procedure":
            procedure_nodes.append(entity)
            
    try:
        # 1. Upsert Equipment
        eq_ids = []
        for eq in equipment_nodes:
            eq_id = await GraphService.upsert_equipment(eq, facility_id)
            eq_ids.append(eq_id)
            
        # 2. Upsert Failures and link to Equipment
        fail_ids = []
        for fail in failure_nodes:
            # For MVP, link to the first equipment found in the doc if any.
            if eq_ids:
                f_id = await GraphService.upsert_failure(fail, eq_ids[0])
                fail_ids.append(f_id)
                
        # 3. Upsert Procedures and link to Failures
        for proc in procedure_nodes:
            p_id = await GraphService.upsert_procedure(proc)
            for f_id in fail_ids:
                await GraphService.link_failure_to_procedure(f_id, p_id)
                
        return {
            "current_stage": "embed_document"
        }
    except Exception as e:
        logger.error(f"Error in graph_write_node: {e}")
        return {"error": str(e), "status": "error"}
