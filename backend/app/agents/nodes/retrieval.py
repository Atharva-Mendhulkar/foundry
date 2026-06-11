import logging
import json
from typing import Dict, Any, List
from app.agents.state import FoundryState
from app.services.llm_service import ollama_client
from app.db.lancedb import get_lancedb_connection
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)

async def retrieval_node(state: FoundryState) -> dict:
    """Hybrid GraphRAG retrieval pipeline."""
    query = state.get("query", "")
    facility_id = state.get("facility_id", "nexus-01")
    
    if not query:
        return {"error": "Missing query", "status": "error"}

    logger.info(f"Retrieval node running for query: {query}")
    
    try:
        # Step 1: Extract entity names using Qwen3
        extraction_prompt = f"""Extract main equipment or component names from this query. 
Return ONLY a comma-separated list of names. If none, return empty string.
Query: {query}"""
        extracted_names_str = await ollama_client.generate(
            prompt=extraction_prompt, 
            temperature=0.0
        )
        entity_names = [n.strip() for n in extracted_names_str.split(",") if n.strip()]
        logger.info(f"Extracted entities from query: {entity_names}")
        
        # Step 2: Vector Search (LanceDB)
        query_embedding = await ollama_client.embed(query, model="nomic-embed-text")
        
        vector_results = []
        try:
            db = get_lancedb_connection()
            if "documents" in db.table_names():
                table = db.open_table("documents")
                # Simple vector search
                results = table.search(query_embedding).limit(5).to_pandas()
                vector_results = results.to_dict(orient="records")
        except Exception as e:
            logger.warning(f"LanceDB search failed: {e}")
            
        # Step 3: Graph Traversal (Neo4j)
        graph_context = await GraphService.get_copilot_context(entity_names)
        
        # Step 4: Build Merged Context
        merged_context = build_merged_context(vector_results, graph_context)
        
        return {
            "resolved_entities": [{"name": n} for n in entity_names],
            "vector_results": vector_results,
            "graph_context": graph_context,
            "merged_context": merged_context,
            "current_stage": "retrieval_complete"
        }
        
    except Exception as e:
        logger.error(f"Error in retrieval node: {e}")
        return {"error": str(e), "status": "error"}

def build_merged_context(vector_results: List[Dict[str, Any]], graph_context: Dict[str, Any]) -> str:
    context_parts = []
    
    if vector_results:
        context_parts.append("--- RELEVANT DOCUMENT EXCERPTS ---")
        for i, res in enumerate(vector_results):
            doc_id = res.get('doc_id', 'Unknown')
            text = res.get('text', '')
            # Try to get a cleaner source citation name, maybe from doc_type
            doc_type = res.get('doc_type', 'DOC').upper()
            context_parts.append(f"[{doc_type}-{doc_id[:8]}] {text}")
            
    if graph_context and (graph_context.get("nodes") or graph_context.get("edges")):
        context_parts.append("\n--- KNOWLEDGE GRAPH CONTEXT ---")
        for node in graph_context.get("nodes", []):
            label = node.get("label", "")
            props = node.get("properties", {})
            name = props.get("name", props.get("title", props.get("description", props.get("code", ""))))
            context_parts.append(f"Entity: {label} - {name}")
            # Could format properties better here, keep it simple
            if label == "Failure":
                context_parts.append(f"  Failure Mode: {props.get('failure_mode')} Severity: {props.get('severity')}")
            if label == "Equipment":
                context_parts.append(f"  Type: {props.get('type')} Status: {props.get('status')}")
                
        for edge in graph_context.get("edges", []):
            edge_type = edge.get("type", "")
            context_parts.append(f"Relation: {edge_type}")
            
    return "\n".join(context_parts)
