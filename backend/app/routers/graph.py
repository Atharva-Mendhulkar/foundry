from fastapi import APIRouter, HTTPException, Query
from app.services.graph_service import GraphService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/equipment/{id}")
async def get_equipment_detail(id: str):
    """Get equipment detail and its subgraph."""
    try:
        subgraph = await GraphService.get_equipment_subgraph(id, depth=2)
        main_node = next((n for n in subgraph["nodes"] if n["id"] == id), None)
        if not main_node:
            raise HTTPException(status_code=404, detail="Equipment not found")
            
        return {
            "node": main_node["properties"],
            "subgraph": subgraph
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting equipment {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/traverse")
async def traverse_graph(from_id: str = Query(..., alias="from"), depth: int = 2):
    """Traverse graph starting from a node."""
    try:
        subgraph = await GraphService.get_equipment_subgraph(from_id, depth)
        return subgraph
    except Exception as e:
        logger.error(f"Error traversing graph from {from_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_graph(q: str, type: str = "all"):
    """Search for entities by name."""
    try:
        results = await GraphService.search_entities(q, type)
        return {"results": results}
    except Exception as e:
        logger.error(f"Error searching graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_graph_stats():
    """Get basic graph statistics."""
    try:
        stats = await GraphService.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
